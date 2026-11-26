"""setup — ``desmosetup``: the terminal steps behind the one screen, and the report.

ops/setup_app.py collects the values. Once the screen is gone this module
runs the steps in order — domain, superuser, Google, pi — and prints the
report.

One run only: nothing here asks what the machine holds, and no message
names the command again. Only pi can fail — a report part then says how
to continue.
"""

from __future__ import annotations

import asyncio
import signal
import sys
import termios
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ops import googleoauth, piauth, setup_app, superuserloginlink
from ops.command import Command
from ops.googleoauth import GoogleStatus

if TYPE_CHECKING:
    import argparse

    from ops.setup_app import Values
    from ops.superuserloginlink import Superuser

GREEN, YELLOW, RED, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


@dataclass(frozen=True, kw_only=True)
class PiOutcome:
    """How far pi got: the provider works, or why it stopped.

    ``login`` is pi's own login command for the provider, ready to print.
    pi picks its own model, so none is recorded.
    """

    provider: str
    login: str
    error: str = ""


@dataclass(frozen=True, kw_only=True)
class Outcome:
    """What the terminal steps achieved; the report prints it."""

    superuser: Superuser
    link: str
    homepage: str
    google: GoogleStatus
    pi: PiOutcome


def google_step(values: Values) -> GoogleStatus:
    """Store the Google credentials when both were given; left empty means not set."""
    if not values.google_key and not values.google_secret:
        return GoogleStatus(configured=False)
    return googleoauth.store(values.google_key, values.google_secret)


async def _check_provider(provider: piauth.Provider) -> None:
    """Fetch the provider's models: the whole test of its credential.

    pi lists a provider's models only once it holds a usable credential.
    An empty list raises ``PiError``. pi picks its own model, so nothing
    about models is saved — only the analytics opt-out is written.
    """
    models = await piauth.list_models(provider.id)
    if not models:
        message = f"pi lists no model for {provider.id} — the credential may be missing or wrong"
        raise piauth.PiError(message)
    piauth.opt_out_of_analytics()


def pi_step(provider: piauth.Provider, api_key: str) -> PiOutcome:
    """Save the screen's key for pi, then fetch the provider's models.

    A provider that takes a key gets the key typed on the screen, saved
    in pi's own file. A sign-in-only provider signed in on the screen
    already. A model list is the whole test: a refusal from pi is a
    failed outcome that says how to continue.
    """
    outcome = PiOutcome(provider=provider.id, login=" ".join(piauth.login_command(provider)))
    if provider.api_key:
        piauth.store_key(provider.id, api_key)
    try:
        asyncio.run(_check_provider(provider))
    except piauth.PiError as error:
        return replace(outcome, error=str(error))
    return outcome


def run_steps(values: Values) -> Outcome:
    """Run the terminal steps in order: domain, superuser, Google, pi."""
    if values.set_domain:
        setup_app.apply_domain(values.homepage)
    superuser = superuserloginlink.create_first(values.first, values.last, values.email)
    link = superuserloginlink.login_link(superuser.email)
    google = google_step(values)
    pi = pi_step(values.provider, values.api_key)
    return Outcome(
        superuser=superuser,
        link=link,
        homepage=values.homepage,
        google=google,
        pi=pi,
    )


def paint(text: str, colour: str) -> str:
    """Wrap the text in one ANSI code; the text itself when the code is empty."""
    return f"{colour}{text}{RESET}" if colour else text


def google_unset_message() -> str:
    """Return the way to add Google later, by hand: the one command that stores it."""
    repo = superuserloginlink.REPO_ROOT
    return (
        "Google login not set. You may run "
        f"`cd {repo} && ./run djangomanage addoauth google <client_id> <secret>`"
    )


def google_lines(google: GoogleStatus, green: str, yellow: str) -> list[str]:
    """Return Google's part: the redirect URL to register, or the by-hand line."""
    if google.configured:
        url = paint(f"Authorized redirect URL: {google.redirect_uri}", green)
        return ["Google login is set", f"  {url}"]
    return [paint(google_unset_message(), yellow)]


def pi_lines(pi: PiOutcome, red: str) -> list[str]:
    """Return pi's part: the provider works, or the command to run and the reason.

    pi picks its own model and shows it in its footer, so the report
    names the provider only.
    """
    if not pi.error:
        return [f"Pi is enabled with {pi.provider}. Just run `pi`"]
    failed = paint(f"Pi configuration failed. You should run `{pi.login}`. Then run `pi`", red)
    return [failed, f"  {pi.error}"]


def format_report(outcome: Outcome, *, color: bool = False) -> str:
    """Return the report: three parts under bold headings, a blank line between parts.

    Only colour what the operator acts on: the link, the by-hand line,
    the failure.
    """
    green, yellow, red, bold = (GREEN, YELLOW, RED, BOLD) if color else ("", "", "", "")
    link = paint(f"Login link for {outcome.superuser.name}: {outcome.link}", green)
    parts = (
        ("Login stuff", [link, f"Homepage link: {outcome.homepage}"]),
        ("Google stuff", google_lines(outcome.google, green, yellow)),
        ("Pi", pi_lines(outcome.pi, red)),
    )
    return "\n\n".join(
        "\n".join([paint(heading, bold), *(f"  {line}" for line in lines)])
        for heading, lines in parts
    )


def drop_stale_input() -> None:
    """Drop what the terminal buffered before the screen starts.

    Anything typed while the installer ran — the command line pasted a
    second time, impatient Enters — would land in the first field.
    Textual flushes only when it stops reading, never when it starts.
    """
    if sys.stdin.isatty():
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)


def main() -> int:
    """Run the screen, the terminal steps and the report; return the exit code.

    Only Next ends the screen. A crash on the way is a bug: Python's own
    traceback is the report, and the code is 1.
    """
    drop_stale_input()
    app = setup_app.SetupApp()
    app.run()
    if app.values is None:
        # No Next: the screen crashed (Textual printed it) or the terminal closed.
        return 1
    # Textual's driver keeps its SIGTSTP and SIGCONT handlers installed.
    # Past the screen they would wake a dead app, so both get their defaults.
    for signal_number in (signal.SIGTSTP, signal.SIGCONT):
        signal.signal(signal_number, signal.SIG_DFL)
    # From here to the report, ctrl+c must not end the run. pi's own
    # calls run off the terminal, so none of them is cancelled by it.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    outcome = run_steps(app.values)
    print(format_report(outcome, color=sys.stdout.isatty()))
    return 0


class SetupCommand(Command):
    """Set the site up after provision: domain, first superuser, Google login, pi's model."""

    name = "desmosetup"

    @staticmethod
    def run(_args: argparse.Namespace, _extra: list[str]) -> None:
        """Exit with main()'s code, so the installer sees a failure."""
        raise SystemExit(main())
