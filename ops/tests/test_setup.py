"""Tests for ops/setup.py and ops/setup_app.py — the desmosetup command.

No Textual pilots (operator decision 2026-11-20). The terminal steps run
with every command scripted; the screen's one rule, validation, is read
directly, and so are the installer's flags.

Class inventory:

- GoogleStepTests, Google left empty is not set; a pair is stored
- PiStepTests, the key or the sign-in, the model list, the opt-out
- RunStepsTests, the steps run in order and make one Outcome
- ReportTests, three parts under bold headings, coloured or plain
- DropStaleInputTests, keystrokes buffered before the screen are
  dropped
- MainTests, one way through: Next, the steps, the report; a crash
  propagates
- ArgsTests, the installer's six flags, each checked for shape
- ValidateTests, every refusal as (field, message)
- CommandTests, the command refuses an unknown argument and hands the
  flags on
"""

from __future__ import annotations

import contextlib
import io
import signal
import termios
import unittest
from dataclasses import replace
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
FLAGS = {
    "--base-url": "https://desmo.example",
    "--first-name": "Jane",
    "--last-name": "Doe",
    "--email": "jane@example.com",
}
ARGS = setup.InstallArgs(
    homepage="https://desmo.example", first="Jane", last="Doe", email="jane@example.com"
)
WITH_GOOGLE = replace(ARGS, google_key=CLIENT_ID, google_secret=SECRET)
CHOICE = setup_app.PiChoice(provider=ZAI, api_key=API_KEY)
VALUES = setup.Values(
    homepage="https://desmo.example",
    first="Jane",
    last="Doe",
    email="jane@example.com",
    google_key="",
    google_secret="",
    provider=ZAI,
    api_key=API_KEY,
)
VALID = setup_app.Answers(provider="zai", api_key=API_KEY)


def values_of(args: setup.InstallArgs) -> setup.Values:
    """Return the Values the steps take for these arguments and the screen's choice."""
    return setup.Values(
        homepage=args.homepage,
        first=args.first,
        last=args.last,
        email=args.email,
        google_key=args.google_key,
        google_secret=args.google_secret,
        provider=CHOICE.provider,
        api_key=CHOICE.api_key,
    )


def argv(**changes: str) -> list[str]:
    """Return the flags as a command line, with some values changed."""
    return [item for flag, value in {**FLAGS, **changes}.items() for item in (flag, value)]


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
            found = setup.google_step(values_of(WITH_GOOGLE))
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

    - test_steps_run_in_order, superuser, link, Google, pi — with what
      the installer's flags and the screen handed on
    - test_superuser_failure_propagates, a failing superuser verb is this
      repo's own bug: it propagates
    """

    def test_steps_run_in_order(self) -> None:
        """The superuser, its link, Google and pi steps run in that order.

        - the superuser is created from the flags' details; no one asks first
        - pi gets the provider and the key the screen collected
        """
        order: list[str] = []
        unset = googleoauth.GoogleStatus(configured=False)

        def step(name: str, result: object) -> Callable[..., object]:
            """Return a stand-in that records its name, then answers."""

            def run(*_args: object) -> object:
                order.append(name)
                return result

            return run

        with (
            mock.patch.object(
                superuserloginlink, "create_first", side_effect=step("superuser", JANE)
            ) as create,
            mock.patch.object(
                superuserloginlink, "login_link", side_effect=step("link", LINK)
            ) as mint,
            mock.patch.object(setup, "google_step", side_effect=step("google", unset)) as google,
            mock.patch.object(setup, "pi_step", side_effect=step("pi", ENABLED)) as pi,
        ):
            found = setup.run_steps(values_of(WITH_GOOGLE))
        self.assertEqual(order, ["superuser", "link", "google", "pi"])
        create.assert_called_once_with("Jane", "Doe", "jane@example.com")
        mint.assert_called_once_with("jane@example.com")
        google.assert_called_once_with(values_of(WITH_GOOGLE))
        pi.assert_called_once_with(ZAI, API_KEY)
        self.assertEqual(found, outcome(unset, ENABLED))

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
            "Login\n"
            f"  Login link for Jane Doe: {LINK}\n"
            "  Homepage link: https://desmo.example\n"
            "\n"
            "Google\n"
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
            f"Google\n  {setup.google_unset_message()}",
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
        self.assertEqual(painted[0], f"{bold}Login{setup.RESET}")
        self.assertEqual(painted[1], f"  {green}Login link for Jane Doe: {LINK}{setup.RESET}")
        self.assertEqual(painted[2], "  Homepage link: https://desmo.example")
        self.assertEqual(painted[4], f"{bold}Google{setup.RESET}")
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

    Tests stand in for the app and for the steps, then read what run_first() prints.

    - test_next_runs_the_steps_and_prints_the_report, the arguments and
      the choice reach the steps as one Values; exit 0
    - test_no_next_exits_1_without_a_report, a screen that ended without
      Next is a crash or a closed terminal
    - test_signals_through_the_steps, ctrl+c cannot end the run, and
      Textual's stop/continue handlers are gone
    - test_stale_input_drops_before_the_screen_and_before_the_steps, the
      second flush comes after the screen and before the steps
    - test_crash_propagates, a failing step is Python's own traceback
    """

    class FakeApp:
        """The app as run_first() sees it: run(), then choice."""

        def __init__(
            self, choice: setup_app.PiChoice | None, after_run: Callable[[], None] | None = None
        ) -> None:
            self.choice = choice
            self.ran = False
            self.after_run = after_run

        def run(self) -> None:
            """Record that the screen ran, then tell after_run."""
            self.ran = True
            if self.after_run is not None:
                self.after_run()

    def run_first(
        self,
        app: FakeApp,
        args: setup.InstallArgs = ARGS,
        steps: setup.Outcome | Exception | Callable[[setup.Values], setup.Outcome] | None = None,
    ) -> tuple[int, str, str]:
        """Call setup.run_first() on the fake app; return the exit code, stdout and stderr.

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
            code = setup.run_first(args)
        self.assertTrue(app.ran)
        return code, out.getvalue(), err.getvalue()

    def test_next_runs_the_steps_and_prints_the_report(self) -> None:
        """The arguments and the screen's choice reach the steps as one Values; the report prints.

        - Google's flags ride along when they were given; exit 0
        """
        seen: list[setup.Values] = []

        def steps(values: setup.Values) -> setup.Outcome:
            """Record the values, then answer the outcome."""
            seen.append(values)
            return outcome(googleoauth.GoogleStatus(configured=False), ENABLED)

        found = outcome(googleoauth.GoogleStatus(configured=False), ENABLED)
        code, out, err = self.run_first(self.FakeApp(CHOICE), args=WITH_GOOGLE, steps=steps)
        self.assertEqual(code, 0)
        self.assertEqual(seen, [values_of(WITH_GOOGLE)])
        self.assertEqual(out.strip(), setup.format_report(found))
        self.assertEqual(err, "")
        self.run_first(self.FakeApp(CHOICE), steps=steps)
        self.assertEqual(seen[-1], VALUES)

    def test_no_next_exits_1_without_a_report(self) -> None:
        """A screen that ended without Next exits 1 and prints nothing.

        - no steps run: there is nothing to report
        """
        with mock.patch("ops.setup.run_steps") as steps:
            code, out, err = self.run_first(self.FakeApp(None))
        steps.assert_not_called()
        self.assertEqual((code, out, err), (1, "", ""))

    def test_signals_through_the_steps(self) -> None:
        """ctrl+c cannot end the run, and Textual's stop/continue handlers are gone.

        - SIGINT is ignored while the steps run (pi's model checks run off
          the terminal)
        - SIGTSTP and SIGCONT are back to their defaults
        """
        watched = (signal.SIGINT, signal.SIGTSTP, signal.SIGCONT)
        for number in watched:  # the steps leave these set: the process ends after the report
            self.addCleanup(signal.signal, number, signal.getsignal(number))
        seen: list[object] = []

        def steps(_values: setup.Values) -> setup.Outcome:
            """Record the signal dispositions while the steps run."""
            seen.extend(signal.getsignal(number) for number in watched)
            return outcome(googleoauth.GoogleStatus(configured=False), ENABLED)

        code, _out, _err = self.run_first(self.FakeApp(CHOICE), steps=steps)
        self.assertEqual(seen, [signal.SIG_IGN, signal.SIG_DFL, signal.SIG_DFL])
        self.assertEqual(code, 0)

    def test_stale_input_drops_before_the_screen_and_before_the_steps(self) -> None:
        """Stale input is flushed before the screen and again before the steps.

        - the second flush comes after the screen and before run_steps,
          so nothing typed as the screen ended reaches pi's login
        """
        for number in (signal.SIGINT, signal.SIGTSTP, signal.SIGCONT):  # the steps leave these set
            self.addCleanup(signal.signal, number, signal.getsignal(number))
        events: list[str] = []
        app = self.FakeApp(CHOICE, after_run=lambda: events.append("screen"))

        def steps(_values: setup.Values) -> setup.Outcome:
            """Record the steps' place in the order."""
            events.append("steps")
            return outcome(googleoauth.GoogleStatus(configured=False), ENABLED)

        with (
            mock.patch("ops.setup_app.SetupApp", return_value=app),
            mock.patch("ops.setup.drop_stale_input", side_effect=lambda: events.append("flush")),
            mock.patch("ops.setup.run_steps", side_effect=steps),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = setup.run_first(ARGS)
        self.assertEqual(code, 0)
        self.assertEqual(events, ["flush", "screen", "flush", "steps"])

    def test_crash_propagates(self) -> None:
        """A failing step is Python's own traceback: it propagates.

        - nothing is caught, and the report never prints
        """
        refusal = "createuser failed (exit code 1): database is unreachable"
        with self.assertRaisesRegex(superuserloginlink.SetupError, r"^createuser failed"):
            self.run_first(self.FakeApp(CHOICE), steps=superuserloginlink.SetupError(refusal))


class ArgsTests(unittest.TestCase):
    """The installer's six flags, each checked for shape.

    Tests parse argument lists and read what comes back, or what refuses.

    - test_the_flags_parse, the origin drops its trailing slash; Google
      comes whole
    - test_google_left_empty_parses, no Google flags is a pair of empty strings
    - test_a_bad_origin_is_refused
    - test_a_bad_name_is_refused, a space, a digit first, an underscore, 51 letters
    - test_a_bad_email_is_refused, no at-sign, or too long
    - test_a_half_google_pair_is_refused
    - test_a_bad_google_pair_is_refused
    - test_a_missing_flag_is_argparse_s_own_refusal, a usage text and code 2
    """

    def refusal(self, flags: list[str]) -> str:
        """Return the message parse_args() refuses ``flags`` with."""
        with self.assertRaises(SystemExit) as raised:
            setup.parse_args(flags)
        self.assertIsInstance(raised.exception.code, str)
        return str(raised.exception.code)

    def test_the_flags_parse(self) -> None:
        """Every flag comes through; the origin loses its spaces and its trailing slash.

        - Google's pair arrives whole
        """
        slashed = argv(**{"--base-url": "https://desmo.example /"})
        found = setup.parse_args([*slashed, "--google-key", CLIENT_ID, "--google-secret", SECRET])
        self.assertEqual(found, WITH_GOOGLE)
        self.assertEqual(setup.parse_args(argv()), ARGS)

    def test_google_left_empty_parses(self) -> None:
        """No Google flags is a pair of empty strings.

        - the steps read that as not set
        """
        self.assertEqual((ARGS.google_key, ARGS.google_secret), ("", ""))

    def test_a_bad_origin_is_refused(self) -> None:
        """An origin that is not https://host[:port] is refused with its text.

        - the hint names the shape
        """
        for origin in ("http://desmo.example", "desmo.example", "https://desmo.example/path"):
            with self.subTest(origin=origin):
                self.assertEqual(
                    self.refusal(argv(**{"--base-url": origin})),
                    f"--base-url must be {setup.ORIGIN_HINT} (got: '{origin}')",
                )

    def test_a_bad_name_is_refused(self) -> None:
        """A name of the wrong shape is refused for either flag.

        - the hint is the createuser command's own
        """
        for flag in ("--first-name", "--last-name"):
            for name in ("Jane Doe", "3Jane", "Jane_Doe", "J" * 51):
                with self.subTest(flag=flag, name=name):
                    self.assertEqual(
                        self.refusal(argv(**{flag: name})),
                        f"{flag}: {NAME_HINT} (got: '{name}')",
                    )

    def test_a_bad_email_is_refused(self) -> None:
        """An email without an at-sign, or one too long, gets the hint.

        - the limit is the RFC 5321 forward-path length
        """
        for email in ("jane.example.com", "jane@" + "x" * 260 + ".com"):
            with self.subTest(email=email[:12]):
                self.assertEqual(
                    self.refusal(argv(**{"--email": email})),
                    f"--email: {EMAIL_HINT} (got: '{email}')",
                )

    def test_a_half_google_pair_is_refused(self) -> None:
        """One Google flag of the pair is refused."""
        self.assertEqual(
            self.refusal([*argv(), "--google-key", CLIENT_ID]),
            setup.GOOGLE_PAIR_HINT,
        )
        self.assertEqual(
            self.refusal([*argv(), "--google-secret", SECRET]),
            setup.GOOGLE_PAIR_HINT,
        )

    def test_a_bad_google_pair_is_refused(self) -> None:
        """A pair of the wrong shape names the wrong flag with its hint."""
        bad_key = "desmo.example"
        self.assertEqual(
            self.refusal([*argv(), "--google-key", bad_key, "--google-secret", SECRET]),
            f"--google-key: {googleoauth.CLIENT_ID_HINT}",
        )
        self.assertEqual(
            self.refusal([*argv(), "--google-key", CLIENT_ID, "--google-secret", "short"]),
            f"--google-secret: {googleoauth.SECRET_HINT}",
        )

    def test_a_missing_flag_is_argparse_s_own_refusal(self) -> None:
        """A missing or an unknown flag is argparse's refusal: a usage text, code 2.

        - nothing of the first run starts
        """
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            setup.parse_args(["--base-url", "https://desmo.example"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--first-name", err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            setup.parse_args([*argv(), "--token", "abc123"])
        self.assertEqual(raised.exception.code, 2)


class ValidateTests(unittest.TestCase):
    """Every refusal as (field, message).

    Tests start from valid answers and change what a field holds.

    - test_valid_answers_pass, []; a sign-in-only provider needs no key
    - test_a_missing_provider_is_named
    - test_a_key_provider_needs_the_key, and whitespace is blank
    """

    def test_valid_answers_pass(self) -> None:
        """Valid answers are not refused.

        - a sign-in-only provider passes without a key
        """
        self.assertEqual(setup_app.validate(VALID, ZAI), [])
        self.assertEqual(
            setup_app.validate(setup_app.Answers(provider="openai-codex", api_key=""), CODEX),
            [],
        )

    def test_a_missing_provider_is_named(self) -> None:
        """No provider names the field with the dropdown's own prompt."""
        self.assertEqual(
            setup_app.validate(setup_app.Answers(provider="", api_key=""), None),
            [("provider", setup_app.PROVIDER_PROMPT)],
        )

    def test_a_key_provider_needs_the_key(self) -> None:
        """A key provider with a blank key names the key field.

        - whitespace is blank too
        """
        for key in ("", "   "):
            with self.subTest(key=key):
                self.assertEqual(
                    setup_app.validate(setup_app.Answers(provider="zai", api_key=key), ZAI),
                    [("api_key", setup_app.API_KEY_HINT)],
                )


class CommandTests(unittest.TestCase):
    """The command behind ``./run desmosetup``.

    Tests parse flags with the command's own parser and stand in for the first run.

    - test_the_flags_reach_the_first_run
    - test_an_unknown_argument_is_refused
    """

    def test_the_flags_reach_the_first_run(self) -> None:
        """The parsed flags reach the first run as InstallArgs."""
        args = setup.SetupCommand().build_parser().parse_args(argv())
        with (
            mock.patch("ops.setup.run_first", return_value=0) as first,
            self.assertRaises(SystemExit) as raised,
        ):
            setup.SetupCommand.run(args, [])
        first.assert_called_once_with(ARGS)
        self.assertEqual(raised.exception.code, 0)

    def test_an_unknown_argument_is_refused(self) -> None:
        """A leftover argument is a usage error naming it."""
        args = setup.SetupCommand().build_parser().parse_args(argv())
        with self.assertRaisesRegex(SystemExit, r"^unknown argument: --token$"):
            setup.SetupCommand.run(args, ["--token", "abc123"])


if __name__ == "__main__":
    unittest.main()
