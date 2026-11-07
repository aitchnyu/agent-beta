"""Unit tests for ops/postdeploychecks.py — canned shell outputs, no git or VM."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from ops import postdeploychecks, shell


class PostdeploychecksTests(unittest.TestCase):
    """The four→three close-out checks with canned shell outputs.

    - test_all_green, clean tree + migrations + no scratch → all PASS
    - test_everything_red, dirty tree + pending migrations + scratch → all FAIL
    - test_run_exits_nonzero_on_failure, SystemExit(1) when a check fails
    """

    GREEN = [
        (0, ""),
        (0, ""),
    ]

    def run_audit(
        self, captures: list[tuple[int, str]], scratch_exists: bool
    ) -> list[tuple[bool, str]]:
        """Drive _audit_lines with canned capture outputs in call order."""
        sentinel = Path("/tmp") if scratch_exists else Path("/nonexistent/probe-scratch")
        with (
            patch.object(shell, "capture", side_effect=captures),
            patch.object(postdeploychecks, "SCRATCH_DIR", sentinel),
        ):
            return postdeploychecks._audit_lines()

    def test_all_green(self) -> None:
        results = self.run_audit([*self.GREEN], scratch_exists=False)
        self.assertEqual([ok for ok, _ in results], [True, True, True])
        self.assertIn("tree clean", results[0][1])
        self.assertIn("migrations applied", results[1][1])

    def test_everything_red(self) -> None:
        captures = [
            (
                0,
                "1 .M N... 100644 100644 100644 a a TODO.md\0"
                "1 .M N... 100644 100644 100644 a a ourapp/views/todos.py\0"
                "? frontend/dist/x.js\0",
            ),
            (1, ""),  # migrate --check: pending
        ]
        results = self.run_audit(captures, scratch_exists=True)
        self.assertEqual([ok for ok, _ in results], [False, False, False])
        self.assertIn("TODO.md", results[0][1])
        self.assertIn("ourapp/views/todos.py", results[0][1])
        self.assertNotIn("frontend/dist", results[0][1])  # deploy-generated
        self.assertIn("pending migrations", results[1][1])
        self.assertIn("cleanscratch", results[2][1])

    def test_run_exits_nonzero_on_failure(self) -> None:
        sentinel = Path("/nonexistent/probe-scratch")
        with (
            patch.object(shell, "capture", side_effect=[(0, "1 .M N... 100644 100644 100644 a a x\0"), (0, "")]),
            patch.object(postdeploychecks, "SCRATCH_DIR", sentinel),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as ctx,
        ):
            postdeploychecks.Postdeploychecks.run(None, [])
        self.assertEqual(ctx.exception.code, 1)
