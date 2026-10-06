#!/bin/bash
# install.sh — the PRODUCTION entry: curl|bash it on a fresh VM you
# administer — any cloud Ubuntu 24.04/26.04 (or Debian) instance you ssh
# into as root — and it provisions the whole machine from a published ref
# of this repo. (The local dress rehearsal: `./local-vm provision-blank` +
# `multipass shell`.) ZERO provisioning logic lives here — it
# manufactures the SAME two-file payload the local dev path ships
# (deploy/inside-vm.sh + the seed tarball of tracked files) and execs the
# unchanged provisioner; the only operator input it carries is
# BASE_URL.
#
#   curl -fsSL https://raw.githubusercontent.com/aitchnyu/agent-beta/main/deploy/install.sh \
#     | sudo bash -s -- --base-url https://example.com [--release <tag> | --branch <name>]
#
# User inputs (nothing else — secrets are minted inside, the rest is the
# tracked deploy/template.env):
#   --base-url  url    the public origin, https://host[:port]; DNS must
#                      already point at the VM (omitted → loopback-only,
#                      README § Local VM).
#   --release tag     what to install; default: the latest published
#                     tag, falling back to main when none exist.
#   --branch  name    any branch instead (mutually exclusive).
#
# After the provision's phases: basic self-tests (units active + one
# HTTPS smoke on the site root) + the access steps. The
# full in-VM battery stays a local-test follow-up (deploy/gate.sh gate —
# TESTING ONLY, loopback installs).
#
# PIPE-SAFETY: the entire body below is ONE { … } compound command.
# `bash -s` fed from a pipe reads the script LAZILY — any child that
# touches stdin (apt-get did, during the first live test) eats the
# unread remainder and silently truncates the script. A single compound
# command forces bash to buffer the whole block before executing any of
# it; the trailing `}` is therefore the last line of the file.

set -euo pipefail

# The repo identity — also what gets cloned below. local-vm's `blank`
# printout derives the curl line from this line
# (MAINTAIN-CONSISTENCY vm-payload).
repo_url="https://github.com/aitchnyu/agent-beta.git"
clone_dir=/tmp/desmo-install

{
usage() {
  echo "Usage: curl -fsSL <raw-url>/deploy/install.sh | sudo bash -s -- [--base-url https://host[:port]] [--release tag | --branch name]" >&2
  [[ -n "${1:-}" ]] && echo "  $1" >&2
  exit 1
}

# ── flags ───────────────────────────────────────────────────────────────────
base_url="" branch="" release=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url) [[ $# -ge 2 ]] || usage "--base-url needs a value"; base_url="$2"; shift 2 ;;
    --branch)  [[ $# -ge 2 ]] || usage "--branch needs a value";  branch="$2";  shift 2 ;;
    --release) [[ $# -ge 2 ]] || usage "--release needs a value"; release="$2"; shift 2 ;;
    *) usage "unknown flag: $1" ;;
  esac
done
[[ -n "$branch" && -n "$release" ]] && usage "--branch and --release are mutually exclusive"
base_url="${base_url// /}"
# ONE https origin (scheme + optional port; no wildcards — caddy can't
# ACME-serve them over HTTP-01).
if [ -n "$base_url" ] && ! [[ "$base_url" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?/?$ ]]; then
  usage "--base-url must be ONE https origin, https://host[:port] (got: '$base_url')"
fi

# ── guards ──────────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
  echo "REFUSING: run as root (curl … | sudo bash -s -- …)." >&2
  exit 1
fi
# Fresh-VM-only: the provisioner's own phase-0 guard (generated secrets
# already installed?) refuses a re-provision BEFORE anything mutates —
# no duplicate check here.
export DEBIAN_FRONTEND=noninteractive
deps=()
command -v curl >/dev/null 2>&1 || deps+=(curl)
command -v git  >/dev/null 2>&1 || deps+=(git)
if [ "${#deps[@]}" -gt 0 ]; then
  echo "==> apt-get install: ${deps[*]} (bare image)"
  apt-get update -y
  apt-get install -y "${deps[@]}"
fi

# ── resolve the ref ─────────────────────────────────────────────────────────
if [ -n "$branch" ]; then
  ref="$branch"
elif [ -n "$release" ]; then
  ref="$release"
else
  # The latest published tag, version-sorted (v10 > v9); peeled ^{} lines
  # dropped. No tags published yet → main.
  if ! ref_list="$(git ls-remote --tags --sort=-v:refname "$repo_url" 2>/dev/null)"; then
    echo "REFUSING: cannot reach $repo_url (git ls-remote failed)." >&2
    exit 1
  fi
  ref="$(printf '%s' "$ref_list" \
    | awk -F'\t' '$2 ~ /^refs\/tags\// && $2 !~ /\^\{\}$/ { sub(/^refs\/tags\//, "", $2); print $2; exit }')"
  [ -n "$ref" ] || ref="main"
fi
echo "==> installing ref: $ref ($repo_url)"

# ── payload — the SAME two files the local dev path ships ───────────────────
# umask pinned like local-vm's: the seed tarball carries file/dir modes
# through extraction, and the guest's mode pins assume the 022 base.
umask 022
rm -rf "$clone_dir"
git clone --depth 1 --branch "$ref" "$repo_url" "$clone_dir"
echo "==> seed tarball (tracked files, from the clone)"
(cd "$clone_dir" && git ls-files -z) | tar czf /tmp/desmo-seed.tgz -C "$clone_dir" --null -T -
install -m 755 "$clone_dir/deploy/inside-vm.sh" /tmp/inside-vm.sh

# ── provision — the one exec; its exit code is the verdict ──────────────────
BASE_URL="$base_url" bash /tmp/inside-vm.sh provision

# ── self-tests — the install verdict ────────────────────────────────────────
echo "==> self-tests"
for unit in desmo_granian.service desmo_huey.service caddy redis-server postgresql desmo_pgbackrest.timer; do
  systemctl is-active --quiet "$unit" || { echo "FAILED: $unit is not active" >&2; exit 1; }
done
echo "    units active (granian, huey, caddy, redis, postgres, backup timer)"
# Smoke the origin's hostname on the VM's :443 (an origin port like the
# tunnel's :8000 is the operator's forward); -k only for loopback's
# internal CA. No --base-url → the template's loopback origin.
probe_origin="${base_url:-https://localhost:8000}"
probe_host="${probe_origin#*://}"       # strip the scheme
probe_host="${probe_host%%/*}"          # strip any trailing path
probe_host="${probe_host%%:*}"          # strip the port
url="https://$probe_host/"
case "$probe_host" in
  localhost|127.*|::1) probe() { curl -fsSk -o /dev/null "$url"; } ;;   # -k: the internal-CA cert
  *)                   probe() { curl -fsS -o /dev/null "$url"; } ;;
esac
# One attempt — but granian (Type=simple) needs a beat after phase 11's
# restart before the first request answers; without the settle, the probe
# races the app boot and fails healthy installs.
sleep 3
if ! probe; then
  echo "FAILED: HTTPS smoke on $url." >&2
  case "$probe_host" in
    localhost|127.*|::1) ;;
    *)
      echo "  The install itself is complete — if ACME issuance is still in" >&2
      echo "  flight (caddy retries for hours; check journalctl -u caddy)," >&2
      echo "  re-probe later: curl -fsS -o /dev/null '$url'" >&2
      ;;
  esac
  exit 1
fi
echo "    HTTPS smoke ok ($url)"

# ── access steps + cleanup ──────────────────────────────────────────────────
case "$probe_host" in
  localhost|127.*|::1)
    cat <<'EOF'

Installed (loopback-only — local test mode, no --base-url given). The app
answers on the VM's https://localhost behind the ssh port forward;
access steps: deploy/access-steps.txt (README § Local VM).
EOF
    ;;
  *)
    cat <<EOF

Installed.

Site (public, ACME TLS):
  $base_url
First login (no email/password signup — create the row + a one-time link;
DB-only commands, so plain `desmo` — ./run sources the credentials env):
  desmo djangomanage createuser you@example.com --first-name You --last-name Name --superuser
  desmo djangomanage makeloginlink you@example.com
Operator surface — a shell, not the web:
  desmo pi          # the pi TUI (README § VM)
EOF
    ;;
esac
rm -rf "$clone_dir"
}
