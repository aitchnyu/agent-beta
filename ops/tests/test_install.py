"""Tests for deploy/install.sh's argument check — the installer refuses before it changes anything.

No VM and no network: the check-only mode parses the flags, checks them
and exits ahead of the root guard. Every refusal is compared with
desmosetup's own message for the same flags (ops/setup.py), so the two
checks cannot drift.

Class inventory:

- CheckArgsTests, the flags through ``install.sh --check-args``, with
  and without a terminal
"""

from __future__ import annotations

import os
import pty
import subprocess
import unittest
from pathlib import Path

from ops import setup

INSTALL_SH = Path(__file__).resolve().parents[2] / "deploy" / "install.sh"
ARGPARSE_REFUSAL = 2  # argparse's own exit code for a missing or an unknown flag
GOOD = [
    "--base-url",
    "https://desmo.example",
    "--first-name",
    "O'Brien",
    "--last-name",
    "Doe",
    "--email",
    "jane@example.com",
]
GOOGLE_KEY = ["--google-key", "1234567890-abc123.apps.googleusercontent.com"]
GOOGLE_SECRET = ["--google-secret", "GOCSPX-" + "x" * 30]


def check(flags: list[str], *, terminal: bool = False) -> tuple[int, str]:
    """Run ``install.sh --check-args``; return its exit code and what it said.

    ``terminal`` runs it with a pty on stdout, as the operator's shell has.
    """
    command = ["bash", str(INSTALL_SH), "--check-args", *flags]
    if not terminal:
        done = subprocess.run(command, capture_output=True, text=True, check=False)
        return done.returncode, (done.stdout + done.stderr).replace("\r", "")
    master, slave = pty.openpty()
    try:
        driven = subprocess.run(
            command, stdout=slave, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, check=False
        )
    finally:
        os.close(slave)
    said = b""
    while True:
        try:
            chunk = os.read(master, 4096)
        except OSError:  # every writer is gone: Linux answers EIO once the pty is drained
            break
        if not chunk:
            break
        said += chunk
    os.close(master)
    return driven.returncode, said.decode(errors="replace").replace("\r", "")


def last_line(said: str) -> str:
    """Return the last line a refusal printed: usage comes first, the reason last."""
    return said.strip().splitlines()[-1].strip()


def desmosetup_says(flags: list[str]) -> str | None:
    """Return what parse_args() refuses these flags with; None when it takes them."""
    try:
        setup.parse_args(flags)
    except SystemExit as error:
        return None if error.code == ARGPARSE_REFUSAL else str(error.code)
    return None


class CheckArgsTests(unittest.TestCase):
    """The installer's flags through ``install.sh --check-args``.

    Tests run the real script; the terminal cases run it under a pty.

    - test_good_flags_pass, without and with a terminal
    - test_a_whole_google_pair_passes
    - test_the_origin_is_needed_and_checked
    - test_names_and_the_email_are_checked, with desmosetup's own messages
    - test_a_terminal_needs_the_superuser, and a driven run does not
    - test_google_is_both_or_neither, with desmosetup's own messages
    - test_release_and_branch_clash, and an unknown flag is refused
    """

    def test_good_flags_pass(self) -> None:
        """The six flags pass the check, terminal or not.

        - an apostrophe in a name is taken as is
        - nothing installs: the check exits with "args ok"
        """
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                code, said = check(GOOD, terminal=terminal)
                self.assertEqual(code, 0)
                self.assertEqual(said.strip(), "args ok")
                self.assertNotIn("REFUSING", said)

    def test_a_whole_google_pair_passes(self) -> None:
        """Both Google flags pass the check."""
        code, said = check([*GOOD, *GOOGLE_KEY, *GOOGLE_SECRET])
        self.assertEqual((code, said.strip()), (0, "args ok"))

    def test_the_origin_is_needed_and_checked(self) -> None:
        """No origin, or one of the wrong shape, is refused.

        - the shape's message is desmosetup's own
        """
        without = GOOD[2:]
        code, said = check(without)
        self.assertEqual(code, 1)
        self.assertEqual(last_line(said), "--base-url is needed: https://host[:port]")
        for origin in ("http://desmo.example", "desmo.example", "https://desmo.example/path"):
            with self.subTest(origin=origin):
                flags = ["--base-url", origin, *GOOD[2:]]
                code, said = check(flags)
                self.assertEqual(code, 1)
                self.assertEqual(last_line(said), desmosetup_says(flags))
                self.assertIsNotNone(desmosetup_says(flags))

    def test_names_and_the_email_are_checked(self) -> None:
        """A name or an email of the wrong shape is refused.

        - the message is desmosetup's own, so the two checks agree
        """
        for flag, value in (
            ("--first-name", "Jane Doe"),
            ("--first-name", "3Jane"),
            ("--last-name", "Jane_Doe"),
            ("--email", "jane.example.com"),
            ("--email", "jane@" + "x" * 260 + ".com"),
        ):
            with self.subTest(flag=flag, value=value[:16]):
                flags = list(GOOD)
                flags[flags.index(flag) + 1] = value
                code, said = check(flags)
                self.assertEqual(code, 1)
                self.assertEqual(last_line(said), desmosetup_says(flags))

    def test_a_terminal_needs_the_superuser(self) -> None:
        """With a terminal the first run follows, so the superuser's flags are needed.

        - a driven run (no terminal) passes without them
        - each missing flag is named
        """
        origin_only = GOOD[:2]
        code, said = check(origin_only)
        self.assertEqual((code, said.strip()), (0, "args ok"))
        for missing in ("--first-name", "--last-name", "--email"):
            with self.subTest(missing=missing):
                kept = list(GOOD)
                at = kept.index(missing)
                del kept[at : at + 2]
                code, said = check(kept, terminal=True)
                self.assertEqual(code, 1)
                self.assertEqual(last_line(said), f"{missing} is needed")

    def test_google_is_both_or_neither(self) -> None:
        """One Google flag, or a pair of the wrong shape, is refused.

        - the message is desmosetup's own
        """
        pairs = (
            GOOGLE_KEY,
            GOOGLE_SECRET,
            ["--google-key", "desmo.example", *GOOGLE_SECRET],
            [*GOOGLE_KEY, "--google-secret", "short"],
        )
        for pair in pairs:
            with self.subTest(pair=pair):
                flags = [*GOOD, *pair]
                code, said = check(flags)
                self.assertEqual(code, 1)
                self.assertEqual(last_line(said), desmosetup_says(flags))

    def test_release_and_branch_clash(self) -> None:
        """Both a release and a branch is refused; so is an unknown flag."""
        code, said = check([*GOOD, "--release", "v1", "--branch", "main"])
        self.assertEqual(
            (code, last_line(said)), (1, "--branch and --release are mutually exclusive")
        )
        code, said = check([*GOOD, "--token", "abc123"])
        self.assertEqual(code, 1)
        self.assertEqual(last_line(said), "unknown flag: --token")


if __name__ == "__main__":
    unittest.main()
