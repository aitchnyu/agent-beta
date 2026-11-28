#!/bin/bash
# install.sh — the PRODUCTION entry: curl|bash it on a fresh VM you
# administer, as root, and it provisions the whole machine from a
# published ref of this repo.
# - Supported: cloud Debian 13 (amd64). Other OSes are untested — phase
#   10's playwright platform table admits debian 13 only.
# - Local dress rehearsal: `./localvm provision-blank` + `./localvm shell`.
# - ZERO provisioning logic lives here — it manufactures the SAME
#   two-file payload the local dev path ships (deploy/inside-vm.sh + the
#   seed tarball of tracked files) and execs the unchanged provisioner.
# - The operator's inputs ride the flags below, all checked before the
#   machine changes.
#
#   args=(
#     --base-url https://example.com
#     --first-name Jane
#     --last-name Doe
#     --email jane@example.com
#     # --google-key 1234-abc.apps.googleusercontent.com --google-secret GOCSPX-…
#     # --release v1
#   )
#   curl -fsSL https://raw.githubusercontent.com/aitchnyu/agent-beta/main/deploy/install.sh \
#     | sudo bash -s -- "${args[@]}"
#
# User inputs (nothing else — secrets are minted inside, the rest is the
# tracked deploy/template.env):
#   --base-url  url    the public origin, https://host[:port]; DNS must
#                      already point at the VM.
#   --first-name, --last-name, --email   the first superuser; a terminal
#                      run (the first run follows) needs all three.
#   --google-key, --google-secret       Google login: both, or neither.
#   --release tag     what to install; default: the latest published
#                     tag, falling back to main when none exist.
#   --branch  name    any branch instead (mutually exclusive).
#   --check-args      check the flags and exit: what the tests drive.
#
# After the provision's phases: basic self-tests (units active + one
# HTTPS smoke on the site root), then — interactive terminals only —
# the first-run setup (desmosetup: one screen for pi's provider, then
# the superuser, Google and the report) and a login as debian. A run
# without a terminal (localvm provision-full) provisions and stops.
# The full in-VM battery stays a local-test follow-up
# (ops.checkframework2 — which itself refuses non-loopback installs: a
# --base-url VM never runs it).
#
# PIPE-SAFETY: the entire body below is ONE { … } compound command.
# `bash -s` fed from a pipe reads the script LAZILY — any child that
# touches stdin (apt-get did, during the first live test) eats the
# unread remainder and silently truncates the script. A single compound
# command forces bash to buffer the whole block before executing any of
# it; the trailing `}` is therefore the last line of the file.

set -euo pipefail

# Wall-clock stamp on every banner — absolute, rounded to the second;
# consecutive banners diff into per-step durations.
_banner() { echo "[$(date +%T)] $*"; }

# The repo identity — also what gets cloned below. localvm's `blank`
# printout derives the curl line from this line
# (MAINTAIN-CONSISTENCY vm-payload).
repo_url="https://github.com/aitchnyu/agent-beta.git"
clone_dir=/tmp/desmo-install

{
usage() {
  echo "Usage: curl -fsSL <raw-url>/deploy/install.sh | sudo bash -s -- --base-url https://host[:port] --first-name <first> --last-name <last> --email <email> [--google-key <key> --google-secret <secret>] [--release tag | --branch name]" >&2
  [[ -n "${1:-}" ]] && echo "  $1" >&2
  exit 1
}

# ── flags ───────────────────────────────────────────────────────────────────
base_url="" branch="" release="" first="" last="" email="" google_key="" google_secret=""
check_args=no
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)      [[ $# -ge 2 ]] || usage "--base-url needs a value";      base_url="$2";      shift 2 ;;
    --first-name)    [[ $# -ge 2 ]] || usage "--first-name needs a value";    first="$2";          shift 2 ;;
    --last-name)     [[ $# -ge 2 ]] || usage "--last-name needs a value";     last="$2";           shift 2 ;;
    --email)         [[ $# -ge 2 ]] || usage "--email needs a value";         email="$2";          shift 2 ;;
    --google-key)    [[ $# -ge 2 ]] || usage "--google-key needs a value";    google_key="$2";     shift 2 ;;
    --google-secret) [[ $# -ge 2 ]] || usage "--google-secret needs a value"; google_secret="$2";  shift 2 ;;
    --branch)        [[ $# -ge 2 ]] || usage "--branch needs a value";        branch="$2";         shift 2 ;;
    --release)       [[ $# -ge 2 ]] || usage "--release needs a value";       release="$2";        shift 2 ;;
    --check-args)    check_args=yes; shift ;;
    *) usage "unknown flag: $1" ;;
  esac
done

# ── arguments: every check comes before the machine changes ─────────────────
# The shapes desmosetup checks too (ops/setup.py); ops/tests/test_install.py
# keeps the two in step.
name_re="^[A-Za-z][A-Za-z'-]{0,49}$"
email_re='^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
client_id_re='^[0-9]+-[A-Za-z0-9]+\.apps\.googleusercontent\.com$'
[[ -n "$branch" && -n "$release" ]] && usage "--branch and --release are mutually exclusive"
[ -n "$base_url" ] || usage "--base-url is needed: https://host[:port]"
base_url="${base_url// /}"
# ONE https origin (scheme + optional port; no wildcards — caddy can't
# ACME-serve them over HTTP-01).
[[ "$base_url" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?/?$ ]] \
  || usage "--base-url must be one https origin, https://host[:port] (got: '$base_url')"
[ -z "$first" ] || [[ "$first" =~ $name_re ]] \
  || usage "--first-name: names are letters, hyphens and apostrophes, starting with a letter (got: '$first')"
[ -z "$last" ] || [[ "$last" =~ $name_re ]] \
  || usage "--last-name: names are letters, hyphens and apostrophes, starting with a letter (got: '$last')"
[ -z "$email" ] || { [[ "$email" =~ $email_re ]] && [ "${#email}" -le 254 ]; } \
  || usage "--email: that does not look like an email address (got: '$email')"
if [ -n "$google_key" ] || [ -n "$google_secret" ]; then
  { [ -n "$google_key" ] && [ -n "$google_secret" ]; } || usage "--google-key and --google-secret go together"
  [[ "$google_key" =~ $client_id_re ]] \
    || usage "--google-key: a Google client key looks like 1234567890-abc123.apps.googleusercontent.com"
  { [ "${#google_secret}" -ge 20 ] && [[ "$google_secret" != *" "* ]]; } \
    || usage "--google-secret: that Google secret looks wrong (Google secrets are about 35 characters, no spaces)"
fi
# A terminal means the first run follows: it needs the first superuser.
if [ -t 1 ]; then
  [ -n "$first" ] || usage "--first-name is needed"
  [ -n "$last" ] || usage "--last-name is needed"
  [ -n "$email" ] || usage "--email is needed"
fi
if [ "$check_args" = yes ]; then
  echo "args ok"
  exit 0
fi

# ── guards ──────────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
  echo "REFUSING: run as root (curl … | sudo bash -s -- …)." >&2
  exit 1
fi
# Fresh-VM-only: the provisioner's own phase-0 guard (a /srv/desmo that
# already exists) refuses a re-provision BEFORE anything mutates —
# no duplicate check here.
export DEBIAN_FRONTEND=noninteractive
deps=()
command -v curl >/dev/null 2>&1 || deps+=(curl)
command -v git  >/dev/null 2>&1 || deps+=(git)
if [ "${#deps[@]}" -gt 0 ]; then
  _banner "==> apt-get install: ${deps[*]} (bare image)"
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
_banner "==> installing ref: $ref ($repo_url)"

# ── payload — the SAME two files the local dev path ships ───────────────────
# umask pinned like localvm's: the seed tarball carries file/dir modes
# through extraction, and the guest's mode pins assume the 022 base.
umask 022
rm -rf "$clone_dir"
git clone --depth 1 --branch "$ref" "$repo_url" "$clone_dir"
_banner "==> seed tarball (tracked files, from the clone)"
(cd "$clone_dir" && git ls-files -z) | tar czf /tmp/desmo-seed.tgz -C "$clone_dir" --null -T -
install -m 755 "$clone_dir/deploy/inside-vm.sh" /tmp/inside-vm.sh

# ── provision — the one exec; its exit code is the verdict ──────────────────
# `if !` (not a bare call): set -e would abort a bare failure instantly,
# verdict-less — this prints the FAILED verdict itself.
if ! BASE_URL="$base_url" bash /tmp/inside-vm.sh provision; then
  echo "FAILED: provision exited non-zero — the VM is incomplete (the phase named above is where it stopped)." >&2
  exit 1
fi

# ── self-tests — the install verdict ────────────────────────────────────────
_banner "==> self-tests"
for unit in desmo_granian.service desmo_huey.service caddy redis-server postgresql desmo_pgbackrest.timer; do
  systemctl is-active --quiet "$unit" || { echo "FAILED: $unit is not active" >&2; exit 1; }
done
echo "    units active (granian, huey, caddy, redis, postgres, backup timer)"
# Smoke the origin's hostname on the VM's :443 (an origin port like :8443
# is the operator's forward, not this machine's); -k only for loopback's
# internal CA.
probe_origin="$base_url"
probe_host="${probe_origin#*://}"       # strip the scheme
probe_host="${probe_host%%/*}"          # strip any trailing path
probe_host="${probe_host%%:*}"          # strip the port
url="https://$probe_host/"
case "$probe_host" in
  # -m 2: a hung connect must not blow the 1s×10 retry budget. -s: the
  # restart race's transient 502s stay off the operator's screen.
  localhost|127.*|::1) probe() { curl -m 2 -fsSk -s -o /dev/null "$url"; } ;;   # -k: the internal-CA cert
  *)                   probe() { curl -m 2 -fsS -s -o /dev/null "$url"; } ;;
esac

# Retry liveness check every 1s up to 10s
attempt=1
until probe; do
  if [ "$attempt" -ge 10 ]; then
    echo "FAILED: HTTPS smoke on $url ($attempt attempts)." >&2
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
  sleep 1
  attempt=$((attempt + 1))
done
echo "    HTTPS smoke ok ($url)"

rm -rf "$clone_dir"

# The finish line — green + bold when the terminal supports it (a piped
# log just gets the plain text).
if [ -t 1 ]; then
  printf '\033[1;32m==> Desmo is provisioned on %s\033[0m\n' "$(hostname)"
else
  echo "==> Desmo is provisioned on $(hostname)"
fi

# Interactive installs end as debian; driven ones exit as before.
# </dev/tty: bash -s's stdin is the curl pipe — instant EOF for su's shell.
if [ -t 1 ]; then
  # The first run, once. sudo, not su: su kills the session on ctrl+c.
  # The flags ride as separate arguments: sudo -i hands them to debian's
  # login shell intact — but drops an empty one, so Google's two come
  # only when they were given.
  _banner "==> first-run setup"
  first_run=(desmosetup --base-url "$base_url" --first-name "$first" --last-name "$last" --email "$email")
  [ -z "$google_key" ] || first_run+=(--google-key "$google_key" --google-secret "$google_secret")
  sudo -n -u debian -i "${first_run[@]}" </dev/tty \
    || _banner "==> first-run setup did not finish — the traceback above says where"
  exec su -l debian </dev/tty
fi
}
