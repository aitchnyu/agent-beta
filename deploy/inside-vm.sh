#!/bin/bash
# inside-vm.sh — build script, runs AS ROOT inside a FRESH test VM, driven
# by ./testvm provision (never by hand). Both phases are BUILD-ONLY: the
# driver refuses an existing instance, and provision_app refuses a VM that
# already holds generated secrets. Two functions so the driver can build
# the tree on the host in between:
#   provision_vm  — users, packages, swap, ufw
#   provision_app — extract tree, generate secrets, postgres, enable units
#
# Usage: inside-vm.sh {provision_vm|provision_app}

set -euo pipefail

phase="${1:?usage: inside-vm.sh provision_vm|provision_app}"
[[ "$phase" =~ ^(provision_vm|provision_app)$ ]] || { echo "bad phase: $phase" >&2; exit 1; }

appdir="/srv/desmo"
creds_dir="/etc/credentials/desmo"
creds_env="$creds_dir/.env.vm"
# pi CLI version for the npm -g install (lockstep with dev's
# npm install -g @earendil-works/pi-coding-agent).
_PI_NPM_VERSION="0.85.0"

provision_vm() {
  echo "==> [vm] users: desmo (less powerful) + the default cloud user (powerful)"
  useradd --create-home --shell /bin/bash desmo
  # THE powerful user: cloud-init grants the default cloud user (ubuntu on
  # multipass, debian on Incus) full passwordless sudo.
  local op_user
  for op_user in ubuntu debian; do
    id "$op_user" >/dev/null 2>&1 && break
  done
  # group-desmo-writable: desmo runs everything here, the operator edits too.
  install -d -m775 -o desmo -g desmo "$appdir"
  # default user joins the desmo group → reads the creds env (root:desmo 640).
  usermod -aG desmo "$op_user"
  # commit marker = GIT_COMMITTER_NAME env (creds file); a global git
  # identity would OVERRIDE env vars — so none is ever set here.

  # `desmo <cmd…>` == cd /srv/desmo/main && ./run <cmd…>; env sourcing
  # stays in ./run's setenv. /usr/local/bin is on every user's PATH.
  cat > /usr/local/bin/desmo <<'EOF'
#!/bin/sh
# desmo — run the deployed repo's ./run from anywhere: `desmo pi` is the
# same as cd /srv/desmo/main && ./run pi.
cd /srv/desmo/main || { echo "no /srv/desmo/main (provision the VM first)" >&2; exit 1; }
exec ./run "$@"
EOF
  chmod 755 /usr/local/bin/desmo

  # Login-shell notice (every user); /etc/profile.d runs for every login shell.
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
  apt-get install -y curl rsync git htop ufw ripgrep fd-find miller pgbackrest \
    postgresql postgresql-client redis-server ca-certificates gnupg
  # fd-find: pi auto-downloads fd to ~/.pi/agent/bin on first launch
  # otherwise; Debian names the binary fdfind, pi wants fd.
  ln -sf /usr/bin/fdfind /usr/local/bin/fd
  # miller (mlr): journal error-log queries per docs/logging.md.

  echo "==> [vm] node 22 (NodeSource; apt's node is too old for vite/rolldown — the frontend build needs it)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs

  # the operator's agent, run via `desmo pi`; npm global (arch-agnostic).
  # --ignore-scripts: pi needs no install scripts — none should run as root.
  echo "==> [vm] pi CLI (npm -g, version-pinned)"
  npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@$_PI_NPM_VERSION"

  echo "==> [vm] caddy (official apt repo)"
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy

  # uv SYSTEM-WIDE — on every user's default PATH.
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
  # 22 = multipass's own channel + the tunnel ride (installs no
  # authorized_keys — README's one-time pubkey step). The forward targets
  # the VM's loopback :443, so 80/443 stay closed to the LAN: localhost
  # only, nothing announced.
  ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null
  ufw --force enable >/dev/null
}

provision_app() {
  [[ -f /tmp/tree.tgz ]] || { echo "tree tarball missing: /tmp/tree.tgz (the driver builds + ships it)" >&2; exit 1; }

  # Build-only: REFUSE before any mutation if generated secrets are
  # installed — extract would clobber them. Detection SOURCES the file in
  # a subshell (the consumers' own semantics): quoted, unquoted, or
  # indented hand-rotated values all count. All-three-empty = a
  # half-failed pre-generation run; retrying that is safe.
  if [[ -f "$creds_env" ]] && (
    . "$creds_env"
    [[ -n "${SECRET_KEY:-}" || -n "${DB_PASSWORD:-}" || -n "${VAPID_PRIVATE_KEY:-}" ]]
  ); then
    echo "REFUSING: VM already provisioned ($creds_env holds generated secrets)." >&2
    echo "  In-place re-provision is unsupported" >&2
    exit 1
  fi

# tree: extracted at / —
#   /
#   └── etc/
#       ├── credentials/desmo/.env.vm
#       ├── systemd/system/desmo_granian.service
#       ├── systemd/system/desmo_huey.service (always — HUEY_WORKERS ≥ 1 enforced)
#       ├── systemd/system/desmo_pgbackrest.service + .timer (nightly backup)
#       ├── caddy/Caddyfile + caddy/sites/desmo.caddy
#       ├── redis/redis.conf
#       └── pgbackrest/pgbackrest.conf
#   /
#   └── usr/local/lib/desmo/gen-vapid-b64.sh (the VAPID mint executable)
#   /
#   └── tmp/vm-seed-commit.sh + tmp/vm-bootstrap.sh   (one-shots the driver runs later)
#   (srv/desmo/main/* — including deploy/ — lands via the SEED tarball,
#    not this tree; modes/ownership are pinned right after extraction)
  # --no-same-owner: everything lands root:root; the desmo group gid is
  # pinned right below.
  echo "==> [app] extract the provisioned file tree (built host-side; see testvm's tree comment)"
  tar --no-same-owner -C / -xzf /tmp/tree.tgz

  chmod 644 /etc/caddy/Caddyfile /etc/caddy/sites/desmo.caddy /etc/redis/redis.conf

  # ── file: /etc/credentials/desmo/.env.vm ────────────────────────────────
  # Shared env, every unit's EnvironmentFile. testvm refuses pre-filled
  # host values, so the three keys land EMPTY and are minted exactly once.
  local new_secret new_dbpass new_vapid
  echo "    SECRET_KEY generated"
  new_secret="$(openssl rand -hex 32)"
  echo "    DB_PASSWORD generated"
  new_dbpass="$(openssl rand -hex 32)"
  echo "    VAPID_PRIVATE_KEY generated"
  # tree-shipped mint — same recipe as run init's deploy/ copy.
  new_vapid="$(/usr/local/lib/desmo/gen-vapid-b64.sh)" || exit 1

  # Dir + landing file are pinned BEFORE any secret exists: install mints
  # the .new file root:desmo 640 at birth (no umask window), awk fills it,
  # and mv swaps it onto the final name carrying that mode — the env file
  # itself never holds a secret with a wrong mode.
  chown root:desmo "$creds_dir" "$creds_env"
  chmod 750 "$creds_dir"
  chmod 640 "$creds_env"
  install -o root -g desmo -m 640 /dev/null "$creds_env.new"
  # Exported INSIDE a subshell — awk's ENVIRON needs exports, lets do them locally
  (
    export SECRET_KEY_NEW="$new_secret"
    export DB_PASSWORD_NEW="$new_dbpass"
    export VAPID_PRIVATE_KEY_NEW="$new_vapid"
    awk '
      /^SECRET_KEY=/        { print "SECRET_KEY=\"" ENVIRON["SECRET_KEY_NEW"] "\""; next }
      /^DB_PASSWORD=/       { print "DB_PASSWORD=\"" ENVIRON["DB_PASSWORD_NEW"] "\""; next }
      /^VAPID_PRIVATE_KEY=/ { print "VAPID_PRIVATE_KEY=\"" ENVIRON["VAPID_PRIVATE_KEY_NEW"] "\""; next }
      { print }
    ' "$creds_env" > "$creds_env.new"
  )
  mv -f "$creds_env.new" "$creds_env"

  # Source + assert: keys non-empty (guards the generation/rewrite path),
  # DB identity present.
  set -a; . "$creds_env"; set +a
  [[ -n "${SECRET_KEY:-}" ]] || { echo "REFUSING: SECRET_KEY is empty after generation" >&2; exit 1; }
  [[ -n "${DB_PASSWORD:-}" ]] || { echo "REFUSING: DB_PASSWORD is empty after generation" >&2; exit 1; }
  [[ -n "${VAPID_PRIVATE_KEY:-}" ]] || { echo "REFUSING: VAPID_PRIVATE_KEY is empty after generation" >&2; exit 1; }
  [[ -n "${DB_NAME:-}" && -n "${DB_USER:-}" ]] || { echo "REFUSING: DB_NAME/DB_USER missing in env" >&2; exit 1; }

  # ── file: /etc/redis/redis.conf ───────────────────────────────────────
  # stock + maxmemory block (appended host-side); restart applies the cap.
  systemctl restart redis-server

  # ── postgres: role + databases (from the env's DB_* values) ──
  # not tree files — created in the running postgres.
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

  # Role + the app/_test databases, owned by the role. %I/%L quoting (a
  # quote in the password cannot inject); \gexec runs each statement.
  # Plain CREATE, no existence checks: the guard above makes this a
  # fresh-VM-only path, and an already-existing role or database (created
  # by hand between provisions) must FAIL LOUDLY here — not silently
  # diverge from the minted password.
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

  # ── pgbackrest: WAL archiving (PITR + restore consistency) ───────────────
  # ALTER SYSTEM (not file edits): archive_command hands every WAL
  # segment to pgbackrest's repo — the same self-contained dbbackups/
  # folder. archive_mode needs a restart to take effect; restart the
  # INSTANCE by its resolved name (pg_lsclusters: version + cluster) —
  # a glob only matches loaded units, and the dummy postgresql meta
  # unit doesn't re-run instances.
  sudo -u postgres psql -q -c "ALTER SYSTEM SET archive_mode = 'on'"
  sudo -u postgres psql -q -c "ALTER SYSTEM SET archive_command = 'pgbackrest --stanza=desmo archive-push %p'"
  local pg_instance
  pg_instance="$(pg_lsclusters -h | awk 'NR==1 {print $1 "-" $2}')"
  systemctl restart "postgresql@${pg_instance}.service"
  # conf: root:postgres 640 — postgres (the only reader) gets group read.
  chown root:postgres /etc/pgbackrest/pgbackrest.conf
  chmod 640 /etc/pgbackrest/pgbackrest.conf

  # ── files: /etc/systemd/system/{desmo_granian,desmo_huey}.service ──────────
  # tree-rendered worker knobs; enable only — the driver STARTS them after
  # the app bootstrap (uv sync/migrate/collectstatic). The backup pair
  # (service + timer) rides the same tree: the service is a one-line
  # shim into `./run backupdb` (all backup logic lives in ./run). The
  # timer is enable --now — enable alone never activates a unit, and
  # nothing reboots the VM after provisioning (no last-trigger stamp
  # yet → no Persistent catch-up fire).
  echo "==> [app] systemd units (tree-rendered; enable only — the driver starts them)"
  systemctl daemon-reload
  systemctl enable "desmo_granian.service" >/dev/null
  systemctl enable "desmo_huey.service" >/dev/null
  systemctl enable --now "desmo_pgbackrest.timer" >/dev/null

  # ── files: /etc/caddy/Caddyfile + /etc/caddy/sites/desmo.caddy ──────────
  # import line + site from the tree; reload picks up sites/*.caddy.
  echo "==> [app] caddy (site + import line arrived via the tree)"
  systemctl enable caddy >/dev/null
  systemctl reload caddy

  # granian serves /git reading both main and scratch repos; safe.directory
  # exempts them from git's dubious-ownership refusal. Grep-guarded adds
  # avoid the duplicate (--add) and multi-value-overwrite (plain set) errors.
  git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$appdir/main" \
    || git config --system --add safe.directory "$appdir/main"
  git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$appdir/scratch" \
    || git config --system --add safe.directory "$appdir/scratch"

  echo "==> [app] build done (site: localhost — via the ssh forward)"
}

case "$phase" in
  provision_vm) provision_vm ;;
  provision_app) provision_app ;;
  *) echo "unknown phase: $phase" >&2; exit 1 ;;
esac
