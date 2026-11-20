r"""gate — checkframework2's in-container acceptance battery.

TESTING ONLY — no operator surface lives here (that's localvm's
runasdesmo, host-side). Runs INSIDE the container as ROOT, after the
host (run's checkframework2) provisioned the instance fresh:

    incus exec volatile-test-machine -- \\
      sudo bash -c 'cd /srv/desmo/main && uv run --no-sync python -m ops.checkframework2'

Called by exactly one thing; the host checks only the exit code, output
streams to the operator. One linear body, read top to bottom: refuse
prod first, overlay the Books test app, smoke the LIVE stack over HTTPS
on loopback (caddy TLS, granian, postgres, login links), three setup
phases then eleven asserts — the first failed assert aborts with
``FAILED:``; an unexpected error tracebacks (nonzero either way).
"""

from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import time
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

from ops import shell
from ops.scratch import step_banner

GATE_BASE = "https://localhost"
MAIN_DIR = Path("/srv/desmo/main")
SCRATCH_DIR = Path("/srv/desmo/scratch")
CREDS_ENV = Path("/etc/credentials/desmo/.env.vm")
OP_USER = "debian"  # provisioning (inside-vm.sh) names the same user

# curl -k equivalent: the loopback site's internal CA is the supported mode.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
# In-memory cookie store: the smoke session (Set-Cookie) + the csrf
# rotation, exactly what the old curl -b/-c jar carried.
_COOKIES: dict[str, str] = {}


def die(what: str) -> NoReturn:
    """Fail the gate: a FAILED line, then exit 1."""
    shell.die(f"FAILED: {what}")


# ── the sudo shims (same env/cwd dance localvm's runasdesmo owns) ────────


def _as_desmo(*cmd: str) -> None:
    """Run cmd as the desmo user: creds env sourced, repo cwd, then exec."""
    _shim(
        "sudo",
        "-u",
        "desmo",
        "-H",
        "bash",
        "-c",
        'set -a; . /etc/credentials/desmo/.env.vm; set +a; cd /srv/desmo/main || exit 1; exec "$@"',
        "gate",
        *cmd,
    )


def _capture_desmo(*cmd: str) -> str:
    return _capture(
        "sudo",
        "-u",
        "desmo",
        "-H",
        "bash",
        "-c",
        'set -a; . /etc/credentials/desmo/.env.vm; set +a; cd /srv/desmo/main || exit 1; exec "$@"',
        "gate",
        *cmd,
    )


def _as_default(script: str) -> None:
    """Run a bash script as the default cloud user.

    Creds env sourced, repo cwd, uv on PATH. The agent assert bodies
    (browsers, playwright probe, the scratch lifecycle) ride this shim.
    """
    _shim(
        "sudo",
        "-u",
        OP_USER,
        "-H",
        "bash",
        "-c",
        "set -a; . /etc/credentials/desmo/.env.vm; set +a; "
        "cd /srv/desmo/main || exit 1; export PATH=/usr/local/bin:$PATH; " + script,
    )


def _default_run(verb: str) -> None:
    _as_default(f"exec ./run {verb}")


def _capture_default(script: str) -> str:
    return _capture(
        "sudo",
        "-u",
        OP_USER,
        "-H",
        "bash",
        "-c",
        "set -a; . /etc/credentials/desmo/.env.vm; set +a; "
        "cd /srv/desmo/main || exit 1; export PATH=/usr/local/bin:$PATH; " + script,
    )


def _shim(*cmd: str) -> None:
    shell.run(*cmd)


def _capture(*cmd: str) -> str:
    process = subprocess.run(
        list(cmd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if process.returncode != 0:
        raise SystemExit(process.returncode)
    return process.stdout


# ── the smoke HTTP client (http.client: no redirects, raw paths) ────────


def _request(
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    with_cookies: bool = True,
) -> tuple[int, bytes]:
    conn = http.client.HTTPSConnection("localhost", context=_SSL_CTX, timeout=30)
    request_headers = dict(headers or {})
    # The smoke session (assert 1's redemption) rides every request that
    # asks for it; with_cookies=False is the anonymous mode.
    if with_cookies and _COOKIES:
        request_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in _COOKIES.items())
    conn.request(method, path, body=body, headers=request_headers)
    response = conn.getresponse()
    data = response.read()
    for header in response.msg.get_all("Set-Cookie") or []:
        pair = header.split(";", 1)[0]
        if "=" in pair:
            name, value = pair.split("=", 1)
            _COOKIES[name.strip()] = value.strip()
    status = response.status
    conn.close()
    return status, data


def _assert_eq(got: object, alts: str, what: str) -> None:
    """Assert got equals one of the alts (space-separated alternatives)."""
    if str(got) in alts.split():
        return
    die(f"{what} (expected {alts}, got {got})")


def _expect_refusal(*cmd: str) -> None:
    process = subprocess.run(
        list(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    )
    if process.returncode == 0:
        die(f"expected refusal, command succeeded: {' '.join(cmd)}")


def _expect_default_refusal(script: str) -> None:
    """Expect a default-user-shim script to refuse (nonzero exit)."""
    process = subprocess.run(
        [
            "sudo",
            "-u",
            OP_USER,
            "-H",
            "bash",
            "-c",
            "set -a; . /etc/credentials/desmo/.env.vm; set +a; "
            "cd /srv/desmo/main || exit 1; export PATH=/usr/local/bin:$PATH; " + script,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if process.returncode == 0:
        die(f"expected refusal, command succeeded: {script}")


# ── step 0: never on a prod VM ────────────────────────────────────────────


def refuse_if_prod() -> None:
    """Default-deny on the installed BASE_URLS — the role truth.

    The battery destroys what it touches (testapp overlay, smoke
    superuser, live-DB restore); a public origin means prod data, so any
    non-loopback origin, a missing BASE_URLS, or an unparseable line all
    refuse — before anything mutates.
    """
    match = re.search(r'^BASE_URLS="([^"]*)"$', CREDS_ENV.read_text(), re.MULTILINE)
    if not match:
        die(
            "BASE_URLS missing or unparseable in "
            "/etc/credentials/desmo/.env.vm — the gate only runs on loopback test VMs."
        )
    for origin in re.split(r"[,\s]+", match.group(1)):
        if not origin:
            continue
        host = re.sub(r"^https://", "", origin).split(":")[0].split("/")[0]
        if host not in ("localhost", "127.0.0.1"):
            die(
                f"BASE_URLS origin '{origin}' is not loopback — this looks like a prod VM; "
                "the gate is a destructive test battery (testapp overlay, smoke superuser, "
                "live-DB restore)."
            )


# ── the gate: one linear body ────────────────────────────────────────────


def _step_refuse_unless_safe() -> None:
    """Step 0 + the real-users safety: refuse before anything mutates."""
    refuse_if_prod()

    # The battery destroys DB state — never real users: refuse unless
    # every user is *@gate.test or the smoke user (any other user is real
    # data, no override).
    users = _capture_desmo(
        "./run",
        "djangomanage",
        "listusers",
        "--exclude",
        r"^(framework@example\.com|.*@gate\.test)$",
    )
    real_users = [line for line in users.splitlines() if "@" in line]
    if real_users:
        print("FAILED: real users present in desmo_db — the gate would erase them:")
        print("\n".join(real_users))
        raise SystemExit(1)


def _step_overlay_testapp() -> None:
    """Replace ourapp/ wholesale with the Books test app (setup 1/3).

    Same semantics as the host tiers' overlay (rsync --delete): the
    seeded ourapp/ (code AND tests) goes, the testapp lands in its place,
    nothing of the template's app survives. The VM gate tests the live
    stack against the Books app; the template's own tests run host-side
    in checkframework1.
    """
    print("\n=== Setup 1/3: deploy the Books test app over the VM's ourapp/ ===")
    shutil.rmtree(MAIN_DIR / "ourapp", ignore_errors=True)  # rm -rf semantics: idempotent
    shutil.copytree(
        MAIN_DIR / "djangoapp" / "tests" / "testapp" / "ourapp",
        MAIN_DIR / "ourapp",
        symlinks=True,  # cp -a semantics: copy the LINK, not the target
    )
    # desmo-owned and group-writable: the default cloud user (group
    # desmo) edits it through the scratch cycle. ADDITIVE g+w (mode |
    # S_IWGRP) — the old find -exec chmod g+w kept exec bits.
    for root, _dirs, files in os.walk(MAIN_DIR / "ourapp"):
        root_path = Path(root)
        shutil.chown(root_path, "desmo", "desmo")
        root_path.chmod(root_path.stat().st_mode | stat.S_IWGRP)
        for name in files:
            path = root_path / name
            shutil.chown(path, "desmo", "desmo")
            path.chmod(path.stat().st_mode | stat.S_IWGRP)


def _step_smoke_superuser() -> None:
    """Migrate, create the smoke superuser, restart granian (setup 2/3)."""
    print("\n=== Setup 2/3: migrate, create the smoke superuser ===")
    _as_desmo("uv", "run", "--no-sync", "python", "manage.py", "migrate", "--noinput")
    # Idempotent: the battery leaves its users in place, so a rerun starts
    # from a DB that may already hold the smoke user; --if-absent skips then.
    _as_desmo(
        "uv",
        "run",
        "--no-sync",
        "python",
        "manage.py",
        "createuser",
        "Framework",
        "Smoke",
        "framework@example.com",
        "--superuser",
        "--if-absent",
    )
    _systemctl("restart", "desmo_granian.service")


def _step_login_link() -> str:
    """Issue the one-time superuser login link (setup 3/3).

    The session redeemed here carries every later authed assert (it
    survives the deployscratch restart — sessions are DB-backed). The
    printed link's origin is BASE_URLS[0] (the proxy-device origin) —
    in-VM asserts want the :443 base, so only the PATH is lifted.
    """
    print("\n=== Setup 3/3: issue the one-time superuser login link ===")
    link_output = _capture_desmo(
        "uv", "run", "--no-sync", "python", "manage.py", "makeloginlink", "framework@example.com"
    )
    login_url: str = json.loads(link_output)["login_url"]
    return urlparse(login_url).path


def _asserts_session(login_path: str) -> None:
    """Assert the link redeems and the session is real (asserts 1-4)."""
    print("\n=== Assert 1: login link redeems ===")
    status, _body = _request(login_path)
    _assert_eq(status, "302 200", "login link redemption status")

    print("\n=== Assert 2: anonymous /users/list → 404 ===")
    status, _body = _request("/users/list", with_cookies=False)
    _assert_eq(status, "404", "anonymous /users/list")

    print("\n=== Assert 3: authed /users/list → 200 (session proof) ===")
    status, _body = _request("/users/list")
    _assert_eq(status, "200", "authed /users/list (session proof)")

    print("\n=== Assert 4: home shows the smoke user ===")
    _status, body = _request("/")
    if b"Framework Smoke" not in body:
        die("home page does not show the smoke user")


def gate() -> None:
    _step_refuse_unless_safe()
    _step_overlay_testapp()
    step_banner("setup testapp")
    _step_smoke_superuser()
    step_banner("setup smoke user")
    login_path = _step_login_link()
    step_banner("setup login link")
    _asserts_session(login_path)
    step_banner("asserts 1-4 session")
    _asserts_agent()
    step_banner("asserts 5-6 agent")
    _asserts_scratch_cycle()
    step_banner("asserts 7-9 scratch cycle")
    _asserts_media()
    step_banner("assert 10 media")
    _asserts_backup()
    step_banner("assert 11 backup")
    print("\ncheckframework2 green.")


def _asserts_agent() -> None:
    """Assert desmo pi preconditions + the playwright probe (asserts 5-6)."""
    print("\n=== Assert 5: default user can run desmo pi ===")
    _capture_default(
        "command -v desmo >/dev/null && command -v pi >/dev/null && "
        '. /etc/credentials/desmo/.env.vm 2>/dev/null && test -n "${SECRET_KEY:-}"'
    )

    print("\n=== Assert 6: playwright browsers launch as the default user ===")
    # Postcondition 1: the shared browser cache is nonempty and readable
    browsers = _capture_default('exec ls "$PLAYWRIGHT_BROWSERS_PATH" | sed -n "1,3p"')
    if not browsers.strip():
        die("shared browser cache empty or unreadable as the default user")
    # Postcondition 2: headless chromium actually LAUNCHES as the default
    # user (exit 0; the OK line is operator output, the exit code is the assert)
    # ruff-format: off
    probe = (
        "from playwright.sync_api import sync_playwright\n"
        "p = sync_playwright().start()\n"
        "b = p.chromium.launch(headless=True)\n"
        'print("agent headless chromium launch OK")\n'
        "b.close(); p.stop()"
    )
    # ruff-format: on
    _capture_default(f"exec timeout 10 uv run --no-sync python -c '{probe}'")


def _asserts_scratch_cycle() -> None:
    """Run the agent's whole scratch lifecycle on the live stack (asserts 7-9)."""
    print("\n=== Assert 7: agent createscratch ===")
    # Precondition: the refusal postcondition below needs scratch ABSENT —
    # establish it regardless of any earlier state (the battery must be
    # order-independent: it may run right after a cleanscratch or on a
    # scratch a previous session left behind).
    _agent_scratch_clean()
    # Postcondition 1: deployscratch without scratch/ refuses
    _expect_default_refusal("exec ./run deployscratch")
    # Postcondition 2: exit 0 means scratch/ exists and scratch-baseline resolves
    _agent_scratch_create()
    # Postcondition 3: scratch's OWN ./run refuses (rsync onto itself otherwise)
    _expect_refusal(
        "sudo",
        "-u",
        OP_USER,
        "-H",
        "bash",
        "-c",
        "cd /srv/desmo/scratch && ./run deployscratch",
    )

    print("\n=== Assert 8: agent deployscratch (marker live on /) ===")
    _agent_scratch_edit()
    _default_run("deployscratch")
    # granian active after the deploy's restart. is-active exits 3 when
    # inactive — the VALUE is the assert (the FAILED line names the state),
    # so the exit code is tolerated here.
    _return_code, active = shell.capture("systemctl", "is-active", "desmo_granian.service")
    _assert_eq(active.strip(), "active", "desmo_granian.service after deployscratch")
    # The marker is in the served page JSON (retries absorb the restart
    # race) — deploy AND restart proven, not just rsync.
    body = _retry_probe("/")
    if b"scratch-deploy-live" not in body:
        die("deploy marker missing from the served page")

    print("\n=== Assert 9: agent cleanscratch ===")
    _agent_scratch_clean()


def _asserts_media() -> None:
    print("\n=== Assert 10: media upload + serve_file ===")
    _media_upload_roundtrip()


def _asserts_backup() -> None:
    print("\n=== Assert 11: pgbackrest (mark, backup, restore live, verify) ===")
    print("    NOTE: this assert's restore REPLACES desmo_db — the battery")
    print("    leaves the DB at that restored state.")
    _backup_roundtrip()


def _systemctl(*args: str) -> None:
    _shim("systemctl", *args)


def _systemctl_show(unit: str) -> str:
    process = subprocess.run(
        ["systemctl", "show", "-p", "Result", "--value", unit],
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        raise SystemExit(process.returncode)
    return process.stdout.strip()


def _retry_probe(path: str = "/") -> bytes:
    """GET with the X-Scratch-Probe header, retrying through the restart race.

    curl's --retry envelope: connection failures AND transient 5xx (caddy
    answers 502 while granian restarts — a complete response, not an error).
    """
    last_error: Exception | None = None
    for _attempt in range(10):
        try:
            status, body = _request(path, headers={"X-Scratch-Probe": "1"})
        except (OSError, http.client.HTTPException) as error:
            last_error = error
            time.sleep(2)
        else:
            if status >= http.HTTPStatus.INTERNAL_SERVER_ERROR:
                last_error = RuntimeError(f"HTTP {status}")
                time.sleep(2)
            else:
                return body
    die(f"probe never recovered after deployscratch restart: {last_error}")


# ── the agent-* wrappers (assert bodies as the default cloud user) ──────


def _agent_scratch_clean() -> None:
    _default_run("cleanscratch")
    if SCRATCH_DIR.exists():
        die("cleanscratch left scratch/ behind")
    print("agent cleanscratch OK")


def _agent_scratch_create() -> None:
    _default_run("createscratch")
    if not SCRATCH_DIR.is_dir():
        die("createscratch did not create scratch/")
    # The frozen baseline ref resolves (default-user-owned git); the SHA
    # itself is noise — capture it, assert the rc.
    code, _sha = shell.capture(
        "sudo",
        "-u",
        OP_USER,
        "-H",
        "git",
        "-C",
        str(SCRATCH_DIR),
        "rev-parse",
        "--verify",
        "scratch-baseline",
    )
    if code != 0:
        raise SystemExit(code)
    print("agent createscratch OK")


def _agent_scratch_edit() -> None:
    """Insert the deployscratch liveness marker into scratch's home view.

    Header-gated (exact-props tests never see it), inside ourapp/
    (framework watch quiet, battery-clean), idempotent (rerun no-ops),
    FIRST return only. Self-contained against home_page's literal
    ``return InertiaResponse(...)`` — no assumption about a props
    variable in scope.
    """
    home = SCRATCH_DIR / "ourapp" / "views" / "home.py"
    text = home.read_text()
    if "scratch_marker" in text:
        print("agent scratch edit OK")
        return
    marker = (
        '    if request.headers.get("X-Scratch-Probe"):\n'
        "        return InertiaResponse(\n"
        '            request, "Home", {"props": {"scratch_marker": "scratch-deploy-live"}}\n'
        "        )\n"
        "    return InertiaResponse"
    )
    patched, count = re.subn(
        r"^    return InertiaResponse", marker, text, count=1, flags=re.MULTILINE
    )
    if count != 1:
        die("could not insert the scratch marker into the home view")
    home.write_text(patched)
    print("agent scratch edit OK")


# ── assert 10: the media round-trip ──────────────────────────────────────


def _media_upload_roundtrip() -> None:
    payload = b"gate-media-bytes"

    # The upload is an unsafe method against a make_ninja_api API
    # (csrf_guard on), over HTTPS — so send what the browser sends: the
    # csrftoken cookie (rotated in at login; the page GET re-bootstraps a
    # jar that predates the rotation) + the matching X-CSRFToken header +
    # the same-origin Origin (Django's strict referer check on secure
    # requests).
    _status, _body = _request("/")
    csrf_token = _COOKIES.get("csrftoken", "")
    if not csrf_token:
        die(
            f"no csrftoken cookie in the smoke jar — the upload needs the CSRF trio. "
            f"cookies: {sorted(_COOKIES)}"
        )

    boundary = "----gateboundary"
    multipart = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="gate-upload.bin"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + payload
        + f"\r\n--{boundary}--\r\n".encode()
    )
    status, body = _request(
        "/media/upload",
        method="POST",
        headers={
            "X-CSRFToken": csrf_token,
            "Origin": GATE_BASE,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        body=multipart,
    )
    if status != http.HTTPStatus.OK:
        die(f"media upload failed (status {status}, body {body[:200]!r})")
    media_name = json.loads(body)["name"]

    # The serve URL streams the exact bytes back — an unintercepted accel
    # response would be an empty body and fail the comparison.
    _status, served = _request(f"/media/{media_name}")
    if served != payload:
        die(f"media round-trip mismatch: sent {payload!r}, got {served!r}")

    # Unknown and traversal names are 404s (never a 500, never bytes from
    # outside MEDIA_ROOT).
    status, _body = _request("/media/not-there.bin")
    _assert_eq(status, "404", "unknown media name")
    status, _body = _request("/media/..%2f..%2f..%2fetc%2fpasswd")
    _assert_eq(status, "404", "media traversal attempt")


# ── assert 11: the backup round-trip ─────────────────────────────────────


def _backup_roundtrip() -> None:
    marker_backed_up = _capture_desmo(
        "uv", "run", "--no-sync", "manage.py", "backupmarker", "set"
    ).strip()
    _shim(str(MAIN_DIR / "run"), "backupdb")
    _systemctl("start", "desmo_pgbackrest.service")
    # The newest set's label — diff labels are COMPOUND (fullF_diffD): the
    # optional group keeps the whole label together; a bare [FD] fragment
    # capture would fail restoredb's exact "backup: <set>" existence match.
    info = _capture("sudo", "-u", "postgres", "pgbackrest", "--stanza=desmo", "info")
    labels = re.findall(r"\d{8}-\d{6}F(?:_\d{8}-\d{6}D)?", info)
    if not labels:
        die("no backup sets listed by pgbackrest info")
    restore_set = labels[-1]
    _as_desmo("uv", "run", "--no-sync", "manage.py", "backupmarker", "set")

    # Both backup paths ran green.
    _assert_eq(
        _systemctl_show("desmo_pgbackrest.service"), "success", "desmo_pgbackrest.service result"
    )

    # The restore rolls the live server back: the AGENT's verb restores
    # the captured snapshot EXACTLY (no replay past it), and the
    # restarted app must serve the BACKED-UP marker (the diverged one
    # post-dates the set ⇒ the restore provably replaced live data).
    _shim(str(MAIN_DIR / "run"), "restoredb", restore_set)
    latest = _capture_desmo("uv", "run", "--no-sync", "manage.py", "backupmarker", "latest").strip()
    _assert_eq(latest, marker_backed_up, "live server serves the backed-up marker")

    # The schedule is wired — timer enabled, next fire listed (is-enabled
    # exits 1 when disabled; the value is the assert).
    _return_code, enabled = shell.capture("systemctl", "is-enabled", "desmo_pgbackrest.timer")
    _assert_eq(enabled.strip(), "enabled", "desmo_pgbackrest.timer enabled")
    timers = _capture("systemctl", "list-timers", "--no-pager")
    if "desmo_pgbackrest" not in timers:
        die("desmo_pgbackrest missing from systemctl list-timers")


if __name__ == "__main__":
    if os.geteuid() != 0:
        die("the gate runs as root, inside the container (run's checkframework2 execs it)")
    gate()
