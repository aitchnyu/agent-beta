"""Tests for ops/setup.py and ops/setup_app.py — the desmosetup command.

No Textual pilots (operator decision 2026-11-20). The terminal steps run
with every command scripted; the screen's pure helpers — the origin
rules, validation, the domain step — are read directly.

Class inventory:

- GoogleStepTests, Google left empty is not set; a pair is stored
- PiStepTests, the key or the sign-in, the model list, the opt-out
- RunStepsTests, the steps run in order and make one Outcome
- ReportTests, three parts under bold headings, coloured or plain
- MainTests, one way through: Next, the steps, the report; a crash
  propagates
- DropStaleInputTests, keystrokes buffered before the screen are
  dropped
- ValidateTests, every refusal as (field, message), in screen order
- TypedOriginTests, the https origin a typed domain means
- CurrentDomainTests, the origin read off the credentials env
- ApplyDomainTests, the provisioner's set-domain step through sudo
"""

from __future__ import annotations

import contextlib
import io
import signal
import tempfile
import termios
import unittest
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

from ops import googleoauth, piauth, setup, setup_app, superuserloginlink
from ops.superuserloginlink import EMAIL_HINT, NAME_HINT

if TYPE_CHECKING:
    from collections.abc import Callable

ZAI = piauth.Provider(id="zai", api_key=True)
CODEX = piauth.Provider(id="openai-codex", oauth=True)
JANE = superuserloginlink.Superuser(first="Jane", last="Doe", email="jane@example.com")
LINK = "https://desmo.example/login-with-secret/abc/"
CALLBACK = "https://desmo.example/accounts/google/login/callback/"
CLIENT_ID = "1234567890-abc123.apps.googleusercontent.com"
SECRET = "GOCSPX-" + "x" * 30
API_KEY = "sk-pilot"
LOGIN = "pi auth login zai --api-key"
ENABLED = setup.PiOutcome(provider="zai", login=LOGIN)
VALUES = setup_app.Values(
    homepage="https://desmo.example",
    set_domain=False,
    first="Jane",
    last="Doe",
    email="jane@example.com",
    google_key="",
    google_secret="",
    provider=ZAI,
    api_key=API_KEY,
)
WITH_GOOGLE = replace(VALUES, google_key=CLIENT_ID, google_secret=SECRET)
VALID = setup_app.Answers(
    domain="https://localhost:8443",
    first="Jane",
    last="Doe",
    email="jane@example.com",
    google_key="",
    google_secret="",
    provider="zai",
    api_key=API_KEY,
)


def outcome(google: googleoauth.GoogleStatus, pi: setup.PiOutcome) -> setup.Outcome:
    """Return an Outcome for Jane with the given Google and pi parts."""
    return setup.Outcome(
        superuser=JANE,
        link=LINK,
        homepage="https://desmo.example",
        google=google,
        pi=pi,
    )


class GoogleStepTests(unittest.TestCase):
    """Google left empty is not set; a pair is stored.

    Tests script the one googleoauth verb and read the GoogleStatus.

    - test_left_empty_is_not_set, no field given: nothing runs, the
      status reads as not set
    - test_pair_is_stored, both fields given: the pair goes through store
    """

    SET = googleoauth.GoogleStatus(configured=True, redirect_uri=CALLBACK)

    def test_left_empty_is_not_set(self) -> None:
        """No field given: nothing runs, and the status reads as not set.

        - the first run is the only run: no one asks what the machine holds
        """
        with mock.patch.object(googleoauth, "store") as store:
            found = setup.google_step(VALUES)
        self.assertEqual(found, googleoauth.GoogleStatus(configured=False))
        store.assert_not_called()

    def test_pair_is_stored(self) -> None:
        """Both fields given: the pair goes through store, once.

        - the status after the store comes back
        """
        with mock.patch.object(googleoauth, "store", return_value=self.SET) as store:
            found = setup.google_step(WITH_GOOGLE)
        self.assertEqual(found, self.SET)
        store.assert_called_once_with(CLIENT_ID, SECRET)


class PiStepTests(unittest.TestCase):
    """The key or the sign-in, the model list, the analytics opt-out.

    Tests script the pi verbs and read the outcome.

    - test_key_provider_saves_the_key_then_the_opt_out, the typed key goes
      to pi's file; the model list is fetched, then the opt-out is written
    - test_sign_in_provider_signs_in_on_the_terminal_first, pi's own login
      is announced and runs before the model list; no key is saved
    - test_abandoned_login_is_a_failed_outcome, a sign-in that ended with
      no credential is the report part
    - test_unexpected_error_propagates, only pi's refusals are report parts
    """

    def test_key_provider_saves_the_key_then_the_opt_out(self) -> None:
        """The typed key goes to pi's file; the model list is fetched, then the opt-out.

        - a non-empty list is the whole test; no model is chosen or saved
        - pi's login never runs for a key provider
        """
        with (
            mock.patch.object(piauth, "store_key") as store,
            mock.patch.object(
                piauth, "list_models", mock.AsyncMock(return_value=["glm-4.7", "glm-5.4"])
            ) as models,
            mock.patch.object(piauth, "opt_out_of_analytics") as opt_out,
            mock.patch.object(piauth, "login_on_terminal") as login,
        ):
            found = setup.pi_step(ZAI, API_KEY)
        store.assert_called_once_with("zai", API_KEY)
        models.assert_awaited_once_with("zai")
        opt_out.assert_called_once_with()
        login.assert_not_called()
        self.assertEqual(found, ENABLED)

    def test_sign_in_provider_signs_in_on_the_terminal_first(self) -> None:
        """A sign-in-only provider signs in on the terminal; the list and the opt-out follow.

        - the sign-in is announced and runs before the model list; no key is saved
        """
        calls: list[str] = []

        def listed(_provider_id: str) -> list[str]:
            """Record the model list's place in the order."""
            calls.append("list")
            return ["gpt-5-codex", "gpt-5"]

        def signed_in(_provider: piauth.Provider) -> None:
            """Record the sign-in's place in the order."""
            calls.append("login")

        out = io.StringIO()
        with (
            mock.patch.object(piauth, "store_key") as store,
            mock.patch.object(piauth, "list_models", mock.AsyncMock(side_effect=listed)) as models,
            mock.patch.object(piauth, "opt_out_of_analytics") as opt_out,
            mock.patch.object(piauth, "login_on_terminal", side_effect=signed_in) as login,
            contextlib.redirect_stdout(out),
        ):
            found = setup.pi_step(CODEX, "")
        self.assertEqual(calls, ["login", "list"])
        login.assert_called_once_with(CODEX)
        models.assert_awaited_once_with("openai-codex")
        store.assert_not_called()
        opt_out.assert_called_once_with()
        self.assertIn("pi signs in with openai-codex", out.getvalue())
        self.assertEqual(
            found,
            setup.PiOutcome(
                provider="openai-codex", login="pi auth login openai-codex --no-browser"
            ),
        )

    def test_abandoned_login_is_a_failed_outcome(self) -> None:
        """A sign-in that ended with no credential is the report part.

        - pi exits 0 even when abandoned, so the empty model list says it
        - nothing is written
        """
        out = io.StringIO()
        with (
            mock.patch.object(piauth, "store_key") as store,
            mock.patch.object(piauth, "list_models", mock.AsyncMock(return_value=[])),
            mock.patch.object(piauth, "opt_out_of_analytics") as opt_out,
            mock.patch.object(piauth, "login_on_terminal") as login,
            contextlib.redirect_stdout(out),
        ):
            found = setup.pi_step(CODEX, "")
        login.assert_called_once_with(CODEX)
        store.assert_not_called()
        opt_out.assert_not_called()
        self.assertEqual(
            found,
            setup.PiOutcome(
                provider="openai-codex",
                login="pi auth login openai-codex --no-browser",
                error="pi lists no model for openai-codex — the credential may be missing or wrong",
            ),
        )

    def test_unexpected_error_propagates(self) -> None:
        """Only pi's refusals are report parts.

        - a broken pi environment raises on
        """
        with (
            mock.patch.object(piauth, "store_key"),
            mock.patch.object(
                piauth, "list_models", mock.AsyncMock(side_effect=FileNotFoundError("no pi"))
            ),
            self.assertRaisesRegex(FileNotFoundError, r"^no pi$"),
        ):
            setup.pi_step(ZAI, API_KEY)


class RunStepsTests(unittest.TestCase):
    """The steps run in order and make one Outcome.

    Tests script each step and record the order they ran in.

    - test_steps_run_in_order, domain, superuser, Google, pi — and the
      homepage comes from the screen
    - test_the_same_domain_runs_no_step, a domain equal to the one in
      effect is not set again
    - test_superuser_failure_propagates, a failing superuser verb is this
      repo's own bug: it propagates
    """

    def test_steps_run_in_order(self) -> None:
        """The domain, superuser, Google and pi steps run in that order.

        - the domain is set first, so the links carry the new origin
        - the superuser is created with the typed details; no one asks first
        - pi gets the key the screen collected
        """
        order: list[str] = []
        unset = googleoauth.GoogleStatus(configured=False)

        def step(name: str, result: object) -> Callable[..., object]:
            """Return a stand-in that records its name, then answers."""

            def run(*_args: object) -> object:
                order.append(name)
                return result

            return run

        changed = replace(WITH_GOOGLE, set_domain=True)
        with (
            mock.patch.object(
                setup_app, "apply_domain", side_effect=step("domain", None)
            ) as domain,
            mock.patch.object(
                superuserloginlink, "create_first", side_effect=step("superuser", JANE)
            ) as create,
            mock.patch.object(
                superuserloginlink, "login_link", side_effect=step("link", LINK)
            ) as mint,
            mock.patch.object(setup, "google_step", side_effect=step("google", unset)) as google,
            mock.patch.object(setup, "pi_step", side_effect=step("pi", ENABLED)) as pi,
        ):
            found = setup.run_steps(changed)
        self.assertEqual(order, ["domain", "superuser", "link", "google", "pi"])
        domain.assert_called_once_with("https://desmo.example")
        create.assert_called_once_with("Jane", "Doe", "jane@example.com")
        mint.assert_called_once_with("jane@example.com")
        google.assert_called_once_with(changed)
        pi.assert_called_once_with(ZAI, API_KEY)
        self.assertEqual(found, outcome(unset, ENABLED))

    def test_the_same_domain_runs_no_step(self) -> None:
        """A domain equal to the one in effect is not set again.

        - no service restarts; the steps start with the superuser
        """
        unset = googleoauth.GoogleStatus(configured=False)
        with (
            mock.patch.object(setup_app, "apply_domain") as domain,
            mock.patch.object(superuserloginlink, "create_first", return_value=JANE),
            mock.patch.object(superuserloginlink, "login_link", return_value=LINK),
            mock.patch.object(setup, "google_step", return_value=unset),
            mock.patch.object(setup, "pi_step", return_value=ENABLED),
        ):
            setup.run_steps(VALUES)
        domain.assert_not_called()

    def test_superuser_failure_propagates(self) -> None:
        """A failing superuser verb propagates: it is this repo's own bug.

        - Google and pi never start
        """
        refusal = "createuser failed (exit code 1): database is unreachable"
        with (
            mock.patch.object(
                superuserloginlink,
                "create_first",
                side_effect=superuserloginlink.SetupError(refusal),
            ),
            mock.patch.object(setup, "google_step") as google,
            mock.patch.object(setup, "pi_step") as pi,
            self.assertRaisesRegex(superuserloginlink.SetupError, r"^createuser failed"),
        ):
            setup.run_steps(VALUES)
        google.assert_not_called()
        pi.assert_not_called()


class ReportTests(unittest.TestCase):
    """Three parts under bold headings, coloured or plain.

    Tests build Outcomes and compare whole reports.

    - test_everything_set, the three parts, two spaces under each heading
    - test_google_left_empty_names_the_by_hand_line, the one command that
      adds Google later
    - test_pi_failure_names_the_login_command, pi's own command to run,
      with the reason under it
    - test_color_wraps_headings_and_what_the_operator_acts_on, the bold
      headings, the link, the by-hand line and the failure
    """

    SET = googleoauth.GoogleStatus(configured=True, redirect_uri=CALLBACK)
    UNSET = googleoauth.GoogleStatus(configured=False)

    def test_everything_set(self) -> None:
        """Everything set prints its three parts, a blank line apart.

        - the link line carries the superuser's full name
        - two spaces of indent under each heading
        - pi's part names the provider, not a model: pi picks its own
        """
        self.assertEqual(
            setup.format_report(outcome(self.SET, ENABLED)),
            f"Login stuff\n"
            f"  Login link for Jane Doe: {LINK}\n"
            "  Homepage link: https://desmo.example\n"
            "\n"
            "Google stuff\n"
            "  Google login is set\n"
            f"    Authorized redirect URL: {CALLBACK}\n"
            "\n"
            "Pi\n"
            "  Pi is enabled with zai. Just run `pi`",
        )

    def test_google_left_empty_names_the_by_hand_line(self) -> None:
        """Google left empty prints the one command that adds it later.

        - never this command again: the first run is the only run
        """
        repo = superuserloginlink.REPO_ROOT
        self.assertEqual(
            setup.google_unset_message(),
            "Google login not set. You may run "
            f"`cd {repo} && ./run djangomanage addoauth google <client_id> <secret>`",
        )
        self.assertEqual(
            setup.format_report(outcome(self.UNSET, ENABLED)).split("\n\n")[1],
            f"Google stuff\n  {setup.google_unset_message()}",
        )

    def test_pi_failure_names_the_login_command(self) -> None:
        """A failed pi prints pi's own command, with the reason under it.

        - the command carries the provider's flag
        """
        failed = setup.PiOutcome(
            provider="zai", login=LOGIN, error="pi's login stored no credential"
        )
        self.assertEqual(
            setup.format_report(outcome(self.SET, failed)).split("\n\n")[2],
            "Pi\n"
            "  Pi configuration failed. You should run `pi auth login zai --api-key`. Then run `pi`\n"
            "    pi's login stored no credential",
        )

    def test_color_wraps_headings_and_what_the_operator_acts_on(self) -> None:
        """With color on, the headings are bold and the acted-on lines are painted.

        - the homepage, "Google login is set" and the enabled line stay plain
        """
        green, yellow, red, bold = setup.GREEN, setup.YELLOW, setup.RED, setup.BOLD
        painted = setup.format_report(outcome(self.SET, ENABLED), color=True).split("\n")
        self.assertEqual(painted[0], f"{bold}Login stuff{setup.RESET}")
        self.assertEqual(painted[1], f"  {green}Login link for Jane Doe: {LINK}{setup.RESET}")
        self.assertEqual(painted[2], "  Homepage link: https://desmo.example")
        self.assertEqual(painted[4], f"{bold}Google stuff{setup.RESET}")
        self.assertEqual(painted[5], "  Google login is set")
        self.assertEqual(painted[6], f"    {green}Authorized redirect URL: {CALLBACK}{setup.RESET}")
        self.assertEqual(painted[8], f"{bold}Pi{setup.RESET}")
        self.assertEqual(painted[9], "  Pi is enabled with zai. Just run `pi`")
        failed = setup.PiOutcome(provider="zai", login=LOGIN, error="not_ready")
        painted = setup.format_report(outcome(self.UNSET, failed), color=True).split("\n")
        self.assertEqual(painted[5], f"  {yellow}{setup.google_unset_message()}{setup.RESET}")
        self.assertEqual(painted[7], f"{bold}Pi{setup.RESET}")
        self.assertEqual(
            painted[8],
            f"  {red}Pi configuration failed. You should run `{LOGIN}`. Then run `pi`{setup.RESET}",
        )
        self.assertEqual(painted[9], "    not_ready")
        self.assertNotIn("\033[", setup.format_report(outcome(self.UNSET, failed)))


class DropStaleInputTests(unittest.TestCase):
    """Keystrokes buffered before the screen starts are dropped.

    Tests stand in for stdin and for the tty flush.

    - test_a_terminal_is_flushed, tcflush(TCIFLUSH) on stdin's descriptor
    - test_a_pipe_is_left_alone, no flush when stdin is not a terminal
    """

    def test_a_terminal_is_flushed(self) -> None:
        """A terminal gets its pending input flushed.

        - the call is tcflush with TCIFLUSH on stdin's descriptor
        """
        stdin = mock.Mock()
        stdin.isatty.return_value = True
        stdin.fileno.return_value = 7
        with mock.patch("sys.stdin", stdin), mock.patch("termios.tcflush") as flush:
            setup.drop_stale_input()
        flush.assert_called_once_with(7, termios.TCIFLUSH)

    def test_a_pipe_is_left_alone(self) -> None:
        """A pipe is left alone.

        - no flush when stdin is not a terminal
        """
        stdin = mock.Mock()
        stdin.isatty.return_value = False
        with mock.patch("sys.stdin", stdin), mock.patch("termios.tcflush") as flush:
            setup.drop_stale_input()
        flush.assert_not_called()


class MainTests(unittest.TestCase):
    """One way through: Next, the steps, the report; a crash propagates.

    Tests stand in for the app and for the steps, then read what main() prints.

    - test_next_runs_the_steps_and_prints_the_report, exit 0
    - test_no_next_exits_1_without_a_report, a screen that ended without
      Next is a crash or a closed terminal
    - test_signals_through_the_steps, ctrl+c cannot end the run, and
      Textual's stop/continue handlers are gone
    - test_stale_input_drops_before_the_screen_and_before_the_steps, the
      second flush comes after the screen and before the steps
    - test_crash_propagates, a failing step is Python's own traceback
    """

    class FakeApp:
        """The app as main() sees it: run(), then values."""

        def __init__(
            self, values: setup_app.Values | None, after_run: Callable[[], None] | None = None
        ) -> None:
            self.values = values
            self.ran = False
            self.after_run = after_run

        def run(self) -> None:
            """Record that the screen ran, then tell after_run."""
            self.ran = True
            if self.after_run is not None:
                self.after_run()

    def run_main(
        self,
        app: FakeApp,
        steps: setup.Outcome
        | Exception
        | Callable[[setup_app.Values], setup.Outcome]
        | None = None,
    ) -> tuple[int, str, str]:
        """Call setup.main() on the fake app; return the exit code, stdout and stderr.

        ``steps`` is what run_steps answers, the error it raises, or its
        stand-in.
        """
        if isinstance(steps, Exception) or callable(steps):
            patched = mock.patch("ops.setup.run_steps", side_effect=steps)
        else:
            patched = mock.patch("ops.setup.run_steps", return_value=steps)
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch("ops.setup_app.SetupApp", return_value=app),
            mock.patch("ops.setup.drop_stale_input"),
            patched,
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = setup.main()
        self.assertTrue(app.ran)
        return code, out.getvalue(), err.getvalue()

    def test_next_runs_the_steps_and_prints_the_report(self) -> None:
        """A saved screen runs the steps, prints the report and exits 0.

        - the screen's values reach the steps
        """
        found = outcome(googleoauth.GoogleStatus(configured=False), ENABLED)
        code, out, err = self.run_main(self.FakeApp(VALUES), steps=found)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), setup.format_report(found))
        self.assertEqual(err, "")

    def test_no_next_exits_1_without_a_report(self) -> None:
        """A screen that ended without Next exits 1 and prints nothing.

        - no steps run: there is nothing to report
        """
        with mock.patch("ops.setup.run_steps") as steps:
            code, out, err = self.run_main(self.FakeApp(None))
        steps.assert_not_called()
        self.assertEqual((code, out, err), (1, "", ""))

    def test_signals_through_the_steps(self) -> None:
        """ctrl+c cannot end the run, and Textual's stop/continue handlers are gone.

        - SIGINT is ignored while the steps run (pi's own calls run off
          the terminal)
        - SIGTSTP and SIGCONT are back to their defaults
        """
        watched = (signal.SIGINT, signal.SIGTSTP, signal.SIGCONT)
        for number in watched:  # main() leaves these set: the process ends after the report
            self.addCleanup(signal.signal, number, signal.getsignal(number))
        seen: list[object] = []

        def steps(_values: setup_app.Values) -> setup.Outcome:
            """Record the signal dispositions while the steps run."""
            seen.extend(signal.getsignal(number) for number in watched)
            return outcome(googleoauth.GoogleStatus(configured=False), ENABLED)

        code, _out, _err = self.run_main(self.FakeApp(VALUES), steps=steps)
        self.assertEqual(seen, [signal.SIG_IGN, signal.SIG_DFL, signal.SIG_DFL])
        self.assertEqual(code, 0)

    def test_stale_input_drops_before_the_screen_and_before_the_steps(self) -> None:
        """Stale input is flushed before the screen and again before the steps.

        - the second flush comes after the screen and before run_steps,
          so nothing typed as the screen ended reaches pi's login
        """
        for number in (signal.SIGINT, signal.SIGTSTP, signal.SIGCONT):  # main() leaves these set
            self.addCleanup(signal.signal, number, signal.getsignal(number))
        events: list[str] = []
        app = self.FakeApp(VALUES, after_run=lambda: events.append("screen"))

        def steps(_values: setup_app.Values) -> setup.Outcome:
            """Record the steps' place in the order."""
            events.append("steps")
            return outcome(googleoauth.GoogleStatus(configured=False), ENABLED)

        with (
            mock.patch("ops.setup_app.SetupApp", return_value=app),
            mock.patch("ops.setup.drop_stale_input", side_effect=lambda: events.append("flush")),
            mock.patch("ops.setup.run_steps", side_effect=steps),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = setup.main()
        self.assertEqual(code, 0)
        self.assertEqual(events, ["flush", "screen", "flush", "steps"])

    def test_crash_propagates(self) -> None:
        """A failing step is Python's own traceback: it propagates.

        - nothing is caught, and the report never prints
        """
        refusal = "createuser failed (exit code 1): database is unreachable"
        with self.assertRaisesRegex(superuserloginlink.SetupError, r"^createuser failed"):
            self.run_main(self.FakeApp(VALUES), steps=superuserloginlink.SetupError(refusal))


class ValidateTests(unittest.TestCase):
    """Every refusal as (field, message), in screen order.

    Tests start from valid answers and change what a field holds.

    - test_valid_answers_pass, []
    - test_each_required_field_is_named, a blank name, email or provider
      names the field
    - test_bad_email_is_named
    - test_google_needs_both_fields, the empty one of a half pair is named
    - test_bad_google_pair_is_refused, the wrong one of the pair is named
    - test_a_typed_domain_is_a_name_or_the_local_origin
    - test_a_key_provider_needs_the_key, and a sign-in-only provider does
      not
    - test_every_refusal_comes_back_in_screen_order
    """

    def test_valid_answers_pass(self) -> None:
        """Valid answers are not refused.

        - a valid Google pair passes too
        """
        self.assertEqual(setup_app.validate(VALID, ZAI), [])
        self.assertEqual(
            setup_app.validate(replace(VALID, google_key=CLIENT_ID, google_secret=SECRET), ZAI),
            [],
        )

    def test_each_required_field_is_named(self) -> None:
        """A blank name, email or provider names the field.

        - the name and email hints are the command's own
        """
        for field, message in (
            ("first", NAME_HINT),
            ("last", NAME_HINT),
            ("email", EMAIL_HINT),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    setup_app.validate(replace(VALID, **{field: ""}), ZAI),
                    [(field, message)],
                )
        self.assertEqual(setup_app.validate(VALID, None), [("provider", setup_app.PROVIDER_PROMPT)])

    def test_bad_email_is_named(self) -> None:
        """An email without an at-sign, or one too long, gets the hint.

        - the limit is the RFC 5321 forward-path length
        """
        for email in ("jane.example.com", "jane@" + "x" * 260 + ".com"):
            with self.subTest(email=email[:12]):
                self.assertEqual(
                    setup_app.validate(replace(VALID, email=email), ZAI),
                    [("email", EMAIL_HINT)],
                )

    def test_google_needs_both_fields(self) -> None:
        """The empty one of a half pair is named.

        - a key alone names the secret; a secret alone names the key
        """
        self.assertEqual(
            setup_app.validate(replace(VALID, google_key=CLIENT_ID), ZAI),
            [("google_secret", setup_app.GOOGLE_HALF_HINT)],
        )
        self.assertEqual(
            setup_app.validate(replace(VALID, google_secret=SECRET), ZAI),
            [("google_key", setup_app.GOOGLE_HALF_HINT)],
        )

    def test_bad_google_pair_is_refused(self) -> None:
        """The wrong one of the pair is named.

        - a bad key names the key; a bad secret names the secret
        """
        self.assertEqual(
            setup_app.validate(replace(VALID, google_key="nope", google_secret=SECRET), ZAI),
            [("google_key", googleoauth.CLIENT_ID_HINT)],
        )
        self.assertEqual(
            setup_app.validate(replace(VALID, google_key=CLIENT_ID, google_secret="short"), ZAI),
            [("google_secret", googleoauth.SECRET_HINT)],
        )

    def test_a_typed_domain_is_a_name_or_the_local_origin(self) -> None:
        """`your.domain`, `sub.your.domain` and the local origin pass; empty and anything else get the hint.

        - the domain cannot be skipped
        """
        for typed in ("your.domain", "sub.your.domain", setup_app.LOCAL_DOMAIN):
            with self.subTest(typed=typed):
                self.assertEqual(setup_app.validate(replace(VALID, domain=typed), ZAI), [])
        for typed in (
            "",
            "localhost",
            "localhost:8443",
            "http://localhost:8443",
            "https://your.domain",
            "your.domain:8443",
            "your.domain/",
            "local host",
        ):
            with self.subTest(typed=typed):
                self.assertEqual(
                    setup_app.validate(replace(VALID, domain=typed), ZAI),
                    [("domain", setup_app.DOMAIN_HINT)],
                )

    def test_a_key_provider_needs_the_key(self) -> None:
        """A provider that takes a key is refused without one.

        - a sign-in-only provider needs no key
        """
        self.assertEqual(
            setup_app.validate(replace(VALID, api_key=""), ZAI),
            [("api_key", setup_app.API_KEY_HINT)],
        )
        self.assertEqual(setup_app.validate(replace(VALID, api_key=""), CODEX), [])

    def test_every_refusal_comes_back_in_screen_order(self) -> None:
        """Every refusal comes back at once, in screen order.

        - domain, then the names, then Google, then pi
        """
        answers = replace(
            VALID,
            domain="http://x",
            first="1",
            email="nope",
            google_key=CLIENT_ID,
            provider="",
            api_key="",
        )
        self.assertEqual(
            [field for field, _message in setup_app.validate(answers, None)],
            ["domain", "first", "email", "google_secret", "provider"],
        )


class TypedOriginTests(unittest.TestCase):
    """The https origin a typed domain means.

    Tests feed what the operator types.

    - test_the_local_origin_is_taken_literally, `https://localhost:8443`
      means itself
    - test_a_domain_or_a_subdomain_gets_https, `your.domain` and
      `sub.your.domain` mean `https://…`
    - test_spaces_around_are_dropped, padding changes nothing
    - test_anything_else_raises, `localhost`, ports, schemes and slashes
      raise the hint
    """

    LOCAL = "https://localhost:8443"

    def test_the_local_origin_is_taken_literally(self) -> None:
        """`https://localhost:8443` means itself.

        - so the report's links carry the port the forward listens on
        """
        self.assertEqual(setup_app.typed_origin(self.LOCAL), self.LOCAL)

    def test_a_domain_or_a_subdomain_gets_https(self) -> None:
        """`your.domain` means `https://your.domain`.

        - a subdomain is a domain name too
        """
        self.assertEqual(setup_app.typed_origin("your.domain"), "https://your.domain")
        self.assertEqual(setup_app.typed_origin("sub.your.domain"), "https://sub.your.domain")

    def test_spaces_around_are_dropped(self) -> None:
        """Padding spaces change nothing.

        - inside the text, a space is not a domain name
        """
        self.assertEqual(setup_app.typed_origin(f"  {self.LOCAL}  "), self.LOCAL)

    def test_anything_else_raises(self) -> None:
        """`localhost`, ports, schemes and slashes raise the hint.

        - `localhost` on its own would mean port 443, which nothing
          forwards: the local origin is typed in full instead
        - the screen refuses it first; this is the last line of defence
        """
        for typed in (
            "",
            "localhost",
            "localhost:8443",
            "http://localhost:8443",
            "https://your.domain",
            "your.domain:8443",
            "your.domain/",
            "your..domain",
            "-your.domain",
        ):
            with self.subTest(typed=typed), self.assertRaisesRegex(ValueError, "^a domain"):
                setup_app.typed_origin(typed)


class CurrentDomainTests(unittest.TestCase):
    """The origin read off the credentials env.

    Tests point CREDS_ENV at a temp file and read what comes back.

    - test_without_credentials_env, a machine without the file serves the
      local origin
    - test_first_origin_of_the_list, the first of a comma list
    - test_trailing_slash_is_dropped, the origin comes back bare
    - test_no_base_urls_line, a file without the line falls back to the
      local origin
    - test_parse_absent_line, text without the line parses to ''
    """

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.env = Path(temp.name) / ".env.vm"
        patch = mock.patch.object(setup_app, "CREDS_ENV", self.env)
        patch.start()
        self.addCleanup(patch.stop)

    def test_without_credentials_env(self) -> None:
        """A machine without the credentials env serves the local origin.

        - nothing is read
        """
        self.assertEqual(setup_app.current_domain(), "https://localhost:8443")

    def test_first_origin_of_the_list(self) -> None:
        """The first origin of a comma list is the site's.

        - quotes are dropped
        """
        self.env.write_text('SECRET_KEY="x"\nBASE_URLS="https://a.example, https://b.example"\n')
        self.assertEqual(setup_app.current_domain(), "https://a.example")

    def test_trailing_slash_is_dropped(self) -> None:
        """A trailing slash is dropped from the origin.

        - the same origin the site prints in links
        """
        self.env.write_text('BASE_URLS="https://a.example/"\n')
        self.assertEqual(setup_app.current_domain(), "https://a.example")

    def test_no_base_urls_line(self) -> None:
        """A file without a BASE_URLS line falls back to the local origin.

        - an empty value does too
        """
        self.env.write_text('SECRET_KEY="x"\n')
        self.assertEqual(setup_app.current_domain(), "https://localhost:8443")
        self.env.write_text('BASE_URLS=""\n')
        self.assertEqual(setup_app.current_domain(), "https://localhost:8443")

    def test_parse_absent_line(self) -> None:
        """Text without a BASE_URLS line parses to ''.

        - nothing is guessed
        """
        self.assertEqual(setup_app.parse_env_origin("DEBUG=False\n"), "")


class ApplyDomainTests(unittest.TestCase):
    """The provisioner's set-domain step through sudo.

    Tests stand in for the process and read what comes back, or what raises.

    - test_success_returns_nothing, exit 0 is enough: the report shows the
      origin
    - test_argv_carries_sudo_and_the_origin, sudo -n, bash, the
      provisioner, set-domain, the origin
    - test_refusal_raises_with_its_line, a non-zero exit is a
      DomainError carrying the last line
    - test_no_output_is_its_own_message, a silent failure says so
    """

    def apply(
        self, returncode: int, stdout: str = "", stderr: str = ""
    ) -> tuple[object, mock.Mock]:
        """Run apply_domain on a scripted process.

        Returns what it returned — or the refusal it raised — and the
        subprocess stand-in.
        """
        proc = mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)
        with mock.patch("subprocess.run", return_value=proc) as run:
            result: object = None
            try:
                setup_app.apply_domain("https://a.example")
            except setup_app.DomainError as error:
                result = str(error)
            return result, run

    def test_success_returns_nothing(self) -> None:
        """Exit 0 returns nothing.

        - the report prints the origin; the step's own line is not shown
        """
        self.assertIsNone(self.apply(0, stdout="domain set: https://a.example\n")[0])

    def test_argv_carries_sudo_and_the_origin(self) -> None:
        """The argv is sudo -n, bash, the provisioner, set-domain and the origin.

        - output is captured, so a refusal can show its own last line
        """
        _result, run = self.apply(0)
        run.assert_called_once_with(
            [
                "sudo",
                "-n",
                "bash",
                str(setup_app.REPO_ROOT / "deploy" / "inside-vm.sh"),
                "set-domain",
                "https://a.example",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_refusal_raises_with_its_line(self) -> None:
        """A non-zero exit is a DomainError carrying the last line.

        - the line is the provisioner's own refusal
        """
        refusal = "REFUSING: one https origin, https://host[:port] (got: 'x')."
        self.assertEqual(self.apply(1, stderr=refusal + "\n")[0], refusal)

    def test_no_output_is_its_own_message(self) -> None:
        """A silent failure says so.

        - never an empty message
        """
        self.assertEqual(self.apply(1)[0], "no output")


if __name__ == "__main__":
    unittest.main()
