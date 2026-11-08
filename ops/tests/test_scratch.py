"""Unit tests for the pure decision logic in ops/scratch.py (no git, filesystem, or VM)."""

from __future__ import annotations

import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from ops import scratch, shell
from ops import testsuite as tst
from ops.scratch import (
    FastPath,
    classify_changed_files,
    framework_files,
    porcelain_paths,
    rsync_exclude_lines,
    share_url_base,
    test_redis_env,
    uncovered_dirty_files,
)

# The FastPath positions read as (docs_or_frontend_only, frontend, framework).
NOT_FAST = FastPath(False, False, False)


class ClassifyTests(unittest.TestCase):
    """The deploy fast-path classification of a changed-set.

    - test_empty_set_takes_full_battery, an empty set runs every check
    - test_backend_file_takes_full_battery, any non-frontend/non-doc file kills the fast path
    - test_app_surface_only_is_fast_without_smoke, app-surface diffs skip the battery and the smoke
    - test_framework_frontend_keeps_the_smoke, frontend outside the app surface keeps the smoke
    - test_docs_only_is_fast_without_frontend, a lone feature doc is fast with no frontend work
    - test_mixed_frontend_and_docs_is_fast, frontend + doc diffs share one fast pass
    - test_nested_doc_takes_full_battery, ourapp/docs/<sub>/x.md is not a top-level doc
    - test_framework_file_kills_the_fast_path, one stray file (e.g. run) drags the full battery
    """

    def test_empty_set_takes_full_battery(self) -> None:
        self.assertEqual(classify_changed_files([]), NOT_FAST)

    def test_backend_file_takes_full_battery(self) -> None:
        changed = ["ourapp/models/todos.py", "frontend/src/app/pages/Todos.vue"]
        self.assertEqual(classify_changed_files(changed), NOT_FAST)

    def test_app_surface_only_is_fast_without_smoke(self) -> None:
        changed = ["frontend/src/app/pages/MockupTodos.vue", "frontend/src/app/styles/app.scss"]
        self.assertEqual(classify_changed_files(changed), FastPath(True, True, False))

    def test_framework_frontend_keeps_the_smoke(self) -> None:
        changed = ["frontend/src/system/utils/clientError.ts"]
        self.assertEqual(classify_changed_files(changed), FastPath(True, True, True))

    def test_docs_only_is_fast_without_frontend(self) -> None:
        changed = ["ourapp/docs/todos.md"]
        self.assertEqual(classify_changed_files(changed), FastPath(True, False, False))

    def test_mixed_frontend_and_docs_is_fast(self) -> None:
        changed = ["frontend/src/app/pages/Todos.vue", "ourapp/docs/todos.md"]
        self.assertEqual(classify_changed_files(changed), FastPath(True, True, False))

    def test_nested_doc_takes_full_battery(self) -> None:
        changed = ["ourapp/docs/notes/deep.md"]
        self.assertEqual(classify_changed_files(changed), NOT_FAST)

    def test_framework_file_kills_the_fast_path(self) -> None:
        changed = ["frontend/src/app/pages/Todos.vue", "run"]
        self.assertEqual(classify_changed_files(changed), NOT_FAST)


class PorcelainPathsTests(unittest.TestCase):
    """The porcelain=v2 -z parser: ordinary, rename, untracked records.

    - test_plain_and_untracked, `1 …` and `? …` records yield their paths
    - test_rename_keeps_new_path, the NUL-continued original path is dropped
    - test_unmerged_yields_path, `u …` records parse by field count
    - test_empty_and_junk_dropped, blank NUL fields and junk skipped
    """

    def test_plain_and_untracked(self) -> None:
        self.assertEqual(
            porcelain_paths("1 .M N... 100644 100644 100644 a a TODO.md\0? ourapp/newmod/x.py\0"),
            ["TODO.md", "ourapp/newmod/x.py"],
        )

    def test_rename_keeps_new_path(self) -> None:
        # -z renames: `2 …` header + NEW path, then the original bare.
        self.assertEqual(
            porcelain_paths(
                "2 R. N... 100644 100644 100644 a b R100 ourapp/views/new.py\0ourapp/views/old.py\0"
            ),
            ["ourapp/views/new.py"],
        )

    def test_unmerged_yields_path(self) -> None:
        self.assertEqual(
            porcelain_paths("u DA N... 100644 100644 100644 a b c d ourapp/conflict.py\0"),
            ["ourapp/conflict.py"],
        )

    def test_empty_and_junk_dropped(self) -> None:
        self.assertEqual(porcelain_paths("\0\0ab\0! ignored/\0"), [])


class UncoveredDirtyFilesTests(unittest.TestCase):
    """The deploy-loss guard: edits a deploy would silently overwrite.

    - test_main_edit_of_scratch_carried_file_is_uncovered, main-dirty file scratch still carries unchanged is listed
    - test_scratch_absent_paths_are_carried_deletions, main-dirty paths absent from scratch's tree pass (graduation / clutter)
    - test_everything_carried_is_covered, main-dirty files also in scratch's changed-set pass
    """

    def test_main_edit_of_scratch_carried_file_is_uncovered(self) -> None:
        uncovered = uncovered_dirty_files(
            ["ourapp/views/todos.py", "TODO.md"],
            ["ourapp/views/todos.py"],
            ["ourapp/views/todos.py", "TODO.md"],
        )
        self.assertEqual(uncovered, ["TODO.md"])

    def test_scratch_absent_paths_are_carried_deletions(self) -> None:
        self.assertEqual(
            uncovered_dirty_files(
                ["frontend/src/ours/pages/MockupTodos.vue", "stray-note.txt"],
                [],
                ["run", "ops/scratch.py"],
            ),
            [],
        )

    def test_everything_carried_is_covered(self) -> None:
        self.assertEqual(
            uncovered_dirty_files(
                ["run", "ops/scratch.py"],
                ["run", "ops/scratch.py", "ourapp/x.py"],
                ["run"],
            ),
            [],
        )


class FrameworkFilesTests(unittest.TestCase):
    """The framework-file filter: what lives outside the app surface.

    - test_app_surface_files_are_not_framework, ourapp/ + frontend/src/app/ lines drop out
    - test_everything_else_is_framework, run, djangoapp/, frontend/src/system/ lines pass through
    """

    def test_app_surface_files_are_not_framework(self) -> None:
        lines = ["ourapp/models/todos.py", "frontend/src/app/pages/Todos.vue", "ourapp/urls.py"]
        self.assertEqual(framework_files(lines), [])

    def test_everything_else_is_framework(self) -> None:
        lines = [
            "run",
            "djangoapp/views/git.py",
            "frontend/src/system/components/Layout.vue",
            "pyproject.toml",
        ]
        self.assertEqual(framework_files(lines), lines)


class ShareBaseTests(unittest.TestCase):
    """The share-URL base extracted from BASE_URLS.

    - test_first_origin_of_the_comma_list, the first entry wins
    - test_spaces_around_commas_are_tolerated, all spaces drop out
    - test_trailing_slashes_are_dropped, links add their own slash
    - test_double_trailing_slashes_fully_drop, a malformed // origin still yields a clean base
    - test_single_origin_without_comma, a lone origin keeps scheme and port
    - test_empty_list_stays_empty, no BASE_URLS means no base
    """

    def test_first_origin_of_the_comma_list(self) -> None:
        self.assertEqual(share_url_base("https://a.example,https://b.example"), "https://a.example")

    def test_spaces_around_commas_are_tolerated(self) -> None:
        self.assertEqual(
            share_url_base("https://a.example , https://b.example"), "https://a.example"
        )

    def test_trailing_slashes_are_dropped(self) -> None:
        self.assertEqual(share_url_base("https://a.example/"), "https://a.example")

    def test_double_trailing_slashes_fully_drop(self) -> None:
        self.assertEqual(share_url_base("https://a.example//"), "https://a.example")

    def test_single_origin_without_comma(self) -> None:
        self.assertEqual(share_url_base("https://a.example:8443"), "https://a.example:8443")

    def test_empty_list_stays_empty(self) -> None:
        self.assertEqual(share_url_base(""), "")


class FilterExcludesTests(unittest.TestCase):
    """The rsync --exclude-from line filter over gitignored listings.

    - test_deploy_direction_drops_the_built_bundle, djangoapp/static/ rides both ways instead
    - test_create_direction_also_drops_env, .env rides to scratch (the deploy re-excludes it)
    - test_rule_prefixes_and_glob_metachars_ride_out, rsync-syntax names are dropped as junk
    - test_blank_lines_never_reach_rsync, empty lines cannot become rules
    """

    def test_deploy_direction_drops_the_built_bundle(self) -> None:
        lines = ["djangoapp/static/", "media/", ".venv/"]
        self.assertEqual(rsync_exclude_lines(lines, r"^djangoapp/static/"), ["media/", ".venv/"])

    def test_create_direction_also_drops_env(self) -> None:
        lines = [".env", "djangoapp/static/", "dbbackups/"]
        self.assertEqual(rsync_exclude_lines(lines, r"^\.env$|^djangoapp/static/"), ["dbbackups/"])

    def test_rule_prefixes_and_glob_metachars_ride_out(self) -> None:
        lines = [
            "- excluded",
            "+ included",
            "! inverted",
            "; comment",
            "# comment",
            "a*b",
            "c?d",
            "e[f]",
            "media/",
        ]
        self.assertEqual(rsync_exclude_lines(lines, r"^djangoapp/static/"), ["media/"])

    def test_blank_lines_never_reach_rsync(self) -> None:
        self.assertEqual(
            rsync_exclude_lines(["", "dbbackups/"], r"^never-matches$"), ["dbbackups/"]
        )


class TestRedisEnvTests(unittest.TestCase):
    """The isolated redis environment for test runs.

    - test_test_redis_env_points_at_the_isolated_db, REDIS_URL overridden, DESMO_TEST_REDIS set
    - test_test_redis_env_keeps_other_environment, every other variable rides unchanged
    """

    def test_test_redis_env_points_at_the_isolated_db(self) -> None:
        with patch.dict(os.environ, {"REDIS_URL": "redis://live:6379/0"}, clear=True):
            test_env = test_redis_env()
        self.assertEqual(test_env["REDIS_URL"], "redis://127.0.0.1:6379/2")
        self.assertEqual(test_env["DESMO_TEST_REDIS"], "1")

    def test_test_redis_env_keeps_other_environment(self) -> None:
        with patch.dict(os.environ, {"OTHER_SETTING": "kept"}, clear=True):
            self.assertEqual(test_redis_env().get("OTHER_SETTING"), "kept")


class PlaywrighttestPdbrcTests(unittest.TestCase):
    """The --pdbrc flag: HOME for the child, refused on a missing file.

    - test_pdbrc_sets_child_home, the rc's parent dir becomes HOME in the test env
    - test_pdbrc_without_flag_leaves_env_alone, no flag → no HOME override
    - test_pdbrc_missing_file_refuses, a nonexistent rc dies before running
    """

    def test_pdbrc_sets_child_home(self) -> None:
        captured: dict[str, dict[str, str] | None] = {}

        def fake_run(*_args: object, env: dict[str, str] | None = None, **_kw: object) -> None:
            captured["env"] = env

        with tempfile.TemporaryDirectory() as home:
            rc = Path(home) / ".pdbrc"
            rc.write_text("q\n", encoding="utf-8")
            with (
                patch.object(scratch, "built_frontend"),
                patch.object(scratch, "test_redis_env", return_value={"REDIS": "1"}),
                patch.object(shell, "run", side_effect=fake_run),
                patch.object(tst, "_write_keepdb_marker"),
            ):
                tst.Playwrighttest.run(Namespace(labels=[], full=False, pdbrc=str(rc)), [])
        env = captured["env"]
        assert env is not None
        self.assertEqual(env["HOME"], home)
        self.assertEqual(env["REDIS"], "1")

    def test_pdbrc_without_flag_leaves_env_alone(self) -> None:
        captured: dict[str, dict[str, str] | None] = {}

        def fake_run(*_args: object, env: dict[str, str] | None = None, **_kw: object) -> None:
            captured["env"] = env

        with (
            patch.object(scratch, "built_frontend"),
            patch.object(scratch, "test_redis_env", return_value={"REDIS": "1"}),
            patch.object(shell, "run", side_effect=fake_run),
            patch.object(tst, "_write_keepdb_marker"),
        ):
            tst.Playwrighttest.run(Namespace(labels=[], full=False, pdbrc=None), [])
        env = captured["env"]
        assert env is not None
        self.assertNotIn("HOME", env)

    def test_pdbrc_missing_file_refuses(self) -> None:
        with (
            patch.object(scratch, "built_frontend"),
            self.assertRaises(SystemExit),
        ):
            tst.Playwrighttest.run(Namespace(labels=[], full=False, pdbrc="/nonexistent/rc"), [])


if __name__ == "__main__":
    unittest.main()
