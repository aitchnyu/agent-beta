"""Unit tests for the ops/cli.py dispatch (no Django, no VM)."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from ops import cli, scratch, testsuite


class DispatchTests(unittest.TestCase):
    """main()'s dict dispatch.

    - test_test_command_parses_full_and_labels, --full lands in args.full, labels pass through
    - test_full_flag_position_independent, --full works after the labels too
    - test_unknown_flags_become_extra, flags manage.py owns ride in extra
    - test_scratch_trio_dispatches, createscratch reaches the Command's run
    - test_playwrighttest_and_screenshots_wiring, labels + extra reach the suite commands
    - test_unknown_command_exits_with_usage, a bad name prints the command list and exits 1
    - test_no_command_exits_with_usage, bare invocation is also a usage error
    """

    def test_test_command_parses_full_and_labels(self) -> None:
        with patch.object(testsuite.Test, "run") as run:
            cli.main(["test", "--full", "ourapp", "djangoapp.tests.test_x"])
        (args, extra), _kwargs = run.call_args
        self.assertEqual(args.labels, ["ourapp", "djangoapp.tests.test_x"])
        self.assertTrue(args.full)
        self.assertEqual(extra, [])

    def test_full_flag_position_independent(self) -> None:
        with patch.object(testsuite.Test, "run") as run:
            cli.main(["test", "ourapp", "--full"])
        (args, _extra), _kwargs = run.call_args
        self.assertEqual(args.labels, ["ourapp"])
        self.assertTrue(args.full)

    def test_unknown_flags_become_extra(self) -> None:
        with patch.object(testsuite.Test, "run") as run:
            cli.main(["test", "ourapp", "--noinput", "--parallel", "2"])
        (args, extra), _kwargs = run.call_args
        self.assertEqual(args.labels, ["ourapp"])
        self.assertFalse(args.full)
        self.assertEqual(extra, ["--noinput", "--parallel", "2"])

    def test_scratch_trio_dispatches(self) -> None:
        for command, klass in (
            ("createscratch", scratch.Createscratch),
            ("deployscratch", scratch.Deployscratch),
            ("cleanscratch", scratch.Cleanscratch),
        ):
            with self.subTest(command=command), patch.object(klass, "run") as run:
                cli.main([command])
            run.assert_called_once()

    def test_playwrighttest_and_screenshots_wiring(self) -> None:
        for command, klass in (
            ("playwrighttest", testsuite.Playwrighttest),
            ("screenshots", testsuite.Screenshots),
        ):
            with self.subTest(command=command), patch.object(klass, "run") as run:
                cli.main([command, "ourapp.tests.test_x"])
            (args, extra), _kwargs = run.call_args
            self.assertEqual(args.labels, ["ourapp.tests.test_x"])
            self.assertEqual(extra, [])

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
