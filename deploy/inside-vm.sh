#!/bin/bash
# inside-vm.sh — build script, runs AS ROOT inside a FRESH test VM.
# Driven by ./testvm provision (never run by hand on the workstation).
# Build-only: provisioning builds a fresh VM (the driver refuses when the
# instance exists) — destroy and rebuild to change anything.
#
# Split into two functions (the driver runs them SEPARATELY, with the file
# tree built on the host in between — see the tree comment in testvm):
#   provision_vm  — machine-level: users, packages, swap, ufw
#   provision_app — extract the tree tarball (ALL config files arrive in
#                   it — units, caddy, redis, sudoers, creds env), fix
#                   ownership, postgres, enable units
#
# Usage: inside-vm.sh {provision_vm|provision_app}

set -euo pipefail

phase="${1:?usage: inside-vm.sh provision_vm|provision_app}"
[[ "$phase" =~ ^(provision_vm|provision_app)$ ]] || { echo "bad phase: $phase" >&2; exit 1; }

appdir="/srv/app"
creds_dir="/etc/credentials/app"
creds_env="$creds_dir/.env.vm"
# pi CLI version for the npm -g install (keep in lockstep with dev's
# npm install -g @earendil-works/pi-coding-agent).
_PI_NPM_VERSION="0.85.0"

provision_vm() {
  echo "==> [vm] users: app (less powerful) + agent (powerful)"
  useradd --create-home --shell /bin/bash app
  useradd --create-home --shell /bin/bash agent
  # agent is THE powerful user (by decision, no dedicated restart rule):
  # full passwordless sudo (tree: /etc/sudoers.d/agent — lands with the
  # tree in provision_app), so the operator/agent working as that user can
  # run systemctl/journalctl non-interactively (the agent's bash tool has
  # no TTY for a password prompt).
  # /srv/app is group-app-writable so the app user runs everything there and
  # agent (the operator) can edit too; owned by app.
  install -d -m775 -o app -g app "$appdir"
  # agent joins the app GROUP: read access to the shared credentials env
  # (root:app 640) and write access to the group-writable /srv/app tree.
  # Not a power escalation: agent already holds full sudo.
  usermod -aG app agent
  # The agent commit marker is the GIT_COMMITTER_NAME env var (the shared
  # credentials file) — a global git identity would OVERRIDE env vars, so
  # none is ever set for the agent user (who commits).
  # Login-shell orientation (banner + repo landing) for the agent user
  # ships as /home/agent/.bash_profile via the TREE in provision_app
  # (deploy/agent-login.txt) — the old ttyd rcfile's replacement.

  echo "==> [vm] apt packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y curl rsync git htop ufw avahi-daemon ripgrep fd-find \
    postgresql postgresql-client redis-server ca-certificates gnupg
  # fd-find: pi auto-downloads its fd helper to ~/.pi/agent/bin on first
  # launch otherwise — pre-install so the first ./run pi is offline-clean.
  # Debian names the binary fdfind; pi (and muscle memory) wants fd.
  ln -sf /usr/bin/fdfind /usr/local/bin/fd
  # NOTE: node 22 below stays: the frontend build (vite/rolldown) needs it,
  # even though the agent CLI no longer rides npm.

  echo "==> [vm] node 22 (NodeSource; apt's node is too old for vite/rolldown)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs

  # The agent (pi CLI) started via `./run pi` by the operator, who shells
  # in over multipass and becomes the agent user. npm global (node 22 is
  # already installed above; arch-agnostic). --ignore-scripts: pi needs
  # no install scripts, and none should run as root.
  echo "==> [vm] pi CLI (npm -g, version-pinned)"
  npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@$_PI_NPM_VERSION"

  echo "==> [vm] caddy (official apt repo)"
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy

  # uv SYSTEM-WIDE (/usr/local/bin — on every user's default PATH)
  echo "==> [vm] uv system-wide (/usr/local/bin)"
  UV_INSTALL_DIR=/usr/local/bin \
    bash -c 'curl -fsSL https://astral.sh/uv/install.sh | sh'

  echo "==> [vm] 2G swapfile + swappiness (2G RAM absorbs build spikes)"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
  sysctl -w vm.swappiness=10 >/dev/null

  echo "==> [vm] redis (config lands later via the tree; start it stock)"
  systemctl enable --now redis-server >/dev/null

  echo "==> [vm] avahi (app.local via the instance hostname)"
  # The single name comes from the hostname claim (instance = `app`) — the
  # one mDNS mechanism macOS/Linux clients resolve reliably. A second name
  # via static hosts was tried and dropped (never announced/defended).
  systemctl enable --now avahi-daemon >/dev/null

  echo "==> [vm] ufw (ssh for multipass exec, http/https; LAN-wide)"
  # 22 is multipass's OWN channel (exec/shell over the internal bridge) —
  # the VM's only login path now; no authorized_keys are installed.
  ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
}

provision_app() {
  [[ -f /tmp/tree.tgz ]] || { echo "tree tarball missing: /tmp/tree.tgz (the driver builds + ships it)" >&2; exit 1; }

# tree: extracted at / —
#   /
#   └── etc/
#       ├── credentials/app/.env.vm
#       ├── systemd/system/app_granian.service
#       ├── systemd/system/app_huey.service    (always — HUEY_WORKERS ≥ 1 enforced)
#       ├── caddy/Caddyfile + caddy/sites/app.caddy
#       ├── redis/redis.conf
#       └── sudoers.d/agent
#   /home/agent/.bash_profile             login banner + repo landing
#   /
#   └── tmp/vm-seed-commit.sh + tmp/vm-bootstrap.sh   (one-shots the driver runs later)
#   (srv/app/main/* — including deploy/ — lands via the SEED tarball in
#    the driver's next phase, not via this tree)
# The tree carries CONTENT only; every mode/ownership pin happens in the
# block right after extraction below (see testvm's tree comment).
  # --no-same-owner: everything lands root:root; the ownership the host
  # can't compute (app group gid) is fixed right below.
  echo "==> [app] extract the provisioned file tree (built host-side; see testvm's tree comment)"
  tar --no-same-owner -C / -xzf /tmp/tree.tgz

  chmod 644 /etc/caddy/Caddyfile /etc/caddy/sites/app.caddy /etc/redis/redis.conf

  # ── file: /etc/credentials/app/.env.vm ────────────────────────────────
  # Shared env (every unit's EnvironmentFile). root:app 640 — root parses
  # it via EnvironmentFile, app-group members (./run as app/agent) read
  # it directly. The sentinel tripwire + DB identity checks follow.
  chown root:app "$creds_dir" "$creds_env"
  chmod 750 "$creds_dir"
  chmod 640 "$creds_env"

  # Sentinel tripwire from the landed env — generic scan of every
  # KEY=value line (the host-side ./testvm check already refused these;
  # this re-check guards the extraction path itself). The env's key set
  # isn't fixed, so no key list is assumed.
  local sentinel_lines
  sentinel_lines="$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=.*DANGEROUSLYUNSET' "$creds_env" || true)"
  if [[ -n "$sentinel_lines" ]]; then
    echo "REFUSING: these env values are still DANGEROUSLYUNSET — fill them in (secrets: openssl rand -hex 32):" >&2
    printf '%s\n' "$sentinel_lines" >&2
    exit 1
  fi
  # DB identity (fixed single-app convention: app_db / app_user).
  set -a; . "$creds_env"; set +a
  [[ -n "${DB_NAME:-}" && -n "${DB_USER:-}" ]] || { echo "REFUSING: DB_NAME/DB_USER missing in env" >&2; exit 1; }
  [[ -n "${DB_PASSWORD:-}" ]] || { echo "REFUSING: DB_PASSWORD is empty — generate with: openssl rand -hex 32" >&2; exit 1; }

  # ── file: /etc/sudoers.d/agent ──────────────────────────────────────────
  # agent's full passwordless sudo (shipped via the tree; content built
  # host-side in testvm). Validate syntax before anything can rely on it.
  chmod 0440 /etc/sudoers.d/agent
  visudo -cf /etc/sudoers.d/agent >/dev/null

  # ── file: /home/agent/.bash_profile ────────────────────────────────────
  # Login-shell banner + repo landing (deploy/agent-login.txt via the
  # tree). agent's home exists since provision_vm's useradd.
  chown agent:agent /home/agent/.bash_profile
  chmod 644 /home/agent/.bash_profile

  # ── file: /etc/redis/redis.conf ───────────────────────────────────────
  # Stock config + the maxmemory/noeviction block (appended host-side).
  # Restart applies the cap; nothing uses redis before the app boots, so
  # the stock-config window from provision_vm is harmless.
  systemctl restart redis-server

  # ── postgres: role + databases (from the env's DB_* values) ──
  # Not a tree file: the role and the two databases (app + test) are
  # created directly in the running postgres, not shipped as files.
  echo "==> [app] postgres (role + DBs aligned to the env file)"
  systemctl enable --now postgresql >/dev/null

  # Wait for the cluster for 60s. (Arithmetic stays out of (( )) so set -e cannot abort the loop itself.)
  local pg_tries=0
  until sudo -u postgres pg_isready -q >/dev/null 2>&1; do
    pg_tries=$((pg_tries + 1))
    if [ "$pg_tries" -ge 60 ]; then
      echo "REFUSING: postgres not ready after 60s" >&2
      exit 1
    fi
    sleep 1
  done

  # Create the login role and the two databases (app + its _test sibling,
  # owned by the role) — the VM is always fresh, nothing exists yet.
  # Values ride as psql variables: %I/%L quote the identifiers/literals
  # inside the SQL (a quote in the password cannot break or inject) and
  # never appear in ps argv. \gexec runs each formatted statement.
  sudo -u postgres psql -tAq -v ON_ERROR_STOP=1 \
    -v db_user="$DB_USER" -v db_pass="$DB_PASSWORD" \
    -v db_name="$DB_NAME" -v db_test="${DB_NAME}_test" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN CREATEDB PASSWORD %L', :'db_user', :'db_pass')
\gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
\gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db_test', :'db_user')
\gexec
SQL

  # ── files: /etc/systemd/system/{app_granian,app_huey}.service ──────────
  # Rendered host-side with the env's worker knobs; huey's unit always ships
  # (HUEY_WORKERS ≥ 1 is validated at provisioning). Enable only — the driver
  # STARTS them after the app bootstrap (uv sync/migrate/collectstatic).
  echo "==> [app] systemd units (tree-rendered; enable only — the driver starts them)"
  systemctl daemon-reload
  systemctl enable "app_granian.service" >/dev/null
  systemctl enable "app_huey.service" >/dev/null

  # ── files: /etc/caddy/Caddyfile + /etc/caddy/sites/app.caddy ──────────
  # The import line (stock Caddyfile) + the app.local site (the app).
  # Reload picks up sites/*.caddy.
  echo "==> [app] caddy (site + import line arrived via the tree)"
  systemctl enable caddy >/dev/null
  systemctl reload caddy

  # granian serves /git url after reading both main and scratch repos.
  # Git refuses repos owned by another user ("dubious ownership")
  # Registering both fixed paths in the system gitconfig exempts
  # them from the ownership check.
  git config --system safe.directory "$appdir/main"
  git config --system --add safe.directory "$appdir/scratch"

  echo "==> [app] build done (site: app.local)"
}

case "$phase" in
  provision_vm) provision_vm ;;
  provision_app) provision_app ;;
  *) echo "unknown phase: $phase" >&2; exit 1 ;;
esac
