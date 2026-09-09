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
# pick the function to match (root: extract/deploy/deps; app: runasapp,
# playwright-install; agent: agent-*).

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

# firefox system deps: playwright's own map when it fits the distro; else
# the minimal launch set (t64 names first, pre-t64 fallback) — verified via
# ldd + a headless launch (2026-08-31).
playwright-deps() {
  _vm_env
  export DEBIAN_FRONTEND=noninteractive
  /srv/app/main/.venv/bin/python -m playwright install-deps firefox ||
    apt-get install -y libgtk-3-0t64 libx11-xcb1 libdbus-glib-1-2 libxt6t64 \
      libasound2t64 libxext6 libxfixes3 libxcb-shm0 libxcb1 libx11-6 \
      libgbm1 libpango-1.0-0 libcairo2 ||
    apt-get install -y libgtk-3-0 libx11-xcb1 libdbus-glib-1-2 libxt6 \
      libasound2 libxext6 libxfixes3 libxcb-shm0 libxcb1 libx11-6 \
      libgbm1 libpango-1.0-0 libcairo2
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
  uv run playwright install firefox
}

# ── agent user ─────────────────────────────────────────────────────────────

agent-browsers() {
  _vm_env
  ls "$PLAYWRIGHT_BROWSERS_PATH" | head -3
}

# The acceptance probe: firefox must LAUNCH headless as agent (the user
# the pi CLI runs as) — platform-agnostic by construction.
agent-playwright-probe() {
  _vm_env
  timeout 120 .venv/bin/python -c '
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.firefox.launch()
print("agent headless firefox launch OK")
b.close(); p.stop()
'
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
