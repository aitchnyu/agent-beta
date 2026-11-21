"""flow — the setup engine as verbs over pi.

Each verb runs its own commands and returns a meaningful dataclass the
caller can branch on; the command/IO details (argv shapes, rc handling,
pi's exit-0-on-error habit, capture) stay here. screens.py only awaits
verbs and maps results to pop/flash/status.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

VERIFY_PROMPT = "Reply with just: ok"
MAX_ERROR_CHARS = 120
MIN_TABLE_COLUMNS = 2  # provider + model
# pi's provider-side error bodies look like: 401: {"code":"401", ...}
# (and exit 0) — the body shape must fail the verify even on rc-0.
ERROR_REPLY_RE = re.compile(r"^\d{3}:\s*\{")


@dataclass(frozen=True, kw_only=True)
class Outcome:
    """A command's verdict: branch on is_ok, show error when not."""

    is_ok: bool
    error: str = ""


@dataclass(frozen=True, kw_only=True)
class UserCreated:
    """The superuser exists; login_link is the minted one-time link."""

    login_link: str


async def _run(*argv: str) -> tuple[int, str, str]:
    """Run argv with stdout and stderr captured separately.

    The djangomanage commands emit one JSON line on stdout; keeping
    stderr apart means stderr noise can never corrupt that line.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout_bytes.decode(errors="replace"),
        stderr_bytes.decode(errors="replace"),
    )


async def _run_stderr(*argv: str) -> tuple[int, str]:
    """Run argv capturing only stderr — pi's login reports failures there."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr_bytes = await proc.communicate()
    return proc.returncode or 0, (stderr_bytes or b"").decode(errors="replace")


def _describe_failure(command: str, exit_code: int, output: str) -> str:
    """One clear line for a failed command — its own last error line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = lines[-1][:MAX_ERROR_CHARS] if lines else "no output"
    return f"{command} failed (exit code {exit_code}): {detail}"


def _pick_model(provider_id: str, models_table: str) -> str:
    """Extract THIS provider's first model from the list-models table."""
    for line in models_table.splitlines():
        columns = line.split()
        if len(columns) >= MIN_TABLE_COLUMNS and columns[0] == provider_id:
            return columns[1]
    return ""


async def get_model(provider_id: str) -> str | None:
    """Return the provider's first model id, or None when it has none."""
    return_code, stdout_text, stderr_text = await _run(
        "sudo", "-u", "debian", "-H", "pi", "--list-models"
    )
    if return_code != 0:
        raise AssertionError(
            _describe_failure("pi --list-models", return_code, stdout_text + stderr_text)
        )
    model = _pick_model(provider_id, stdout_text + stderr_text)
    return model or None


async def wait_for_success_response(provider_id: str, model_id: str) -> Outcome:
    """Exercise the credential with one cheap model call.

    pi exits 0 even for provider-side errors (an unknown model, a 401
    body), so the reply's body shape is the verdict too.
    """
    return_code, stdout_text, stderr_text = await _run(
        "sudo",
        "-u",
        "debian",
        "-H",
        "pi",
        "--print",
        VERIFY_PROMPT,
        "--provider",
        provider_id,
        "--model",
        model_id,
    )
    reply = (stdout_text + stderr_text).strip()
    if return_code == 0 and reply and not ERROR_REPLY_RE.match(reply):
        # ok carries the model's reply, not an error message
        return Outcome(is_ok=True, error=reply)
    return Outcome(
        is_ok=False,
        error=reply[:MAX_ERROR_CHARS] or f"no reply from pi (exit code {return_code})",
    )


async def verify_provider(provider_id: str) -> Outcome:
    """Verify the provider's stored credential with a real model call."""
    model = await get_model(provider_id)
    if model is None:
        return Outcome(is_ok=False, error=f"no models listed for provider {provider_id}")
    return await wait_for_success_response(provider_id, model)


async def run_pi_oauth_login(provider_id: str) -> Outcome:
    """Run pi's device-code login; the caller owns the terminal suspend."""
    return_code, stderr_text = await _run_stderr(
        "sudo", "-u", "debian", "-H", "pi", "auth", "login", provider_id, "--no-browser"
    )
    if return_code == 0:
        return Outcome(is_ok=True)
    return Outcome(
        is_ok=False,
        error=_describe_failure("pi auth login", return_code, stderr_text),
    )


async def create_superuser_with_link(first_name: str, last_name: str, email: str) -> UserCreated:
    """Create the first superuser and mint its one-time login link.

    createuser first — a link for a user that failed to create would be
    a lie. Any failure raises AssertionError carrying the command's own
    error line; the caller's crash guard presents it.
    """
    return_code, stdout_text, stderr_text = await _run(
        "./run",
        "djangomanage",
        "createuser",
        first_name,
        last_name,
        email,
        "--superuser",
        "--if-absent",
    )
    if return_code != 0:
        raise AssertionError(
            _describe_failure("createuser", return_code, stdout_text + stderr_text)
        )
    return_code, stdout_text, stderr_text = await _run(
        "./run", "djangomanage", "makeloginlink", email, "--minutes", "1440"
    )
    if return_code != 0:
        raise AssertionError(
            _describe_failure("makeloginlink", return_code, stdout_text + stderr_text)
        )
    try:
        login_url = json.loads(stdout_text)["login_url"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise AssertionError(f"makeloginlink printed no login link ({error})") from error
    return UserCreated(login_link=login_url)


async def store_google_oauth(client_id: str, client_secret: str) -> None:
    """Store the Google OAuth client credentials via addoauth.

    Any failure raises AssertionError carrying the command's own error
    line; the caller's crash guard presents it.
    """
    return_code, stdout_text, stderr_text = await _run(
        "./run", "djangomanage", "addoauth", "google", client_id, client_secret
    )
    if return_code != 0:
        raise AssertionError(_describe_failure("addoauth", return_code, stdout_text + stderr_text))
