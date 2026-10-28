"""Unit tests for the ops/cli.py dispatch (no Django, no VM)."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from ops import cli, scratch, testsuite


class DispatchTests(unittest.TestCase):
    """main()'s dict dispatch.

    - test_test_command_parses_full_and_labels, --full lands in is_full, labels pass through
    - test_full_flag_position_independent, --full works after the labels too
    - test_unknown_flags_become_extra, flags manage.py owns ride in extra
    - test_scratch_trio_dispatches, createscratch reaches scratch.createscratch
    - test_playwrighttest_and_screenshots_wiring, labels reach the suite functions
    - test_unknown_command_exits_with_usage, a bad name prints the command list and exits 1
    - test_no_command_exits_with_usage, bare invocation is also a usage error
    """

    def test_test_command_parses_full_and_labels(self) -> None:
        calls: list[tuple[object, ...]] = []
        with patch.object(testsuite, "test", lambda *a, **k: calls.append((*a, k))):
            cli.main(["test", "--full", "ourapp", "djangoapp.tests.test_x"])
        self.assertEqual(calls, [(["ourapp", "djangoapp.tests.test_x"], [], {"is_full": True})])

    def test_full_flag_position_independent(self) -> None:
        calls: list[tuple[object, ...]] = []
        with patch.object(testsuite, "test", lambda *a, **k: calls.append((*a, k))):
            cli.main(["test", "ourapp", "--full"])
        self.assertEqual(calls, [(["ourapp"], [], {"is_full": True})])

    def test_unknown_flags_become_extra(self) -> None:
        calls: list[tuple[object, ...]] = []
        with patch.object(testsuite, "test", lambda *a, **k: calls.append((*a, k))):
            cli.main(["test", "ourapp", "--noinput", "--parallel", "2"])
        self.assertEqual(
            calls, [(["ourapp"], ["--noinput", "--parallel", "2"], {"is_full": False})]
        )

    def test_scratch_trio_dispatches(self) -> None:
        for command, target in (
            ("createscratch", "createscratch"),
            ("deployscratch", "deployscratch"),
            ("cleanscratch", "cleanscratch"),
        ):
            with self.subTest(command=command):
                with patch.object(scratch, target) as run:
                    cli.main([command])
                run.assert_called_once_with()

    def test_playwrighttest_and_screenshots_wiring(self) -> None:
        for command, target in (
            ("playwrighttest", "playwrighttest"),
            ("screenshots", "screenshots"),
        ):
            with self.subTest(command=command):
                with patch.object(testsuite, target) as run:
                    cli.main([command, "ourapp.tests.test_x"])
                run.assert_called_once_with(["ourapp.tests.test_x"], [])

    def test_unknown_command_exits_with_usage(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main(["nope"])
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("|".join(cli.COMMANDS), stderr.getvalue())

    def test_no_command_exits_with_usage(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main([])
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("usage:", stderr.getvalue())
