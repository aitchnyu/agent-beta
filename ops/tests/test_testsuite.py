"""Unit tests for the decision logic in ops/testsuite.py (no Django, no VM)."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from ops import testsuite


class MigrationHashTests(unittest.TestCase):
    """_hash_migration_trees over a temporary tree pair.

    - test_same_trees_hash_identically, the digest is deterministic
    - test_edited_migration_changes_hash, content edits count
    - test_added_migration_changes_hash, new files count
    - test_deleted_migration_changes_hash, removals count
    - test_renamed_migration_changes_hash, renames count (paths are hashed)
    - test_same_contents_different_dirs_differ, the tree names are part of the hash
    - test_non_python_files_ignored, only *.py feeds the hash
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.trees = [self.root / "djangoapp" / "migrations", self.root / "ourapp" / "migrations"]
        for tree in self.trees:
            tree.mkdir(parents=True)
        (self.trees[0] / "0001_initial.py").write_text("a = 1\n", encoding="utf-8")
        (self.trees[1] / "0001_core.py").write_text("b = 2\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup() 

    def _hash(self) -> str:
        return testsuite._hash_migration_trees(self.trees, relative_to=self.root)

    def test_same_trees_hash_identically(self) -> None:
        self.assertEqual(self._hash(), self._hash())

    def test_edited_migration_changes_hash(self) -> None:
        before = self._hash()
        (self.trees[0] / "0001_initial.py").write_text("a = 2\n", encoding="utf-8")
        self.assertNotEqual(self._hash(), before)

    def test_added_migration_changes_hash(self) -> None:
        before = self._hash()
        (self.trees[1] / "0002_next.py").write_text("c = 3\n", encoding="utf-8")
        self.assertNotEqual(self._hash(), before)

    def test_deleted_migration_changes_hash(self) -> None:
        before = self._hash()
        (self.trees[1] / "0001_core.py").unlink()
        self.assertNotEqual(self._hash(), before)

    def test_renamed_migration_changes_hash(self) -> None:
        before = self._hash()
        (self.trees[0] / "0001_initial.py").rename(self.trees[0] / "0001_renamed.py")
        self.assertNotEqual(self._hash(), before)

    def test_same_contents_different_dirs_differ(self) -> None:
        other = self.root / "other" / "migrations"
        other.mkdir(parents=True)
        (other / "0001_initial.py").write_text("a = 1\n", encoding="utf-8")
        self.assertNotEqual(
            testsuite._hash_migration_trees([other], relative_to=self.root),
            testsuite._hash_migration_trees([self.trees[0]], relative_to=self.root),
        )

    def test_non_python_files_ignored(self) -> None:
        before = self._hash()
        (self.trees[0] / "notes.txt").write_text("ignored", encoding="utf-8")
        self.assertEqual(self._hash(), before)


class TestCommandTests(unittest.TestCase):
    """testsuite.test's flag/env/marker assembly, with shell.run recorded.

    - test_marker_match_adds_keepdb, a matching marker reuses the test DB
    - test_missing_marker_runs_fresh, no marker means no --keepdb, and the marker is written
    - test_drifted_marker_runs_fresh, a mismatching marker means no --keepdb, then refreshes
    - test_full_run_uses_no_fast_flags, --full keeps full logs, no failfast, no keepdb, marker untouched
    - test_extra_flags_pass_after_labels, extra flags append after the labels
    - test_run_always_non_interactive, --noinput is on every path
    - test_marker_not_written_when_run_fails, a failed fast run leaves the old marker
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.marker = Path(self._tmp.name) / "test-migrations.sha"
        self.runs: list[tuple[tuple[str, ...], dict[str, str]]] = []

        def record_run(
            *cmd: str,
            _cwd: Path | None = None,
            env: dict[str, str] | None = None,
            _check: bool = True,
            _quiet_stderr: bool = False,
        ) -> None:
            self.runs.append((cmd, env or {}))

        stack = ExitStack()
        self.addCleanup(stack.close)
        # Baseline so assertions see what test() SET, not what the outer
        # runner happened to export (the fast path exports LOG_LEVEL too).
        stack.enter_context(patch.dict("os.environ", {"LOG_LEVEL": "baseline"}))
        for p in (
            patch("ops.shell.run", record_run),
            patch.object(testsuite, "_MARKER", self.marker),
            patch.object(testsuite, "_migrations_hash", lambda: "digest-1"),
        ):
            stack.enter_context(p)
        self.addCleanup(self._tmp.cleanup)

    def _cmd(self) -> tuple[str, ...]:
        return self.runs[0][0]

    def _env(self) -> dict[str, str]:
        return self.runs[0][1]

    def test_marker_match_adds_keepdb(self) -> None:
        self.marker.write_text("digest-1\n", encoding="utf-8")
        testsuite.test(["ourapp"], [], is_full=False)
        self.assertIn("--keepdb", self._cmd())
        self.assertIn("--failfast", self._cmd())
        self.assertEqual(self._env()["LOG_LEVEL"], "WARNING")

    def test_missing_marker_runs_fresh(self) -> None:
        testsuite.test(["ourapp"], [], is_full=False)
        self.assertNotIn("--keepdb", self._cmd())
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "digest-1\n")

    def test_drifted_marker_runs_fresh(self) -> None:
        self.marker.write_text("old-digest\n", encoding="utf-8")
        testsuite.test(["ourapp"], [], is_full=False)
        self.assertNotIn("--keepdb", self._cmd())
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "digest-1\n")

    def test_full_run_uses_no_fast_flags(self) -> None:
        self.marker.write_text("stale\n", encoding="utf-8")
        testsuite.test(["ourapp"], [], is_full=True)
        cmd = self._cmd()
        self.assertNotIn("--failfast", cmd)
        self.assertNotIn("--keepdb", cmd)
        self.assertEqual(self._env()["LOG_LEVEL"], "baseline")
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "stale\n")

    def test_extra_flags_pass_after_labels(self) -> None:
        testsuite.test(["ourapp.tests.test_x"], ["--pdb"], is_full=False)
        cmd = self._cmd()
        self.assertLess(cmd.index("ourapp.tests.test_x"), cmd.index("--pdb"))

    def test_run_always_non_interactive(self) -> None:
        for is_full in (False, True):
            self.runs.clear()
            testsuite.test(["ourapp"], [], is_full=is_full)
            self.assertIn("--noinput", self._cmd())

    def test_marker_not_written_when_run_fails(self) -> None:
        self.marker.write_text("old-digest\n", encoding="utf-8")

        def failing_run(*_args: str, **_kwargs: object) -> None:
            raise SystemExit(1)

        with patch("ops.shell.run", failing_run), self.assertRaises(SystemExit):
            testsuite.test(["ourapp"], [], is_full=False)
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "old-digest\n")
