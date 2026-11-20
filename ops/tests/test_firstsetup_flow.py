"""Tests for ops/firstsetup/flow.py — the setup verbs over pi.

No Textual (operator decision 2026-11-20). Each verb runs its own
commands; tests script the subprocess spawn and assert the returned
dataclasses — Outcome/UserCreated — directly.

Class inventory:

- GetModelTests: the provider's first model from the table listing
- WaitForSuccessResponseTests: the one-turn model call — ok, 401, the
  400-rc0 trap, empty reply naming pi's rc
- VerifyProviderTests: the composition — no models short-circuits
- RunPiOAuthLoginTests: the device-code login — ok, cancelled error
  from stderr, argv shape
- CreateSuperuserWithLinkTests: createuser → makeloginlink — link
  captured, createuser failure stops, linkless output refuses
- StoreGoogleOauthTests: addoauth ok / failure raises
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

from ops.firstsetup.flow import (
    Outcome,
    UserCreated,
    create_superuser_with_link,
    get_model,
    run_pi_oauth_login,
    store_google_oauth,
    verify_provider,
    wait_for_success_response,
)

MODELS_TABLE = b"provider  model\nzai  glm-5.3-flash\nopenai-codex  gpt-5-codex\n"


def completed(
    exit_code: int = 0, stdout_bytes: bytes = b"", stderr_bytes: bytes = b""
) -> mock.AsyncMock:
    """Return a finished subprocess: communicate() → (out, err), rc set."""
    proc = mock.AsyncMock()
    proc.communicate.return_value = (stdout_bytes, stderr_bytes)
    proc.returncode = exit_code
    return proc


def spawn_with(*responses: mock.AsyncMock) -> mock.AsyncMock:
    """Return a create_subprocess_exec stand-in answering scripted results."""
    return mock.AsyncMock(side_effect=list(responses))


class GetModelTests(unittest.TestCase):
    """The provider's first model from the table listing.

    verify_provider branches on this answer to decide whether a print
    call is possible at all.

    - test_own_row_wins, the provider's own first model comes back
    - test_absent_provider_is_none, no row means None
    """

    def test_own_row_wins(self) -> None:
        """The provider's own first model comes back.

        - zai's row is second in the table, and its model wins
        """
        exec_mock = spawn_with(completed(stdout_bytes=MODELS_TABLE))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            self.assertEqual(asyncio.run(get_model("zai")), "glm-5.3-flash")

    def test_absent_provider_is_none(self) -> None:
        """A provider absent from the table reads as None.

        - the caller branches on None to skip the print call
        """
        exec_mock = spawn_with(completed(stdout_bytes=b"provider  model\ntogether  x\n"))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            self.assertIsNone(asyncio.run(get_model("zai")))


class WaitForSuccessResponseTests(unittest.TestCase):
    """The one-turn model call.

    Real behavior (probed in the VM with a real zai key): pi exits 0
    even on provider errors (an unknown model returns a 400 body) —
    the body shape must fail the call even on rc-0.

    - test_ok_reply_verifies, a plain reply on rc-0 is True
    - test_provider_error_fails, rc=1 → the provider's own 401 line
    - test_error_body_fails_even_with_rc0, '400: {...}' with rc=0 →
      NOT verified (the wrong-model trap)
    - test_empty_reply_names_rc, no reply at all names pi's rc
    """

    def _wait(self, exit_code: int, out: bytes) -> Outcome:
        exec_mock = spawn_with(completed(exit_code=exit_code, stdout_bytes=out))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            return asyncio.run(wait_for_success_response("zai", "glm-5.3-flash"))

    def test_ok_reply_verifies(self) -> None:
        """A plain reply on rc-0 verifies.

        - Outcome(is_ok=True, error=reply) — the error field carries the reply text
        """
        self.assertEqual(self._wait(0, b"ok"), Outcome(is_ok=True, error="ok"))

    def test_provider_error_fails(self) -> None:
        """A bad credential surfaces the provider's own error line.

        - the 401 code and message text both ride the error field
        """
        error = b'401: {"code":"401","message":"token expired or incorrect"}'
        outcome = self._wait(1, error)
        self.assertFalse(outcome.is_ok)
        self.assertIn("401", outcome.error)
        self.assertIn("token expired or incorrect", outcome.error)

    def test_error_body_fails_even_with_rc0(self) -> None:
        """A 4xx body fails the call even when pi exits 0.

        - the wrong-model trap (rc=0, 400 body) is NOT verified
        """
        outcome = self._wait(0, b'400: {"code":"1211","message":"Unknown Model"}')
        self.assertFalse(outcome.is_ok)
        self.assertIn("400", outcome.error)

    def test_empty_reply_names_rc(self) -> None:
        """No reply text at all fails naming pi's exit code.

        - the error is exactly "no reply from pi (exit code 5)"
        """
        self.assertEqual(
            self._wait(5, b""), Outcome(is_ok=False, error="no reply from pi (exit code 5)")
        )


class VerifyProviderTests(unittest.TestCase):
    """The composition both auth screens call.

    This one verb is the whole credential check a screen performs —
    no shell-side wrangling.

    - test_verifies_through_model_call, model found → the print verdict
    - test_no_models_short_circuits, no model → explicit error, no
      second command spawned
    """

    def test_verifies_through_model_call(self) -> None:
        """A stored, working credential verifies.

        - Outcome(is_ok=True, error="ok") — exactly what the screen branches on
        """
        exec_mock = spawn_with(completed(stdout_bytes=MODELS_TABLE), completed(stdout_bytes=b"ok"))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            self.assertEqual(asyncio.run(verify_provider("zai")), Outcome(is_ok=True, error="ok"))

    def test_no_models_short_circuits(self) -> None:
        """A provider with no models returns the explicit error.

        - only the models listing spawns; the error names the provider
        """
        exec_mock = spawn_with(completed(stdout_bytes=b"provider  model\ntogether  x\n"))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            outcome = asyncio.run(verify_provider("zai"))
        self.assertEqual(outcome, Outcome(is_ok=False, error="no models listed for provider zai"))
        self.assertEqual(exec_mock.await_count, 1)


class RunPiOAuthLoginTests(unittest.TestCase):
    """pi's device-code login.

    The screen suspends the terminal around this; the verdict is all
    it wants back.

    - test_rc0_logs_in, rc-0 means ok
    - test_failure_error_carries_stderr, a cancelled login's error is
      built from pi's own stderr
    - test_argv_shape, the command runs as debian with the provider id
      and --no-browser; stderr is piped
    """

    def test_rc0_logs_in(self) -> None:
        """A rc-0 login is ok.

        - Outcome(is_ok=True) — the caller proceeds to verification
        """
        exec_mock = spawn_with(completed())
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            self.assertTrue(asyncio.run(run_pi_oauth_login("openai-codex")).is_ok)

    def test_failure_error_carries_stderr(self) -> None:
        """A cancelled login's error is built from stderr.

        - the message names rc=1 and pi's own stderr text
        """
        exec_mock = spawn_with(completed(exit_code=1, stderr_bytes=b"device flow aborted"))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            result = asyncio.run(run_pi_oauth_login("openai-codex"))
        self.assertFalse(result.is_ok)
        self.assertIn("login failed (exit code 1)", result.error)
        self.assertIn("device flow aborted", result.error)

    def test_argv_shape(self) -> None:
        """The login runs as debian with the right shape.

        - sudo -u debian -H pi auth login, the provider id, --no-browser
        - stderr is piped so a failure can surface pi's own message
        """
        exec_mock = spawn_with(completed())
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            asyncio.run(run_pi_oauth_login("zai"))
        argv = exec_mock.call_args.args
        self.assertEqual(argv[:6], ("sudo", "-u", "debian", "-H", "pi", "auth"))
        self.assertIn("zai", argv)
        self.assertIn("--no-browser", argv)
        self.assertIs(exec_mock.call_args.kwargs["stderr"], asyncio.subprocess.PIPE)


USER_ARGS = ("Jane", "Doe", "jane@example.com")


class CreateSuperuserWithLinkTests(unittest.TestCase):
    """createuser → makeloginlink as one verb.

    Setup's whole first-user story: a user plus the one-time link that
    signs the operator in.

    - test_created_with_link, both green → UserCreated carrying the
      login_url from makeloginlink's JSON
    - test_createuser_failure_raises, a failing createuser raises
      AssertionError with its own error line; makeloginlink never runs
    - test_linkless_output_raises, green output without a login_url
      raises rather than lying
    """

    def test_created_with_link(self) -> None:
        """Both commands green → created, carrying the JSON login_url.

        - makeloginlink's login_url field is the link, verbatim
        """
        link = "https://localhost:8443/login-with-secret/xyz/"
        script = [
            completed(stdout_bytes=b'{"message": "created", "created": true}'),
            completed(
                stdout_bytes=json.dumps({"message": f"use {link}", "login_url": link}).encode()
            ),
        ]
        exec_mock = spawn_with(*script)
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            result = asyncio.run(create_superuser_with_link(*USER_ARGS))
        self.assertEqual(result, UserCreated(login_link=link))

    def test_createuser_failure_raises(self) -> None:
        """A failing createuser raises AssertionError with its own error line.

        - the message names createuser, the exit code, and the last output line
        - makeloginlink never runs
        """
        exec_mock = spawn_with(
            completed(
                exit_code=1,
                stdout_bytes=b"Traceback (most recent call last):\nValueError: bad email",
            )
        )
        with (
            mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock),
            self.assertRaisesRegex(
                AssertionError, r"^createuser failed \(exit code 1\): ValueError: bad email$"
            ),
        ):
            asyncio.run(create_superuser_with_link(*USER_ARGS))
        self.assertEqual(exec_mock.await_count, 1)

    def test_linkless_output_raises(self) -> None:
        """Green output without a login_url raises rather than lying.

        - the AssertionError names makeloginlink's missing link
        """
        exec_mock = spawn_with(
            completed(stdout_bytes=b'{"created": true}'), completed(stdout_bytes=b"nothing here")
        )
        with (
            mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock),
            self.assertRaisesRegex(AssertionError, r"^makeloginlink printed no login link"),
        ):
            asyncio.run(create_superuser_with_link(*USER_ARGS))


GOOGLE_ARGS = ("1234567890-abc123.apps.googleusercontent.com", "GOCSPX-" + "x" * 28)


class StoreGoogleOauthTests(unittest.TestCase):
    """addoauth as one verb.

    Google has no provider screen in pi — the credentials go straight
    into Django.

    - test_stored, green addoauth returns quietly — the caller marks
      google configured
    - test_failure_raises, a failure raises AssertionError carrying the
      command's own last output line
    """

    def test_stored(self) -> None:
        """A green addoauth stores.

        - returns None; no exception
        """
        exec_mock = spawn_with(completed(stdout_bytes=b"stored"))
        with mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock):
            self.assertIsNone(asyncio.run(store_google_oauth(*GOOGLE_ARGS)))

    def test_failure_raises(self) -> None:
        """A failing addoauth raises its own error line.

        - the message names addoauth, the exit code, and the last output line
        """
        exec_mock = spawn_with(
            completed(
                exit_code=1, stdout_bytes=b"Traceback (most recent call last):\nValueError: bad key"
            )
        )
        with (
            mock.patch("ops.firstsetup.flow.asyncio.create_subprocess_exec", exec_mock),
            self.assertRaisesRegex(
                AssertionError, r"^addoauth failed \(exit code 1\): ValueError: bad key$"
            ),
        ):
            asyncio.run(store_google_oauth(*GOOGLE_ARGS))
