"""superuserloginlink — ``desmosuperuserloginlink``: the first superuser's login link.

No TUI, no prompts. The command prints the oldest superuser's name, email
and one-time login link, and creates nothing: with no superuser on the
machine it says how to make one, and exits 1. Each djangomanage verb runs
as its own command and prints one JSON line; the shapes stay here.

``desmosetup`` creates the first superuser with :func:`create_first` and
mints the link with :func:`login_link`.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ops.command import Command

REPO_ROOT = Path(__file__).resolve().parent.parent
# A link printed at provision may be opened hours later: 24 hours.
LINK_MINUTES = "1440"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_MAX = 254  # the RFC 5321 forward-path limit
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'-]{0,49}$")

NAME_HINT = "names are letters, hyphens and apostrophes, starting with a letter"
EMAIL_HINT = "that does not look like an email address"
NO_SUPERUSER_MESSAGE = (
    "No superuser exists. Create one by hand, then run this again:\n"
    f"  cd {REPO_ROOT} && ./run djangomanage createuser <first> <last> <email> --superuser"
)


class SetupError(Exception):
    """A failure to show as is; the command exits 1."""


@dataclass(frozen=True, kw_only=True)
class Superuser:
    """One superuser as listusers lists them."""

    first: str
    last: str
    email: str

    @property
    def name(self) -> str:
        """The full name, or the email when the names are blank."""
        return f"{self.first} {self.last}".strip() or self.email


def _run(*argv: str) -> tuple[int, str, str]:
    """Run ``./run djangomanage <argv>``; return its rc, stdout, stderr."""
    proc = subprocess.run(
        [str(REPO_ROOT / "run"), "djangomanage", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _json_line(argv: list[str]) -> dict[str, object]:
    """Run one djangomanage verb and return the JSON line it printed."""
    return_code, stdout_text, stderr_text = _run(*argv)
    if return_code != 0:
        raise SetupError(_failure(argv[0], return_code, stdout_text + stderr_text))
    try:
        payload: dict[str, object] = json.loads(stdout_text)
    except ValueError as error:
        message = f"{argv[0]} printed no JSON line ({error})"
        raise SetupError(message) from error
    return payload


def _failure(command: str, exit_code: int, output: str) -> str:
    """One clear line for a failed command — its own last error line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = lines[-1][:200] if lines else "no output"
    return f"{command} failed (exit code {exit_code}): {detail}"


def first_superuser() -> Superuser | None:
    """Return the oldest superuser, or None when there is none.

    ``listusers --superusers`` lists superusers oldest first, so its
    first row is the one this command serves.
    """
    payload = _json_line(["listusers", "--superusers", "--page", "1"])
    rows = payload.get("users")
    if not isinstance(rows, list):
        message = "listusers printed no users list"
        raise SetupError(message)
    if not rows or not isinstance(rows[0], dict):
        return None
    first = rows[0]
    return Superuser(
        first=str(first.get("first", "")),
        last=str(first.get("last", "")),
        email=str(first.get("email", "")),
    )


def create_first(first: str, last: str, email: str) -> Superuser:
    """Create the first superuser through createuser and return them.

    An email that already exists created nobody, and is refused with the
    way forward. The three values are validated by the caller.
    """
    payload = _json_line(["createuser", first, last, email, "--superuser", "--if-absent"])
    if payload.get("created") is False:
        message = (
            f"{email} already exists, so no superuser was created. Run these two lines:\n"
            f"  cd {REPO_ROOT} && ./run djangomanage promotetosuperuser {email}\n"
            "  desmosuperuserloginlink\n"
            "The first makes the user a superuser; the second prints their login link."
        )
        raise SetupError(message)
    return Superuser(first=first, last=last, email=email)


def login_link(email: str) -> str:
    """Mint the superuser's one-time login link and return it."""
    payload = _json_line(["makeloginlink", email, "--minutes", LINK_MINUTES])
    url = payload.get("login_url")
    if not isinstance(url, str) or not url:
        message = "makeloginlink printed no login_url"
        raise SetupError(message)
    return url


def print_link(superuser: Superuser) -> None:
    """Print the superuser's name, email and one-time login link."""
    url = login_link(superuser.email)
    hours = int(LINK_MINUTES) // 60
    # `name` falls back to the email when both names are blank, so the
    # line never reads "Superuser:  (email)".
    print(f"Superuser: {superuser.name} ({superuser.email})")
    print(f"Login link — valid {hours} hours, single use:\n")
    print(f"  {url}\n")
    print("Open it in your browser to sign in.")


def main() -> int:
    """Print the first superuser's login link; exit 1 when there is none or a verb fails."""
    try:
        first = first_superuser()
        if first is None:
            print(NO_SUPERUSER_MESSAGE)
            return 1
        print_link(first)
    except SetupError as error:
        print(f"error: {error}")
        return 1
    return 0


class SuperuserloginlinkCommand(Command):
    """Print the first superuser's one-time login link; create nothing."""

    name = "desmosuperuserloginlink"

    @staticmethod
    def run(_args: object, _extra: list[str]) -> None:
        """Exit with main()'s code, so the caller sees a failure."""
        raise SystemExit(main())
