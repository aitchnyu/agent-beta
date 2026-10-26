"""Unit tests for the pure decision logic in ops/scratch.py (no git, filesystem, or VM)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ops.scratch import (
    FastPath,
    classify_changed_files,
    framework_files,
    rsync_exclude_lines,
    share_url_base,
    test_redis_env,
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


if __name__ == "__main__":
    unittest.main()
