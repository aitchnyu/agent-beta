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
#                   it — units, caddy, redis, creds env), fix
#                   ownership, postgres, enable units
#
# Usage: inside-vm.sh {provision_vm|provision_app}

set -euo pipefail

phase="${1:?usage: inside-vm.sh provision_vm|provision_app}"
[[ "$phase" =~ ^(provision_vm|provision_app)$ ]] || { echo "bad phase: $phase" >&2; exit 1; }

appdir="/srv/desmo"
creds_dir="/etc/credentials/desmo"
creds_env="$creds_dir/.env.vm"
# pi CLI version for the npm -g install (keep in lockstep with dev's
# npm install -g @earendil-works/pi-coding-agent).
_PI_NPM_VERSION="0.85.0"

provision_vm() {
  echo "==> [vm] users: desmo (less powerful) + the default cloud user (powerful)"
  useradd --create-home --shell /bin/bash desmo
  # The DEFAULT cloud user (ubuntu on multipass, debian on Incus) is THE
  # powerful user: cloud-init already grants it full passwordless sudo
  local op_user
  for op_user in ubuntu debian; do
    id "$op_user" >/dev/null 2>&1 && break
  done
  # /srv/desmo is group-desmo-writable so the desmo user runs everything
  # there and the default user (the operator) can edit too; owned by desmo.
  install -d -m775 -o desmo -g desmo "$appdir"
  # The default user joins the desmo GROUP: read access to the shared
  # credentials env (root:desmo 640) and write access to the
  # group-writable /srv/desmo tree.
  usermod -aG desmo "$op_user"
  # The agent commit marker is the GIT_COMMITTER_NAME env var (the shared
  # credentials file) — a global git identity would OVERRIDE env vars, so
  # none is ever set for the committing user.

  # The desmo wrapper — `desmo <cmd…>` == cd /srv/desmo/main && ./run <cmd…>
  # (env sourcing stays in ./run's setenv; written inline by decision, no
  # repo file). /usr/local/bin is on every user's default PATH.
  cat > /usr/local/bin/desmo <<'EOF'
#!/bin/sh
# desmo — run the deployed repo's ./run from anywhere: `desmo pi` is the
# same as cd /srv/desmo/main && ./run pi.
cd /srv/desmo/main || { echo "no /srv/desmo/main (provision the VM first)" >&2; exit 1; }
exec ./run "$@"
EOF
  chmod 755 /usr/local/bin/desmo

  # Login-shell notice (every user): the desmo command is available.
  # /etc/profile.d runs for every login shell.
  cat > /etc/profile.d/desmo.sh <<'EOF'
# desmo notice — login shells (bold yellow)
printf '\n\033[1;33m%s\033[0m\n\033[1;33m%s\033[0m\n\n' \
  "The desmo command is available on this machine: 'desmo <cmd>' runs ./run" \
  "on /srv/desmo/main from anywhere (e.g. 'desmo pi'; commands: 'desmo help')."
EOF
  chmod 644 /etc/profile.d/desmo.sh

  echo "==> [vm] apt packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y curl rsync git htop ufw ripgrep fd-find miller \
    postgresql postgresql-client redis-server ca-certificates gnupg
  # fd-find: pi auto-downloads its fd helper to ~/.pi/agent/bin on first
  # launch otherwise — pre-install so the first ./run pi is offline-clean.
  # Debian names the binary fdfind; pi (and muscle memory) wants fd.
  ln -sf /usr/bin/fdfind /usr/local/bin/fd
  # miller (mlr): journal error-log queries per docs/logging.md.
  # NOTE: node 22 below stays: the frontend build (vite/rolldown) needs it,
  # even though the agent CLI no longer rides npm.

  echo "==> [vm] node 22 (NodeSource; apt's node is too old for vite/rolldown)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs

  # The agent (pi CLI) started via `desmo pi` by the operator — the
  # default cloud user multipass shells into. npm global (node 22 is
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

  echo "==> [vm] ufw (ssh only — the app rides the tunnel's loopback hop)"
  # 22 is multipass's OWN channel (exec/shell over the internal bridge) and
  # the port-forward tunnel's ride (ubuntu@<bridged-ip>; provisioning
  # installs no authorized_keys — the README's one-time pubkey step). The
  # forward's target is the VM's loopback :443, which ufw never filters —
  # so 80/443 stay CLOSED to the LAN: no name is served off-box (localhost
  # only; avahi is gone, nothing is announced).
  ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null
  ufw --force enable >/dev/null
}

provision_app() {
  [[ -f /tmp/tree.tgz ]] || { echo "tree tarball missing: /tmp/tree.tgz (the driver builds + ships it)" >&2; exit 1; }

# tree: extracted at / —
#   /
#   └── etc/
#       ├── credentials/desmo/.env.vm
#       ├── systemd/system/desmo_granian.service
#       ├── systemd/system/desmo_huey.service (always — HUEY_WORKERS ≥ 1 enforced)
#       ├── caddy/Caddyfile + caddy/sites/desmo.caddy
#       └── redis/redis.conf
#   /
#   └── tmp/vm-seed-commit.sh + tmp/vm-bootstrap.sh   (one-shots the driver runs later)
#   (srv/desmo/main/* — including deploy/ — lands via the SEED tarball in
#    the driver's next phase, not via this tree)
# The tree carries CONTENT only; every mode/ownership pin happens in the
# block right after extraction below (see testvm's tree comment).
  # --no-same-owner: everything lands root:root; the ownership the host
  # can't compute (desmo group gid) is fixed right below.
  echo "==> [app] extract the provisioned file tree (built host-side; see testvm's tree comment)"
  tar --no-same-owner -C / -xzf /tmp/tree.tgz

  chmod 644 /etc/caddy/Caddyfile /etc/caddy/sites/desmo.caddy /etc/redis/redis.conf

  # ── file: /etc/credentials/desmo/.env.vm ────────────────────────────────
  # Shared env (every unit's EnvironmentFile). root:desmo 640 — root parses
  # it via EnvironmentFile, desmo-group members (./run as desmo or the
  # default user) read it directly. The sentinel tripwire + DB identity
  # checks follow.
  chown root:desmo "$creds_dir" "$creds_env"
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
  # DB identity (fixed single-app convention: desmo_db / desmo_user).
  set -a; . "$creds_env"; set +a
  [[ -n "${DB_NAME:-}" && -n "${DB_USER:-}" ]] || { echo "REFUSING: DB_NAME/DB_USER missing in env" >&2; exit 1; }
  [[ -n "${DB_PASSWORD:-}" ]] || { echo "REFUSING: DB_PASSWORD is empty — generate with: openssl rand -hex 32" >&2; exit 1; }

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

  # ── files: /etc/systemd/system/{desmo_granian,desmo_huey}.service ──────────
  # Rendered host-side with the env's worker knobs; huey's unit always ships
  # (HUEY_WORKERS ≥ 1 is validated at provisioning). Enable only — the driver
  # STARTS them after the app bootstrap (uv sync/migrate/collectstatic).
  echo "==> [app] systemd units (tree-rendered; enable only — the driver starts them)"
  systemctl daemon-reload
  systemctl enable "desmo_granian.service" >/dev/null
  systemctl enable "desmo_huey.service" >/dev/null

  # ── files: /etc/caddy/Caddyfile + /etc/caddy/sites/desmo.caddy ──────────
  # The import line (stock Caddyfile) + the app site (names from ALLOWED_HOSTS).
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

  echo "==> [app] build done (site: localhost — via the ssh forward)"
}

case "$phase" in
  provision_vm) provision_vm ;;
  provision_app) provision_app ;;
  *) echo "unknown phase: $phase" >&2; exit 1 ;;
esac
