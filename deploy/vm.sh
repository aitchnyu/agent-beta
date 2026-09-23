#!/bin/bash
# vm.sh — shared GUEST-side helpers for multipass commands (run INSIDE the
# VM by `run`/`testvm` call sites and by hand). Convention (INSTRUCTIONS.md
# § "Multipass helpers in deploy/vm.sh"): any multipass command longer than
# two lines lives HERE as a named function — call sites stay one-liners, no
# `bash -c` string blobs, no `declare -f` embedding.
#
#   multipass exec app -- sudo bash /srv/app/main/deploy/vm.sh <fn> [args]
#   multipass exec app -- sudo -u app -H bash /srv/app/main/deploy/vm.sh runasapp <cmd…>
#
# Ships with the repo (the seed lands it at /srv/app/main/deploy/vm.sh);
# ./testvm provision also drops an early copy at /tmp/vm.sh for steps that
# run BEFORE the seed is extracted. Runs as whatever user invokes it —
# pick the function to match (root: extract/deploy/deps/gate; app:
# runasapp, playwright-install; agent: agent-*).

set -euo pipefail

# Shared env for user functions: credentials env exported + repo as cwd.
_vm_env() {
  set -a
  . /etc/credentials/app/.env.vm
  set +a
  cd /srv/app/main
}

# ── root ──────────────────────────────────────────────────────────────────

extract-app-seed() {
  tar xzf /tmp/app-seed.tgz -C /srv/app/main
  chown -R app:app /srv/app/main
  # Group-write the tree (like the enclosing /srv/app 775): the agent
  # user (./run agent) must be able to edit main/ — deployscratch's
  # builds, git resets — not just read it.
  find /srv/app/main -exec chmod g+w {} +
}

# Append the computed platform keys when the pinned playwright doesn't know
# this OS natively (cross-platform: the host derives and passes the entry,
# e.g. ubuntu24.04-arm64 — see ./testvm provision step 6b). Idempotent: a
# retry (or a transient native-install failure misread as
# platform-unknown) must not append duplicate keys — grep before append.
playwright-override-env() {
  grep -q '^PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=' /etc/credentials/app/.env.vm \
    || printf 'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE="%s"\n' "$1" >> /etc/credentials/app/.env.vm
  grep -q '^PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=' /etc/credentials/app/.env.vm \
    || printf 'PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS="1"\n' >> /etc/credentials/app/.env.vm
}

# Cross-platform browser setup: native first, mapped fallback (testvm 6b).
playwright-setup() {
  # Native first: on a distro the pinned playwright knows, this is the only
  # path — no override keys, validation passes as-is.
  if sudo -u app -H bash /srv/app/main/deploy/vm.sh playwright-install; then
    return 0
  fi
  # Native failed → this OS is unknown to playwright (e.g. 26.04 at 1.60).
  # Map onto the nearest LTS entry for THIS architecture — computed, never
  # hardcoded, so amd64 hosts work as well as arm64.
  local arch
  arch="$(dpkg --print-architecture)"
  echo "    native platform unknown to playwright — mapping to ubuntu24.04-$arch"
  # The keys must PERSIST (runtime launches validate too), so append them
  # to the credentials env — root-writable only; every user sources it
  # through ./run setenv.
  playwright-override-env "ubuntu24.04-$arch"
  # Retry with the mapping now in the environment (validation skipped: the
  # deps list would be checked against the MAPPED platform's packages).
  sudo -u app -H bash /srv/app/main/deploy/vm.sh playwright-install
}

# Provisioning's /tmp leftovers — each embeds secrets or is a spent one-shot:
# - tree.tgz           embeds the credentials env (sat world-readable — must not survive)
# - app-seed.tgz       the repo snapshot tarball
# - inside-vm.sh       transferred one-shot (open fds survive unlink — safe mid-run)
# - vm.sh              transferred early copy; the seeded deploy/vm.sh remains
# - vm-seed-commit.sh  tree-extracted root one-shot; app could never delete it
# - vm-bootstrap.sh    same (ran as app at step 6)
cleanup-provision-tmp() {
  rm -f /tmp/tree.tgz /tmp/app-seed.tgz /tmp/inside-vm.sh /tmp/vm.sh \
    /tmp/vm-seed-commit.sh /tmp/vm-bootstrap.sh
}

# chromium system deps on ubuntu 26.04 (t64 names): playwright's own map,
# else the minimal launch set (playwright's ubuntu map minus GTK/dbus-glib
# — headless chromium dlopens neither).
playwright-deps() {
  _vm_env
  export DEBIAN_FRONTEND=noninteractive
  if /srv/app/main/.venv/bin/python -m playwright install-deps chromium; then
    return 0
  fi
  apt-get install -y libnss3 libnspr4 libdbus-1-3 libdrm2 libgbm1 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libx11-6 libx11-xcb1 libxcb1 libpango-1.0-0 libcairo2 \
    libasound2t64 libatk1.0-0t64 libatk-bridge2.0-0t64 libatspi2.0-0t64 \
    libcups2t64 libglib2.0-0t64
}

deploy-ourapp() {
  tar xzf /tmp/testapp-ourapp.tgz -C /srv/app/main
  chown -R app:app /srv/app/main/ourapp
  find /srv/app/main/ourapp -exec chmod g+w {} +
  rm -f /tmp/testapp-ourapp.tgz
}

# ── app user ──────────────────────────────────────────────────────────────

# runasapp <command…> — env sourced, repo cwd, uv on PATH; the one
# sanctioned way to run one command as the app user.
runasapp() {
  _vm_env
  export PATH=/usr/local/bin:$PATH
  "$@"
}

playwright-install() {
  _vm_env
  export PATH=/usr/local/bin:$PATH
  uv run playwright install chromium --only-shell
}

# ── agent user ─────────────────────────────────────────────────────────────

agent-browsers() {
  _vm_env
  ls "$PLAYWRIGHT_BROWSERS_PATH" | sed -n '1,3p'
}

# The acceptance probe: chromium must LAUNCH headless as agent (the user
# the pi CLI runs as) — platform-agnostic by construction.
agent-playwright-probe() {
  _vm_env
  timeout 10 .venv/bin/python -c '
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch()
print("agent headless chromium launch OK")
b.close(); p.stop()
'
}

# The agent's scratch lifecycle in checkframework2 
agent-scratch-create() {
  # Credentials env → PLAYWRIGHT_BROWSERS_PATH, AGENT_MODEL et al; cwd = main/
  _vm_env
  # uv lives in /usr/local/bin; sudo's secure_path may not carry it
  export PATH=/usr/local/bin:$PATH
  # The work itself: copy main/ → scratch/, tag scratch-baseline, share
  # .venv + node_modules via hardlink-or-copy
  ./run createscratch
  # Postcondition 1: the scratch tree exists
  test -d /srv/app/scratch
  # Postcondition 2: the frozen baseline ref the framework-file watch and
  # _scratch_checks diff against actually resolves (agent-owned git)
  git -C /srv/app/scratch rev-parse --verify scratch-baseline >/dev/null
  echo "agent createscratch OK"
}

# Insert the deployscratch liveness marker into scratch's home view —
# header-gated (exact-props tests never see it), inside ourapp/ (framework
# watch quiet, battery-clean), grep-guarded (rerun no-ops). The sed:
#   before:  ...  return InertiaResponse(...)
#   after:   ...  if request.headers.get("X-Scratch-Probe"):
#                 props["scratch_marker"] = "scratch-deploy-live"
#             return InertiaResponse(...)
agent-scratch-edit() {
  _vm_env
  local home=/srv/app/scratch/ourapp/views/home.py
  grep -q scratch_marker "$home" \
    || sed -i 's/^    return InertiaResponse/    if request.headers.get("X-Scratch-Probe"):\n        props["scratch_marker"] = "scratch-deploy-live"\n    return InertiaResponse/' "$home"
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
  test ! -e /srv/app/scratch
  echo "agent cleanscratch OK"
}

# ── the deployment gate (checkframework2's in-VM body) ─────────────────────
# `gate` — checkframework2's body, dispatched like any other helper:
# - runs as ROOT, after the host (run's checkframework2) provisioned the
#   VM fresh
# - overlays the Books test app over the VM's ourapp/
# - smokes the LIVE stack over HTTPS on loopback (caddy TLS, granian,
#   postgres, login links) — what only a real deployment shows
# - three setup phases then nine asserts, one linear body (read it top
#   to bottom), first failure aborts with FAILED: <what>
# - the host side checks only gate's exit code; output streams to the
#   operator

gate_base="https://localhost"
gate_jar="/tmp/fw-smoke-cookies"   # in-VM cookie jar for the smoke curls

# Same sudo shims every external caller of this file uses — vm.sh is a
# dispatcher, not a sourceable library, and runasapp/agent-* assume the
# target user already. gate-as-agent-user forwards exactly one argument:
# every agent-* wrapper is argless.
gate-as-app-user() { sudo -u app -H bash /srv/app/main/deploy/vm.sh runasapp "$@"; }
gate-as-agent-user() { sudo -u agent -H bash /srv/app/main/deploy/vm.sh "$1"; }

# Fail the gate: clean the smoke jar, say why, exit nonzero.
gate-fail() {
  rm -f "$gate_jar"
  echo "FAILED: $*" >&2
  exit 1
}

# A command that MUST refuse: expect a nonzero exit, quietly. NB: the if
# (not `cmd && fail`) is load-bearing — a failing `&&` list as the last
# command would make THIS function return nonzero and, under vm.sh's
# set -e, kill the whole gate on the expected path.
gate-expect-refusal() { # <description> <command…>
  local desc=$1
  shift
  if "$@" >/dev/null 2>&1; then
    gate-fail "$desc"
  fi
}

# <got> <want[ want…]> <what> — a single value ("404") or space-separated
# alternatives ("302 200"). A case-pattern CANNOT take its | alternation
# from an expanded variable (parse-time construct), hence the loop.
gate-assert-eq() {
  local got=$1 alts=$2 want
  for want in $alts; do
    [ "$want" = "$got" ] && return 0
  done
  gate-fail "$3 (expected $alts, got $got)"
}

# The gate itself — one linear body, read top to bottom. Invoked by run's
# checkframework2 over ONE multipass exec; its exit code is the verdict.
# Local vars needed across steps (the login link, the page bodies).
gate() {
  local link body

  # ── Setup 1/3: overlay the test app ────────────────────────────────────
  # Tar the testapp's ourapp/ from the seeded tree, extract it over the
  # VM's /srv/app/main/ourapp — an overlay MERGE (files only in the seeded
  # ourapp/ survive, e.g. its own tests; the tarball has no --delete).
  echo; echo "=== Setup 1/3: deploy the Books test app over the VM's ourapp/ ==="
  tar -C /srv/app/main/djangoapp/tests/testapp -czf /tmp/testapp-ourapp.tgz ourapp \
    || gate-fail "testapp tar failed"
  deploy-ourapp || gate-fail "testapp overlay extraction failed"

  # ── Setup 2/3: migrate + the smoke superuser ───────────────────────────
  # framework@example.com ("Framework Smoke"), then restart granian on the
  # overlaid code.
  echo; echo "=== Setup 2/3: migrate, create the smoke superuser ==="
  gate-as-app-user .venv/bin/python manage.py migrate --noinput \
    || gate-fail "migrate failed"
  gate-as-app-user .venv/bin/python manage.py createuser framework@example.com \
    --first-name Framework --last-name Smoke --superuser \
    || gate-fail "smoke superuser creation failed"
  systemctl restart app_granian.service \
    || gate-fail "app_granian.service restart failed"

  # ── Setup 3/3: issue the one-time superuser login link ─────────────────
  # The cookie jar filled by assert 1 carries the session every later
  # authed assert rides on (it survives the deployscratch restart —
  # sessions are DB-backed).
  echo; echo "=== Setup 3/3: issue the one-time superuser login link ==="
  link=$(gate-as-app-user .venv/bin/python manage.py makeloginlink \
    framework@example.com --base-url "$gate_base" \
    | grep -oE "$gate_base/login-for-test/[^ ]+/" | sed -n '1p') || true
  [ -n "$link" ] || gate-fail "no login link issued"

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
  body=$(curl -k -sS -b "$gate_jar" "$gate_base/") \
    || gate-fail "home fetch failed"
  grep -q "Framework Smoke" <<<"$body" || gate-fail "home does not show the smoke user"

  # ── Assert 5: the operator shells in via multipass and becomes the
  # agent user (sudo -iu agent). The two `./run pi` preconditions: pi on
  # PATH, and the credentials env (AGENT_MODEL) readable as agent via its
  # app-group membership.
  echo; echo "=== Assert 5: agent user can run ./run pi ==="
  # Postcondition 1: pi is on the agent user's PATH
  sudo -u agent -H bash -c 'command -v pi >/dev/null' \
    || gate-fail "pi not on the agent user's PATH"
  # Postcondition 2: the credentials env (AGENT_MODEL) resolves as agent
  # via its app-group membership
  sudo -u agent -H bash -c \
    '. /etc/credentials/app/.env.vm 2>/dev/null; test -n "${AGENT_MODEL:-}"' \
    || gate-fail "AGENT_MODEL does not resolve as agent (credentials env unreadable)"

  # ── Assert 6: the agent's scratch ./run playwrighttest needs browsers
  # in the SHARED cache (readable as agent) and a chromium that actually
  # LAUNCHES headless as agent — the acceptance probe.
  echo; echo "=== Assert 6: playwright browsers launch as agent ==="
  local browsers
  # Postcondition 1: the shared browser cache is nonempty and readable as agent
  browsers=$(gate-as-agent-user agent-browsers) \
    || gate-fail "agent-browsers failed"
  [ -n "$browsers" ] || gate-fail "shared playwright browser cache empty/unreadable as agent"
  # Postcondition 2: headless chromium actually launches as agent (exit 0;
  # the wrapper's OK line is operator output, the exit code is the assert)
  gate-as-agent-user agent-playwright-probe \
    || gate-fail "headless chromium does not launch as agent (deps or platform env missing)"

  # ── Assert 7: createscratch as the agent. The agent's whole edit loop
  # rides the scratch cycle; the fresh VM is the only place its VM-only
  # paths run (protected-hardlink fallback in _link_or_copy_tree,
  # agent-owned scratch git).
  echo; echo "=== Assert 7: agent createscratch ==="
  # Postcondition 1: deployscratch without scratch/ refuses
  gate-expect-refusal "deployscratch without scratch/ must refuse" \
    gate-as-agent-user agent-scratch-deploy
  # Postcondition 2: exit 0 means scratch/ exists and scratch-baseline resolves
  gate-as-agent-user agent-scratch-create \
    || gate-fail "createscratch as agent (scratch/ or scratch-baseline ref missing)"
  # Postcondition 3: scratch's OWN ./run refuses (rsync onto itself otherwise)
  gate-expect-refusal "scratch's own ./run must refuse to deploy" \
    sudo -u agent -H bash -c 'cd /srv/app/scratch && ./run deployscratch'

  # ── Assert 8: deployscratch as the agent, deploy provably live. The
  # marker prop rides the full battery, the sudo-rsync + re-own + g+w VM
  # branch, and the granian restart.
  echo; echo "=== Assert 8: agent deployscratch (marker live on /) ==="
  # Postcondition 1: the header-gated marker is inserted into scratch's home view
  gate-as-agent-user agent-scratch-edit \
    || gate-fail "marker edit in scratch's home view"
  # Postcondition 2: exit 0 means the full battery is green and the rsync landed
  gate-as-agent-user agent-scratch-deploy \
    || gate-fail "deployscratch as agent (battery or deploy failed)"
  # Postcondition 3: granian is active after the deploy's restart
  gate-assert-eq "$(systemctl is-active app_granian.service)" \
    active "app_granian.service after deployscratch"
  # Postcondition 4: / fetches with the X-Scratch-Probe header on the smoke session
  # (retries absorb the restart race)
  body=$(curl -k -sS --retry 10 --retry-delay 2 --retry-connrefused \
    -b "$gate_jar" -H "X-Scratch-Probe: 1" "$gate_base/") \
    || gate-fail "home fetch failed after deployscratch"
  # Postcondition 5: the marker is in the served page JSON — deploy AND
  # restart proven, not just rsync
  grep -q "scratch-deploy-live" <<<"$body" \
    || gate-fail "deploy marker not live on / (restart or deploy broken)"

  # ── Assert 9: the cycle ends clean — scratch/ gone.
  echo; echo "=== Assert 9: agent cleanscratch ==="
  # Postcondition 1: exit 0 means cleanscratch ran as agent and scratch/ is gone
  gate-as-agent-user agent-scratch-clean \
    || gate-fail "cleanscratch as agent (scratch/ still present)"

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
