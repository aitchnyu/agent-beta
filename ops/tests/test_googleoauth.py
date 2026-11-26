"""Tests for ops/googleoauth.py — Google sign-in's validation and storage.

No Django, no VM. ``addoauth`` is scripted through ``_run``; tests
compare what comes back, the command run, and what raises.

Class inventory:

- CheckValuesTests, the client key and secret pair is validated or refused
- StoreTests, addoauth stores the pair and its JSON line is the status
"""

from __future__ import annotations

import json
import unittest
from typing import TYPE_CHECKING, cast
from unittest import mock

from ops import googleoauth

if TYPE_CHECKING:
    from collections.abc import Iterator

CLIENT_ID = "1234567890-abc123.apps.googleusercontent.com"
SECRET = "GOCSPX-" + "x" * 30
REDIRECT_URI = "https://example.test/accounts/google/login/callback/"
ADD = ("addoauth", "google", CLIENT_ID, SECRET)


def call(*argv: str, prints: dict[str, object] | None = None, fails: str = "") -> dict[str, object]:
    """Describe one scripted djangomanage call: its argv and what it answered.

    ``prints`` is the JSON line it printed; ``fails`` is the last stderr
    line of a call that exited 1.
    """
    return {"argv": argv, "prints": prints, "fails": fails}


def scripted(test: unittest.TestCase, script: list[dict[str, object]]) -> mock.Mock:
    """Return an ``_run`` stand-in that answers exactly the scripted calls.

    Each call must match the next scripted argv. Every scripted call must
    be used, so a wrong command fails the test instead of silently
    answering.
    """
    queue: Iterator[dict[str, object]] = iter(script)

    def answer(*argv: str) -> tuple[int, str, str]:
        """Answer one call with its scripted JSON line, or its scripted failure."""
        step = next(queue)
        expected = cast("tuple[str, ...]", step["argv"])
        test.assertEqual(argv, expected, "unexpected call")
        if step["fails"]:
            return 1, "", f"{step['fails']}\n"
        return 0, json.dumps(step["prints"]) + "\n", ""

    test.addCleanup(lambda: test.assertEqual(list(queue), [], "scripted call never made"))
    return mock.Mock(side_effect=answer)


class CheckValuesTests(unittest.TestCase):
    """The client key and secret pair is validated or refused.

    Tests feed pairs and read the hint, or None.

    - test_valid_pair_passes, a real-shaped pair is accepted
    - test_bad_client_id, a key without the Google suffix gets its hint
    - test_short_or_spaced_secret, a short or spaced secret gets its hint
    """

    def test_valid_pair_passes(self) -> None:
        """A real-shaped pair is accepted.

        - None, no hint
        """
        self.assertIsNone(googleoauth.check_values(CLIENT_ID, SECRET))

    def test_bad_client_id(self) -> None:
        """A client key without the Google suffix gets its hint.

        - the secret is not looked at
        """
        self.assertEqual(googleoauth.check_values("nope", SECRET), googleoauth.CLIENT_ID_HINT)

    def test_short_or_spaced_secret(self) -> None:
        """A short or spaced secret gets its hint.

        - both shapes are refused with the same hint
        """
        for secret in ("short", "GOCSPX-" + "x" * 30 + " tail"):
            with self.subTest(secret=secret):
                self.assertEqual(
                    googleoauth.check_values(CLIENT_ID, secret), googleoauth.SECRET_HINT
                )


class StoreTests(unittest.TestCase):
    """addoauth stores the pair, and its JSON line is the status.

    Tests script the one djangomanage call and read what ``store`` returns.

    - test_one_call_is_the_status, addoauth runs once; its redirect URI
      comes back as a configured status
    - test_created_false_reads_the_same, an updated row is still set
    - test_failure_raises_and_redacts_secret, a non-zero exit raises with
      its last line, and the secret never reaches the message
    - test_line_without_json_raises, an answer with no JSON raises the
      raw decoder error
    """

    def test_one_call_is_the_status(self) -> None:
        """One addoauth call runs, and its redirect URI comes back as a configured status.

        - argv carries the provider, the key and the secret
        - nothing reads the status back: one Django start
        """
        run = scripted(
            self,
            [
                call(
                    *ADD,
                    prints={
                        "message": "Created Google SocialApp (provider=google) …",
                        "provider": "google",
                        "client_id": CLIENT_ID,
                        "redirect_uri": REDIRECT_URI,
                        "created": True,
                    },
                )
            ],
        )
        with mock.patch.object(googleoauth, "_run", run) as run_mock:
            status = googleoauth.store(CLIENT_ID, SECRET)
        self.assertEqual(
            status, googleoauth.GoogleStatus(configured=True, redirect_uri=REDIRECT_URI)
        )
        self.assertEqual(run_mock.call_count, 1)

    def test_created_false_reads_the_same(self) -> None:
        """An updated row is still set.

        - only ``created`` differs, and the status does not carry it
        """
        run = scripted(
            self,
            [
                call(
                    *ADD,
                    prints={
                        "message": "Updated …",
                        "provider": "google",
                        "client_id": CLIENT_ID,
                        "redirect_uri": REDIRECT_URI,
                        "created": False,
                    },
                )
            ],
        )
        with mock.patch.object(googleoauth, "_run", run):
            status = googleoauth.store(CLIENT_ID, SECRET)
        self.assertEqual(
            status, googleoauth.GoogleStatus(configured=True, redirect_uri=REDIRECT_URI)
        )

    def test_failure_raises_and_redacts_secret(self) -> None:
        """A non-zero exit raises with its own last line, and the secret never reaches it.

        - the line shows the secret replaced
        """
        run = scripted(self, [call(*ADD, fails=f"boom {SECRET}")])
        with (
            mock.patch.object(googleoauth, "_run", run),
            self.assertRaisesRegex(
                googleoauth.SetupError, r"^addoauth failed \(exit code 1\): boom <secret>$"
            ) as raised,
        ):
            googleoauth.store(CLIENT_ID, SECRET)
        self.assertNotIn(SECRET, str(raised.exception))

    def test_line_without_json_raises(self) -> None:
        """An answer with no JSON raises the raw decoder error.

        - nothing wraps it: a crash is a bug in our own command
        """
        run = mock.Mock(return_value=(0, "not json\n", ""))
        with (
            mock.patch.object(googleoauth, "_run", run),
            self.assertRaisesRegex(json.JSONDecodeError, r"^Expecting value"),
        ):
            googleoauth.store(CLIENT_ID, SECRET)


if __name__ == "__main__":
    unittest.main()
