#!/bin/bash
# gate.sh — the deployment gate: checkframework2's in-VM acceptance battery,
# wholesale. TESTING ONLY — no operator surface lives here (that's local-vm's
# runasdesmo; INSTRUCTIONS.md § "In-VM scripts"). Runs INSIDE the VM:
#
#   multipass exec desmo -- sudo bash /srv/desmo/main/deploy/gate.sh gate
#
# Called by exactly one thing: run's checkframework2 (one exec; the host
# side checks only gate's exit code, output streams to the operator).
# Ships with the repo (the seed lands it at /srv/desmo/main/deploy/gate.sh).
#
# `gate` — one linear body, read top to bottom:
# - runs as ROOT, after the host (run's checkframework2) provisioned the
#   VM fresh
# - overlays the Books test app over the VM's ourapp/
# - smokes the LIVE stack over HTTPS on loopback (caddy TLS, granian,
#   postgres, login links) — what only a real deployment shows
# - three setup phases then several asserts, first failure aborts with
#   FAILED: <what>
#
# The argless agent-* wrappers below are gate assert bodies dispatched via
# gate-as-default-user (they run as the default cloud user, not desmo).

set -euo pipefail

# The gate's internal env shim for its agent-* assert bodies: credentials
# env exported + repo as cwd. (The OPERATOR's run-as-desmo surface is
# local-vm's runasdesmo — this file keeps its own plumbing.)
_vm_env() {
  set -a
  . /etc/credentials/desmo/.env.vm
  set +a
  cd /srv/desmo/main
}

# ── desmo user ────────────────────────────────────────────────────────────
# (the operator's run-as-desmo surface is local-vm's runasdesmo; the gate
# reaches it through the gate-as-desmo-user shim below)

# ── default cloud user (ubuntu/debian — the pi agent's user) ──────────────

agent-browsers() {
  _vm_env
  ls "$PLAYWRIGHT_BROWSERS_PATH" | sed -n '1,3p'
}

# The acceptance probe: chromium must LAUNCH headless as the default user
# (the user the pi CLI runs as) — platform-agnostic by construction.
agent-playwright-probe() {
  _vm_env
  timeout 10 uv run --no-sync python -c '
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch(headless=True)
print("agent headless chromium launch OK")
b.close(); p.stop()
'
}

# Assert-5 body: the `desmo pi` preconditions — the desmo wrapper and the
# pi binary on PATH, and the credentials env readable via desmo-group
# membership (probed via the generated SECRET_KEY, which is non-empty on
# every correctly provisioned VM). The model/auth live in pi's own stores.
agent-pi-preconditions() {
  command -v desmo >/dev/null
  command -v pi >/dev/null
  . /etc/credentials/desmo/.env.vm 2>/dev/null
  test -n "${SECRET_KEY:-}"
}

# The agent's scratch lifecycle in checkframework2
agent-scratch-create() {
  # Credentials env → PLAYWRIGHT_BROWSERS_PATH et al; cwd = main/
  _vm_env
  # uv lives in /usr/local/bin; sudo's secure_path may not carry it
  export PATH=/usr/local/bin:$PATH
  # The work itself: copy main/ → scratch/, tag scratch-baseline, share
  # .venv + node_modules via hardlink-or-copy
  ./run createscratch
  # Postcondition 1: the scratch tree exists
  test -d /srv/desmo/scratch
  # Postcondition 2: the frozen baseline ref the framework-file watch and
  # _scratch_checks diff against actually resolves (default-user-owned git)
  git -C /srv/desmo/scratch rev-parse --verify scratch-baseline >/dev/null
  echo "agent createscratch OK"
}

# Insert the deployscratch liveness marker into scratch's home view —
# header-gated (exact-props tests never see it), inside ourapp/ (framework
# watch quiet, battery-clean), grep-guarded (rerun no-ops). FIRST return
# only (the 0,/re/ range): the view also ends with the mockup route's
# return, and `props` exists only in home's scope. The sed:
#   before:  ...  return InertiaResponse(...)
#   after:   ...  if request.headers.get("X-Scratch-Probe"):
#                 props["scratch_marker"] = "scratch-deploy-live"
#             return InertiaResponse(...)
agent-scratch-edit() {
  _vm_env
  local home=/srv/desmo/scratch/ourapp/views/home.py
  grep -q scratch_marker "$home" \
    || sed -i '0,/^    return InertiaResponse/s/^    return InertiaResponse/    if request.headers.get("X-Scratch-Probe"):\n        props["scratch_marker"] = "scratch-deploy-live"\n    return InertiaResponse/' "$home"
  echo "agent scratch edit OK"
}

agent-scratch-deploy() {
  _vm_env
  export PATH=/usr/local/bin:$PATH
  ./run deployscratch
}

agent-scratch-clean() {
  _vm_env
  ./run cleanscratch
  # Postcondition 1: scratch/ no longer exists
  test ! -e /srv/desmo/scratch
  echo "agent cleanscratch OK"
}

# ── the deployment gate (checkframework2's in-VM body) ─────────────────────
# `gate` — checkframework2's body, dispatched like any other helper:
# - runs as ROOT, after the host (run's checkframework2) provisioned the
#   VM fresh
# - overlays the Books test app over the VM's ourapp/
# - smokes the LIVE stack over HTTPS on loopback (caddy TLS, granian,
#   postgres, login links) — what only a real deployment shows
# - three setup phases then several asserts, one linear body (read it top
#   to bottom), first failure aborts with FAILED: <what>
# - the host side checks only gate's exit code; output streams to the
#   operator

gate_base="https://localhost"
gate_jar="/tmp/fw-smoke-cookies"   # in-VM cookie jar for the smoke curls

# The default cloud user (ubuntu on multipass, debian on Incus) — first
# existing wins; provisioning (inside-vm.sh) detects the same way.
_op_user() {
  local u
  for u in ubuntu debian; do
    id "$u" >/dev/null 2>&1 && { echo "$u"; return 0; }
  done
  echo "no default cloud user (ubuntu/debian) found" >&2
  return 1
}

# Same sudo shims every external caller of this file uses — gate.sh is a
# dispatcher, not a sourceable library, and the agent-* wrappers assume the
# target user already. gate-as-default-user forwards exactly one argument:
# every agent-* wrapper is argless. The desmo shim routes through local-vm's
# runasdesmo — the ONE sanctioned surface, same as the operator's docs.
gate-as-desmo-user() { sudo -u desmo -H bash /srv/desmo/main/local-vm runasdesmo "$@"; }
gate-as-default-user() { sudo -u "$(_op_user)" -H bash /srv/desmo/main/deploy/gate.sh "$1"; }

# A command that MUST refuse: expect a nonzero exit, quietly. NB: the if
# (not `cmd && fail`) is load-bearing — a failing `&&` list as the last
# command would make THIS function return nonzero and, under vm.sh's
# set -e, kill the whole gate on the expected path.
gate-expect-refusal() { # <command…>
  if "$@" >/dev/null 2>&1; then
    echo "FAILED: expected refusal, command succeeded: $*" >&2
    exit 1
  fi
}

# <got> <want[ want…]> <what> — a single value ("404") or space-separated
# alternatives ("302 200"). A case-pattern CANNOT take alternation from
# an expanded variable (parse-time construct), hence the loop. This is
# the gate's one fail path: everything else aborts naturally under
# set -e with the command's own error; value comparisons exit 0 when
# wrong, so the mismatch must fail explicitly.
gate-assert-eq() {
  local got=$1 alts=$2 want
  for want in $alts; do
    [ "$want" = "$got" ] && return 0
  done
  echo "FAILED: $3 (expected $alts, got $got)" >&2
  exit 1
}

# The gate itself — one linear body, read top to bottom. Invoked by run's
# checkframework2 over ONE multipass exec; its exit code is the verdict.
# Local vars needed across steps (the login link, the page bodies).
gate() {
  local link body

  # ── Setup 1/3: replace the app with the test app ───────────────────────
  # Wholesale replace — same semantics as the host tiers' overlay_app
  # (rsync --delete): the seeded ourapp/ (code AND tests) goes, the
  # testapp lands in its place, nothing of the template's app survives.
  # The VM gate tests the live stack against the Books app; the
  # template's own tests run host-side in checkframework1.
  echo; echo "=== Setup 1/3: deploy the Books test app over the VM's ourapp/ ==="
  rm -rf /srv/desmo/main/ourapp
  cp -a /srv/desmo/main/djangoapp/tests/testapp/ourapp /srv/desmo/main/ourapp
  chown -R desmo:desmo /srv/desmo/main/ourapp
  find /srv/desmo/main/ourapp -exec chmod g+w {} +

  # ── Setup 2/3: migrate + the smoke superuser ───────────────────────────
  # framework@example.com ("Framework Smoke"), then restart granian on the
  # overlaid code.
  echo; echo "=== Setup 2/3: migrate, create the smoke superuser ==="
  gate-as-desmo-user uv run --no-sync python manage.py migrate --noinput
  gate-as-desmo-user uv run --no-sync python manage.py createuser framework@example.com \
    --first-name Framework --last-name Smoke --superuser
  systemctl restart desmo_granian.service

  # ── Setup 3/3: issue the one-time superuser login link ─────────────────
  # The cookie jar filled by assert 1 carries the session every later
  # authed assert rides on (it survives the deployscratch restart —
  # sessions are DB-backed). The printed link's origin is BASE_URLS[0]
  # (the tunnel origin) — in-VM asserts want the :443 base, so the grep
  # lifts just the PATH.
  echo; echo "=== Setup 3/3: issue the one-time superuser login link ==="
  login_path="$(gate-as-desmo-user uv run --no-sync python manage.py makeloginlink \
    framework@example.com \
    | grep -oE '/login-for-test/[^ ]+/' | sed -n '1p')" || true
  [ -n "$login_path" ]
  link="$gate_base$login_path"

  # ── Assert 1: 302 (redirect after login; 200 also fine) and a
  # session cookie in the jar.
  echo; echo "=== Assert 1: login link redeems ==="
  gate-assert-eq "$(curl -k -sS -o /dev/null -w '%{http_code}' -c "$gate_jar" "$link")" \
    "302 200" "login link redemption status"

  # ── Assert 2: the framework superuser route hides from anonymous
  # viewers.
  echo; echo "=== Assert 2: anonymous /users/list → 404 ==="
  gate-assert-eq "$(curl -k -sS -o /dev/null -w '%{http_code}' "$gate_base/users/list")" \
    404 "anonymous /users/list"

  # ── Assert 3: 200 proves the redeemed cookie is a real superuser
  # session.
  echo; echo "=== Assert 3: authed /users/list → 200 (session proof) ==="
  gate-assert-eq "$(curl -k -sS -o /dev/null -w '%{http_code}' -b "$gate_jar" "$gate_base/users/list")" \
    200 "authed /users/list (session proof)"

  # ── Assert 4: the home page shows the smoke user's display name.
  echo; echo "=== Assert 4: home shows the smoke user ==="
  body=$(curl -k -sS -b "$gate_jar" "$gate_base/")
  grep -q "Framework Smoke" <<<"$body"

  # ── Assert 5: the operator shells in via multipass as the default
  # cloud user (no sudo -iu hop) and runs `desmo pi`. Preconditions: the
  # desmo wrapper + pi binary on PATH, and the credentials env
  # (SECRET_KEY probes readability) readable via desmo-group membership.
  echo; echo "=== Assert 5: default user can run desmo pi ==="
  gate-as-default-user agent-pi-preconditions

  # ── Assert 6: the agent's scratch ./run playwrighttest needs browsers
  # in the SHARED cache (readable as the default user) and a chromium that
  # actually LAUNCHES headless as that user — the acceptance probe.
  echo; echo "=== Assert 6: playwright browsers launch as the default user ==="
  local browsers
  # Postcondition 1: the shared browser cache is nonempty and readable as the default user
  browsers=$(gate-as-default-user agent-browsers)
  [ -n "$browsers" ]
  # Postcondition 2: headless chromium actually launches as the default
  # user (exit 0; the wrapper's OK line is operator output, the exit code
  # is the assert)
  gate-as-default-user agent-playwright-probe

  # ── Assert 7: createscratch as the agent (the default cloud user). The
  # agent's whole edit
  # loop rides the scratch cycle; the fresh VM is the only place its
  # VM-only paths run (protected-hardlink fallback in _link_or_copy_tree,
  # operator-owned scratch git).
  echo; echo "=== Assert 7: agent createscratch ==="
  # Postcondition 1: deployscratch without scratch/ refuses
  gate-expect-refusal gate-as-default-user agent-scratch-deploy
  # Postcondition 2: exit 0 means scratch/ exists and scratch-baseline resolves
  gate-as-default-user agent-scratch-create
  # Postcondition 3: scratch's OWN ./run refuses (rsync onto itself otherwise)
  gate-expect-refusal sudo -u "$(_op_user)" -H bash -c 'cd /srv/desmo/scratch && ./run deployscratch'

  # ── Assert 8: deployscratch as the agent (the default cloud user),
  # deploy provably live.
  # The marker prop rides the full battery, the sudo-rsync + re-own + g+w
  # VM branch, and the granian restart.
  echo; echo "=== Assert 8: agent deployscratch (marker live on /) ==="
  # Postcondition 1: the header-gated marker is inserted into scratch's home view
  gate-as-default-user agent-scratch-edit
  # Postcondition 2: exit 0 means the full battery is green and the rsync landed
  gate-as-default-user agent-scratch-deploy
  # Postcondition 3: granian is active after the deploy's restart
  gate-assert-eq "$(systemctl is-active desmo_granian.service)" \
    active "desmo_granian.service after deployscratch"
  # Postcondition 4: / fetches with the X-Scratch-Probe header on the smoke session
  # (retries absorb the restart race)
  body=$(curl -k -sS --retry 10 --retry-delay 2 --retry-connrefused \
    -b "$gate_jar" -H "X-Scratch-Probe: 1" "$gate_base/")
  # Postcondition 5: the marker is in the served page JSON — deploy AND
  # restart proven, not just rsync
  grep -q "scratch-deploy-live" <<<"$body"

  # ── Assert 9: the cycle ends clean — scratch/ gone.
  echo; echo "=== Assert 9: agent cleanscratch ==="
  # Postcondition 1: exit 0 means cleanscratch ran as the default user and
  # scratch/ is gone
  gate-as-default-user agent-scratch-clean

  # ── Assert 10: media serving — upload + serve_file over the live stack
  # (testapp /media endpoints; the GET rides the X-Accel-Redirect handoff).
  echo; echo "=== Assert 10: media upload + serve_file ==="
  printf 'gate-media-bytes' > /tmp/gate-upload.bin
  
  # Postcondition 1: the multipart upload stored the file and replied with
  # its unguessable storage name (ninja's JSON has a space after the colon)
  media_name=$(curl -k -sS -b "$gate_jar" -F "file=@/tmp/gate-upload.bin" \
    "$gate_base/media/upload" | sed -n 's/.*"name":[[:space:]]*"\([^"]*\)".*/\1/p')
  [ -n "$media_name" ]
  # Postcondition 2: the serve URL streams the exact bytes back — an
  # unintercepted accel response would be an empty body and fail the cmp
  curl -k -sS -b "$gate_jar" "$gate_base/media/$media_name" -o /tmp/gate-download.bin
  cmp /tmp/gate-upload.bin /tmp/gate-download.bin
  # Postcondition 3: unknown and traversal names are 404s (never a 500,
  # never bytes from outside MEDIA_ROOT)
  gate-assert-eq "$(curl -k -sS -o /dev/null -w '%{http_code}' -b "$gate_jar" "$gate_base/media/not-there.bin")" \
    404 "unknown media name"
  gate-assert-eq "$(curl -k -sS -o /dev/null -w '%{http_code}' -b "$gate_jar" --path-as-is \
    "$gate_base/media/..%2f..%2f..%2fetc%2fpasswd")" \
    404 "media traversal attempt"
  rm -f /tmp/gate-upload.bin /tmp/gate-download.bin

  # ── Assert 11: the backup round-trip on the LIVE server — mark, back
  # up, diverge, restore onto the live cluster, and read the backed-up
  # marker back through the app (the BackupMarker model). The role
  # grant, stanza, and WAL archiving are provisioning's; the
  # midnight-UTC cadence and Persistent catch-up stay untested (a
  # reboot is too heavy for the gate).
  echo; echo "=== Assert 11: pgbackrest (mark, backup, restore live, verify) ==="
  local marker_backed_up restore_set backup_info backup_timers
  # Setup: a marker goes in, BOTH backup paths run (the agent's verb,
  # then the timer's shim — each takes its own backup), the NEWEST
  # set's label is captured, and a SECOND marker diverges the live DB
  # past that snapshot.
  marker_backed_up="$(gate-as-desmo-user uv run manage.py backupmarker set)"
  /srv/desmo/main/run backupdb
  systemctl start desmo_pgbackrest.service
  # The newest set's label — diff labels are COMPOUND (fullF_diffD): the
  # optional group keeps the whole label together; a bare [FD] fragment
  # capture would fail restoredb's exact "backup: <set>" existence match.
  restore_set="$(sudo -u postgres pgbackrest --stanza=desmo info \
    | grep -oE '[0-9]{8}-[0-9]{6}F(_[0-9]{8}-[0-9]{6}D)?' | tail -n1)"
  gate-as-desmo-user uv run manage.py backupmarker set

  # Postcondition 1: both backup paths ran green and the repo lists
  # the backup sets.
  gate-assert-eq "$(systemctl show -p Result --value desmo_pgbackrest.service)" \
    success "desmo_pgbackrest.service result"
  backup_info="$(sudo -u postgres pgbackrest --stanza=desmo info)"
  grep -q . <<<"$backup_info"

  # Postcondition 2: the restore rolls the live server back — the
  # AGENT's verb (./run restoredb '<set>') restores the captured
  # snapshot EXACTLY (no replay past it), and the restarted app must
  # serve the BACKED-UP marker (the diverged one post-dates the set ⇒
  # the restore provably replaced live data).
  /srv/desmo/main/run restoredb "$restore_set"
  gate-assert-eq "$(gate-as-desmo-user uv run manage.py backupmarker latest)" \
    "$marker_backed_up" "live server serves the backed-up marker"

  # Postcondition 3: the schedule is wired — timer enabled, next fire listed.
  gate-assert-eq "$(systemctl is-enabled desmo_pgbackrest.timer)" \
    enabled "desmo_pgbackrest.timer enabled"
  backup_timers="$(systemctl list-timers --no-pager)"
  grep -q desmo_pgbackrest <<<"$backup_timers"

  rm -f "$gate_jar"
  printf '\ncheckframework2 green.\n'
}

# ── dispatcher ────────────────────────────────────────────────────────────

if [ -n "${1:-}" ] && declare -F "$1" >/dev/null; then
  fn="$1"
  shift
  "$fn" "$@"
else
  echo "Usage: $0 <function> [args] — one function per line:" >&2
  declare -F | awk '{print "  " $3}' >&2
  exit 1
fi
