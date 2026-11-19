"""providers — the provider list and auth kinds, live from pi itself.

Provider enumeration rides pi's unknown-provider error (``pi auth login
<bogus>`` names every provider); the auth KIND (oauth vs api_key) comes
from pi's own provider registry via a node one-liner — never a stale
hardcoded list.
"""

from __future__ import annotations

import asyncio
import json
import re

_PROVIDERS_LINE = re.compile(r"^Providers: (.+)$", re.MULTILINE)

# Reads pi's provider registry at runtime: {id: "oauth"|"api_key"}.
#
# The node runtime is the ONLY live source of the auth KIND. Probed
# against pi 1.5.2: `--list-models` has no json/format flag and carries
# no auth column; `print-api-key --provider X` reports the same "No
# usable API key is configured" for both kinds; `auth login` refuses
# non-interactive use. A hardcoded list would go stale, so the registry
# wins over a stale constant.
_AUTH_KIND_SCRIPT = """
import * as pi from "/usr/lib/node_modules/@earendil-works/pi-coding-agent/dist/index.js";
const rt = await pi.ModelRuntime.create({ refreshOnCreate: false });
const out = {};
for (const id of rt.providerIds()) {
  const p = rt.getProvider(id);
  const auth = p?.auth ?? {};
  out[id] = auth.oauth ? "oauth" : auth.apiKey ? "api_key" : "unknown";
}
console.log(JSON.stringify(out));
"""


def parse_providers_line(text: str) -> list[dict[str, object]]:
    """Parse the 'Providers: a, b, c' line into rows ([] when absent)."""
    match = _PROVIDERS_LINE.search(text)
    if not match:
        return []
    return [
        {"id": name.strip(), "name": name.strip()}
        for name in match.group(1).split(",")
        if name.strip()
    ]


def parse_models_table(text: str) -> list[dict[str, object]]:
    """Fallback: unique first column of the ``--list-models`` table."""
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        columns = line.split()
        name = columns[0] if columns else ""
        if not name or name == "provider" or name in seen:
            continue
        seen.add(name)
        rows.append({"id": name, "name": name})
    return rows


async def query_auth_kinds() -> dict[str, str]:
    """Query pi's runtime for each provider's auth kind.

    Returns {provider_id: "oauth"|"api_key"|"unknown"}; raises when the
    registry cannot be read — the caller decides how loud that is
    (silently defaulting every provider to api_key would make the
    OAuth screens unreachable).
    """
    proc = await asyncio.create_subprocess_exec(
        "sudo",
        "-u",
        "debian",
        "-H",
        "node",
        "--input-type=module",
        "-e",
        _AUTH_KIND_SCRIPT,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _err = await proc.communicate()
    if proc.returncode != 0:
        message = f"auth-kind registry failed (rc={proc.returncode})"
        raise RuntimeError(message)
    text = out.decode(errors="replace").strip()
    if not text:
        message = "auth-kind registry returned no output"
        raise RuntimeError(message)
    parsed = dict(json.loads(text.splitlines()[-1]))
    return {str(pid): str(kind) for pid, kind in parsed.items()}


async def list_providers() -> list[dict[str, object]]:
    """Load the provider list, or raise when pi yields none.

    An empty list is never legitimate — the menu would show a powerless
    dropdown with no explanation, so both dead sources raise with the
    underlying output.
    """
    # The login command is expected to FAIL (unknown provider) — its
    # error message carries the list; the rc is irrelevant here.
    proc = await asyncio.create_subprocess_exec(
        "sudo",
        "-u",
        "debian",
        "-H",
        "pi",
        "auth",
        "login",
        "__list_providers__",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _err = await proc.communicate()
    first_output = out.decode(errors="replace").strip()
    providers = parse_providers_line(first_output)
    if providers:
        return providers
    # Fallback: the models table.
    proc = await asyncio.create_subprocess_exec(
        "sudo",
        "-u",
        "debian",
        "-H",
        "pi",
        "--list-models",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _err = await proc.communicate()
    table_output = out.decode(errors="replace").strip()
    providers = parse_models_table(table_output)
    if providers:
        return providers
    detail = (table_output or first_output)[:200] or "no output from pi"
    message = f"provider list unavailable: {detail}"
    raise RuntimeError(message)


def auth_kind_of(provider_id: str, auth_kinds: dict[str, str] | None = None) -> str:
    """Return the provider's auth kind: "oauth" or "api_key".

    ``auth_kinds`` is the live registry from query_auth_kinds(); when
    absent (or the id is missing from it), api_key is the safe default —
    the api-key screen's verify step catches OAuth-only providers.
    """
    if auth_kinds and auth_kinds.get(provider_id) == "oauth":
        return "oauth"
    return "api_key"
