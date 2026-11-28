"""piauth — the engine behind ``desmosetup``: pi's providers, credential and model list.

Each verb runs its own commands and returns plain data; the argv shapes,
pi's exit-0-on-error habit and pi's file formats stay here. ``setup.py``
awaits the verbs and maps results to the report, so everything in this
module is testable without Textual.

Nothing here catches an error: a failure raises. ``PiError`` carries a
refusal in pi's own words; anything else raises the raw exception. The
handler in ``setup.py`` decides what a failure means.
"""

from __future__ import annotations

import asyncio
import json
import os
import pwd
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

# The launcher on PATH: /usr/local/bin/pi on the VM (it delegates to
# ./run pi), npm's own binary in dev.
PI = "pi"
# Where pi runs — the repo root, as ./run pi would use.
REPO_ROOT = Path(__file__).resolve().parent.parent

MAX_ERROR_CHARS = 120

# Reads pi's provider registry at runtime: every provider, and whether
# it signs in with an account (oauth) or takes a pasted key.
#
# The node runtime is the ONLY live source. The CLI has no verb for it
# (probed on 1.5.2 and 1.6.1, whose CLIs are identical): `--list-models`
# carries no auth column; `print-api-key --provider X` reports the same
# "No usable API key is configured" for both kinds; `auth login` refuses
# non-interactive use. A hardcoded list would go stale, so the registry
# wins over a stale constant.
#
# pi's entry module: HARDCODED on purpose. deploy/inside-vm.sh installs pi
# with `npm -g` as root, which always lands in /usr/lib/node_modules. If
# that install prefix ever changes, change it here too. It is the library
# entry: the CLI binary is dist/bundle/cli.js.
PI_ENTRY = "/usr/lib/node_modules/@earendil-works/pi-coding-agent/dist/index.js"
_CATALOG_SCRIPT = f"""
import * as pi from "{PI_ENTRY}";
const rt = await pi.ModelRuntime.create({{ refreshOnCreate: false }});
const out = {{}};
for (const id of rt.providerIds()) {{
  const auth = rt.getProvider(id)?.auth ?? {{}};
  out[id] = {{ oauth: !!auth.oauth, api_key: !!auth.apiKey }};
}}
console.log(JSON.stringify(out));
"""


class PiError(Exception):
    """A refusal the caller can show as is — it never carries a secret."""


def _agent_dir() -> Path:
    """Return pi's per-user directory of the user running this process.

    The passwd entry, not ``$HOME``: ``su -l`` and sudo hand over shells
    where HOME may still be the caller's.
    """
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".pi" / "agent"


AGENT_DIR = _agent_dir()
AUTH_JSON = AGENT_DIR / "auth.json"
SETTINGS_JSON = AGENT_DIR / "settings.json"


async def _run(*argv: str) -> tuple[int, str, str]:
    """Run argv with stdout and stderr captured separately, off the terminal.

    Callers that parse an answer read stdout alone, so stderr noise never
    lands in a parsed line. The child gets a session of its own, so no
    signal from the terminal reaches it: ctrl+c stays pi's login prompt's
    alone (ops/setup.py runs that one on the terminal).
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=REPO_ROOT,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout_bytes.decode(errors="replace"),
        stderr_bytes.decode(errors="replace"),
    )


def _describe_failure(command: str, exit_code: int, output: str) -> str:
    """One clear line for a failed command — its own last error line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = lines[-1][:MAX_ERROR_CHARS] if lines else "no output"
    return f"{command} failed (exit code {exit_code}): {detail}"


# ── pi's own files ──────────────────────────────────────────────────────────


def read_json(path: Path) -> dict[str, object]:
    """Return pi's file as a dict; a missing file is {} (a fresh machine).

    A file that is there must parse. An unparsable one raises, because
    reading it as {} would wipe every credential on the next write.
    """
    if not path.exists():
        return {}  # fresh machine — pi creates the file on login
    data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        message = f"{path.name} is not a JSON object — fix it by hand; refusing to overwrite it"
        raise PiError(message)
    return data


def merge_into(path: Path, values: dict[str, object], *, indent: int | None = None) -> None:
    """Fold top-level keys into one of pi's JSON files, never clobbering the rest.

    pi has created the file by the time this runs (probed on 1.5.2 and
    1.6.1: even
    ``--list-models`` makes a private ``auth.json``). So the write goes in
    place, and the file keeps its mode.
    """
    data = read_json(path)
    data.update(values)
    path.write_text(json.dumps(data, indent=indent), encoding="utf-8")


def store_key(provider_id: str, key: str) -> None:
    """Save an API key for the provider in pi's own credential file.

    The shape is pi's — ``{type: "api_key", key}`` — what its own login
    writes. The file is private from its first byte: the directory 0700,
    the file 0600. The key never rides a command line.
    """
    AUTH_JSON.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    merge_into(AUTH_JSON, {provider_id: {"type": "api_key", "key": key}})
    AUTH_JSON.chmod(0o600)


def opt_out_of_analytics() -> None:
    """Record the analytics opt-out in pi's settings file, creating it.

    pi asks about analytics only when that file does not exist, so this
    write is what keeps its first-time dialog away.
    """
    merge_into(SETTINGS_JSON, {"enableAnalytics": False}, indent=2)


# ── providers and models ────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class Provider:
    """One provider as the picker offers it."""

    id: str
    oauth: bool = False  # can sign in with an account
    api_key: bool = False  # takes a pasted key


def parse_auth_support(text: str) -> dict[str, dict[str, bool]]:
    """Parse the registry's JSON into {provider id: {oauth, api_key}}."""
    raw: dict[str, dict[str, object]] = json.loads(text)
    return {
        provider_id: {"oauth": bool(flags.get("oauth")), "api_key": bool(flags.get("api_key"))}
        for provider_id, flags in raw.items()
    }


async def catalog() -> list[Provider]:
    """Return every provider pi knows, with how each can authenticate.

    One call on pi's registry gives both the ids and the capabilities.
    It failing raises, because defaulting the capabilities would offer
    the wrong way to authenticate.
    """
    return_code, stdout_text, stderr_text = await _run(
        "node", "--input-type=module", "-e", _CATALOG_SCRIPT
    )
    if return_code != 0 or not stdout_text.strip():
        raise PiError(_describe_failure("auth registry", return_code, stdout_text + stderr_text))
    support = parse_auth_support(stdout_text.strip())
    return [Provider(id=provider_id, **flags) for provider_id, flags in support.items()]


def login_command(provider: Provider) -> list[str]:
    """Return pi's own login command for the provider.

    A provider that takes an API key gets ``--api-key`` (pi then asks for
    it); a sign-in-only provider gets ``--no-browser``. The setup runs it
    on the terminal for a sign-in-only provider, and the report names it
    as the way to continue by hand. pi exits 0 even when it refuses or is
    abandoned, so a caller judges by :func:`list_models`, never by the rc.
    """
    flag = "--api-key" if provider.api_key else "--no-browser"
    return [PI, "auth", "login", provider.id, flag]


def _default_sigint() -> None:
    """Restore the login child's own SIGINT: pi must feel ctrl+c, not inherit an ignore."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def login_on_terminal(provider: Provider) -> None:
    """Run pi's own login on this terminal, for a provider that only signs in.

    While pi runs, this process ignores ctrl+c and pi must feel it: a
    child inherits an ignored SIGINT, so pi gets the default back before
    it starts. The caller owns the terminal — the screen is gone.
    """
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        subprocess.run(
            login_command(provider),
            cwd=REPO_ROOT,
            check=False,
            preexec_fn=_default_sigint,
        )
    finally:
        signal.signal(signal.SIGINT, previous)


def parse_model_table(text: str) -> dict[str, list[str]]:
    """Return pi's model table as {provider id: model ids in listed order}.

    Column positions come from the table's own header line (pi 1.5.2
    and 1.6.1 print ``provider model context max-out thinking images``). A column
    reordered or added upstream moves the parse with it. A table without
    a header parses to {} — nothing is guessed.
    """
    header: dict[str, int] = {}

    def cell(columns: list[str], name: str) -> str:
        index = header.get(name)
        return columns[index] if index is not None and index < len(columns) else ""

    table: dict[str, list[str]] = {}
    for line in text.splitlines():
        columns = line.split()
        if not header:
            if "provider" in columns and "model" in columns:
                header = {name: index for index, name in enumerate(columns)}
            continue
        provider, model = cell(columns, "provider"), cell(columns, "model")
        if provider and model:
            table.setdefault(provider, []).append(model)
    return table


async def list_models(provider_id: str) -> list[str]:
    """Return the provider's model ids from pi's table, in listed order.

    pi lists a provider's rows only once it holds a credential (probed on
    1.5.2 and 1.6.1: a machine with one zai key lists zai alone). So this verb runs
    AFTER authentication. Any failure raises PiError carrying the
    command's own error line. Only stdout is the table: stderr is noise.
    """
    return_code, stdout_text, stderr_text = await _run(PI, "--list-models")
    if return_code != 0:
        raise PiError(_describe_failure("pi --list-models", return_code, stdout_text + stderr_text))
    return parse_model_table(stdout_text).get(provider_id, [])
