#!/bin/bash
# inside-vm.sh — the WHOLE provisioner: runs AS ROOT inside a FRESH test VM
# (instance "desmo"), driven by ONE exec from ./local-vm (never by
# hand). Build-only: the driver refuses an existing instance, and phase 0
# refuses a VM that already holds generated secrets. One linear function,
# phase-banner'd — read it top to bottom.
#
# Payload — THE manifest: the driver ships exactly TWO files (the phase-10
# rm list below must match this block; local-vm points here and
# keeps no list of its own):
#   /tmp/inside-vm.sh    this script
#   /tmp/desmo-seed.tgz  the tracked working tree → /srv/desmo/main (phase 2);
#                        its deploy/ carries the static env template, the
#                        render templates, and the gate.sh testing battery
#
# All config is the TRACKED deploy/template.env — zero operator inputs.
# Phase 0 validates it straight out of the tarball (before any mutation),
# phase 3 installs it as the credentials env and mints the three machine
# secrets into it.
#
# ── The fs this provision creates/touches (phase in parens) ────────────────
#   /                             users: desmo + the default cloud user joins
#   │                             group desmo (1); ufw 22/tcp only (1)
#   ├── etc/
#   │   ├── credentials/desmo/    750 root:desmo (3)
#   │   │   └── .env.vm           640 root:desmo — the template + minted
#   │   │                         SECRET_KEY/DB_PASSWORD/VAPID (3)
#   │   ├── systemd/system/
#   │   │   ├── desmo_granian.service    rendered 644 (4); enabled (7),
#   │   │   ├── desmo_huey.service       started (11)
#   │   │   ├── desmo_pgbackrest.service   nightly backup shim (4)
#   │   │   └── desmo_pgbackrest.timer     00:00 UTC (4; enable --now 7)
#   │   ├── pgbackrest/
#   │   │   └── pgbackrest.conf   640 root:postgres, stanza `desmo` (4)
#   │   ├── caddy/
#   │   │   ├── Caddyfile         + "import sites/*.caddy" (5, guarded)
#   │   │   └── sites/desmo.caddy the app site, 644 (4)
#   │   ├── redis/redis.conf      + maxmemory block (5, guarded)
#   │   └── profile.d/desmo.sh    login-shell notice (1)
#   ├── usr/local/bin/
#   │   ├── desmo                 `desmo <cmd>` wrapper (1)
#   │   └── fd                    symlink → fdfind (1); uv, pi, node ride
#   │                             apt/npm/NodeSource/caddy repos (1)
#   ├── srv/desmo/                775 desmo:desmo (1)
#   │   ├── main/                 the seed extract, desmo-owned, g+w (2)
#   │   │   ├── dbbackups/        postgres 700 — self-contained pgbackrest
#   │   │   │                     repo (2; stanza-create 6)
#   │   │   ├── .git              first commit = provisioned baseline (8)
#   │   │   ├── .venv, frontend/  uv sync + npm build (9)
#   │   │   └── staticfiles/      collectstatic (9)
#   │   └── playwright-browsers/  shared cache + chromium deps (10)
#   ├── swapfile                  2G (1, guarded) + /etc/fstab line +
#   │                             /etc/sysctl.d/99-swap.conf (1)
#   └── tmp/                      payload + template probe rm'd (10)
#
#   Not fs, same provision: postgres role desmo_user + DBs desmo_db and
#   desmo_db_test + WAL archiving via ALTER SYSTEM (6); git --system
#   safe.directory main + scratch (7); DB migrations (9).
#
# Usage: inside-vm.sh {provision|seed-commit|bootstrap}
#   provision     as ROOT — the one the driver execs (all phases)
#   seed-commit   as desmo — self-dispatched by phase 8
#   bootstrap     as desmo — self-dispatched by phase 9

set -euo pipefail

appdir="/srv/desmo"
maindir="$appdir/main"
seed_deploy="$maindir/deploy"   # templates + gate.sh ride IN the seed
creds_dir="/etc/credentials/desmo"
creds_env="$creds_dir/.env.vm"
# pi CLI version for the npm -g install (lockstep with dev's
# npm install -g @earendil-works/pi-coding-agent).
_PI_NPM_VERSION="0.85.0"

# KEY="value" from an env-format file (first match wins; missing → empty —
# the `|| true` keeps set -e/pipefail from aborting BEFORE the friendly
# refusal paths that consume missing keys).
_envval() { # <key> <file>
  { grep -E "^$1=" "$2" | head -1 | cut -d= -f2- | tr -d '"'; } || true
}

provision() {
  # ── Phase 0/11: guards — payload, template values, VM freshness ────────
  echo "==> [0/11] guards"
  if [ ! -f /tmp/desmo-seed.tgz ]; then
    echo "REFUSING: /tmp/desmo-seed.tgz missing (the driver builds + ships it)." >&2
    exit 1
  fi
  # Probe the static template straight out of the tarball — no extraction,
  # no mutation; a bad template refuses before anything runs. The SAME
  # probed file becomes the credentials env in phase 3.
  template=/tmp/template.env
  if ! tar -xzOf /tmp/desmo-seed.tgz deploy/template.env > "$template" 2>/dev/null; then
    echo "REFUSING: deploy/template.env missing from the seed tarball." >&2
    exit 1
  fi

  # Template value checks — fail-hard. A bad value is a REPO bug (the
  # template is tracked and reviewed; there is no operator input), so these
  # guard drift, not typos. Worker knobs are baked into the units at render
  # (digits only — a `/` or `&` would corrupt the sed).
  local granian_workers granian_threads huey_workers site_hostnames site_names
  granian_workers="$(_envval GRANIAN_WORKERS "$template")"
  granian_threads="$(_envval GRANIAN_THREADS "$template")"
  huey_workers="$(_envval HUEY_WORKERS "$template")"
  if [ -z "$granian_workers" ] || [ -z "$granian_threads" ] || [ -z "$huey_workers" ]; then
    echo "REFUSING: GRANIAN_WORKERS/GRANIAN_THREADS/HUEY_WORKERS must be set explicitly in deploy/template.env (huey needs at least 1 worker)." >&2
    exit 1
  fi
  local knob
  for knob in "$granian_workers" "$granian_threads" "$huey_workers"; do
    if [[ ! "$knob" =~ ^[0-9]+$ ]]; then
      echo "REFUSING: worker knobs must be non-negative integers in deploy/template.env (got: '$knob')." >&2
      exit 1
    fi
  done
  # Huey always runs — 0 workers is not a valid deployment (periodic tasks
  # like the daily pick would silently never run).
  if [ "$huey_workers" -lt 1 ]; then
    echo "REFUSING: HUEY_WORKERS must be at least 1 in deploy/template.env (got: $huey_workers)." >&2
    exit 1
  fi
  # ALLOWED_HOSTS is the single source of truth for BOTH the hosts Django
  # accepts and the caddy site names — derived ONCE here; phase 4 renders
  # from these vars (no second derivation anywhere).
  site_hostnames="$(_envval ALLOWED_HOSTS "$template")"
  if [ -z "$site_hostnames" ]; then
    echo "REFUSING: ALLOWED_HOSTS must be set in deploy/template.env (Django hosts + caddy site names)." >&2
    exit 1
  fi
  site_names="$(printf '%s' "$site_hostnames" | tr ',' ' ' | tr -s ' ' | sed -e 's/^ //' -e 's/ $//' -e 's/ /, /g')"
  if [[ ! "$site_names" =~ ^[A-Za-z0-9._*-]+(, [A-Za-z0-9._*-]+)*$ ]]; then
    echo "REFUSING: ALLOWED_HOSTS must be plain hostnames, comma-separated (got: '$site_hostnames')." >&2
    exit 1
  fi
  # The three machine-secret keys must ship as their @NAME@ placeholders —
  # the mint fills exactly those tokens; anything else (empty included)
  # would ship verbatim, so refuse with the offending lines named.
  local secrets_bad
  secrets_bad="$(grep -E '^(SECRET_KEY|DB_PASSWORD|VAPID_PRIVATE_KEY)=' "$template" \
    | grep -vxF -e 'SECRET_KEY="@SECRET_KEY@"' \
              -e 'DB_PASSWORD="@DB_PASSWORD@"' \
              -e 'VAPID_PRIVATE_KEY="@VAPID_PRIVATE_KEY@"' \
    || true)"
  if [ -n "$secrets_bad" ]; then
    echo "REFUSING: the three machine secrets in deploy/template.env must ship as their @NAME@ placeholders (provision fills them); fix these lines:" >&2
    printf '%s\n' "$secrets_bad" | sed -E 's/=.*/=<not-the-placeholder>/' >&2
    exit 1
  fi
  # Shared browser cache: without the key browsers land per-user and the
  # agent's scratch tests can't find them (drift guard for a template edit).
  if ! grep -qE '^PLAYWRIGHT_BROWSERS_PATH=' "$template"; then
    echo "WARNING: PLAYWRIGHT_BROWSERS_PATH unset in the template — browsers land in per-user caches." >&2
  fi

  # Build-only: REFUSE before any mutation if generated secrets are
  # installed — the seed extract + env install would clobber them. Detection
  # SOURCES the file in a subshell (the consumers' own semantics): quoted,
  # unquoted, or indented hand-rotated values all count. All-three-empty = a
  # half-failed pre-mint run; retrying that is safe — the pre-mint steps are
  # convergent (phase 1's useradd/swap and phase 5's config appends are
  # guarded; extracts and renders overwrite in place). A POST-mint failure
  # leaves secrets installed: this refusal then routes you to
  # ./local-vm delete && ./local-vm provision.
  if [ -f "$creds_env" ] && (
    . "$creds_env"
    [ -n "${SECRET_KEY:-}" ] || [ -n "${DB_PASSWORD:-}" ] || [ -n "${VAPID_PRIVATE_KEY:-}" ]
  ); then
    echo "REFUSING: VM already provisioned ($creds_env holds generated secrets)." >&2
    echo "  In-place re-provision is unsupported" >&2
    exit 1
  fi
  # Pin the umask: dirs this body creates (/etc/pgbackrest,
  # /etc/caddy/sites) and every redirect-written config ride 022 — a
  # stricter caller shell would land e.g. /etc/redis 700 (redis can't
  # traverse). Explicit installs/chmods pin everything else.
  umask 022

  # ── Phase 1/11: machine — users, packages, node, pi, caddy, uv, swap ───
  echo "==> [1/11] machine (users, apt, node, pi, caddy, uv, swap, redis, ufw)"
  echo "    users: desmo (less powerful) + the default cloud user (powerful)"
  # Guarded: a pre-mint retry (see phase 0) re-runs phase 1 — useradd would
  # abort under set -e on the second pass.
  id desmo >/dev/null 2>&1 || useradd --create-home --shell /bin/bash desmo
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

  echo "    apt packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y curl rsync git htop ufw ripgrep fd-find miller pgbackrest \
    postgresql postgresql-client redis-server ca-certificates gnupg
  # fd-find: pi auto-downloads fd to ~/.pi/agent/bin on first launch
  # otherwise; Debian names the binary fdfind, pi wants fd.
  ln -sf /usr/bin/fdfind /usr/local/bin/fd
  # miller (mlr): journal error-log queries per docs/logging.md.

  echo "    node 22 (NodeSource; apt's node is too old for vite/rolldown — the frontend build needs it)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs

  # the operator's agent, run via `desmo pi`; npm global (arch-agnostic).
  # --ignore-scripts: pi needs no install scripts — none should run as root.
  echo "    pi CLI (npm -g, version-pinned)"
  npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@$_PI_NPM_VERSION"

  echo "    caddy (official apt repo)"
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy

  # uv SYSTEM-WIDE — on every user's default PATH.
  echo "    uv system-wide (/usr/local/bin)"
  UV_INSTALL_DIR=/usr/local/bin \
    bash -c 'curl -fsSL https://astral.sh/uv/install.sh | sh'

  echo "    2G swapfile + swappiness (2G RAM absorbs build spikes)"
  # Guarded whole-block: a pre-mint retry hits an active swapfile —
  # fallocate/mkswap/swapon on it would fail, and a second fstab append
  # would duplicate the entry. /proc/swaps is the live truth.
  if ! grep -q '^/swapfile' /proc/swaps; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
  sysctl -w vm.swappiness=10 >/dev/null

  # redis: config lands in phase 5; start it stock.
  echo "    redis (stock; phase 5 appends the maxmemory block)"
  systemctl enable --now redis-server >/dev/null

  echo "    ufw (ssh only — the app rides the tunnel's loopback hop)"
  # 22 = multipass's own channel + the tunnel ride (installs no
  # authorized_keys — README's one-time pubkey step). The forward targets
  # the VM's loopback :443, so 80/443 stay closed to the LAN: localhost
  # only, nothing announced.
  ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null
  ufw --force enable >/dev/null

  # ── Phase 2/11: seed — extract /srv/desmo/main from the tarball ────────
  echo "==> [2/11] seed /srv/desmo/main (tarball from the tracked working tree)"
  install -d -o desmo -g desmo "$maindir"
  tar xzf /tmp/desmo-seed.tgz -C "$maindir"
  # Own the tree as desmo:
  #   - main tree: the agent's user edits it (builds, git resets)
  #   - dbbackups/: PRUNED — stays postgres-owned (pgbackrest runs as
  #     postgres and refuses root); "-path <dir> -prune" is find's
  #     skip, cutting the subtree so the -exec beyond -o never fires
  #     inside it
  find "$maindir" -path "$maindir/dbbackups" -prune -o -exec chown desmo:desmo {} +
  # Group-write the tree (like the enclosing /srv/desmo 775):
  #   - main tree: chown alone leaves 644/755 files — the next build
  #     as the default user dies on desmo-owned dirs without g+w
  #   - dbbackups/: PRUNED — the repo stays mode 700; g+w would open
  #     it to the desmo group
  find "$maindir" -path "$maindir/dbbackups" -prune -o -exec chmod g+w {} +
  # Nightly-backup substrate: dbbackups/ is the self-contained
  # pgbackrest repo (chunks + WAL archive together — copying the one
  # folder carries the whole backup), owned by postgres — every
  # pgbackrest invocation runs as postgres (it refuses root). The
  # stanza is created in phase 6 (needs the phase-4 conf + live pg);
  # the conf and archive_command are phase 4/6's.
  install -d -o postgres -g postgres -m 700 "$maindir/dbbackups"

  # ── Phase 3/11: credentials env — install + mint the machine secrets ───
  echo "==> [3/11] credentials env + machine secrets"
  install -d -o root -g desmo -m 750 "$creds_dir"
  # The phase-0 probe — the SAME bytes that were validated — pinned at
  # birth (root:desmo 640, no umask window); the mint below fills its three
  # @NAME@ placeholders.
  install -o root -g desmo -m 640 "$template" "$creds_env"

  # The three machine secrets, minted exactly once (phase 0 enforced the
  # @NAME@ placeholders, so the tokens await fill here).
  local new_secret new_dbpass new_vapid
  echo "    SECRET_KEY generated"
  new_secret="$(openssl rand -hex 32)"
  echo "    DB_PASSWORD generated"
  new_dbpass="$(openssl rand -hex 32)"
  echo "    VAPID_PRIVATE_KEY generated"
  # The seeded repo's mint — same recipe as run init's deploy/ copy.
  new_vapid="$(bash "$seed_deploy/gen-vapid-b64.sh")"

  # Fill the @NAME@ tokens in place — the .new file is born root:desmo 640
  # (install), awk fills it, and mv swaps it onto the final name carrying
  # that mode; the env file never holds a secret with a wrong mode. Secrets
  # travel via ENVIRON (not argv — no ps exposure), and gsub-in-place keeps
  # each line's surrounding text. Minted values are hex/base64url, so no
  # gsub-special char (`&`, `\`) can appear in a replacement.
  install -o root -g desmo -m 640 /dev/null "$creds_env.new"
  # Exported INSIDE a subshell — awk's ENVIRON needs exports, lets do them locally
  (
    export SECRET_KEY_NEW="$new_secret"
    export DB_PASSWORD_NEW="$new_dbpass"
    export VAPID_PRIVATE_KEY_NEW="$new_vapid"
    awk '
      { gsub(/@SECRET_KEY@/, ENVIRON["SECRET_KEY_NEW"])
        gsub(/@DB_PASSWORD@/, ENVIRON["DB_PASSWORD_NEW"])
        gsub(/@VAPID_PRIVATE_KEY@/, ENVIRON["VAPID_PRIVATE_KEY_NEW"])
        print }
    ' "$creds_env" > "$creds_env.new"
  )
  mv -f "$creds_env.new" "$creds_env"
  # No @TOKEN@ may survive the fill (guards a placeholder/pattern drift
  # becoming a literal "secret").
  if grep -qE '@(SECRET_KEY|DB_PASSWORD|VAPID_PRIVATE_KEY)@' "$creds_env"; then
    echo "REFUSING: a mint placeholder survived the fill" >&2
    exit 1
  fi

  # Source + assert: keys non-empty (guards the generation/rewrite path),
  # DB identity present.
  set -a; . "$creds_env"; set +a
  if [ -z "${SECRET_KEY:-}" ]; then
    echo "REFUSING: SECRET_KEY is empty after generation" >&2
    exit 1
  fi
  if [ -z "${DB_PASSWORD:-}" ]; then
    echo "REFUSING: DB_PASSWORD is empty after generation" >&2
    exit 1
  fi
  if [ -z "${VAPID_PRIVATE_KEY:-}" ]; then
    echo "REFUSING: VAPID_PRIVATE_KEY is empty after generation" >&2
    exit 1
  fi
  if [ -z "${DB_NAME:-}" ] || [ -z "${DB_USER:-}" ]; then
    echo "REFUSING: DB_NAME/DB_USER missing in env" >&2
    exit 1
  fi

  # ── Phase 4/11: config render — seeded templates → final paths ─────────
  echo "==> [4/11] render configs (templates from the seeded deploy/*.in)"
  # Render inputs: knobs + site names were resolved (and validated) in
  # phase 0; only pg_main resolves here — the versioned postgres data dir
  # (Debian paths it per major — /var/lib/postgresql/<v>/main) needs the
  # phase-1 install.
  local pg_main
  pg_main="$(echo /var/lib/postgresql/*/main)"

  # The render — defined at its only phase of use; closes over the phase-0
  # knobs/site names + the pg_main above.
  _render() { # <template-path>
    sed -e "s/@GRANIAN_WORKERS@/$granian_workers/g" \
        -e "s/@GRANIAN_THREADS@/$granian_threads/g" \
        -e "s/@HUEY_WORKERS@/$huey_workers/g" \
        -e "s/@SITE_HOSTNAMES@/$site_names/g" \
        -e "s|@PG_MAIN@|$pg_main|g" "$1"
  }

  # systemd units (worker knobs + site names rendered in). 644, root:root —
  # pinned explicit, same modes the old tree extraction landed.
  _render "$seed_deploy/granian.service.in" > /etc/systemd/system/desmo_granian.service
  _render "$seed_deploy/huey.service.in" > /etc/systemd/system/desmo_huey.service
  _render "$seed_deploy/pgbackrest.service.in" > /etc/systemd/system/desmo_pgbackrest.service
  _render "$seed_deploy/pgbackrest.timer.in" > /etc/systemd/system/desmo_pgbackrest.timer
  chmod 644 /etc/systemd/system/desmo_granian.service \
    /etc/systemd/system/desmo_huey.service \
    /etc/systemd/system/desmo_pgbackrest.service \
    /etc/systemd/system/desmo_pgbackrest.timer

  # pgbackrest.conf — stanza `desmo`, plain unencrypted repo (self-contained
  # dbbackups/), 14-full retention. root:postgres 640 — postgres (the only
  # reader) gets group read.
  install -d -m 755 /etc/pgbackrest
  _render "$seed_deploy/pgbackrest.conf.in" > /etc/pgbackrest/pgbackrest.conf
  chown root:postgres /etc/pgbackrest/pgbackrest.conf
  chmod 640 /etc/pgbackrest/pgbackrest.conf

  # The app site — caddy picks it up via the phase-5 import line.
  install -d -m 755 /etc/caddy/sites
  _render "$seed_deploy/Caddyfile.site.in" > /etc/caddy/sites/desmo.caddy
  chmod 644 /etc/caddy/sites/desmo.caddy

  # ── Phase 5/11: stock configs — mutate the live ones in place ──────────
  echo "==> [5/11] stock configs (redis maxmemory, caddy sites import)"
  # Grep-guarded appends (the safe.directory pattern from phase 7): a
  # pre-mint retry re-runs this phase, and a duplicate import line would
  # fail `systemctl reload caddy` below. The old fetch-host/append/ship-back
  # round trip is gone — the files are right here.
  grep -q '^# BEGIN desmo-vm' /etc/redis/redis.conf \
    || cat "$seed_deploy/redis-append.conf" >> /etc/redis/redis.conf
  grep -q '^import sites/\*\.caddy' /etc/caddy/Caddyfile \
    || printf '\nimport sites/*.caddy\n' >> /etc/caddy/Caddyfile
  # Restart applies the maxmemory cap.
  systemctl restart redis-server

  # ── Phase 6/11: postgres — role, databases, WAL archive, stanza ────────
  echo "==> [6/11] postgres (role + DBs aligned to the env file, WAL archive, stanza)"
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
  # Plain CREATE, no existence checks: the phase-0 guard makes this a
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

  # WAL archiving into the self-contained dbbackups/ repo via ALTER SYSTEM
  # (not file edits). archive_mode needs an instance restart — resolved by
  # name (pg_lsclusters): the postgresql meta unit doesn't re-run instances.
  sudo -u postgres psql -q -c "ALTER SYSTEM SET archive_mode = 'on'"
  sudo -u postgres psql -q -c "ALTER SYSTEM SET archive_command = 'pgbackrest --stanza=desmo archive-push %p'"
  local pg_instance
  pg_instance="$(pg_lsclusters -h | awk 'NR==1 {print $1 "-" $2}')"
  systemctl restart "postgresql@${pg_instance}.service"

  # stanza-create (the phase-2 dbbackups/ dir's other half — needs the
  # phase-4 conf + a live postgres, hence here and not in phase 2).
  sudo -u postgres pgbackrest --stanza=desmo stanza-create

  # ── Phase 7/11: enable units + caddy (started in phase 11) ─────────────
  echo "==> [7/11] enable units + caddy (start happens in phase 11)"
  # Enable only — START happens after the app bootstrap (phase 9/10). The
  # backup pair: the service is a one-line shim into `./run backupdb` (all
  # backup logic lives in ./run). The timer is enable --now — enable alone
  # never activates a unit, and nothing reboots the VM after provisioning
  # (no last-trigger stamp yet → no Persistent catch-up fire).
  systemctl daemon-reload
  systemctl enable "desmo_granian.service" >/dev/null
  systemctl enable "desmo_huey.service" >/dev/null
  systemctl enable --now "desmo_pgbackrest.timer" >/dev/null

  # reload picks up sites/*.caddy (the phase-5 import line).
  systemctl enable caddy >/dev/null
  systemctl reload caddy

  # granian serves /git reading both main and scratch repos; safe.directory
  # exempts them from git's dubious-ownership refusal. Grep-guarded adds
  # avoid the duplicate (--add) and multi-value-overwrite (plain set) errors.
  git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$maindir" \
    || git config --system --add safe.directory "$maindir"
  git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$appdir/scratch" \
    || git config --system --add safe.directory "$appdir/scratch"

  # ── Phase 8/11: first commit — the provisioned baseline ────────────────
  echo "==> [8/11] git init + first commit in /srv/desmo/main"
  # Self-dispatch as desmo (see the seed_commit subcommand at the bottom).
  sudo -u desmo -H bash "$0" seed-commit

  # ── Phase 9/11: bootstrap the app as desmo ─────────────────────────────
  echo "==> [9/11] bootstrap (uv sync, npm build, migrate, collectstatic)"
  sudo -u desmo -H bash "$0" bootstrap

  # ── Phase 10/11: playwright (encapsulated) + /tmp hygiene ──────────────
  echo "==> [10/11] playwright browsers + deps (deploy/install-playwright.sh)"
  # One script owns it all: the platform table (refuses unknown OSes HARD),
  # override keys, browsers into the shared cache, chromium system deps,
  # and a launch verification — a missing lib fails provision right here.
  bash "$seed_deploy/install-playwright.sh"

  # /tmp leftovers — the payload + the phase-0 probe:
  # - desmo-seed.tgz   the repo snapshot tarball
  # - template.env  the probe (config-only, but /tmp is world-readable)
  # - inside-vm.sh     THIS script — open fds survive unlink (bash holds the
  #                    fd; only systemctl calls follow in phase 11)
  rm -f /tmp/desmo-seed.tgz /tmp/template.env /tmp/inside-vm.sh

  # ── Phase 11/11: start services ────────────────────────────────────────
  echo "==> [11/11] start services"
  # Huey's unit always ships (HUEY_WORKERS ≥ 1 is validated in phase 0).
  systemctl restart desmo_granian.service desmo_huey.service
  systemctl restart caddy

  echo "==> provision done (site: localhost — via the ssh forward)"
}

# ── desmo subcommands (self-dispatched by phases 8/9) ─────────────────────

# The first commit marking the provisioned baseline: main/ is its OWN repo
# (the seed ships no .git; /srv/desmo is not one — scratch/ is external).
seed_commit() {
  set -a; . "$creds_env"; set +a
  cd "$maindir"
  git init -q
  # Group-shared: the default cloud user (desmo pi) commits here too —
  # sharedRepository + the chmod fix what init made under the umask.
  git config core.sharedRepository group
  chmod -R g+w .git
  # Author identity via repo config (NOT env — that holds only the
  # committer marker). Blank email by design: git can't auto-derive one
  # here, and without it every commit fails.
  git config user.name "agent"
  git config user.email ""
  git add -A
  git commit -qm 'First commit: provisioned from the repo seed'
}

# The app bootstrap: dependencies, frontend build, migrations, static files.
bootstrap() {
  set -a; . "$creds_env"; set +a
  cd "$maindir"
  export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
  uv sync
  (cd frontend && npm install --no-audit --no-fund && npm run build)
  uv run python manage.py migrate --noinput
  uv run python manage.py collectstatic --noinput --clear
}

case "${1:-}" in
  provision) provision ;;        # root — the one the driver execs
  seed-commit) seed_commit ;;    # desmo — phase 8
  bootstrap) bootstrap ;;        # desmo — phase 9
  *)
    echo "usage: inside-vm.sh {provision|seed-commit|bootstrap}" >&2
    exit 1
    ;;
esac

# MAINTAIN-CONSISTENCY vm-payload — the payload manifest (header) + the
# phase-10 rm list must match what deploy-local-vm.sh actually transfers
