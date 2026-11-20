"""Unit tests for the ops/scratch.py command bodies.

Tmp trees + fakes only: nothing outside a TemporaryDirectory is touched,
no VM, no real rsync/npm/uv (shell.run/shell.capture are patched). The
pure decision logic stays in test_scratch.py.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from ops import scratch, shell
from ops.scratch import FastPath, _changed_set, _check_battery, _link_or_copy_tree

NOT_FAST = FastPath(False, False, False)


class _TmpTrees(unittest.TestCase):
    """Shared fixture: MAIN_DIR/SCRATCH_DIR/AGENT_TMP_DIR as tmp siblings."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.main = base / "main"
        self.scratch_tree = base / "scratch"
        self.agent_tmp = base / "desmo-tmp"
        self.main.mkdir()
        self.scratch_tree.mkdir()
        self.agent_tmp.mkdir()
        patches = [
            patch.object(scratch, "MAIN_DIR", self.main),
            patch.object(scratch, "SCRATCH_DIR", self.scratch_tree),
            patch.object(scratch, "AGENT_TMP_DIR", self.agent_tmp),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        super().setUp()


class MarkerHelperTests(unittest.TestCase):
    """marker_content_for / write_marker.

    - test_absent_marker_reads_none, a missing file is None
    - test_write_then_read_round_trips_stripped, write adds the newline, read strips it
    - test_write_creates_parent_dirs, a nested marker path materializes
    """

    def test_absent_marker_reads_none(self) -> None:
        """A missing marker file reads as None.

        - marker_content_for returns None for an absent path
        """
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(scratch.marker_content_for(Path(tmp) / "nope.sha"))

    def test_write_then_read_round_trips_stripped(self) -> None:
        """write_marker then marker_content_for round-trip stripped.

        - the file carries the digest plus a trailing newline
        - the read strips it back to the bare digest
        """
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "m.sha"
            scratch.write_marker(marker, "digest")
            self.assertEqual(marker.read_text(), "digest\n")
            self.assertEqual(scratch.marker_content_for(marker), "digest")

    def test_write_creates_parent_dirs(self) -> None:
        """write_marker creates missing parent directories.

        - a nested marker path materializes with its value
        """
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "a" / "b" / "m.sha"
            scratch.write_marker(marker, "d")
            self.assertTrue(marker.is_file())


class BuiltFrontendTests(unittest.TestCase):
    """built_frontend(): the dist/ marker skip.

    - test_first_call_builds_and_writes_marker, no marker means a build + marker
    - test_matching_marker_skips_build, same digest means npm never runs
    """

    def test_first_call_builds_and_writes_marker(self) -> None:
        """No marker means a build, then the marker.

        - npm run build runs in the frontend dir
        - dist/.build-sha lands with the source digest
        """
        with tempfile.TemporaryDirectory() as tmp:
            frontend = Path(tmp)
            with (
                patch.object(scratch, "visible_files_hash", return_value="d1"),
                patch.object(shell, "run") as run,
            ):
                scratch.built_frontend(frontend)
            run.assert_called_once_with("npm", "run", "build", cwd=frontend)
            self.assertEqual((frontend / "dist" / ".build-sha").read_text(), "d1\n")

    def test_matching_marker_skips_build(self) -> None:
        """A matching marker skips the build.

        - visible_files_hash equals the marker → npm never runs
        """
        with tempfile.TemporaryDirectory() as tmp:
            frontend = Path(tmp)
            scratch.write_marker(frontend / "dist" / ".build-sha", "same")
            with (
                patch.object(scratch, "visible_files_hash", return_value="same"),
                patch.object(shell, "run") as run,
            ):
                scratch.built_frontend(frontend)
            run.assert_not_called()


class ConfigureOutputTests(unittest.TestCase):
    """configure_output(): color flags by tty, NO_COLOR contract.

    - test_captured_output_disables_color, a non-tty stdout sets the
      never-color flags, NO_COLOR=1, and pops FORCE_COLOR
    - test_tty_keeps_color_and_env_untouched, a tty returns early
    """

    def tearDown(self) -> None:
        scratch.RUFF_COLOR = ()
        scratch.MYPY_COLOR = ()
        scratch.DJANGO_NO_COLOR = ()
        os.environ.pop("NO_COLOR", None)

    def test_captured_output_disables_color(self) -> None:
        """A non-tty stdout disables all color.

        - the never-color flags are set for ruff/mypy/django
        - NO_COLOR=1 lands in the environment and FORCE_COLOR is popped
          (asserted inside the patched env, before its restore)
        """
        with (
            io.StringIO() as buffer,
            contextlib.redirect_stdout(buffer),
            patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=False),
        ):
            scratch.configure_output()
            self.assertEqual(os.environ.get("NO_COLOR"), "1")
            self.assertNotIn("FORCE_COLOR", os.environ)
        self.assertEqual(scratch.RUFF_COLOR, ("--color=never",))
        self.assertEqual(scratch.MYPY_COLOR, ("--no-color-output",))
        self.assertEqual(scratch.DJANGO_NO_COLOR, ("--no-color",))

    def test_tty_keeps_color_and_env_untouched(self) -> None:
        """A tty stdout keeps color and leaves the environment alone.

        - the color flags stay empty
        - NO_COLOR is not set
        """
        with (
            contextlib.redirect_stdout(SimpleNamespace(isatty=lambda: True)),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("NO_COLOR", None)
            scratch.configure_output()
        self.assertEqual(scratch.RUFF_COLOR, ())
        self.assertNotIn("NO_COLOR", os.environ)


class GuardTests(_TmpTrees):
    """The cwd/directory guards.

    - test_require_main_run_refuses_scratch_tree, MAIN==SCRATCH dies
    - test_require_main_run_passes_in_main, distinct dirs pass
    - test_require_scratch_run_refuses_other_cwd, a cwd other than scratch/ dies
    - test_require_scratch_run_passes_in_scratch, cwd==SCRATCH_DIR passes
    """

    def test_require_main_run_refuses_scratch_tree(self) -> None:
        """A main/-only command refuses to run from scratch/'s own ./run.

        - the refusal names the command and points at main/'s ./run
        - SystemExit follows the die() message
        """
        stderr = io.StringIO()
        with (
            patch.object(scratch, "SCRATCH_DIR", self.main),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch._require_main_run("createscratch")
        self.assertIn("run 'createscratch' from main/'s ./run instead", stderr.getvalue())

    def test_require_main_run_passes_in_main(self) -> None:
        """The guard passes when MAIN and SCRATCH are distinct.

        - no exception is raised from main/
        """
        scratch._require_main_run("createscratch")

    def test_require_scratch_run_refuses_other_cwd(self) -> None:
        """A scratch/-writing command refuses any other cwd.

        - the refusal names the friendly command and names ../scratch
        - SystemExit follows the die() message
        """
        stderr = io.StringIO()
        with (
            patch.object(scratch, "SCRATCH_DIR", Path("/nonexistent-scratch")),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.require_scratch_run(friendly_name="screenshots")
        self.assertIn("'screenshots' writes tracked files", stderr.getvalue())

    def test_require_scratch_run_passes_in_scratch(self) -> None:
        """The guard passes with cwd == SCRATCH_DIR.

        - no exception is raised from inside scratch/
        """
        with (
            patch.object(scratch, "SCRATCH_DIR", self.scratch_tree),
            contextlib.chdir(self.scratch_tree),
        ):
            scratch.require_scratch_run(friendly_name="screenshots")


class RsyncExcludesFileTests(unittest.TestCase):
    """rsync_excludes_file(): .gitignore listing → exclude file.

    - test_writes_filtered_listing, ignored dirs land in the file, the
      directional filter drops its carries
    - test_git_failure_refuses, a non-repo dir refuses via die
    """

    def test_writes_filtered_listing(self) -> None:
        """The exclude file carries gitignored paths, filtered.

        - ignored directories land in the file
        - the directional filter drops its own carries
        """
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tree, check=True)
            (tree / ".gitignore").write_text("junk/\ndist/\n")
            (tree / "junk").mkdir()
            (tree / "junk" / "x").write_text("x")
            (tree / "src.py").write_text("print()")
            exclude_file = scratch.rsync_excludes_file(r"^dist/$", tree)
            self.addCleanup(exclude_file.unlink)
            lines = exclude_file.read_text().splitlines()
            self.assertIn("junk/", lines)
            self.assertNotIn("dist/", lines)

    def test_git_failure_refuses(self) -> None:
        """A failing git listing refuses via die.

        - a non-repo dir makes git ls-files fail
        - SystemExit follows, no exclude file is written
        """
        stderr = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as tmp,
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.rsync_excludes_file(r"^never$", Path(tmp))
        self.assertIn("git ls-files failed", stderr.getvalue())


class LinkOrCopyTreeTests(unittest.TestCase):
    """_link_or_copy_tree(): hardlink fast path, plain-copy fallback.

    - test_hardlink_copy_lands_the_tree, cp -al succeeds and the tree arrives
    - test_failed_hardlink_falls_back_to_copy, cp -al refusal means cp -a
    """

    def test_hardlink_copy_lands_the_tree(self) -> None:
        """A `cp -al` lands the whole tree.

        - nested files arrive with their contents
        """
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "src"
            (src / "nested").mkdir(parents=True)
            (src / "nested" / "f.txt").write_text("payload")
            dst = base / "dst"
            _link_or_copy_tree(src, dst)
            self.assertEqual((dst / "nested" / "f.txt").read_text(), "payload")

    def test_failed_hardlink_falls_back_to_copy(self) -> None:
        """A failed hardlink copy falls back to a plain copy.

        - the failed hardlink attempt is made once
        - the plain copy runs in its place
        """
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "src"
            src.mkdir()
            (src / "f.txt").write_text("payload")
            dst = base / "dst"
            with (
                patch("subprocess.run", return_value=SimpleNamespace(returncode=1)) as failed_cp,
                patch.object(shell, "run") as fallback,
            ):
                _link_or_copy_tree(src, dst)
            failed_cp.assert_called_once()
            fallback.assert_called_once_with("cp", "-a", str(src), str(dst))


class CreatescratchTests(_TmpTrees):
    """Createscratch.run: the tree pipeline (all effects faked).

    - test_happy_path_rsyncs_tags_and_bootstraps, rsync → baseline tag →
      venv-link skips → uv sync + npm install → the ready line
    - test_wipe_failure_refuses, an unwipeable old scratch dies before layering
    """

    def test_happy_path_rsyncs_tags_and_bootstraps(self) -> None:
        """Createscratch layers the pipeline in order.

        - rsync runs with the generated exclude file
        - the scratch-baseline tag is forced in scratch/
        - uv sync and npm install bootstrap
        - the ready line prints
        """
        exclude = self.main / "fake.excludes"
        exclude.write_text("")
        stdout = io.StringIO()
        with (
            patch.object(scratch, "rsync_excludes_file", return_value=exclude) as excludes,
            patch.object(shell, "run") as run,
            patch.object(shell, "capture", return_value=(0, "Updated tag")) as capture,
            contextlib.redirect_stdout(stdout),
        ):
            scratch.Createscratch.run(Namespace(), [])
        excludes.assert_called_once_with(r"^\.env$|^djangoapp/static/", self.main)
        rsync_call = run.call_args_list[0].args
        self.assertEqual(rsync_call[:3], ("rsync", "-a", f"--exclude-from={exclude}"))
        capture.assert_called_once_with(
            "git", "tag", "-f", "scratch-baseline", "HEAD", cwd=self.scratch_tree
        )
        bootstraps = [call.args[:2] for call in run.call_args_list]
        self.assertIn(("uv", "sync"), bootstraps)
        self.assertIn(("npm", "install"), bootstraps)
        self.assertIn("scratch/ ready", stdout.getvalue())

    def test_wipe_failure_refuses(self) -> None:
        """An unwipeable old scratch refuses before layering.

        - rmtree failing lands the REFUSING message
        - SystemExit follows the die() message
        """
        stderr = io.StringIO()
        with (
            patch("shutil.rmtree", side_effect=OSError("busy")),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.Createscratch.run(Namespace(), [])
        self.assertIn("failed to wipe", stderr.getvalue())


class CleanscratchTests(_TmpTrees):
    """Cleanscratch.run.

    - test_removes_scratch_and_agent_tmp, both scoped trees vanish
    - test_absent_scratch_reports_and_still_clears_tmp, the no-scratch branch
      still wipes agent tmp
    """

    def test_removes_scratch_and_agent_tmp(self) -> None:
        """Cleanscratch removes both scoped trees.

        - scratch/ and the agent tmp dir vanish
        - the Removed line prints
        """
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            scratch.Cleanscratch.run(Namespace(), [])
        self.assertFalse(self.scratch_tree.exists())
        self.assertFalse(self.agent_tmp.exists())
        self.assertIn("Removed", stdout.getvalue())

    def test_absent_scratch_reports_and_still_clears_tmp(self) -> None:
        """No scratch/ still clears agent tmp.

        - the No scratch/ at line prints
        - the agent tmp dir is wiped regardless
        """
        self.scratch_tree.rmdir()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            scratch.Cleanscratch.run(Namespace(), [])
        self.assertIn("No scratch/ at", stdout.getvalue())
        self.assertFalse(self.agent_tmp.exists())


class LoadEnvTests(_TmpTrees):
    """_load_env(): the plain KEY=value parser.

    - test_dev_env_quoting_and_comments, quotes strip, ` #` trailing
      comments strip, comments/blanks skip
    - test_vm_env_file_when_dev_env_absent, no .env + VM marker → the
      credentials file loads
    - test_missing_env_warns_and_returns, neither file → stderr warning only
    """

    KEY = "DESMO_LOAD_ENV_TEST_KEY"

    def tearDown(self) -> None:
        os.environ.pop(self.KEY, None)
        os.environ.pop(f"{self.KEY}_2", None)
        os.environ.pop(f"{self.KEY}_3", None)

    def test_dev_env_quoting_and_comments(self) -> None:
        """The .env parser handles quotes and trailing comments.

        - double quotes strip
        - a trailing ` # comment` strips, quotes protect a literal #
        - comment and blank lines skip
        """
        env_file = self.main / ".env"
        env_file.write_text(
            "# comment\n"
            f'{self.KEY}="quoted value"\n'
            f"{self.KEY}_2=bare # trailing note\n"
            f'{self.KEY}_3="quoted # not a comment"\n'
            "\n"
            "NO_EQUALS_LINE\n"
        )
        scratch._load_env()
        self.assertEqual(os.environ[self.KEY], "quoted value")
        self.assertEqual(os.environ[f"{self.KEY}_2"], "bare")
        self.assertEqual(os.environ[f"{self.KEY}_3"], "quoted # not a comment")

    def test_vm_env_file_when_dev_env_absent(self) -> None:
        """On the VM, the credentials file loads when .env is absent.

        - the marker sees the VM environment
        - values land from the VM env file
        """
        vm_env = self.main.parent / "fake.env.vm"
        vm_env.write_text(f'{self.KEY}="from vm"\n')
        with (
            patch.object(scratch, "is_running_on_vm", return_value=True),
            patch.object(scratch, "VM_ENV_FILE", vm_env),
        ):
            scratch._load_env()
        self.assertEqual(os.environ[self.KEY], "from vm")
        vm_env.unlink()

    def test_missing_env_warns_and_returns(self) -> None:
        """Neither env file warns and returns.

        - the warning names the missing .env
        - nothing raises
        """
        stderr = io.StringIO()
        with (
            patch.object(scratch, "is_running_on_vm", return_value=False),
            contextlib.redirect_stderr(stderr),
        ):
            scratch._load_env()
        self.assertIn("Warning: no .env", stderr.getvalue())


class ChangedSetTests(_TmpTrees):
    """_changed_set(): baseline diff + untracked, merged once.

    - test_merges_diff_and_untracked_sorted, both listings union sorted
    - test_missing_baseline_refuses, no scratch-baseline dies
    - test_failed_diff_refuses, a partial listing never deploys
    - test_failed_ls_files_refuses, same for the untracked listing
    """

    def test_merges_diff_and_untracked_sorted(self) -> None:
        """The changed set merges baseline diff and untracked, sorted.

        - diff entries and ls-files others union
        - the list comes back sorted
        - a mixed set classifies as not-fast-path
        """

        def fake_capture(*cmd: str, **_kw: object) -> tuple[int, str]:
            if "rev-parse" in cmd:
                return 0, "sha"
            if "diff" in cmd:
                return 0, "b.py\na.py"
            return 0, "c.py"

        with patch.object(shell, "capture", side_effect=fake_capture):
            changed, fast_path = _changed_set()
        self.assertEqual(changed, ["a.py", "b.py", "c.py"])
        self.assertEqual(fast_path, NOT_FAST)

    def test_missing_baseline_refuses(self) -> None:
        """A missing scratch-baseline ref refuses.

        - rev-parse failing lands the no-scratch-baseline message
        - SystemExit follows the die() message
        """
        stderr = io.StringIO()
        with (
            patch.object(shell, "capture", return_value=(1, "")),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            _changed_set()
        self.assertIn("no scratch-baseline ref", stderr.getvalue())

    def test_failed_diff_refuses(self) -> None:
        """A failed baseline diff refuses.

        - the git diff failure lands its REFUSING message
        - SystemExit follows the die() message
        """

        def fake_capture(*cmd: str, **_kw: object) -> tuple[int, str]:
            if "rev-parse" in cmd:
                return 0, "sha"
            if "diff" in cmd:
                return 128, ""
            return 0, ""

        stderr = io.StringIO()
        with (
            patch.object(shell, "capture", side_effect=fake_capture),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            _changed_set()
        self.assertIn("git diff failed", stderr.getvalue())

    def test_failed_ls_files_refuses(self) -> None:
        """A failed untracked listing refuses.

        - the ls-files failure lands its REFUSING message
        - SystemExit follows the die() message
        """

        def fake_capture(*cmd: str, **_kw: object) -> tuple[int, str]:
            if "ls-files" in cmd:
                return 128, ""
            return 0, "sha" if "rev-parse" in cmd else ""

        stderr = io.StringIO()
        with (
            patch.object(shell, "capture", side_effect=fake_capture),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            _changed_set()
        self.assertIn("git ls-files failed", stderr.getvalue())


class CheckBatteryTests(_TmpTrees):
    """_check_battery(): fast path vs full battery.

    - test_docs_only_validates_changed_docs, a d2 check per existing doc,
      no npm/ruff steps
    - test_deleted_doc_skips_validation, a removed doc has nothing to validate
    - test_frontend_app_surface_lints_and_builds_without_smoke, npm lint +
      build, no browser pass
    - test_framework_frontend_keeps_the_smoke, framework frontend edits run it
    - test_full_battery_runs_backend_and_smoke_for_framework_files, ruff +
      mypy + ourapp tests + npm lint + smoke when framework files changed
    - test_full_battery_skips_smoke_for_app_only_diffs, no outside files means
      no browser pass
    """

    def _run_battery(self, changed: list[str], fast_path: FastPath) -> list[tuple[str, ...]]:
        steps: list[tuple[str, ...]] = []

        def fake_step(_retry: str, *cmd: str, **_kw: object) -> None:
            steps.append(cmd)

        with (
            patch.object(shell, "run_step", side_effect=fake_step),
            patch.object(scratch, "built_frontend"),
            patch.object(scratch, "run_smoke_tests") as smoke,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            _check_battery(changed, fast_path)
        self._smoke = smoke.called
        return steps

    def test_docs_only_validates_changed_docs(self) -> None:
        """A docs-only diff validates exactly the changed docs.

        - one d2 check runs per existing doc
        - no npm/ruff step runs
        - no browser pass runs
        """
        doc = self.scratch_tree / "ourapp" / "docs" / "feature.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# doc\n")
        steps = self._run_battery(["ourapp/docs/feature.md"], FastPath(True, False, False))
        self.assertEqual(
            steps, [("node", str(self.main / "deploy" / "checkmarkdownd2.mjs"), str(doc))]
        )
        self.assertFalse(self._smoke)

    def test_deleted_doc_skips_validation(self) -> None:
        """A deleted doc has nothing to validate.

        - no step runs at all
        - no browser pass runs
        """
        steps = self._run_battery(["ourapp/docs/gone.md"], FastPath(True, False, False))
        self.assertEqual(steps, [])
        self.assertFalse(self._smoke)

    def test_frontend_app_surface_lints_and_builds_without_smoke(self) -> None:
        """A frontend app-surface diff lints and builds.

        - npm lint runs
        - the frontend is built via marker
        - no browser pass runs
        """
        steps = self._run_battery(["frontend/src/app/pages/X.vue"], FastPath(True, True, False))
        self.assertEqual([cmd[:3] for cmd in steps], [("npm", "run", "lint")])
        self.assertFalse(self._smoke)

    def test_framework_frontend_keeps_the_smoke(self) -> None:
        """A framework frontend diff keeps the browser pass.

        - the smoke suite runs on top of lint+build
        """
        self._run_battery(["frontend/src/system/utils/x.ts"], FastPath(True, True, True))
        self.assertTrue(self._smoke)

    def test_full_battery_runs_backend_and_smoke_for_framework_files(self) -> None:
        """A framework-file diff runs the full battery.

        - ruff/mypy/ourapp/npm steps all run
        - the browser pass runs
        """
        steps = self._run_battery(["run", "ourapp/views/x.py"], NOT_FAST)
        heads = [cmd[:2] for cmd in steps]
        for expected in (("uv", "run"), ("npm", "run")):
            self.assertIn(expected, heads)
        self.assertTrue(self._smoke)

    def test_full_battery_skips_smoke_for_app_only_diffs(self) -> None:
        """An app-only diff skips the browser pass.

        - the full battery still runs
        - no smoke suite
        """
        self._run_battery(["ourapp/views/x.py"], NOT_FAST)
        self.assertFalse(self._smoke)


class IsBackupInFlightTests(unittest.TestCase):
    """is_backup_in_flight(): probe failures read as not-running.

    - test_held_lock_means_running, the json lock path parses True
    - test_probe_failure_reads_not_running, rc != 0 is False
    - test_garbage_json_reads_not_running, unparseable output is False
    - test_missing_keys_read_not_running, a shorter json shape is False
    """

    def test_held_lock_means_running(self) -> None:
        """A held backup lock reads as in-flight.

        - the pgbackrest json parses to True
        """
        payload = json.dumps([{"status": {"lock": {"backup": {"held": True}}}}])
        with patch.object(shell, "capture", return_value=(0, payload)):
            self.assertTrue(scratch.is_backup_in_flight())

    def test_probe_failure_reads_not_running(self) -> None:
        """A failed probe reads as not running.

        - rc != 0 is False, conservatively
        """
        with patch.object(shell, "capture", return_value=(1, "")):
            self.assertFalse(scratch.is_backup_in_flight())

    def test_garbage_json_reads_not_running(self) -> None:
        """Unparseable probe output reads as not running.

        - garbage json is False, never a crash
        """
        with patch.object(shell, "capture", return_value=(0, "not json")):
            self.assertFalse(scratch.is_backup_in_flight())

    def test_missing_keys_read_not_running(self) -> None:
        """A shorter json shape reads as not running.

        - missing lock keys default to False
        """
        with patch.object(shell, "capture", return_value=(0, json.dumps([{"status": {}}]))):
            self.assertFalse(scratch.is_backup_in_flight())


class RunSmokeTestsTests(_TmpTrees):
    """run_smoke_tests(): the browser pass in scratch, on the isolated redis.

    - test_step_runs_tagged_suite_in_scratch, the scratch-test-subset tag
      in scratch/ with the test redis env
    """

    def test_step_runs_tagged_suite_in_scratch(self) -> None:
        """The smoke step runs the tagged suite in scratch.

        - the scratch-test-subset tag rides the command
        - cwd is scratch/ and the env carries the test redis URL
        """
        captured: dict[str, object] = {}

        def fake_step(_retry: str, *cmd: str, **kw: object) -> None:
            captured["cmd"] = cmd
            captured.update(kw)

        with patch.object(shell, "run_step", side_effect=fake_step):
            scratch.run_smoke_tests()
        cmd = cast("tuple[str, ...]", captured["cmd"])
        self.assertIn("--tag=scratch-test-subset", cmd)
        self.assertEqual(captured["cwd"], self.scratch_tree)
        assert isinstance(captured["env"], dict)
        self.assertEqual(captured["env"]["REDIS_URL"], "redis://127.0.0.1:6379/2")


class CheckscratchTests(_TmpTrees):
    """Checkscratch.run: the between-batches gate.

    - test_green_run_reports_deploy_ready, battery runs, main/ untouched
    - test_missing_scratch_refuses, no scratch/ dies
    """

    def test_green_run_reports_deploy_ready(self) -> None:
        """A green check run reports deploy-ready.

        - the battery runs
        - the Check battery green line prints
        """
        stdout = io.StringIO()
        with (
            patch.object(scratch, "_load_env"),
            patch.object(scratch, "_changed_set", return_value=([], NOT_FAST)),
            patch.object(scratch, "_check_battery"),
            contextlib.redirect_stdout(stdout),
        ):
            scratch.Checkscratch.run(Namespace(), [])
        self.assertIn("Check battery green", stdout.getvalue())

    def test_missing_scratch_refuses(self) -> None:
        """A missing scratch/ refuses the check.

        - the not-found message points at createscratch
        - SystemExit follows the die() message
        """
        self.scratch_tree.rmdir()
        stderr = io.StringIO()
        with (
            patch.object(scratch, "_load_env"),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            scratch.Checkscratch.run(Namespace(), [])
        self.assertIn("Run createscratch first", stderr.getvalue())


class DeployscratchTests(_TmpTrees):
    """Deployscratch.run: guards, then battery, then the deploy tail.

    - test_refuses_off_vm, not the VM dies before anything runs
    - test_refuses_missing_scratch, no scratch/ dies
    - test_refuses_backup_in_flight, a held backup lock dies
    - test_refuses_uncovered_main_dirty_edits, main/-dirty files scratch
      carries unchanged die with the overwrite warning
    - test_full_deploy_tail, rsync → own → backup → migrate →
      collectstatic → daemon-reload + restarts → baseurls
    - test_fast_path_skips_backend_tail, frontend-only diffs deploy files
      + collectstatic and never touch systemctl/migrate
    """

    def _deploy(self, changed: list[str], fast_path: FastPath) -> list[tuple[str, ...]]:
        runs: list[tuple[str, ...]] = []

        def fake_run(*cmd: str, **_kw: object) -> None:
            runs.append(cmd)

        exclude = self.main / "fake.excludes"
        exclude.write_text("")
        with (
            patch.object(scratch, "_load_env"),
            patch.object(scratch, "is_running_on_vm", return_value=True),
            patch.object(scratch, "is_backup_in_flight", return_value=False),
            patch.object(scratch, "_changed_set", return_value=(changed, fast_path)),
            patch.object(scratch, "_check_battery"),
            patch.object(scratch, "rsync_excludes_file", return_value=exclude),
            patch.object(shell, "run", side_effect=fake_run),
            patch.object(shell, "capture", return_value=(0, "")),
            patch.dict(os.environ, {"BASE_URLS": "https://share.example"}, clear=False),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            scratch.Deployscratch.run(Namespace(), [])
        return runs

    def test_refuses_off_vm(self) -> None:
        """Deploy refuses off the VM.

        - the deploys the VM's main message lands
        - SystemExit follows the die() message
        """
        stderr = io.StringIO()
        with (
            patch.object(scratch, "_load_env"),
            patch.object(scratch, "is_running_on_vm", return_value=False),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.Deployscratch.run(Namespace(), [])
        self.assertIn("deployscratch deploys the VM's main", stderr.getvalue())

    def test_refuses_missing_scratch(self) -> None:
        """Deploy refuses without a scratch tree.

        - the not-found message points at createscratch
        - SystemExit follows the die() message
        """
        self.scratch_tree.rmdir()
        stderr = io.StringIO()
        with (
            patch.object(scratch, "_load_env"),
            patch.object(scratch, "is_running_on_vm", return_value=True),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.Deployscratch.run(Namespace(), [])
        self.assertIn("Run createscratch first", stderr.getvalue())

    def test_refuses_backup_in_flight(self) -> None:
        """Deploy refuses while a backup runs.

        - the a-backup-is-running message lands
        - SystemExit follows the die() message
        """
        stderr = io.StringIO()
        with (
            patch.object(scratch, "_load_env"),
            patch.object(scratch, "is_running_on_vm", return_value=True),
            patch.object(scratch, "is_backup_in_flight", return_value=True),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.Deployscratch.run(Namespace(), [])
        self.assertIn("a backup is running", stderr.getvalue())

    def test_refuses_uncovered_main_dirty_edits(self) -> None:
        """Main/-dirty edits scratch carries unchanged refuse to deploy.

        - the silent-overwrite warning lists the uncovered files
        - SystemExit follows the die() message
        """
        status = "1 .M N... 100644 100644 100644 a a ourapp/views/x.py\0"

        def fake_capture(*cmd: str, **_kw: object) -> tuple[int, str]:
            return (0, status) if "status" in cmd else (0, "ourapp/views/x.py\0")

        stderr = io.StringIO()
        with (
            patch.object(scratch, "_load_env"),
            patch.object(scratch, "is_running_on_vm", return_value=True),
            patch.object(scratch, "is_backup_in_flight", return_value=False),
            patch.object(scratch, "_changed_set", return_value=(["ourapp/other.py"], NOT_FAST)),
            patch.object(shell, "capture", side_effect=fake_capture),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            scratch.Deployscratch.run(Namespace(), [])
        self.assertIn("silently overwrite", stderr.getvalue())

    def test_full_deploy_tail(self) -> None:
        """A full deploy runs the whole tail.

        - sudo rsync and the ownership fixes run
        - backup, migrate, collectstatic all run
        - daemon-reload and restarts run
        - the baseurls share lands
        """
        runs = self._deploy(["run"], NOT_FAST)
        heads = [cmd[:2] for cmd in runs]
        self.assertIn(("sudo", "rsync"), heads)
        self.assertIn(("sudo", "find"), heads)
        self.assertIn(("sudo", "systemctl"), heads)
        self.assertIn(("uv", "run"), heads)
        systemctl_verbs = [cmd[2] for cmd in runs if cmd[:2] == ("sudo", "systemctl")]
        self.assertIn("start", systemctl_verbs)
        self.assertIn("daemon-reload", systemctl_verbs)
        self.assertIn("restart", systemctl_verbs)
        commands = [list(cmd) for cmd in runs]
        self.assertTrue(any("migrate" in cmd for cmd in commands))
        self.assertTrue(any("collectstatic" in cmd for cmd in commands))
        self.assertTrue(any("baseurls" in cmd for cmd in commands))

    def test_fast_path_skips_backend_tail(self) -> None:
        """A frontend-only diff skips the backend tail.

        - no migrate, no systemctl verbs
        - collectstatic still runs
        """
        runs = self._deploy(["frontend/src/app/pages/X.vue"], FastPath(True, True, False))
        commands = [list(cmd) for cmd in runs]
        self.assertFalse(any("migrate" in cmd for cmd in commands))
        self.assertTrue(any("collectstatic" in cmd for cmd in commands))
        systemctl_verbs = [cmd[2] for cmd in runs if cmd[:2] == ("sudo", "systemctl")]
        self.assertEqual(systemctl_verbs, [])
