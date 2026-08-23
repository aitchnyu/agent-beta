# VM provisioning: multipass test server for app1

> ## Decision update (2026-08-19): no CA trust, ever
> Clicking through the browser's self-signed-cert warning is the supported
> mode; provisioning no longer prints or prescribes CA-import steps (the
> historical mentions below predate this). The app uses no HSTS/service
> workers, so nothing breaks. A previously imported CA can be removed with
> `sudo security remove-trusted-cert -k /Library/Keychains/System.keychain
> /tmp/app1-root.crt` (macOS) if desired.
>
> Same day: `./run backupvm` was REMOVED (user decision). `deprovisionvm` no
> longer gates on a backup stamp and takes no `--force`; deleting the VM is
> plainly destructive and the rescue steps (ssh + pg_dump) are documented in
> its comment instead. Historical backupvm mentions below predate this.

> ## As-built note (2026-08-18, after the live deploy)
> Built and converged on a real multipass VM (Ubuntu 26.04 arm64). Trust this
> note where it and the plan below differ.
> - **Access model changed: no `.local` site.** Google OAuth validates
>   redirect hosts against the Public Suffix List (guava `InternetDomainName`)
>   and rejects `<appname>.local` — not a registrable domain. sslip.io
>   (IP-derived public name) was wired, then dropped. Final: **Caddy serves
>   `localhost` only**; the Mac browses `https://localhost:8443` through an
>   ssh tunnel (`ssh -N -L 8443:localhost:443 app1`) — Google exempts
>   localhost from the TLD rule, and the origin is stable across VM IP
>   changes. `ssh/80/443` LAN exposure is moot; the tunnel is the only path.
> - **Machine name = `app1`** (multipass instance/hostname). provisionvm
>   installs the Mac-side alias `Host app1 → HostName app1.local User deploy`
>   into `~/.ssh/config` (idempotent), so everything says `ssh app1`.
> - **huey 3.3.2 renamed `runhuey` → `run_huey`** — fixed in the unit's
>   ExecStart AND the Mac's `./run hueydev` (same latent bug).
> - **opencode unit needs five pre-created home dirs** in ReadWritePaths:
>   `~/.opencode` (session bootstrap writes `.gitignore` there — EROFS 500s
>   on `POST /session` without it), `~/.config/opencode`, `~/.cache/opencode`,
>   `~/.local/share/opencode`, `~/.local/state`. A ReadWritePaths entry
>   pointing at a missing dir fails the unit with 226/NAMESPACE.
> - **`djangoproject/asgi.py` now wraps the app** in granian's
>   `wrap_asgi_with_proxy_headers(trusted_hosts="127.0.0.1")` — caddy
>   forwards `X-Forwarded-Proto`, granian ignores it by default, and allauth
>   then builds `http://localhost` OAuth redirect URIs → Google
>   `redirect_uri_mismatch`. Inert in dev (runserver is WSGI).
> - **Provider credentials are a manual step**: copy the Mac's
>   `~/.local/share/opencode/auth.json` to the VM (same path, user deploy,
>   mode 600) and restart `app1-opencode` — without it the daemon 500s every
>   prompt with "Model not found: zai-coding-plan/glm-5.2" (unauthenticated
>   providers' models don't resolve). Not automated (secrets).
> - **VM `.env` is converged to localhost-only**: `ALLOWED_HOSTS=localhost`,
>   `CSRF_TRUSTED_ORIGINS=https://localhost:8443` (inside-vm.sh rewrites only
>   those two lines). `addgoogleoauth` runs over ssh; Google console
>   redirect URI: `https://localhost:8443/accounts/google/login/callback/`.
> - **Firefox needs the Caddy root CA imported into its own NSS store**
>   (Settings → Certificates → Authorities); the macOS keychain import
>   covers Safari/Chrome/curl only.
> - **Playwright Firefox: no ubuntu-26.04-arm64 build** — `playwright
>   install` fails non-fatally; browser tests stay on the Mac.
> - **`exclude-newer` rot**: the relative `"7 days"` cutoff eventually
>   excludes a pinned dep from any full uv re-resolve (hit with
>   inertia-django 2.0.0) — now an absolute timestamp in pyproject.toml.
> - Driver details as-built: repo seed is a **tarball over `multipass
>   transfer`** (rsync-over-multipass is unreliable), templates stage into
>   `/tmp/provision/` inside the VM, granian offloads `/static` itself
>   (`--static-path-route/--static-path-mount` → `main/staticfiles`).
> - **Stale-session handling (post-rebuild UX)**: a browser holding a
>   pre-rebuild localStorage session id poisoned every action (prompt 500s,
>   delete/abort toasts with raw daemon JSON, Stop wedged, Reset disabled
>   while streaming). Fixes shipped 2026-08-19: proxy treats daemon
>   NotFoundError on abort/delete as idempotent success
>   (`{"ok": true, "already": true}`) and passes transcript 404 through as
>   404 (not 502); prompt_async failures emit an SSE error frame with
>   `code: "session_not_found"`; the transport classifies "gone" as terminal
>   (no 120s recovery stall), drops the stored id, and auto-retries the
>   message once on a fresh session; Stop aborts the client stream when the
>   daemon can't idle-close it; Reset is no longer disabled while streaming
>   (it's the unwedge button); page-load transcript 404 clears the stale id.
> - **SSE buffering under ASGI (major)**: chats showed nothing until the turn
>   ended (Stop/continue), and `permission.asked` cards never rendered
>   mid-turn. Root cause: Django 6's `_set_streaming_content` classifies
>   `streaming_content` via `iter(value)` FIRST; a sync generator takes the
>   sync path, and `StreamingHttpResponse.__aiter__` then materialises it with
>   `sync_to_async(list)(...)` — the WHOLE stream buffers until the generator
>   completes. Server-independent (granian and uvicorn both reproduced; a bare
>   ASGI app streamed fine). WSGI runserver iterates natively, so dev never
>   showed it. Fix in `djangoapp/views/opencode.py`: `_AsyncStreamAdapter`
>   wraps the sync SSE generator for ASGI requests only (`isinstance(request,
>   ASGIRequest)`), is async-ONLY (a `__iter__` would reclassify it sync —
>   regression-tested), and pulls each chunk via
>   `sync_to_async(next, thread_sensitive=False)` so a blocking SSE read
>   doesn't serialize all other sync views onto asgiref's single sensitive
>   thread. Verified live: session frame at t≈3s, deltas trickling while the
>   turn is open, through caddy → granian → Django.
> - **VM clock was 2h53m behind** (multipass + chrony NTS reached sync but
>   never stepped) — broke apt (`Release file not valid yet`) and TLS sanity.
>   Fix: `sudo chronyc makestep`. Recreate recipe should watch for this.
> - **opencode npm cache**: unit sets `npm_config_cache=/srv/<appname>/.npm`
>   (default `~/.npm` sits on the read-only home → background plugin-install
>   retries every few minutes burn CPU forever).
> - Deployed smoke-green: HTTPS 200 through the tunnel (CA trusted), SSE
>   agent proxy, huey consumer up, sourcemaps 404, sudoers restart rule,
>   Google login + superuser promoted, session create 200 / prompt 204.

## Goal
Provision an arm64 Linux VM (multipass on the Mac) that runs the whole app —
web (HTTPS), agent (opencode), background tasks (huey), Postgres, Redis — so the
**entire edit → test → deploy loop happens on the VM** and the Mac is just a
browser + SSH client. Browsed at `https://localhost:8443` over an ssh tunnel,
driven as `ssh <appname>` (see As-built: Google OAuth rejects `.local` names,
so the site is localhost-only). Provisioned by an idempotent script in this
repo, recreatable at will, with history rescue (`backupvm`) before any
teardown.

## Current state (analysis done 2026-08-18)

- App is Django 6 + WSGI/ASGI (`djangoproject/asgi.py` exists, unused), Postgres
  hard dep, Redis hard dep (client-error rate limiter fails closed + Huey via
  `REDIS_URL`), Inertia+Vue frontend built by Vite into
  `djangoapp/static/djangoapp`.
- The agent view (`djangoapp/views/opencode.py`) is an SSE proxy
  (`StreamingHttpResponse`, `text/event-stream`) → the app server must be ASGI;
  sync gunicorn workers would pin one worker per agent stream. Server of
  record: **granian** (Rust core, single dep, lighter than uvicorn; no extras
  needed — access log is off by default).
- `run` script owns all operator entrypoints (`init`, `dev`, `checkscratch`,
  `createscratch`, `mergescratch`, …) — `provisionvm`/`backupvm`/`deprovisionvm`
  join it. Two Mac-isms need Linux fixes: `open` in `coverage()`, `lsof`
  assumption in `opencode()`.
- No `granian` dependency in `pyproject.toml` yet; no `STATIC_ROOT`
  (`collectstatic` never needed — dev serves from app static dirs); no
  `CSRF_TRUSTED_ORIGINS` (HTTPS login POSTs need it).
- Everything else (nginx? mkcert? docker?) — deliberately absent: Caddy `tls
  internal` replaces mkcert; apt replaces containers.

## Decisions (locked)

- **VM host = multipass**, arm64 Ubuntu **26.04** (fallback `24.04` — script
  takes the release as a flag; nothing depends on the release). Launched
  **bridged** (`--network en0`) so Avahi/mDNS advertises `<appname>.local` from
  the VM; macOS resolves `.local` natively, IP changes are absorbed.
- **Resources: 1G RAM hard cap + 2G swapfile** (multipass has no ballooning;
  npm builds will swap, accepted). htop installed. Default disk.
- **Parameterized app name**: `./run provisionvm <appname>` templates
  `/srv/<appname>`, `<appname>-granian`/`-huey`/`-opencode` units, and the
  Caddy site — one VM can host app2 later the same way.
- **Layout**: `/srv/<appname>/{main,scratch}` (FHS served-data home; keeps
  `ProtectHome=yes` unit hardening possible). Scratch shares main's Postgres DB,
  exactly like the Mac loop today.
- **Services (systemd)**: `<appname>-granian` — `granian --interface asgi
  --no-ws` on 127.0.0.1:8000, entry `djangoproject.asgi:application`, no
  reload extras (locked restart-on-deploy; Django's own sync-to-async
  threadpool handles sync views + SSE generators under ASGI);
  `<appname>-huey` — `run_huey -w 2` (huey 3.x renamed it from `runhuey`);
  `<appname>-opencode` — `opencode serve`
  with cwd `/srv/<appname>` (parent of main/, so the scratch edit-permission
  rules keep matching).
- **Going live = restart on deploy**: `mergescratch` on the VM ends with
  `sudo systemctl restart <appname>-granian <appname>-huey` — granted by a
  passwordless sudoers rule for exactly that command (all three unit names,
  no wildcards). Watchers were considered and rejected as the primary
  mechanism: mergescratch is the single authoritative deploy event, a watcher
  can fire mid-rsync (half-copied tree), and one mechanism covers both
  services. (Both servers ship dev-grade reload — uvicorn `--reload` built in,
  granian behind its `[reload]` extra; huey has nothing — would need a
  `app1-huey-reload.path` systemd path unit. Bolt-on later if live-editing
  inside main/ is ever wanted, not part of this build.)
- **Edge = Caddy**: `tls internal`, `reverse_proxy 127.0.0.1:8000` with
  `flush_interval -1` (unbuffered agent SSE), `*.map` under
  `/static/djangoapp/` denied (sourcemap rule). Mac trusts Caddy's root CA once
  per VM lifetime (provision prints the scp + `security add-trusted-cert`
  commands — must be re-run after every recreate: new CA).
- **Infra = apt, localhost-only**: postgres (`<dbname>` + test DB, user with
  CREATEDB — Django's test runner creates `test_*` DBs), redis (`maxmemory`
  capped — TODO note), caddy, avahi, ufw (22/80/443 only). **Node from
  NodeSource 22** (apt's Node is too old for vite/rolldown), `uv` + opencode
  per-user for the `deploy` user.
- **Code moves once**: initial seed at provision = rsync repo (incl. `.git`)
  Mac → `/srv/<appname>/main`, `.env` scp'd once and **never** overwritten by
  provision/mergescratch. After that the VM's `.git` is the **only** history —
  no GitHub remote; `backupvm` is the safety net.
- **Tests on the VM**: full loop runs there (`checkscratch`, `checkall`);
  Playwright + Firefox + headless deps installed (slow on 1G, accepted).
- **Env on the VM**: `DEBUG=False`, `ALLOWED_HOSTS=localhost`,
  `CSRF_TRUSTED_ORIGINS=https://localhost:8443` (converged by inside-vm.sh —
  the tunnel origin), localhost DB/Redis. Google OAuth: register
  `https://localhost:8443/accounts/google/login/callback/` in the Google
  console; `addgoogleoauth` run once on the VM over ssh.

## Phased checklist

### Phase 1 — repo-side prep (works on the Mac first)
- [ ] `pyproject.toml` — add `uvicorn` dependency.
- [ ] `djangoproject/settings.py` — add `STATIC_ROOT` (env-driven, default
      `BASE_DIR / "staticfiles"`); add `CSRF_TRUSTED_ORIGINS` from env
      (comma-separated, like `ALLOWED_HOSTS`).
- [ ] `run` — Linux fixes: `coverage()` `open` → `command -v open || xdg-open`;
      `opencode()` port check falls back to `ss -ltn` when `lsof` is absent.
- [ ] `.env.example` — document the new vars (`STATIC_ROOT`, optional
      `CSRF_TRUSTED_ORIGINS`).

### Phase 2 — deploy/ scaffolding in the repo (full manifest of what lands on the VM)

Repo side — `@APPNAME@`/`@DBNAME@` placeholders, sed-rendered at provision time:

```
deploy/
  provision-vm.sh      # Mac driver (./run provisionvm wraps it)
  inside-vm.sh         # converge script, runs as root INSIDE the VM (idempotent)
  granian.service.in    huey.service.in   opencode.service.in
  Caddyfile.site.in    restart.sudoers.in
```

**1. `/etc/systemd/system/@APPNAME@-granian.service`**

```ini
[Unit]
Description=@APPNAME@ granian (ASGI)
After=network.target postgresql.service redis-server.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/srv/@APPNAME@/main
ExecStart=/srv/@APPNAME@/main/.venv/bin/granian --interface asgi --no-ws \
  --host 127.0.0.1 --port 8000 djangoproject.asgi:application
Restart=always
RestartSec=3
# .env is loaded by python-dotenv inside settings — no systemd EnvironmentFile.
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/srv/@APPNAME@
PrivateTmp=yes
MemoryMax=256M

[Install]
WantedBy=multi-user.target
```

ExecStart points **into `main/.venv`** (created by `uv sync` at seed/deploy) —
avoids `~/.local/bin` PATH and uv-cache problems under `ProtectHome`. No
reload extras (locked decision: mergescratch restarts); access log is off by
default; `--no-ws` drops websocket handling the app doesn't use.

**2. `/etc/systemd/system/@APPNAME@-huey.service`**

```ini
[Unit]
Description=@APPNAME@ huey consumer
After=network.target postgresql.service redis-server.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/srv/@APPNAME@/main
ExecStart=/srv/@APPNAME@/main/.venv/bin/python manage.py runhuey -w 2
Restart=always
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/srv/@APPNAME@
PrivateTmp=yes
MemoryMax=128M

[Install]
WantedBy=multi-user.target
```

**3. `/etc/systemd/system/@APPNAME@-opencode.service`**

```ini
[Unit]
Description=@APPNAME@ opencode daemon (agent)
After=network.target

[Service]
User=deploy
Group=deploy
# cwd = parent of main/ so scratch/ and main/ are both inside the worktree
# (same rule as ./run opencode on the Mac)
WorkingDirectory=/srv/@APPNAME@
ExecStart=/usr/local/bin/opencode serve --hostname 127.0.0.1 --port 4196
Environment=OPENCODE_CONFIG_DIR=/srv/@APPNAME@/main/agentconfig
Environment=OPENCODE_CONFIG=/srv/@APPNAME@/main/agentconfig/opencode.json
Restart=always
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
# read-only /home; punch holes for opencode's own state dir (~/.local/share/opencode)
ProtectHome=read-only
ReadWritePaths=/srv/@APPNAME@ /home/deploy/.local/share/opencode
PrivateTmp=yes
MemoryMax=160M

[Install]
WantedBy=multi-user.target
```

opencode installs **system-wide to `/usr/local/bin`** (provision copies the
per-user install there) — otherwise `ProtectHome` hides the binary. Config
ships with the repo (`main/agentconfig/`), so it deploys with the code.

**Memory budget sanity (1G cap)**: granian 256M + huey 128M + opencode 160M
+ postgres ~150M + redis 128M + caddy ~30M + base system ≈ 900M steady;
swap absorbs npm-build spikes.

**4. `/etc/caddy/Caddyfile`** — one site block per app (appended per app):

```
@APPNAME@.local {
	tls internal
	# sourcemaps must never reach clients (README contract)
	@maps path /static/djangoapp/*.map
	respond @maps 404
	reverse_proxy 127.0.0.1:8000 {
		flush_interval -1   # unbuffered SSE for the agent chat
	}
}
```

**5. `/etc/sudoers.d/@APPNAME@-restart`** (0440, root:root) — two exact
command strings (sudoers matches literally; mergescratch restarts the first):

```
deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart @APPNAME@-granian.service @APPNAME@-huey.service, /usr/bin/systemctl restart @APPNAME@-granian.service @APPNAME@-huey.service @APPNAME@-opencode.service
```

**6. Postgres** — no config-file edits: Ubuntu defaults (scram on localhost,
listen 127.0.0.1) are already right. Provision creates:
- role `@DBNAME@` LOGIN PASSWORD … **CREATEDB** (Django's test runner creates
  `test_@DBNAME@` itself)
- DB `@DBNAME@` (shared by main/ and scratch/), DB `@DBNAME@_test`.

**7. `/etc/redis/redis.conf`** — two lines only:
- `maxmemory 128mb`
- `maxmemory-policy noeviction` (queue safety: huey queue + rate-limiter keys
  must never be LRU-evicted; the cap just bounds RAM)

**8. ufw** — default deny incoming / allow outgoing; allow `OpenSSH`, `80`, `443`.

**9. swap** — `/swapfile` 2G (fallocate → mkswap → swapon + fstab line);
`vm.swappiness=10` via `/etc/sysctl.d/99-swap.conf`.

**10. avahi** — apt install + enable (multipass already sets hostname =
instance name, so `@APPNAME@.local` advertises automatically; no avahi config
edits).

**11. `/srv/@APPNAME@/main/.env`** (scp'd once at seed, never overwritten):
`DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS=@APPNAME@.local`,
`CSRF_TRUSTED_ORIGINS=https://@APPNAME@.local`, `DB_*` (localhost),
`REDIS_URL=redis://127.0.0.1:6379/0`, `TIME_ZONE`.

**12. Mac side (printed by provisionvm, not generated)**: ssh-config stanza
(`Host @APPNAME@` / `HostName @APPNAME@.local` / `User deploy`) and the two
Caddy-root-CA trust commands.

### Phase 3 — `./run provisionvm <appname>` (Mac-side driver)
- [ ] `multipass launch --name <appname> --network en0 --memory 1G --disk 20G
      26.04` (skip if instance exists; `--release` flag, default 26.04).
- [ ] `multipass transfer` deploy/ files in; `multipass exec` `inside-vm.sh`:
      apt (postgresql, redis, caddy, avahi-daemon, htop, ufw, firefox +
      headless libs), NodeSource 22, per-user `uv` for `deploy` (opencode
      installed per-user then copied to `/usr/local/bin` — see unit 3),
      2G swapfile, `/srv/<appname>` chown, DBs + CREATEDB user, redis
      `maxmemory`, units + sudoers + Caddy + ufw.
- [ ] Seed **only if `/srv/<appname>/main` is empty**: rsync repo from Mac
      (incl. `.git`), scp `.env`.
- [ ] First run only: `uv sync`, `npm ci && npm run build`, `migrate`,
      `collectstatic`, `playwright install firefox`, enable+start units.
- [ ] Print the macOS trust steps (scp caddy root.crt +
      `security add-trusted-cert`) and the ssh-config stanza
      (`Host <appname>` → `HostName <appname>.local User deploy`).

### Phase 4 — VM-side run-script integration + README
- [ ] `mergescratch` — when on the VM (detect: no `en0`/multipass marker), end
      with `sudo systemctl restart <appname>-granian <appname>-huey`.
- [ ] `collectstatic` folded into the deploy path (mergescratch post-step on
      the VM; Vite build already lands in `djangoapp/static/`, but
      `STATIC_ROOT` must be refreshed for granian).
- [ ] README — new **"VM (test server)"** section after Quick start:

      ## VM (test server)

      The whole loop can run on a Linux VM (multipass) instead of the Mac;
      the Mac becomes just a browser + ssh client. One command provisions it
      (bridged network, 1G RAM + swap, postgres/redis/caddy, `/srv/<appname>`,
      systemd units `<appname>-{granian,huey,opencode}`):

      ```bash
      ./run provisionvm app1     # idempotent; prints the ssh-config + CA-trust
                                 # steps to run on the Mac once
      ```

      Then `https://app1.local` (agent chat included, SSE over HTTPS) and
      `ssh app1.local`. **Everything happens on the VM**: createscratch →
      agent edits `scratch/` → checkscratch → mergescratch (restarts the
      services; changes live immediately). Commits live in the VM's `.git` —
      it is the only copy, so:

      ```bash
      ./run backupvm app1        # rsync main/ incl. .git + pg_dump → Mac
      ./run deprovisionvm app1   # refuses without a fresh backupvm
      ```

      Recreate = `backupvm` → `deprovisionvm` → `provisionvm` (re-seeds from
      the backup) → re-trust the new Caddy CA (commands reprinted). Details:
      `prompts/20260818-vm-provisioning-multipass.md`.

- [ ] README **Commands** list — add `provisionvm`, `backupvm`,
      `deprovisionvm` to the comma list.
- [ ] README **Quick start** — one pointer line: "Prefer a VM instead of
      local services? See [VM (test server)](#vm-test-server)."
- [ ] README **Logging** section — unchanged (granian's `_granian` logger
      flows through the root handler → NDJSON, same contract).

### Phase 5 — lifecycle commands
- [ ] `./run backupvm <appname>` — rsync `main/` (incl. `.git`, excluding
      `.venv`/`node_modules`/caches) + `pg_dump` to a Mac-side dir.
- [ ] `./run deprovisionvm <appname>` — refuses without a backupvm this
      session (override `--force`); then `multipass delete` + `purge`.
- [ ] Recreate recipe documented: `backupvm` → `deprovisionvm` → `provisionvm`
      (seed finds empty `/srv`, restores history) → re-trust Caddy CA.

### Phase 6 — validate
- [ ] Fresh provision end-to-end green: `https://<appname>.local` loads, agent
      chat streams (SSE) over HTTPS, ssh `deploy@<appname>.local` works.
- [ ] Re-run `provisionvm` on the healthy VM — converges, no destructive
      steps, `.env` untouched.
- [ ] On-VM loop: `createscratch` → edit → `checkscratch` → `mergescratch` →
      services restart, change live.
- [ ] `checkall` passes on the VM (incl. Playwright/Firefox).
- [ ] Recreation drill: `backupvm` → `deprovisionvm` → `provisionvm` → git
      history intact, CA re-trusted, app up.
- [ ] Redis respects maxmemory; `htop` shows swap behavior within the 1G cap.

## Out of scope
- GitHub remote / CI (VM's `.git` is the only history, by decision).
- Docker/containerized Postgres/Redis (apt-native, by decision).
- Memory ballooning (multipass doesn't support it; swap is the accepted fix).
- Production hardening beyond unit sandboxing + ufw (this is a test VM).
- Multi-VM orchestration (one VM, potentially multiple apps via the
  parameterized name).

---

# Part 2 — Env files, secrets, and provisioning rework

> ## Decision update (2026-08-20, later): no sslip, no converge, one-time login keys
> Implemented same evening; supersedes the sslip/tunnel-adjacent and
> converge decisions below.
> - **sslip + static IP removed** (`VM_IP` key gone): the site is
>   `<appname>.local` (avahi/mDNS) served directly over LAN HTTPS with the
>   click-through internal CA. Bridged launch is plain DHCP.
> - **Build-or-destroy**: `provision_local_vm` REFUSES when the instance
>   exists — no converge path anywhere. The credentials env installs
>   unconditionally (never-clobber/diff-note logic deleted). To apply
>   changes: `delete_local_vm` → rebuild.
> - **Google OAuth is out of the VM story**: `.local` isn't registrable, so
>   VM login is `manage.py makeloginlink <email>` → one-time
>   `/login-for-test/by-key/<key>/` URL (`TestLoginKey` model: SHA-256-hashed
>   key at rest, atomic single redemption via select_for_update, 15-min
>   expiry, expired-row sweep on issue). Not DEBUG-gated — the unguessable
>   single-use key IS the gate. `addgoogleoauth` remains dev-only.
> - Google-redirect/PSL deliberations (sslip, 127.0.0.1.sslip.io, fake.com
>   interception, static-IP prediction) remain below as history.

> Status: PLAN AGREED (2026-08-20, via one-by-one Q&A). Supersedes Part 1
> and the as-built note above wherever they differ (sslip replaces
> localhost/tunnel, underscore service names, env-file system, Caddy
> static). Implementation has NOT started.

## Goal
One env-file system for dev and VM: root-level `.env`/`.env.vm` (from
matched `.example` templates) carrying **every** key, consumed without
python-dotenv — dev via the `run` script shell-sourcing, VM via a single
shared systemd `EnvironmentFile` under `/etc/credentials/<appname>/`.
Provisioning splits into `provision_vm()` + `provision_app()`, driven by
`./run provision_local_vm` / `delete_local_vm`. Access flips from the
ssh-tunnel/localhost model to a **static-IP sslip.io name served directly
over HTTPS** (Google-OAuth-legal). Static assets move from granian to
Caddy. Agent commits as "Opencode Agent" with no email.

## Current state
- Env today: `main/.env` (dev, python-dotenv in settings) and
  `deploy/env.vm.example` → `deploy/env.vm` (VM, staged into
  `/srv/app1/main/.env`, also dotenv). Layouts differ; keys scattered
  (`OPENCODE_PROVIDER`/`OPENCODE_MODEL_ID` in app env; `CSRF_TRUSTED_ORIGINS`
  env knob; no auth/model keys).
- Services: dash-named `app1-granian/huey/opencode`; granian serves
  `/static` itself (`--static-path-*` → `main/staticfiles`); Caddy site is
  `localhost`-only behind `ssh -N -L 8443:localhost:443`.
- Provisioning: `deploy/provision-vm.sh` (driver) + `deploy/inside-vm.sh`
  (monolithic converge); `run` exposes `provisionvm`/`deprovisionvm`
  (backupvm already removed). SSH alias resolves via avahi (`app1.local`).
- DB identity hardcoded in places as `instant`/`instant_test`; unit
  `restart.sudoers.in` pins dash names; `_vm_livereload` derives app prefix
  from the sudoers filename.
- opencode auth: manual scp of `~/.local/share/opencode/auth.json`;
  binaries (1.18.x Mac / 1.18.18 VM) support `OPENCODE_AUTH_CONTENT`.
- Running `app1` VM predates all of this — to be **rebuilt fresh**.

## Decisions (locked)

### Env files
- Root-level, dot-prefixed: templates **`.env.example`** + **`.env.vm.example`**
  with **identical section layouts**; filled copies `.env` / `.env.vm`
  (gitignored). All keys present in all four files; keys that don't apply in
  a context are present-but-commented with a note.
- `SECRET_KEY` and `DB_PASSWORD` default to the sentinel **`DANGEROUSLYUNSET`**
  in the examples — **fail hard** in BOTH `settings.py` (refuse to boot) and
  `inside-vm.sh` (refuse to provision). Generation command
  `openssl rand -hex 32` documented next to the keys in the examples AND in
  README (agents must be able to find it).
- `OPENCODE_AUTH_CONTENT` (full auth JSON — opencode env contract, read-only
  for static API keys) + `OPENCODE_PROVIDER` + `OPENCODE_MODEL` in **both**
  envs (dev too — replaces reliance on `~/.local/share/opencode/auth.json`).
  Replaces the old `OPENCODE_MODEL_ID` key.
- DB naming by **convention via env values only**: `DB_NAME=<appname>_db`,
  `DB_USER=<appname>_user`. Provision neither forces nor refuses on
  mismatch — the env file is the single source of truth (plus the matching
  `test_` DB / CREATEDB user as today).
- Git identity via env: `GIT_AUTHOR_NAME`/`GIT_COMMITTER_NAME`=
  "Opencode Agent"; `GIT_AUTHOR_EMAIL`/`GIT_COMMITTER_EMAIL` empty (valid —
  commits carry no address). Works for every inherited git process
  including fresh `scratch/` repos. Provision ensures NO global git
  identity exists on the VM (local config would override env vars).
- VM knobs: `GRANIAN_WORKERS` (default 1), `GRANIAN_THREADS` (default 1),
  `HUEY_WORKERS` (default 2; **0 = the huey unit is not enabled/started**).
- `VM_IP`: static bridged address (see network section). Empty/commented →
  DHCP + LAN-IP auto-detect fallback (documented as unstable across DHCP
  changes).

### No python-dotenv
- Dependency removed. Dev: `run`'s `setenv()` does `set -a; . ./.env;
  set +a` before every managed process (runserver/hueydev/opencode/tests/
  djangomanage). Shell-sourcing semantics accepted and documented
  (plain quoted values only). Sweep for dotenv assumptions: settings,
  tests, `manage.py`, docs, `.env copy` tab artifact.
- VM: **all three units** get
  `EnvironmentFile=/etc/credentials/@APPNAME@/.env.vm` (root:root 600,
  staged once by provision). `main/.env` disappears from the VM entirely.
  Note for tests: Django test runner inherits env via `run` too.

### Network & access (supersedes the localhost/tunnel model)
- **sslip-only**: Caddy serves `app1.<ip-dashes>.sslip.io` on 443, direct
  LAN, **no tunnel, no localhost name**. TLS stays `tls internal`
  (click-through warning is the supported mode — Let's Encrypt cannot issue
  for sslip names).
- Static IP via `VM_IP` in `.env.vm` → `multipass launch --network
  en0,mode=manual,ip=$VM_IP/24`. **Ping-check the address before every
  provision run; any answer = abort** with guidance (pick outside the
  router's DHCP pool). Rebuild-stable: same `.env.vm` → same IP → same
  sslip name → Google console redirect URI is write-once.
- Fallback when `VM_IP` empty: DHCP + detect (NAT-subnet-filtered), sslip
  name derived at converge time.
- ssh alias: `Host app1 → HostName $VM_IP User deploy` (no avahi/mDNS
  dependency). ufw stays LAN-wide (22/80/443) — accepted.
- **`CSRF_TRUSTED_ORIGINS` env key removed**: settings derives origins as
  plain `https://<host>` for every `ALLOWED_HOSTS` entry. No port
  special-cases (the tunnel is gone).

### Static files
- Caddy serves `/static/*`: `handle` + `root` at `main/staticfiles` +
  `file_server`; **immutable long-cache headers** for content-hashed
  assets; `*.map` deny stays in Caddy. granian drops `--static-path-*`
  flags (pure app server). `collectstatic` still runs at deploy
  (`_vm_livereload` unchanged in that respect).

### Services & scripts
- Service names switch to **underscores**: `app1_granian`, `app1_huey`,
  `app1_opencode` — units, sudoers rule (exact restart strings, huey
  included only when enabled), `_vm_livereload` marker derivation updated.
- `deploy/inside-vm.sh` restructured into **`provision_vm()`** (machine:
  apt, postgres, redis, caddy, deploy user, swap, ufw, avahi-agnostic) and
  **`provision_app()`** (per-app: `/srv/<appname>`, credentials env file,
  DBs, units, sudoers, Caddy site, seed).
- `run` exposes **`provision_local_vm <appname>`** (provision_vm then
  provision_app; idempotent create-or-converge; stages `.env.vm` into
  `/etc/credentials` on first run; installs/refreshes ssh alias; prints the
  sslip access URL + Google console redirect URI) and
  **`delete_local_vm <appname>`** (delete + purge, removes the ssh alias,
  checks for `/etc/credentials` residue). These REPLACE
  `provisionvm`/`deprovisionvm`.
- Only CLI params: `<appname>` (+ rare `--release`). Everything else lives
  in `.env.vm`.

### Docs
- README: copy `.env.vm.example` → `.env.vm`; entropy commands; sslip URL
  as the access story; old tunnel instructions removed.
- INSTRUCTIONS.md: agents must **rename any legacy `deploy/env.vm` /
  `.env_vm` to root `.env.vm`** before provisioning.
- Multi-app sweep: grep for hardcoded `instant`/`app1`/dash-unit names
  across `run`, `deploy/`, `asgi.py`, `manage.py`, README commands.

### Rollout
- **Fresh rebuild**: `delete_local_vm` the current app1, provision via the
  new pipeline. DB test data is throwaway; `addgoogleoauth` re-run after
  rebuild with the sslip callback URI. New root `.env.vm` **regenerates all
  secrets from scratch** (old `deploy/env.vm` deleted, nothing carried
  over).

## Phased checklist

### Phase 1 — env templates + settings
- [ ] Root `.env.example` + `.env.vm.example` (identical layouts, all keys,
      context-inapplicable commented, `DANGEROUSLYUNSET` sentinels +
      `openssl rand -hex 32` notes).
- [x] `settings.py`: DANGEROUSLYUNSET fail-hard; drop python-dotenv usage;
      derive `CSRF_TRUSTED_ORIGINS` from ALLOWED_HOSTS (plain https://host);
      read `OPENCODE_MODEL`/`OPENCODE_PROVIDER` (retire `OPENCODE_MODEL_ID`).
- [x] Remove python-dotenv from pyproject + lock; sweep all dotenv
      references (code, tests, docs).

### Phase 2 — run script
- [x] `setenv()` shell-sources root `.env` (`set -a; . ./.env; set +a`).
- [x] `provision_local_vm` / `delete_local_vm` (replace provisionvm /
      deprovisionvm); ping-check logic; ssh-alias management.
- [x] `_vm_livereload` + scratch excludes adjusted for underscore units and
      new layout.

### Phase 3 — deploy/ restructure
- [x] `inside-vm.sh` → `provision_vm()` + `provision_app()` (+ shared
      helpers); consume `.env.vm` for ALL values (DB names, workers, IP);
      DANGEROUSLYUNSET tripwire; huey-0 disable path; no global git identity.
- [x] Units: underscore names, shared
      `EnvironmentFile=/etc/credentials/@APPNAME@/.env.vm`, granian without
      static flags, opencode keeps XDG holes + npm cache env.
- [x] `restart.sudoers.in` regenerated for underscore names.
- [x] `Caddyfile.site.in`: sslip site address (rendered from VM_IP or
      detection), static `handle` + immutable cache + `*.map` deny.
- [x] Driver (`provision-vm.sh`): static-IP launch flag, stages root
      `.env.vm` → `/etc/credentials/<appname>/.env.vm`, prints sslip URL.

### Phase 4 — docs
- [x] README: env-file workflow, entropy commands, sslip access, service
      names, new run commands.
- [x] INSTRUCTIONS.md: legacy env rename rule.
- [x] Multi-app hardcode sweep (`instant`, `app1`, dash units).

### Phase 5 — rollout & validation
- [ ] Fresh `.env.vm` (all-new secrets, VM_IP chosen outside DHCP pool).
- [ ] `delete_local_vm app1` → `provision_local_vm app1` green end-to-end.
- [ ] `https://app1.<ip>.sslip.io/` serves; static via Caddy with cache
      headers; `*.map` 404; SSE streams (ASGI adapter intact).
- [ ] Google console: add sslip callback URI; `addgoogleoauth` on VM;
      login round-trip (CSRF derivation proves out).
- [ ] `OPENCODE_AUTH_CONTENT` path: daemon authenticates with NO
      `auth.json` file present.
- [ ] Agent commit shows author "Opencode Agent" with no email (incl. from
      a fresh scratch/ repo).
- [ ] `HUEY_WORKERS=0` variant: huey unit absent/disabled, rest healthy.
- [ ] Re-run `provision_local_vm` on the healthy VM — converges, env file
      untouched, ping-check passes.

### Phase 6 — decision-update work (2026-08-20 later; done same evening)
- [x] `TestLoginKey` model (`djangoapp/models/login_key.py`): SHA-256 key
      hash at rest, `issue`/`redeem`, atomic one-time redemption, expired
      sweep; migration 0020.
- [x] `login_for_test_by_key` view + `/login-for-test/by-key/<key>/` URL;
      404 on unknown/used/expired; redirect to LOGIN_REDIRECT_URL.
- [x] `makeloginlink` command: email lookup (iexact, 0/>1 guards),
      `--minutes`, `--base-url`, prints one-time URL.
- [x] Tests (`djangoapp/tests/test_login_keys.py`): 7 green.
- [x] sslip + VM_IP + ping-check removed from driver/inside-vm/Caddyfile;
      site = `<appname>.local`.
- [x] Build-or-destroy: driver refuses on existing instance; env installs
      unconditionally; converge/clobber-check code deleted.
- [x] `.env.example`/`.env.vm.example`/README/INSTRUCTIONS updated
      (no VM_IP, `.local` access, makeloginlink login, Google OAuth
      dev-only).

---

# Part 3 — ttyd console, single-app VM, /agent removal

> ## Decision update (2026-08-21, post-build): console rides app.local:7000
> - `console.local` is DEAD: avahi static-hosts entries (and a held
>   `avahi-publish -R` record) are never announced/defended like hostname
>   claims, and macOS empirically refused to resolve the second name even
>   after cache flushes — while `app.local` (the hostname claim) works on
>   every rebuild. One hostname, two ports:
>   **`https://app.local/`** (app) + **`http://app.local:7000/`** (ttyd
>   console). ufw opens 7000; CONSOLE_URL/printouts/docs updated; the
>   avahi-statics code is deleted from provision_vm.
> - The console port is **plain HTTP**: scheme-less typing
>   ("app.local:7000") defaults to http:// and a TLS listener 400s that
>   (no auto-redirect on non-standard ports; caddy dual-protocol same-port
>   sniffing proved unreliable). LAN-trusted + auth-less by decision, so
>   TLS there buys nothing; the app itself stays HTTPS on 443.
> - **Ubuntu's packaged `ttyd.service` is disabled + masked** in
>   provision_vm: apt auto-enables it (root, `-O login` PAM gate) and it
>   steals port 7681 from our console_ttyd unit.
> - **granian flag correction**: this granian version spells it
>   `--blocking-threads`, not `--threads` (unit template fixed).

> ## Decision update (2026-08-21, during implementation): no restart rule
> - The dedicated passwordless `systemctl restart` sudoers rule is GONE
>   (`deploy/restart.sudoers.in` deleted, provision step removed,
>   `_vm_livereload` no longer restarts — it runs collectstatic and prints
>   the restart command).
> - The `console` user instead gets full `NOPASSWD: ALL` sudo
>   (`/etc/sudoers.d/console`): it is the powerful user by design, and the
>   agent's bash tool has no TTY for a password prompt. The operator/agent
>   restarts services explicitly:
>   `sudo systemctl restart app_granian app_huey`.
>
> ## Places the <appname> parameterization lived (swept to fixed `app`)
> Recorded per request — where multi-app assumptions were removed:
> - `run`: `provision_local_vm <appname>` / `delete_local_vm <appname>`
>   args (now argless); `_vm_livereload` derived the unit prefix from the
>   sudoers FILENAME (`ls /etc/sudoers.d/*-restart`) — now the fixed
>   `/etc/credentials/app/.env.vm` marker + hardcoded unit names;
>   `setenv()`'s VM glob `/etc/credentials/*/.env.vm` (first-match) — now
>   the fixed path.
> - `deploy/inside-vm.sh`: `<appname>` CLI arg + validation;
>   `/srv/$appname`; `/etc/credentials/$appname/`; unit names
>   `$appname_*`; sudoers `/etc/sudoers.d/$appname-restart`; Caddy site
>   `$appname.caddy` + `@APPNAME@.local` address token.
> - `deploy/provision-vm.sh`: multipass instance name; seed tarball
>   destination `/srv/<appname>/main`; ssh alias `Host <appname>`;
>   printout URLs.
> - `deploy/granian.service.in` / `huey.service.in` /
>   `opencode.service.in` (deleted): `@APPNAME@` path/credential tokens.
> - `deploy/Caddyfile.site.in`: `@APPNAME@.local` site address.
> - `.env.vm.example`: `ALLOWED_HOSTS="app1.local"`, `DB_NAME="app1_db"` /
>   `DB_USER="app1_user"` (convention `<appname>_db`), ssh comments
>   `ssh app1 'cd /srv/app1/main …'`.
> - `makeloginlink`: base-url fallback already used ALLOWED_HOSTS[0]
>   (unchanged — env-driven, not appname-driven).
> - README: every `app1` mention (commands, ssh examples, paths).
> - `run init`'s DB creation: was hardcoded `instant`, then `$DB_NAME`
>   (env-driven — unaffected by this sweep).

> Status: PLAN AGREED (2026-08-21, via one-by-one Q&A). Supersedes Part 2
> wherever they differ (no opencode service, no multi-app
> parameterization, new users, ttyd console). Implementation has NOT
> started.

## Goal
Replace the in-app agent chat with a browser terminal: `/agent` page and the
opencode daemon are removed everywhere; the agent becomes the plain
opencode CLI (TUI) running INSIDE a ttyd web terminal, driven from
`console.local`. The VM collapses to a single fixed app (`app.local`),
provisioned build-or-destroy, with the app running under a less powerful
user and the console/agent under a powerful one that can restart services.

## Decisions (locked)

### /agent removal (full sweep)
- Delete: `djangoapp/views/opencode.py` + its tests + `/agent` URLs +
  `require_superuser`'s only remaining consumer check (if truly unused);
  frontend `OpencodeChat.vue`, `pages/opencode/` (composables, api,
  parseSse), opencode event schemas in `schemas.ts`; `./run opencode` +
  its preflight; the opencode process in `./run dev` (→ 3 processes:
  runserver, vite, huey); the `OPENCODE_BASE_URL` env key; and the ASGI
  `_AsyncStreamAdapter` in `views/opencode.py` (existed only for chat SSE
  streaming — asgi.py reverts to plain `get_asgi_application` + the
  granian proxy-headers wrap ONLY if still needed for login redirects…
  re-evaluate: with no SSE, keep the wrap since allauth still builds
  https URLs behind caddy).
- Keep: `makeloginlink`/`makesuperuser`/`addgoogleoauth` (dev-only), the
  whole scratch loop, `_vm_livereload`, `TestLoginKey`, client-error
  plumbing.

### Single-app world (multi-app parameterization swept out)
- Fixed names everywhere: multipass instance + ssh alias = `app`; tree =
  `/srv/app/{main,scratch}`; units = `app_granian`, `app_huey`;
  DB = `app_db`/`app_user` (env values); credentials =
  `/etc/credentials/app/.env.vm`; Caddy sites = `app.local` +
  `console.local`; commands `./run provision_local_vm` / `./run
  delete_local_vm` take NO appname argument. `setenv()`'s VM glob
  (`/etc/credentials/*/.env.vm`) hardens to the fixed path.
- Hostnames: `app.local` (the app; static + proxy as today, internal CA
  click-through OK) and `console.local` (the terminal proxy). Both are
  single-label mDNS names — portable across macOS and Linux clients.
  avahi publishes `app.local` via the instance hostname; `console.local`
  needs a static avahi entry (`/etc/avahi/hosts` + publish) since the
  hostname can only be one name.

### Users
- `app` — less powerful: runs `app_granian`/`app_huey`, owns `/srv/app`,
  NO sudo. The sudoers restart rule moves away from it.
- `console` — powerful: runs ttyd, holds the passwordless
  `systemctl restart app_granian.service app_huey.service` sudoers rule.
  The agent (opencode CLI in the ttyd session) acts as `console`, so its
  bash tool can restart services and run mergescratch's restart step.
- ssh alias `app` → User console (the operator's shell).

### ttyd console
- apt-installed ttyd (Ubuntu 26.04 universe); unit `console_ttyd`:
  User=console, WorkingDirectory=/srv/app, `-W` (writable TTY for TUIs),
  listens 127.0.0.1:7681, hardening like the other units but read-write
  `/srv/app`.
- `EnvironmentFile=/etc/credentials/app/.env.vm` — ttyd inherits
  OPENCODE_AUTH_CONTENT / OPENCODE_MODEL / OPENCODE_PROVIDER / git
  identity, so the opencode CLI inside authenticates with NO auth.json and
  commits as "Opencode Agent". Plus `OPENCODE_CONFIG=/srv/app/main/
  agentconfig/opencode.json` (repo's agentconfig/ STAYS — same tool
  permission rules for the in-terminal agent).
- Caddy `console.local` reverse_proxy → 127.0.0.1:7681 (websockets pass
  through Caddy automatically). **No ttyd auth** (user decision —
  LAN-trusted; recorded, not relitigated).
- The unit does NOT autostart an agent: the operator runs `opencode` in
  the browser terminal.

### Env + UI
- New keys `APP_URL` / `CONSOLE_URL` in BOTH env files (all-keys rule;
  commented in dev when unneeded). Consumed by: provisioning printout,
  README, and the app UI — a superuser-only "Console" nav link via shared
  props (rendered only when CONSOLE_URL is set, so dev can leave it off).
- Dev agent flow: `./run console` — loads .env (setenv semantics) and
  execs the opencode TUI in the current terminal (the dev analog of
  console.local).

### Rollout
- Fresh rebuild: `./run delete_local_vm` (old app1) → `./run
  provision_local_vm`. Old instance/alias/creds die with it; login again
  via makeloginlink; test data is throwaway.

## Phased checklist

### Phase 1 — /agent removal
- [ ] Delete backend: views/opencode.py, tests/views/test_opencode.py,
      /agent URL patterns; check require_superuser consumers.
- [ ] asgi.py: drop `_AsyncStreamAdapter` (verify the granian
      proxy-headers wrap must STAY for allauth https URLs — it does;
      login redirects depend on it).
- [ ] Delete frontend: OpencodeChat.vue, pages/opencode/*, opencode
      schemas, nav references.
- [ ] `run`: drop `opencode()` + preflight + the dev-stack process;
      add `console()` helper.
- [ ] Env: remove OPENCODE_BASE_URL; add APP_URL/CONSOLE_URL keys to
      both examples.
- [ ] Suite green after removal (ruff, mypy, ./run test, frontend
      type-check + build).

### Phase 2 — single-app hardcoding sweep
- [ ] run: provision_local_vm/delete_local_vm lose the appname arg;
      _vm_livereload hardcodes app_* units; setenv glob → fixed path.
- [ ] deploy/: inside-vm.sh + driver hardcode `app` (tree, units, creds,
      DB names from env values); sudoers = console's restart rule for
      app_granian/app_huey only.
- [ ] Units: User=app for granian/huey (new user); console_ttyd.service.in
      added; ownerships moved (deploy → app/console) in provisioning.

### Phase 3 — ttyd + console.local
- [ ] provision_vm: apt ttyd, `console` user + sudoers restart rule.
- [ ] console_ttyd unit: User=console, cwd /srv/app, -W,
      EnvironmentFile + OPENCODE_CONFIG, 127.0.0.1:7681.
- [ ] avahi: static `console.local` entry pointing at the VM IP.
- [ ] Caddyfile: console.local site (reverse_proxy 7681).
- [ ] Driver: starts/restarts console_ttyd; printout gains
      https://console.local/.

### Phase 4 — UI + docs
- [ ] Shared props: superuser-only Console link (CONSOLE_URL-driven).
- [ ] README: console.local workflow (opencode in the browser terminal),
      ./run console for dev, updated provisioning commands.
- [ ] INSTRUCTIONS.md: agent now runs in ttyd; env inheritance note.

### Phase 5 — rollout & validation
- [ ] `./run delete_local_vm` (old app1) → `./run provision_local_vm`.
- [ ] https://app.local/ serves (login via makeloginlink; Console link
      appears for superuser).
- [ ] https://console.local/ terminal loads; `opencode` TUI inside
      authenticates via OPENCODE_AUTH_CONTENT (no auth.json); agent
      commit shows "Opencode Agent" no email.
- [ ] Agent can restart services from the terminal (sudoers as console).
- [ ] Static via Caddy + cache headers; `*.map` 404; huey-0 variant
      still supported.
- [ ] Full suite green.

> ## Decision update (2026-08-21, evening): console moves to
> `https://app.local/agent/`; the 7000 port and the WS reconnect loop die
> together
>
> - **Root cause of the infinite WS reconnect loop** (supersedes "it's
>   spawn-related noise"): `console_ttyd`'s ExecStart ran a BARE ttyd —
>   this build requires a start command, so every accepted WS connection
>   spawned a process that instantly died with **exit 254**, ttyd closed
>   the socket (1006), and the browser reconnect-forevered. The unit also
>   passed `--listen`, which 1.7.7 doesn't have (`-i`/`-p`). Fixed
>   ExecStart: `ttyd -W -i 127.0.0.1 -p 7681 -w /srv/app -- /bin/bash`
>   (loopback bind, cwd, explicit command). Dev `./run dev` had the same
>   bare-ttyd bug — same fix; ttyd now installed via brew on the Mac.
> - **The 7000 port is DEAD**: caddy now mounts the terminal in the main
>   site — `redir /agent /agent/ 308` + `handle_path /agent/* { reverse_proxy
>   127.0.0.1:7681 }`. handle_path strips the prefix, so ttyd needs NO
>   `-b` base-path. One hostname, ONE port (443, real TLS): the
>   HTTPS-Only-mode complaints and the plain-HTTP caveat both vanish.
>   ufw drops the 7000 rule.
> - **1.7.7 wire details** (for future debugging): the client connects with
>   subprotocol `tty` and sends a BINARY first frame
>   `{"AuthToken":"","columns":N,"rows":M}`; WS probes via curl must use
>   `--http1.1` (an h2 request can't carry `Upgrade:` and ttyd 404s it).
> - CONSOLE_URL everywhere (both env examples, `.env`, `.env.vm`, the VM's
>   credentials file, settings comment, README, INSTRUCTIONS, driver
>   printout, run comments) → `https://app.local/agent`.
> - Verified live: `/agent/token` via https, WS 101 through caddy, journal
>   shows clean `started process` / `killing process` (no 254), prompt
>   lands as `console@app:/srv/app$`; locally: brew ttyd 1.7.7, WS 101 +
>   bash spawn on 7681.

> ### Follow-up (same night): Firefox SEC_ERROR_BAD_SIGNATURE on
> `https://app.local/` — stale caddy root in the macOS System keychain
>
> - Symptom: Firefox hard-errors (no exception button) while Chrome shows
>   the usual click-through. NOT a caddy/cert problem: served chain
>   verified OK under LibreSSL, BoringSSL(Chrome), and NSS itself
>   (`vfychain -pp` "Chain is good"; `tstclnt` = plain untrusted-issuer).
> - Root cause: an OLD VM build's "Caddy Local Authority - 2026 ECC Root"
>   (fp `908D:D2E1…`, key ≠ current VM's root `4D:DC:04:A1…`) was sitting
>   TRUSTED in `/Library/Keychains/System.keychain` (an old "always trust"
>   click). Firefox imports macOS system anchors (SecTrustSettings), so
>   NSS path-builds the new intermediate against the old root's key →
>   genuinely invalid signature → SEC_ERROR_BAD_SIGNATURE.
> - Fix: `sudo security delete-certificate -Z <SHA256> /Library/Keychains/
>   System.keychain`, restart Firefox.
> - Standing rule: do NOT add the VM's caddy root to macOS trust — every
>   rebuild mints a NEW CA, and a stale trusted one turns the supported
>   click-through into a hard Firefox error. Click-through stays the mode.
> - Diagnostics toolbox that worked: per-IP `--resolve` cert fingerprints,
>   `cert_override.txt`/cert9.db greps, DoH (trr mode 3) exonerated via
>   direct DoH JSON query, `MOZ_LOG=pipnss:5,certverifier:5` on a
>   `-no-remote -profile` second instance (revealed SecTrustSettings
>   import), `security find-certificate -a -c Caddy -Z` on both keychains.

> ### Follow-up 2 (2026-08-22): every /static/ asset 404ed on the VM —
> caddy `handle` vs `handle_path`
>
> - First real browser visit of the VM app (post cert fix) found all
>   hashed assets 404ing while existing on disk and world-readable.
> - Cause: the static block used `handle /static/*` — caddy file_server
>   resolved root + the UNSTRIPPED URI, i.e.
>   `staticfiles/static/djangoapp/…`, a `static/` level that collectstatic
>   never writes (STATIC_URL is a URL prefix only; STATIC_ROOT collects to
>   `staticfiles/djangoapp/…`). Bug since provisioning; every earlier check
>   only ever curled `/` (HTML from Django), never an asset.
> - Fix: `handle_path /static/*` (strip, same as the /agent block).
>   Verified: css/js 200 + immutable header, `*.map` still 404, app + /agent
>   untouched.

> ### Follow-up 3 (2026-08-22): auth-JSON leak, `agent` command, welcome
> banner, console∈app group
>
> - **OPENCODE_AUTH_CONTENT corruption**: the root `.env.vm` had an inline
>   `# comment` INSIDE the closing quote — shell sourcing concatenates it
>   into the value (systemd EnvironmentFile passes it verbatim), so the
>   console showed `{"type":"api",…}# Provider/model…`. Also the JSON
>   lacked the provider wrapper. Fixed to the documented contract:
>   `'{"zai-coding-plan":{"type":"api","key":"…"}}'` + explicit
>   OPENCODE_PROVIDER/OPENCODE_MODEL. Provisioning now FAILS HARD when the
>   staged OPENCODE_AUTH_CONTENT doesn't parse as JSON (python3 -m
>   json.tool) — catches this leak class at build time. Never edit env
>   values with sed; use exact-string edits so quoting/spaces survive.
> - **`agent` command** (VM): /usr/local/bin/agent — sources
>   /etc/credentials/app/.env.vm itself (works from ttyd AND ssh), sets
>   OPENCODE_CONFIG(_DIR) to main/agentconfig, cds to /srv/app (worktree
>   PARENT — same scoping as dev `./run console`), idempotent `git init`,
>   execs opencode. opencode itself is now provisioned via
>   `npm i -g opencode-ai@1.18.0` (was MISSING from the VM entirely).
> - **Welcome banner**: ttyd's bash is an interactive NON-login shell →
>   ~/.bashrc (not ~/.profile) is what runs; provisioning appends a short
>   banner (user, repo, app URL, `agent` hint) to /home/console/.bashrc.
> - **console joins the app group** (provision gap): the creds file is
>   root:app 640 and /srv/app is group-app 775, but nothing put console IN
>   the group — the agent script couldn't source the env and console
>   couldn't write the tree despite comments claiming both. `usermod -aG
>   app console`. (Restart console_ttyd after changing groups — running
>   shells keep old groups.)
> - **Git worktree**: provisioning now `git init`s /srv/app AS app (owner
>   matches main/) + `git config --system safe.directory /srv/app` — git
>   flags cross-user repos as dubious ownership regardless of groups, and
>   both app (bootstrap) and console (./run, agent) work the tree.

> ### Follow-up 4 (2026-08-22): `agent` froze on the loading screen —
> opencode's TUI blocks on UNANSWERED TERMINAL PROBES
>
> - Symptom: `agent` draws the logo + loading dots, never advances; log
>   stalls at `booting location services`; headless `opencode models`
>   worked fine (catalog + authenticated provider call OK).
> - Root cause: opencode 1.18's TUI (opentui) sends a probe burst at boot —
>   DECRQM `CSI ? Pm $p` (2026/2027/2031/1016/1004/2004), XTVERSION
>   `CSI > 0 q`, XTGETTCAP, DA, OSC 10/11, `CSI ? u` — and blocks until
>   replies arrive. **ttyd 1.7.7's xterm.js answers none of them** (the
>   bundle has a DECRPM generator but never fires for these). Bisect
>   result: answering ANY ONE probe unblocks boot. The ~11s lurches before
>   the hang were per-probe timeouts; the final wait is infinite.
> - Fix: `deploy/pty_shim.py` → installed /usr/local/lib/agent/pty_shim.py;
>   `agent` execs `pty_shim.py opencode` when stdin is a tty. The shim
>   relays the real tty bidirectionally (raw mode, winsize propagation),
>   and injects valid replies to the probes a browser terminal never
>   sends (`;0$y` not-recognized for unknown modes — a valid DECRPM).
>   Verified end-to-end via `ssh -tt`: TUI boots to the main screen.
> - tmux as middleman was tried and REJECTED: tmux does not answer the
>   probes either (still hung inside `tmux new-session`).
> - Testing gotcha: `script -qec CMD file </dev/null` is NOT a valid ttyd
>   surrogate — script tears the command pty down on stdin EOF (instant
>   exit-0 false negatives). Use `ssh -tt`.
> - Side quest fixed en route: the VM clock was 3h45m SLOW (multipass
>   guest drift after host sleep; chrony only slews: 3.75h at 500ppm ≈
>   312 days). Provisioning now appends `makestep 1 -1` to
>   chrony.conf + `chronyc makestep` at build; live VM fixed the same way.
>   (Not the TUI hang's cause, but a real bug — time-signed calls and TLS
>   windows depend on it.)

> ### Follow-up 5 (2026-08-22): heredocs → template files; ttyd hang
> RETESTED — the pty_shim claim is RETRACTED
>
> - **Template extraction** (user rule: no inline cat/printf file
>   authoring in the build script): the four inline blocks became
>   templates staged like every other input — `deploy/agent.sh` (→
>   /usr/local/bin/agent), `deploy/console-welcome.bashrc` (appended to
>   /home/console/.bashrc), `deploy/redis-append.conf`,
>   `deploy/chrony-append.conf` (marker-guarded appends). Single-line
>   structural writes (sudoers, swappiness, fstab, caddy import, ssh
>   stanza) stay as commands — control flow, not authored content.
>   Verified: redis/chrony templates byte-identical to the live files;
>   agent.sh now also deployed live (the live one had drifted — it lacked
>   the pty_shim branch).
> - **The ttyd TUI hang is NOT fixed, and the shim does NOT fix it.**
>   Follow-up 4's "verified end-to-end via ssh -tt" was CONFOUNDED: ssh
>   relays the pty to the operator's LOCAL terminal emulator, which
>   answers the probes itself — the boot came from the local terminal,
>   not the shim. Clean retest (node WS driver speaking the ttyd wire
>   protocol: subprotocol "tty", binary AuthToken init, INPUT frames):
>   `agent` through REAL ttyd still stalls at `booting location services`
>   (opencode debug log), logo + loading dots only, 1Hz idle timer loop
>   in strace, zero pty reads/writes.
> - Bisected and EXONERATED (all boot fine on a python-pty harness):
>   window size (0x0 and 120x40), exact ttyd env dump (no SSH_*,
>   no COLORTERM/TERM_PROGRAM, full credentials-env keys), the shim,
>   tmux-wrapping (status bar renders, pane stays blank), orphan-lock
>   contention (real but secondary — killed runs leave bun `.so` crash
>   dumps in tmpfs + a reparented opencode holding the instance lock;
>   `creating instance` stall = debris, not the bug), clock (synced),
>   TERM (xterm-256color confirmed inside the session).
> - Gotchas learned: console_ttyd has PrivateTmp=yes — files written to
>   /tmp inside the web console land in a per-session
>   /tmp/systemd-private-*-console_ttyd.service-*/tmp; `pkill -f` with a
>   plain pattern self-matches the ssh command carrying it (use
>   `[o]pencode`-style brackets); long-silent ssh runs get torn down
>   (ServerAliveInterval); `script -qec CMD file </dev/null` is never a
>   valid ttyd surrogate.
> - OPEN: the delta is ttyd's fork/pty itself. Every python-spawned pty
>   boots; only ttyd's never does (browser or dumb client). Next steps if
>   revisited: packet-level WS diff, strace TTYD's pty setup vs forkpty,
>   or swap the console backend; upstream opentui#1333 / PR #1396 remain
>   the root-fix track. The pty_shim has been REMOVED (2026-08-22, user
>   decision): its premise (unanswered probes cause the hang) was
>   disproven by the no-answer control boot, and ttyd hangs identically
>   with/without it — `agent` is a plain `exec opencode` again; template
>   and staging references deleted; /usr/local/lib/agent removed live.

> ### Follow-up 6 (2026-08-22): chrony makestep fix REMOVED (user
> decision)
>
> - The `makestep 1 -1` append (deploy/chrony-append.conf + the
>   inside-vm.sh block + `chronyc makestep` at build) is deleted; live
>   VM's /etc/chrony/chrony.conf marker block stripped, chrony restarted
>   — stock Ubuntu default (`makestep 1 3`, conservative) restored. The
>   clock fix stands only as history: the drift was real (3h45m slow
>   after host sleep, slew ≈ never) and the one-time manual
>   `chronyc makestep` already corrected it; provisioning will NOT
>   self-heal future drift. If skew symptoms recur (expired login links,
>   TLS/signed-call oddities), check `chronyc tracking` first and step
>   manually.

## Out of scope (Part 3)
- ttyd authentication (decided against; revisit only if the LAN trust
  assumption breaks).
- Multi-label subdomains (console.app.local) — rejected for Linux client
  portability; single-label siblings instead.
- Multi-app on one VM (the parameterization is gone by decision).
- The "new agent" research items in TODO.md (memory, subagents) — the
  CLI-in-ttyd model just inherits whatever opencode ships.

## `aihere` markers (2026-08-22 sweep, complete — ADDRESSED same day)

Live `aihere` markers in the codebase (excluding `prevproject/`,
historical `prompts/`, `.kilo/worktrees/` copies, `.idea/`,
`djangoapp/static/djangoapp/*.map` — git-ignored build artifacts that
mirror `main.ts` source — and `INSTRUCTIONS.md`, which documents the
convention rather than carrying markers). Each is an instruction to
change the code; address each, then remove the comment (never sooner).

- [x] `frontend/src/main.ts:18` — `aihere halve this comment`: comment
      compressed 8→5 lines (loop hazard + cleared-on-settle kept,
      narration dropped); marker removed.
- [x] `frontend/src/main.ts:31` — `aihere use await`: the
      `Promise.resolve().then(run).catch(...).finally(...)` chain became
      an async `try { await run() } catch { … } finally { latch=false }`
      body; busy-latch semantics preserved; callers ignore the returned
      promise (no no-floating-promises rule in this config). Lint,
      type-check, build green.
- [x] `deploy/Caddyfile.site.in:19` — `aihere remove the mention of
      earlier shapes throughout`: the parenthetical history block
      (avahi-statics second name, plain-HTTP :7000 port) deleted; header
      re-checked — no other dead-shape mentions remain.
- [x] `run:97` — `aihere halve this comment`: the `dev()` comment
      compressed 11→6 lines (four processes + parent-cwd scoping +
      start-command-required gotcha kept).
- [x] `README.md:7` — `aihere we intend only web terminal for prod`:
      the Agent-driven bullet now states the production interface is ONLY
      the VM's web terminal (`https://app.local/agent/`) and that
      `./run console` is a dev convenience.
- [x] `README.md:54` — `aihere below stuff is out of date`: the
      `./run dev` paragraph rewritten — console description matches the
      current wiring (`CONSOLE_URL` nav link, `opencode`/`./run console`
      in the browser terminal, ttyd optional), and the pointer refreshed
      to the facts+todos reference app in `docs/reference/`.

New instances flagged after the Part-4 work (addressed 2026-08-22):

- [x] `deploy/inside-vm.sh:215` — `aihere remove all defaults, let them
      crash`: the worker-knob `: "${var:=default}"` fallbacks deleted;
      missing GRANIAN_WORKERS/GRANIAN_THREADS/HUEY_WORKERS in .env.vm now
      REFUSES the build with a per-knob list (fail-hard like the secret
      tripwires). Both env templates set all three, so rebuilds pass.
- [x] `deploy/ttyd.service.in:12` — `aihere halve this comment`: the
      ExecStart comment block compressed 13→7 lines (cwd+rcfile, -W +
      loopback, start-command-required gotcha kept).

# Part 4 (planned 2026-08-22, NOT yet implemented): `./run agent` +
`./run console` split; agent.sh dies; console lands in main/ with one
banner rcfile

User decisions locked via Q&A (one-by-one):

1. **`./run agent` runs opencode with all settings; `./run console` runs
   ttyd.** Two commands, distinct jobs:
   - `agent()` (new; absorbs today's console() body): setenv → export
     OPENCODE_CONFIG(_DIR) → cd to the repo PARENT (scopes main/ +
     scratch/ on both Mac and VM — VM's setenv already falls back to
     /etc/credentials/app/.env.vm) → exec opencode. No git-init guard —
     provisioning owns the /srv/app worktree.
   - `console()` (repurposed): standalone ttyd on 7681 —
     `ttyd -W -i 127.0.0.1 -p 7681 -w <repo> -- /bin/bash --rcfile
     deploy/console-bashrc` (+ pkill a stale 7681 listener first).
   - `dev()` keeps all FOUR processes (ttyd stays in dev), but its ttyd
     line gets the same repo-cwd + rcfile spawn.
2. **Consoles cd into main/** — the working repo dir, not the parent:
   VM ttyd unit `-w /srv/app/main`; local ttyd `-w` the repo itself.
   (Agent scoping still uses the parent — that's `run agent`'s cd, not
   the console shell's cwd.)
3. **No more agent.sh** — deploy/agent.sh deleted; inside-vm.sh install
   block deleted; provision-vm.sh staging updated; live
   /usr/local/bin/agent removed.
4. **One banner rcfile, generic wording** (user choice over env-detect):
   new `deploy/console-bashrc` used by BOTH local ttyd and the VM unit;
   sources the normal bashrc chain first (`/etc/skel/.bashrc` /
   `~/.bashrc` if present — keeps the VM prompt/aliases), then prints a
   GENERIC banner (repo layout, `./run agent` hint; no machine-specific
   URLs, no sudo note). The append-to-~/.bashrc mechanism dies:
   deploy/console-welcome.bashrc deleted, inside-vm.sh append block
   deleted, live /home/console/.bashrc block stripped.

Implementation checklist (when GO) — DONE 2026-08-22:

- [x] `run`: `agent()` (old console body: setenv → preflight → parent cd →
      exec opencode), `console()` repurposed to standalone ttyd
      (repo cwd + `--rcfile deploy/console-bashrc`, stale-7681 pkill),
      `dev()`'s fourth process is now `./run console`. Verified:
      `./run agent --version` = 1.18.0 on BOTH Mac and VM (full preflight
      + exec); local console WS-driven — banner prints, pwd = repo.
- [x] `deploy/console-bashrc`: chains ~/.bashrc (else skel) then prints
      the generic banner (repo-cwd note, `./run agent`, `./run dev` — no
      machine-specific URLs, user choice).
- [x] `deploy/ttyd.service.in`: `-w /srv/app/main` +
      `-- /bin/bash --rcfile /srv/app/main/deploy/console-bashrc`.
- [x] `inside-vm.sh`: agent.sh install block deleted; .bashrc welcome
      append deleted; rcfile installed to main/deploy/ from the staging
      area (the seed tarball EXCLUDES deploy/ — discovered when the live
      deploy hit a missing dir — so provisioning installs it; dir created
      ahead of the seed, tar merge leaves it alone).
- [x] Deleted `deploy/agent.sh`, `deploy/console-welcome.bashrc`.
- [x] Live VM: /usr/local/bin/agent removed; old .bashrc banner block
      stripped; run + console-bashrc + new unit deployed; console_ttyd
      restarted; verified active + banner + `./run agent --version`.
- [x] Local: `./run console` standalone verified via WS driver; `./run
      dev` delegates its console leg to `./run console` (one spawn
      definition); `./run agent` verified.
- [x] README (Features bullet, prerequisites ttyd note, quick-start
      commands, dev paragraph, VM workflow paragraph, run-command list),
      driver printout (`./run agent` hint). INSTRUCTIONS.md had nothing
      stale to update.

> ### Follow-up 7 (2026-08-22): `./testvm` script replaces the run/VM
> drivers — and a self-inflicted VM deletion
>
> - `provision_local_vm`/`delete_local_vm` left `run`; the whole
>   deploy/provision-vm.sh driver + delete became the repo-root `./testvm`
>   (`provision [--release …]` / `delete`), same dynamic-dispatch shape.
>   deploy/provision-vm.sh deleted; deploy/inside-vm.sh stays (staged to
>   the VM by testvm). References swept: README (VM section, Commands
>   section split run/testvm), .env.vm(.example) header comments,
>   inside-vm.sh comments. TODO.md (user notes) left untouched.
> - During testing, `./testvm delete` was run against the LIVE instance and
>   purged it (git history + DB gone — the superuser created earlier went
>   with it; recreate via makeloginlink/makesuperuser after rebuild). The
>   VM is currently ABSENT; rebuild with `./testvm provision`. A
>   confirmation gate was added then REMOVED on user decision: **delete
>   asks nothing — it deletes immediately**. Bare `./testvm` (no
>   args) prints usage instead of crashing on set -u.
> - **testvm never touches the host's ssh config** (user rule, 2026-08-22):
>   delete() no longer removes the `Host app` stanza, and provision() no
>   longer ADDS it (the whole section-5 ssh-alias install is gone). The
>   printout/README/.env.vm.example login commands switched from
>   `ssh app '…'` to the self-sufficient `multipass exec app -- sudo -u app
>   -H bash -c '…'` form. Accessing the VM is the operator's own affair
>   (`multipass shell app`, or a personally maintained ssh alias).
> - **authorized_keys plumbing removed too** (same user instruction, same
>   day): testvm no longer collects the workstation's pubkeys
>   (`ssh-add -L`/`~/.ssh/id_*.pub`) or stages `$t/pubkey`; inside-vm.sh no
>   longer creates /home/console/.ssh/authorized_keys. The VM is driven
>   ONLY via `multipass exec` (its own ssh channel over the internal
>   bridge — hence ufw 22 stays open) and the web terminal.

> ### Follow-up 8 (2026-08-22, fresh VM): model fallback, agent cwd →
> repo root, and the TRUE root cause of the console TUI hang: MemoryMax
>
> - **Model glm-4.7**: dev `.env` had NO OPENCODE_* keys at all, so the
>   TUI fell back to the user's personal
>   `~/.local/share/opencode/auth.json` and ITS default model. Fixed: the
>   agent block (AUTH_CONTENT + PROVIDER + MODEL="glm-5.2") added to dev
>   `.env` (mirroring `.env.vm`; example header updated to `./run agent`).
> - **agent cwd**: `./run agent` now cds to the REPO ROOT (main/) instead
>   of the parent — TUI pwd = the repo on both machines. Consequences, per
>   opencode docs (permissions are WORKING-DIR-relative; siblings need
>   `external_directory`): opencode.json instructions →
>   `agentconfig/steer.md`; edit allows keep `scratch/**` plus
>   `/srv/app/scratch/**` (VM), and `external_directory` carries the dev
>   sibling allow [CORRECTED TWICE 2026-08-23: the original claim of
>   `$HOME/dev/*/scratch/**` in BOTH blocks was aspirational; Part 5 C1
>   added it that way, then a hand-edit simplified the file — the SHIPPED
>   form is `$HOME/**/scratch/**` in external_directory ONLY, edit keeps
>   scratch/** + /srv/app/scratch/**; editing ../scratch on dev rides the
>   external_directory allow alone]; bash rules switched to
>   `./run …` / `cd ../scratch *` / `rm -rf ../scratch*` forms. steer.md
>   Layout section rewritten (repo-relative paths). README workflow
>   section updated. Parent git-init dropped from agent() (provisioning
>   owns /srv/app's worktree).
> - **THE TUI HANG IS SOLVED — root cause: `MemoryMax=96M` on
>   console_ttyd.** opencode's bun runtime needs far more than 96M; the
>   cgroup never OOM-killed (oom_kill 0) — it reclaimed/thrashed forever
>   (memory.events `max` = 1,060,480 hits), so the TUI crawled at its
>   loading screen forever. Every earlier "python pty boots, ttyd doesn't"
>   result is explained: the harness ran OUTSIDE the unit's cgroup; the
>   probes/termios/env/size exonerations were real but irrelevant. Lifted
>   to `MemoryMax=512M` (memory.peak touches the cap, mostly page cache;
>   TUI boots through real ttyd — verified twice via the WS driver on the
>   fresh VM, then with the production unit file). ttyd.service.in carries
>   the fix with a comment. This supersedes the probe theory entirely
>   (Follow-up 4's retraction stands; the shim stays deleted).
> - Telemetry/color settings were NEVER persistently changed (one-off
>   OPENCODE_DISABLE_TELEMETRY/LOG_LEVEL env vars on test commands on the
>   old VM only; nothing in env files, units, or agentconfig).

> ### Follow-up 9 (2026-08-22): parent-is-a-repo abolished; main/ is its
> own repo with a first commit
>
> - inside-vm.sh's `/srv/app` git-init + `safe.directory` block deleted
>   (supersedes Follow-up 3's worktree note and Follow-up 8's "provisioning
>   owns the worktree" remark). The agent needs NO parent repo: cwd =
>   main/ (its own repo), scratch/ rides external_directory allows.
> - `testvm provision` now `git init`s /srv/app/main AFTER the seed lands
>   and makes the first commit ("First commit: provisioned from the repo
>   seed") with the env-file identity — the provisioned baseline; agent
>   commits follow.
> - Live VM migrated: /srv/app/.git removed (system safe.directory unset),
>   main/ init'd + committed (8689759); `./run agent` TUI re-verified
>   BOOTED through real ttyd; all services active.
> - Dev leftover: /Users/jesvin/dev/ourinstant/.git (the old agent()'s
>   idempotent init, zero commits) deleted. run agent()'s comment updated
>   (no parent git-init remains anywhere).

## `aihere` markers (2026-08-22 evening sweep — ADDRESSED same night)

- [x] `deploy/granian.service.in:5` — `aihere split all service files with
      newlines for readability`: all THREE unit templates (granian, huey,
      ttyd) regrouped with blank lines — identity / ExecStart / env file /
      Restart / hardening blocks. Marker removed.
- [x] `deploy/Caddyfile.site.in:8` — `aihere halve the below comment`: the
      /agent block halved (ttyd behind handle_path strip, operator surface,
      no-auth-by-decision); WS-derivation mechanics dropped. Marker removed.
- [x] `testvm:32-41` — tree-of-files staging: testvm now carries the full
      TREE OF FILES header comment (every VM path provisioning writes),
      validates .env.vm FAIL-HARD host-side (sentinels, AUTH JSON, worker
      knobs — moved out of inside-vm.sh; ALLOWED_HOSTS warning too), then
      after provision_vm FETCHES stock /etc/redis/redis.conf +
      /etc/caddy/Caddyfile from the VM, mutates them locally (append
      blocks), builds the whole tree in $t/tree mirroring absolute VM
      paths (units + caddy site rendered host-side — the @WORKERS@ sed
      left inside-vm.sh), and ships ONE tarball. inside-vm.sh provision_app
      extracts at / (--no-same-owner), fixes ownership (creds root:app,
      sudoers 0440 + visudo), restarts redis, then postgres + enables.
      Every file line tagged `tree: <path>` on the testvm side (10 tags);
      the inside-vm.sh cross-references are its per-file `# ── file:`
      blocks + the tree comment [CORRECTED 2026-08-23: an earlier note
      claimed "9 tree: tags inside-vm.sh" — the per-line tags live in
      testvm only]. The old scatter (6
      transfer/mv pairs + in-VM installs/renders) is gone; the `all` phase
      is dropped (tree lands between the phases). Updated run/testvm
      deployed to the live VM.
      Rationale for keeping the tar: `multipass transfer -r` can't merge
      into existing dirs (nests or clobbers); per-file transfers are the
      scatter the marker killed; tar extract-at-/ is the only one-shot
      overlay (user agreed).
- NOTE (observed, not changed): the user commented `#MemoryMax=512M` out
      of deploy/ttyd.service.in (marked "# commented"). Rebuilds ship an
      UNCAPPED console_ttyd — no 96M-thrash hang (that needed a LOW cap),
      but no runaway bound either. The live VM's deployed unit still has
      MemoryMax=512M active.

> ### Follow-up 10 (2026-08-22 night): tree comments go hierarchical;
> DANGEROUSLYUNSET leaves settings.py
>
> - Both tree-of-files comments (testvm header + inside-vm.sh pre-extract)
>   reformatted as an indented hierarchy (`/etc/credentials/app/…` style
>   paths → tree with └──/├── branches, annotations kept); testvm's
>   per-file `tree:` build-line tags unchanged (still the greppable
>   cross-reference).
> - **DANGEROUSLYUNSET is now VM-provisioning-only**: both settings.py
>   tripwires (SECRET_KEY + DB_PASSWORD) REMOVED — the app never inspects
>   the sentinel (SECRET_KEY defaults to "fake"; the not-DEBUG "fake"
>   prod check remains). Enforcement lives solely BEFORE the app on the VM
>   path: ./testvm provision validates host-side (both keys) and
>   inside-vm.sh provision_app re-checks DB_PASSWORD post-extract. Dev
>   .env.example wording updated: `./run init` fills the key, the operator
>   sets DB_PASSWORD (or DB connections just fail — no tripwire). README
>   + run init comment reworded. ruff/mypy clean, 157 tests OK; settings/
>   run/testvm redeployed to the VM, granian restarted, services active.
> - Refined minutes later (user): the sentinel scan is now GENERIC — any
>   KEY=value line whose value carries DANGEROUSLYUNSET refuses the build
>   (testvm host-side + inside-vm.sh post-extract re-check), because the
>   env's key set is NOT fixed; new vars inherit the tripwire for free.
>   Regex `^[A-Za-z_][A-Za-z0-9_]*=.*DANGEROUSLYUNSET` — verified: catches
>   quoted/bare sentinels on known AND unknown keys, ignores comment
>   mentions. DB_PASSWORD keeps a plain empty check in inside-vm.sh (not a
>   sentinel matter); the per-key SECRET_KEY/DB_PASSWORD loops are gone.
>   Also this session, user request: settings.py dropped ALL
>   os.environ.get() (CONSOLE_URL/STATIC_ROOT/REDIS_URL now required
>   indexing; STATIC_ROOT added to dev .env/.env.example, REDIS_URL
>   uncommented — every env file ships all keys).

## `aihere` markers (2026-08-23 sweep — ADDRESSED same day)

Live `aihere` markers in the codebase (standard exclusions; INSTRUCTIONS.md
is the convention doc, not a marker). Markers may not be comments — each is
listed with file:line, the marker text, and what fulfilling it means.
INSTRUCTIONS.md now states markers may sit on any line of any file.

- [x] `deploy/ttyd.service.in:13` — halve cwd/rcfile comment: 7 → 4 lines
      (cwd+rcfile, -W/loopback; start-command note kept).
- [x] `run:23` — halve setenv() comment: 8 → 4 lines (set -a semantics,
      plain-values-only, dev .env vs VM creds path).
- [x] `run:105` — remove the dev() stale-stack pkill (relaunching is the
      operator's problem).
- [x] `run:144` — halve agent() header: 8 → 4 lines.
- [x] `testvm:2` — header from shebang to the tree comment halved (~30 →
      17 lines); kept usage, build-only semantics, fail-hard env note,
      destructive-delete warning, never-touches-ssh note.
- [x] `testvm:109` — OPENCODE_AUTH_CONTENT JSON-validation block deleted
      (user: assume the JSON is correct).
- [x] `testvm:131` — worker-knob refusal keeps only its first line (the
      per-missing-key list gone).
- [x] `testvm:142` — "converge" purged everywhere (testvm header+step-1
      comment, inside-vm.sh header; TODO.md is user notes, untouched).
- [x] `testvm:237` — the two inline multiline `multipass exec … bash -c`
      bodies became shipped scripts: deploy/vm-seed-commit.sh (git init +
      first commit) + deploy/vm-bootstrap.sh (uv sync, build, migrate,
      collectstatic), riding the tree at /tmp/ and invoked by single-line
      execs. Tree comments (testvm header + inside-vm.sh pre-extract)
      gained the /tmp group.
- [x] `testvm:271` — the access-steps printout heredoc became
      deploy/access-steps.txt, catted by provision (host-side file, never
      ships to the VM).
- Verified: zsh -n/bash -n all five scripts green; zero `aihere` and zero
  `converge` mentions outside TODO.md; run/testvm/inside-vm.sh redeployed
  to the VM repo copy.


## Out of scope (Part 2)
- CA trust on workstations (click-through stays the mode).
- Production hardening beyond current unit sandboxing (backups/monitoring/
  upgrades remain TODO-level).
- Any second app on the VM (only the naming/sweep work to enable it).
- Loopback/127.0.0.1.sslip.io alias (considered, dropped with the tunnel).

# Part 5 (2026-08-23): post-review fixes — IMPLEMENTED same day

Source: 6-agent review of commits ca2bbc4 + 7f5f5f3 (adherence, security,
frontend, backend tests, docs, deploy/shell; top findings independently
re-verified). All confirmed items below; numbering kept for traceability.

## A. Service/config bugs (deploy)

- [x] A1 (=W2) **granian.service.in lost `Restart=always`** — dropped in
      the blank-line regroup (huey/ttyd kept theirs; a crashed granian now
      stays dead on rebuilds). Re-add `Restart=always` + `RestartSec=3` as
      its own group. Live VM's deployed unit predates the edit (still has
      it) — template-only fix, redeploy on next provision.
- [x] A2 (=W1) **Caddy `.map` 404 is unreachable** — `handle_path
      /static/*` (with file_server) orders before `respond @maps 404`, and
      vite emits sourcemaps → **maps are served today** (README logging
      contract violated). Fix: move the guard INSIDE the static block
      where the prefix is already stripped — `handle_path /static/* {
      @maps path /djangoapp/*.map; respond @maps 404; root …; file_server }`.
      Verify live: `curl -sk https://app.local/static/djangoapp/assets/<hash>.css.map`
      → 404, hashed assets still 200. Redeploy site file to the live VM.
- [x] A3 (=F1) **missing worker knob aborts silently** — `envval`'s
      grep-pipeline failure + `set -euo pipefail` kills testvm before the
      friendly refusal (only present-but-empty reaches it). Fix: end
      envval's pipeline with `|| true` so missing → empty → refusal path.
- [x] A4 (=F2) **knobs never validated numeric** — junk values silently
      skip the huey unit or corrupt render()'s sed (`/` or `&`). Fix:
      `[[ "$knob" =~ ^[0-9]+$ ]]` for all three before render, refuse
      otherwise.
- [x] A5 (=F5) **no postgres readiness wait** — first psql can beat the
      cluster's first start and abort the build. Fix: poll
      `pg_isready -q` (timeout ~60s) after `enable --now postgresql`.

## B. Frontend

- [x] B1 (=F3) **deleted `_opencode.scss` styles still needed by live
      code** — `.opencode-mockup`/`.opencode-diagram` used by
      RichTextViewer.vue, mermaid.ts, html.ts allowlist (UserDetails,
      UserHistory, FileViewer pages); diagrams lost `overflow-x`,
      `svg { max-width: 100% }`, framing; error state unstyled. Fix:
      RENAME to neutral classes (`rich-mockup`, `rich-diagram`) and
      resurrect the needed rules (from `git show ca2bbc4^:
      frontend/src/styles/_opencode.scss`) in a new
      `styles/_richcontent.scss` @used from main.scss; update
      RichTextViewer.vue, mermaid.ts, html.ts allowlist in the same pass
      (rename kills the stale "opencode" naming too).

## C. Agent permissions

- [x] C1 (=F4) **dev scratch NOT pre-approved** — opencode.json lacks the
      dev sibling allows claimed in Follow-up 8; editing `../scratch` on
      dev prompts, contradicting steer.md:33 + README:214. Fix: add
      `$HOME/dev/*/scratch/**` to BOTH `edit` and `external_directory`
      (glob covers the ourinstant dir; VM keeps `/srv/app/scratch/**`).
      Correct Follow-up 8's claim in this file while at it.
      [AMENDED: a later hand-edit simplified the shipped file to
      `$HOME/**/scratch/**` in external_directory only (edit unchanged) —
      recorded in Follow-up 8's correction note; this item's shape is
      historical.]

## D. Security-adjacent (small, targeted)

- [x] D1 (=F1v) **SECRET_KEY tripwire is dead code for the shipped
      sentinel** — settings.py's not-DEBUG guard rejects `"fake"` but both
      examples ship `"DANGEROUSLYUNSET"`. Constraint (Follow-up 10, user
      rule): DANGEROUSLYUNSET is NOT handled in settings.py. Fix
      consistent with that: **`.env.example` ships `SECRET_KEY="fake"`
      again** (dev; `./run init` regenerates it; the fake-guard covers
      prod misuse) — `.env.vm.example` KEEPS `DANGEROUSLYUNSET`
      (provisioning refuses it host-side). No settings.py change.
      [AMENDED 2026-08-23 evening, user decision: revert the example
      value — `.env.example` ships `SECRET_KEY="DANGEROUSLYUNSET"` like
      the VM template; its comment states the DEV env does NOT enforce
      the sentinel (only ./testvm provision does, on the VM path). The
      settings.py "fake" guard stays as-is; the D1 rationale above no
      longer applies.]
- [x] D2 (=F2v) **login keys logged before redemption** — middleware logs
      `request.path` (raw key) on every hit, before the atomic redeem;
      aborts leave a valid key in the journal. Fix: redact in the
      middleware binding + a logging filter for `django.server` access
      lines: `/login-for-test/by-key/<key>/` → `/login-for-test/by-key/
      <redacted>/`. Test: hit the route, assert no log line contains the
      raw key.
- [x] D3 (=L1) **psql interpolation of DB creds** — quote in
      DB_PASSWORD breaks/injects; password visible in `ps` argv. Fix:
      pass values via psql variables with `:'var'` quoting, fed over
      stdin (not `-v` on the command line) — no string interpolation.
- [x] D4 (=BUG1) **makeloginlink `--minutes` ≤ 0** mints an already-dead
      link and prints it as success. Fix: validate `> 0`, CommandError
      otherwise.

## E. Test + hygiene

- [x] E1 (=GAP2/3/6/7) **login-key test gaps**: assert `--base-url` is
      honored; assert `used_at` populated after success; assert expired
      redeem does NOT mark used (`used_at__isnull=True`); assert session
      key rotates on login (`assertNotEqual`); iexact-email case variant.
      (Concurrent select_for_update coverage: note-only — needs a second
      DB connection harness; skip for now.)
- [x] E2 (=F5/deps) **dead frontend deps**: delete `utils/diff.ts`
      (zero importers), drop `diff` + `@types/diff` from package.json;
      drop the `npm run test` script + `vitest` devDep (no test files
      since parseSse.test.ts went) — re-add when a real test lands.
- [x] E3 (=dead python dep) **httpx**: no importers since the daemon
      removal; `uv remove httpx` + fix the stale pyproject comment.
- [x] E4 (=dead knob) **APP_URL**: active in both examples, read by
      nothing (provisioning printouts hardcode app.local). Remove from
      both examples; local env files keep working (extra keys harmless).
- [x] E5 docs nits: README Commands list add `hueydev`/`coverage`;
      CLIENT_ERROR_RATE_LIMIT noted as commented-optional default 30;
      STATIC_ROOT duplicated comment in .env.example.

## F. Stale docs/comments sweep

- [x] F1 **steer.md chat/daemon framing** — still "web chat steering",
      "I run the daemon", "./run dev starts opencode", allowlist shown as
      `main/run …` forms (now `./run …`), "rm -rf scratch relative works
      (daemon runs from parent)". Rewrite header + Feature-workflow intro
      + allowlist section to the TUI-in-console model (./run agent, repo
      cwd, ../scratch).
- [x] F2 **Caddyfile.site.in:1-2,16** — "rendered by deploy/inside-vm.sh"
      → rendered host-side by ./testvm; drop "(over ssh)" from the
      makeloginlink hint (multipass exec is the path).
- [x] F3 **settings.py comments** — CSRF note still says
      `app1.<ip>.sslip.io` (→ app.local behind caddy); "granian mounts
      this at /static" (→ caddy serves /static/* from STATIC_ROOT);
      `EnvironmentFile=/etc/credentials/<appname>/…` (→ fixed `app` path).
- [x] F4 **view docstrings/comments** — require_superuser docstring drops
      `/agent/` (Caddy route now); urls.py orphan "# /agent is served
      under Caddy" comment moved/removed to where it means something.
- [x] F5 **prompt-file self-correction** — Follow-up 8's dev-scratch
      claim fixed by C1; evening-sweep's "9 `tree:` tags inside-vm.sh"
      corrected (actual: 10 in testvm; inside-vm.sh uses `# ── file:`
      blocks + 2 `tree:` mentions).
- [x] F6 **INSTRUCTIONS.md stale rows** — dead playwright test name
      (`HookComponentE2eTestCase`, file no longer exists) and dead link
      (`docs/playwright-debugging.md` — only in prevproject). Update to
      current test paths or drop the two lines.

## G. Redeploy + validate (after A–F)

- [x] G1 Live VM: re-render + deploy the fixed granian unit, caddy site
      (A1/A2), inside-vm.sh, and repo copies (run/testvm/opencode.json/
      steer.md via seed-equivalent install); restart granian + reload
      caddy; verify `.map` 404 + app 200 + agent boots.
- [x] G2 Full gates: `./run checkall` (or the explicit set: ruff, mypy,
      157 backend tests, frontend lint/type-check/build — build is
      mandatory after B1/E2: `npm install` to prune, then build).
- [x] G3 Append the as-built note to this Part and flip every checkbox
      only after its verification line passes.

## No action (documented decisions, recorded for the record)

## As-built (Part 5, 2026-08-23)

All 25 items implemented same day. Highlights/deviations from the plan text:

- A2: the maps guard moved INSIDE `handle_path /static/*` (post-strip path
  `/djangoapp/*.map`) — verified LIVE: `…assets/main-B9bVGJ2B.css` → 200 +
  immutable header, `….css.map` → **404** (was serving before), app/agent
  200, granian `Restart=always` active, all four services green after
  redeploy + full on-VM bootstrap (uv sync pruned httpx, npm build with the
  new stylesheet, collectstatic 146 files).
- A5+D3: the postgres block became one `\gexec` heredoc with psql
  variables (%I/%L quoting, nothing in argv) behind a `pg_isready` poll
  (arithmetic kept out of `(( ))` so set -e can't abort the loop).
- B1: rename landed as planned — `rich-mockup`/`rich-diagram` +
  `styles/_richcontent.scss` (with `@use "variables" as *`; the initial
  build broke without it — fixed). Zero `opencode-*` marker references
  remain in frontend/src.
- C1: `$HOME/dev/*/scratch/**` (glob, not the literal ourinstant path) in
  both edit + external_directory; Follow-up 8's claim corrected in-place.
  [Later hand-edit simplified the file: `$HOME/**/scratch/**` in
  external_directory only — the as-built shape above is historical;
  Follow-up 8's note records the final form.]
- D2: redaction is two layers — `redact_login_keys()` in djangoapp/logging
  (middleware binds/logs the redacted path) + a `_redact_secrets`
  processor in _SHARED_PROCESSORS (covers django.server access lines and
  any straggler path/event). Tests: new test_log_redaction.py (3) + the
  assertLogs no-raw-key test; 167 backend tests OK (was 157).
  [REVERTED 2026-08-23, user decision: "remove the var redaction" — the
  whole D2 layer (both functions, the processor, the middleware
  pre-redaction, and all 4 tests) was removed the same day it landed;
  login-key URLs ride request logs unredacted again. Keys stay one-time
  + 15-min, which is the accepted mitigation.]
- E2: package.json lost diff/@types/diff/vitest + the test scripts; npm
  pruned 45 packages; frontend lint/type-check/build green.
- G2 gates: ruff clean, mypy 96 files clean (via ./run typecheck — bare
  mypy still dies without env: settings import), 167 tests OK, frontend
  all green. checkall's Playwright leg not re-run (browser suite; the
  explicit set above is the same gate checkall runs minus it).
- VM repo synced via a changed-files tar + manual rm of diff.ts; VM clock
  observed ~14h behind again during deploy (tar future-timestamp warnings)
  — known drift, chrony fix removed by earlier decision; manual
  `chronyc makestep` still available if skew symptoms appear.

- Unauthenticated LAN console + internal-CA click-through (H1) — user
  decision, LAN-trusted.
- `#MemoryMax=512M` commented out in ttyd.service.in — user hand-edit;
  rebuilds ship uncapped (no 96M hang; no runaway bound).
- settings.py not handling DANGEROUSLYUNSET (Follow-up 10) — enforced by
  D1's example-side fix instead.
- Concurrent-redemption test harness, `npm ci` vs `install` in bootstrap,
  journald persistence config, `/tmp` fixed paths for concurrent runs —
  noted by reviewers, accepted as-is for now.

> ### Follow-up 12 (2026-08-23 night): user commands + Quick start rewrite
>
> - **`createuser`** (new): email + `--first-name`/`--last-name`/
>   `--superuser`; username derives from the email local part; duplicate
>   email (iexact) refuses; `--superuser` routes through `User.update` so
>   the grant is audited in UserHistory; stdout points at makeloginlink.
>   5 tests (test_createuser.py). There is no signup flow — this is how
>   user rows come to exist on the VM (and dev without Google login).
> - **`makesuperuser` renamed `promotetosuperuser`** (git mv command +
>   test file; all refs swept: tests, README, access-steps.txt,
>   .env.vm.example, local .env.vm comment).
> - **README Quick start** (the evening's aihere: "make this a bullet list,
>   just mention why with no caveats"): converted to why-only bullets —
>   prerequisites, environment, run, first user (createuser +
>   makeloginlink + promotetosuperuser), Google login (addgoogleoauth),
>   agent (points the operator's AI agent at INSTRUCTIONS.md), test-VM
>   pointer. The console URL/CONSOLE_URL nav-link note the old prose
>   carried moved to the Commands section (info preserved, not lost).
> - Gates: ruff/mypy clean, 168 tests OK (+5); commands smoke-tested on
>   the live VM (help output for both); old makesuperuser files removed
>   there.

> ### Follow-up 13 (2026-08-23 late): git identity reduced to ONE env var
>
> User: keep only GIT_COMMITTER_NAME out of the four identity vars; email
> expected blank. The other three were LOAD-BEARING: with them gone, no
> commit works on the VM — git cannot auto-derive an email from the
> app.(none) hostname ("Author identity unknown" hard-fail), and a generic
> EMAIL="" is treated as unset. Design that satisfies the ask:
> - **Env (all files + live creds): GIT_COMMITTER_NAME="Opencode Agent"
>   only** — the agent marker. Comments rewritten everywhere (env examples,
>   inside-vm.sh, ttyd.service.in, run createscratch).
> - **Author identity lives in the REPO config**: vm-seed-commit.sh sets
>   user.name "console" + user.email "" (empty-string email is VALID via
>   config — verified: author console <>, committer Opencode Agent <>).
>   Dev keeps the human's own identity; run createscratch seeds a fallback
>   ($(id -un) + blank email) ONLY when no global user.name resolves.
> - Two pre-existing gaps this exposed, both fixed: (1) console couldn't
>   work main/ at the FS level — seed extraction now group-writes the
>   whole tree (find -exec chmod g+w) and the repo sets
>   core.sharedRepository=group; (2) macOS AppleDouble ._ files rode the
>   seed tarball into the first commit — seed now uses COPYFILE_DISABLE=1
>   + --exclude='._*'; live VM's ._ files deleted + committed.
> - safe.directory is BACK, scoped to /srv/app/main (system level) —
>   console got "dubious ownership" without it (Follow-up 9 removed the
>   parent-repo version; the need returns for the main/ repo itself).
> - Verified live: console commits AND resets in main/ (author console <>,
>   committer Opencode Agent <>); the sync commit itself was made through
>   the new path.

> ### Follow-up 14 (2026-08-24): glm-4.7 AGAIN — the env "model" keys were
> never real
>
> - User observed `./run agent` still prompting with glm-4.8/4.7 locally
> despite Follow-up 8's fix. Root cause: **OPENCODE_MODEL and
> OPENCODE_PROVIDER do not exist** — `strings` on the opencode binary
> shows no such env vars (only OPENCODE_AUTH_CONTENT/CONFIG/CONFIG_DIR/…
> are real). The two keys added to .env in Follow-up 8 were inert
> no-ops; opencode fell back to the provider's models.dev default.
>   Follow-up 8's "verified" was false — it checked that the debug
>   command RAN, never the resolved `model` field.
> - Fix: `"model": "zai-coding-plan/glm-5.2"` added to
>   agentconfig/opencode.json (the one real knob); the dead keys deleted
>   from .env/.env.example/.env.vm/.env.vm.example + the live VM creds
>   file (comments now say: model is NOT an env knob).
> - Verified BOTH machines via `opencode debug config`: model resolves to
>   zai-coding-plan/glm-5.2 (dev + VM); units restarted with the cleaned
>   env.

> ### Follow-up 15 (2026-08-24, minutes later): Follow-up 14's env-var
> conclusion was ITSELF wrong — final state: config-file model only
>
> User challenged the removal of OPENCODE_PROVIDER/OPENCODE_MODEL; retest
> showed the qualified env form resolving ONCE (`zai-coding-plan/glm-5.2`)
> — so I restored env keys and removed the config field. That one success
> then proved UNREPRODUCIBLE (identical command → undefined minutes
> later; catalog refreshed and still undefined — `debug config` does not
> reliably reflect env model overrides in 1.18.0), while a PRECEDENCE
> test proved config-file "model" SHADOWS the env var regardless.
> FINAL DESIGN (verified local + VM): "model":
> "zai-coding-plan/glm-5.2" in agentconfig/opencode.json — the single,
> deterministic knob; NO OPENCODE_MODEL/OPENCODE_PROVIDER anywhere (env
> comments explain why). Lesson recorded twice now: verify the RESOLVED
> value, reproducibly, not that a command merely ran.

> ### Follow-up 16 (2026-08-24): DEFINITIVE resolution — env-driven model
> via config substitution; Follow-ups 14/15 both wrong in opposite ways
>
> User asked to disable the JSON model pin and restore the env knob.
> Controlled experiments (opencode 1.18.15) settled everything:
> - Follow-up 14 was RIGHT for the WRONG reason: there is no native
>   OPENCODE_MODEL/OPENCODE_PROVIDER env var (per docs — the `strings`
>   "evidence" was worthless either way). Proven: env-only OPENCODE_MODEL
>   (any value) → live run still used glm-4.7 fallback.
> - Follow-up 15's "debug config is unreliable" was FALSE: `debug config`
>   only ever shows the merged config FILES — an env-only model NEVER
>   appears there, so its "undefined" results were the tool working
>   correctly. Its one "reproducible-then-lost success" must have had a
>   model key in the config under test. And the "precedence" test was
>   really: config value wins because the env var never existed.
> - The DOCUMENTED mechanism (Config → Variables → Env vars): config values
>   support `{env:NAME}` substitution. So the env CAN be the single knob:
>   `"model": "{env:OPENCODE_MODEL}"` in opencode.json is a pass-through,
>   not a pin.
> - FINAL DESIGN (user's choice): opencode.json model =
>   "{env:OPENCODE_MODEL}"; OPENCODE_MODEL="zai-coding-plan/glm-5.2"
>   (provider-qualified, required) in .env/.env.vm (+ examples, commented).
>   Unset resolves to "" → opencode SILENTLY falls back to a provider
>   default → new `./run agent` preflight check (5) refuses on
>   unset/empty instead.
> - Verified: `debug config` shows model=zai-coding-plan/glm-5.2 (env
>   sourced); live `opencode run` request used `> build · glm-5.2`; guard
>   refuses when unset; .env.vm exports it (VM gets it via existing
>   staging — units/source path unchanged). VM sync pending next provision.
