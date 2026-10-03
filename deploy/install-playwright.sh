#!/bin/bash
# install-playwright.sh — the WHOLE playwright install for the VM: platform
# decision, override keys, browsers into the shared cache, chromium system
# deps, and a launch verification. Runs AS ROOT (provisioning's phase 10,
# or by hand via multipass exec sudo). HARD-FAILS on an OS outside its
# platform table: an unhandled OS must abort provision, never silently map
# onto a fallback build.
#
# Usage: install-playwright.sh            # root — everything (phase 10's entry)
#        install-playwright.sh browsers   # desmo — self-dispatched download only
#        install-playwright.sh verify     # desmo — self-dispatched launch check

set -euo pipefail

maindir="/srv/desmo/main"
creds_env="/etc/credentials/desmo/.env.vm"

main() {
  # Detect the OS/arch: os-release is the portable source, dpkg the arch.
  . /etc/os-release
  local arch override=""
  arch="$(dpkg --print-architecture)"

  # ── the platform table — which OSes we DELIBERATELY support ────────────
  # Extend a row only after verifying the entry end-to-end (browsers
  # download, deps resolve, the launch check passes); that bar is why
  # unknown OSes refuse instead of mapping.
  case "$ID $VERSION_ID" in
    "ubuntu 24.04")
      # Native: the pinned playwright knows this platform — no override keys.
      ;;
    "ubuntu 26.04")
      # Unknown to the pinned playwright — the VERIFIED fallback entry.
      override="ubuntu24.04-$arch"
      ;;
    *)
      echo "REFUSING: $ID $VERSION_ID ($arch) is not in install-playwright.sh's platform table — extend the table after verifying playwright's fallback for it, then rebuild the VM." >&2
      exit 1
      ;;
  esac

  if [ -n "$override" ]; then
    # Append BOTH keys to the credentials env — they must persist (runtime
    # launches validate too); every user sources the file through ./run
    # setenv. Grep-guarded: a re-run must not duplicate.
    echo "==> platform override: $override (keys appended to the credentials env)"
    grep -q '^PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=' "$creds_env" \
      || printf 'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE="%s"\n' "$override" >> "$creds_env"
    grep -q '^PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=' "$creds_env" \
      || printf 'PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS="1"\n' >> "$creds_env"
  fi

  # Browsers as desmo — the shared cache (PLAYWRIGHT_BROWSERS_PATH) stays
  # desmo-owned exactly as before (self-dispatch below).
  sudo -u desmo -H bash "$0" browsers

  # System deps as root with the creds env sourced LIVE — any override
  # appended above is in effect by construction (no stale-environment bug).
  # install-deps resolves the MAPPED platform's package list; if it silently
  # fails anyway (it exits 0 on "cannot install"), the launch check below
  # turns that into a hard refusal.
  set -a; . "$creds_env"; set +a
  echo "==> playwright chromium system deps ($([ -n "$override" ] && printf 'mapped %s' "$override" || printf 'native'))"
  uv run --no-sync --directory "$maindir" python -m playwright install-deps chromium

  # The real assertion: a headless launch of the installed shell. Missing
  # libs or a bad platform mapping fail HERE, at provision time.
  sudo -u desmo -H bash "$0" verify
}

# ── desmo subcommands (self-dispatched) ─────────────────────────────────────

# Download the headless chromium shell (what the tests launch) into the
# shared cache. uv --no-sync: borrow the venv's interpreter without letting
# uv touch (sync) the desmo-owned venv.
browsers() {
  set -a; . "$creds_env"; set +a
  cd "$maindir"
  uv run --no-sync python -m playwright install chromium --only-shell
}

# Launch verification — the headless shell must actually start.
verify() {
  set -a; . "$creds_env"; set +a
  cd "$maindir"
  if ! uv run --no-sync python - <<'PY'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
print("headless chromium launch OK")
PY
  then
    echo "REFUSING: headless chromium failed to launch after install — missing system deps or a bad platform-table entry (traceback above)." >&2
    exit 1
  fi
}

case "${1:-}" in
  "") main ;;             # root — everything
  browsers) browsers ;;   # desmo — download only
  verify) verify ;;       # desmo — launch check
  *)
    echo "usage: install-playwright.sh [browsers|verify]" >&2
    exit 1
    ;;
esac
