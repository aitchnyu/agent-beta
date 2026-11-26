"""googleoauth — Google sign-in for ``desmosetup``: validation and storage.

No prompts and no command of its own: the setup screen collects the client
key and secret, and this module stores them through ``addoauth``.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVIDER = "google"

CLIENT_ID_RE = re.compile(r"^\d+-[A-Za-z0-9]+\.apps\.googleusercontent\.com$")
MIN_SECRET_LEN = 20  # Google secrets are ~35 chars
CLIENT_ID_HINT = "a Google client key looks like 1234567890-abc123.apps.googleusercontent.com"
SECRET_HINT = "that Google secret looks wrong (Google secrets are about 35 characters, no spaces)"  # noqa: S105 — names a bad secret's shape; is not one


class SetupError(Exception):
    """A failure to show as is."""


@dataclass(frozen=True, kw_only=True)
class GoogleStatus:
    """What the machine holds for Google sign-in."""

    configured: bool
    redirect_uri: str = ""


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


def _failure(command: str, exit_code: int, output: str) -> str:
    """One clear line for a failed command — its own last error line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = lines[-1][:200] if lines else "no output"
    return f"{command} failed (exit code {exit_code}): {detail}"


def check_values(client_id: str, secret: str) -> str | None:
    """Return why the pair is refused, or None when it is valid."""
    if not CLIENT_ID_RE.match(client_id):
        return CLIENT_ID_HINT
    if len(secret) < MIN_SECRET_LEN or " " in secret:
        return SECRET_HINT
    return None


def store(client_id: str, secret: str) -> GoogleStatus:
    """Store the credentials through ``addoauth``; return the status it prints.

    One call: the verb's JSON line carries the redirect URI to register.
    """
    return_code, stdout_text, stderr_text = _run("addoauth", PROVIDER, client_id, secret)
    if return_code != 0:
        # The secret rides the argv: redact it before any output is shown.
        output = (stdout_text + stderr_text).replace(secret, "<secret>")
        raise SetupError(_failure("addoauth", return_code, output))
    payload: dict[str, object] = json.loads(stdout_text)
    return GoogleStatus(configured=True, redirect_uri=str(payload.get("redirect_uri") or ""))
