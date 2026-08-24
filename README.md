# Instant

A Django **single-app template**: clone it, build your app in `ourapp/`, and drive
changes through an agent that edits a throwaway.

## Features
- **Agent-driven development** — a [Crush](https://github.com/charmbracelet/crush)
  TUI
  edits a throwaway `scratch/` copy of the repo; you review, then
  `mergescratch` deploys to `main/` (server auto-reloads). Start it with
  `./run agent` — in production ONLY inside the VM's web terminal
  (`https://app.local/agent/`, where it runs the same command). See
  [Edit → test → deploy workflow](#edit--test--deploy-workflow).
- **Async tasks + cron (Huey)** — Redis-backed background tasks and scheduled
  jobs via `huey.contrib.djhuey` (reusing the same Redis as the error rate
  limiter). Run the consumer with `./run hueydev` (or `./run dev`). The reference
  app ships a daily "Fact of the Day" cron as the example (`docs/reference/`).
- **Models management** — a superuser UI at `/manage/models` to browse, sort,
  inspect and edit any model's rows, with a per-row audit log
  (create/update/delete diffs). See [Models management (superuser)](#models-management-superuser).
- **User management** — `/users` CRUD + search, identity by `public_id` (never
  the integer `pk`), audit history, and Google social login. See
  [User management](#user-management) and [Google OAuth](#google-oauth-social-login).
- **File browser** — `/files` to browse and preview the repo filesystem in-app.
- **Git viewer** — `/git` to browse commits, view diffs, and inspect the
  uncommitted working tree.
- **Structured logging** — one NDJSON line per record across the backend **and**
  frontend-reported errors (`/client-errors`, rate-limited via Redis), all
  `jq`-filterable. See [Logging](#logging).
- **Single-page Inertia + Vue frontend** — one build, sourcemaps emitted for
  offline row:col resolution; framework pages under `frontend/src/pages/`, the
  app's own under `frontend/src/ours/`.

## Quick start
- **Prerequisites** — Python 3.14+ with [`uv`](https://docs.astral.sh/uv/),
  Node.js + npm, PostgreSQL, and Redis run the app;
  [Crush](https://github.com/charmbracelet/crush) runs the agent
  (`npm install -g @charmland/crush`);
  [`ttyd`](https://github.com/tsl0922/ttyd) serves the web console.
- **Environment** — `./run init` copies `.env.example` → `.env`, generates
  `SECRET_KEY`, creates + migrates the database, and builds the frontend;
  set `DB_PASSWORD` to your local postgres afterwards.
- **Run** — `./run dev` starts runserver + vite + huey + the web console in
  one terminal (Ctrl-C stops all four); then open
  http://127.0.0.1:8000/ — `ourapp/` is a placeholder landing page, and
  `docs/reference/` holds the copyable example app (facts + todos).
- **First user** — there is no signup flow: create the row and sign in via a
  one-time link —
  `./run djangomanage createuser you@example.com --first-name You --last-name Name --superuser`
  then `./run djangomanage makeloginlink you@example.com` (opens
  `/login-for-test/by-key/…`, single use; `promotetosuperuser <email>`
  promotes an existing user later).
- **Google login** (dev) — register OAuth credentials and store them with
  `./run djangomanage addgoogleoauth <client_id> <secret>`.
- **Agent** — point your AI agent at this repo and have it read
  `INSTRUCTIONS.md` (the operating manual: workflows, conventions,
  command allowlist); start it with `./run agent`.
- **Test VM instead** — the whole loop can run on a Linux VM (multipass):
  see [VM (test server)](#vm-test-server).

## VM (test server)

The whole loop can run on a Linux VM (multipass) instead of your local
machine; the workstation becomes just a browser + ssh client. All VM config
lives in one env file — copy the template first:

```bash
cp .env.vm.example .env.vm    # then fill in generated secrets
```

- **Secrets**: `SECRET_KEY` and `DB_PASSWORD` ship as `DANGEROUSLYUNSET`
  and provisioning refuses to build on that value (validated host-side by
  `./testvm provision`, before anything ships). Generate high-entropy
  values with `openssl rand -hex 32`.
- Database names are fixed (`app_db`/`app_user` from the env values) — one
  app per VM by design.

Then one command builds everything (1G RAM + 2G swap, postgres + redis
localhost-only, caddy TLS, `/srv/app/main` (a `scratch/` sibling appears
when you run `./run createscratch` there), systemd units
`app_granian` + `app_huey` under the **less powerful `app` user**, and
`console_ttyd` under the **powerful `console` user** — huey omitted when
`HUEY_WORKERS=0`):

```bash
./testvm provision              # builds and prints access + login steps
```

One hostname, one HTTPS port, direct over the LAN (no tunnel); the
terminal rides the same origin at `/agent/`. The internal-CA cert means a
click-through warning (the supported mode):

- **`https://app.local/`** — the app. Login is **not Google OAuth**
  (`.local` isn't registrable): mint a one-time link for an existing user —

  ```bash
  multipass exec app -- sudo -u app -H bash -c \
    'set -a; . /etc/credentials/app/.env.vm; set +a; cd /srv/app/main; .venv/bin/python manage.py makeloginlink <email>'
  ```

  — open the printed `/login-for-test/by-key/…` URL once (single use,
  15-min expiry), then `promotetosuperuser <email>` to unlock admin pages and
  the "Console" nav link.

**Everything else happens on the VM**: `./run createscratch` → `./run
agent` (in the console terminal) edits `scratch/` → `./run checkscratch`
→ `./run mergescratch` (runs collectstatic — static is live immediately;
code changes need `sudo systemctl restart app_granian app_huey`, printed
by the merge). The env on the VM is a single file all services share
(`/etc/credentials/app/.env.vm`, staged from the root `.env.vm`).

Provisioning is **build-or-destroy**: it refuses when the VM exists — to
apply changes, delete and rebuild.

```bash
./testvm delete                 # multipass delete+purge — destructive, no backup step
```

The VM's `.git` is its own history — copy anything you need off it
(tar via `multipass transfer`, `pg_dump` via `multipass exec`) before
deleting. Plan + full manifest of
everything provisioning touches: `prompts/20260818-vm-provisioning-multipass.md`.

## Google OAuth (social login)

Credentials live in the database, not in settings or `.env`. After the first
`migrate`, register the Google app once:

```bash
./run djangomanage addgoogleoauth <client_id> <secret>
```

This creates (or updates) a `SocialApp` for `provider="google"` linked to the
current `SITE_ID`, with `scope=["profile","email"]` and
`auth_params={"access_type":"online"}` — the equivalent of the old
`SOCIALACCOUNT_PROVIDERS` block. Re-run it to rotate credentials; no duplicate
row is created. This is for DEV (or any deployment whose hostname Google
accepts); the test VM skips Google OAuth entirely and logs in via one-time
`makeloginlink` URLs — see [VM (test server)](#vm-test-server).

## Sign in (one-time login link)

There is no signup flow and (in dev) possibly no Google login yet — sign in
by minting a one-time link for an existing user (e.g. one created with
`createuser`):

```bash
./run python manage.py makeloginlink alice@example.com
```

Open the printed `/login-for-test/by-key/…` URL once — single use,
15-minute expiry (`--minutes N` to change), and only the SHA-256 of the key
is stored. On the test VM the same command runs via `multipass exec` — see
[VM (test server)](#vm-test-server).

## Promote a user to superuser

Social-login users can't be superuser at creation. Promote an existing user by
email (matched case-insensitively; sets both `is_superuser` and `is_staff` so
`/admin` works):

```bash
./run python manage.py promotetosuperuser alice@example.com
```

Once promoted, that user can reach the management routes below.

## The user app (`ourapp/`)

`ourapp/` is a normal Django app (in `INSTALLED_APPS`). It ships with only the
landing page — you add your features there and in its frontend. Features are
split into modules (one per feature), never stuffed into one file:

- **Models** (`ourapp/models/`): one module per feature (`models/<feature>.py`),
  imported in `models/__init__.py` so Django finds them. Each concrete class
  subclasses `djangoapp.models.BaseModel`, which provides `public_id`, audit
  fields (`created_by`, `created_at`, `last_updated_at`, `last_updated_by`) and
  `get_absolute_url()`. Give each a docstring. Add/change a model →
  `./run djangomanage makemigrations ourapp`.
- **API** (`ourapp/views/`): one django-ninja `Router` per feature
  (`views/<feature>.py`); `views/__init__.py` owns the single `NinjaAPI` and
  registers every router. Page responses render via Inertia
  (`InertiaResponse(request, "ours/<Page>", {"props": …})`), data responses are
  pydantic schemas.
- **URLs** (`ourapp/urls.py`): mounts the ninja API at the project root, so each
  route is served at its literal URL — **including the landing page `/`**, which
  the app owns (the framework serves no home route).
- **Commands** (`ourapp/management/commands/`): seed/setup commands, one module
  per command.
- **Tests**: `ourapp/tests/` — flat, one file per feature + layer
  (`test_<feature>_<layer>.py`; layer = `models`/`views`/`commands`/`playwright`).
  Playwright files are tagged so `./run test` skips them and `./run playwrighttest`
  runs them.
- **Frontend**: one Vue+Inertia app. App pages live in
  `frontend/src/ours/pages/<Name>.vue` (component name `ours/<Name>`); shared
  components in `frontend/src/ours/components/`.

The app also has its own `README.md` (a brief feature catalog) and `docs/`
(one markdown file per feature, linked from the README). See
`agentconfig/steer.md` for the "Checklist — adding or changing a feature".

See `docs/reference/` for a complete copyable example (the **facts** feature —
a `Topic` + `Fact`, a seed command, two pages — and the **todos** feature — a
`Todo` owned by a `User`, one page).

## Models management (superuser)

Mounted under `/manage` (superuser-only; anyone else gets a 404). Lists every
concrete `BaseModel` subclass in `ourapp/` by class name, with its docstring and
browseable rows. A foreign-key cell links to the referenced row via that row's
`get_absolute_url()`.

- `/manage/models` — list of models (name, docstring, row count)
- `/manage/models/<model>/list` — paginated rows (sortable by created/edited)
- `/manage/models/<model>/id/<public_id>` — single-row detail

## Edit → test → deploy workflow

The repo is `main/` (with `.git`); `scratch/` is a throwaway sibling (the
agent reaches it via `../scratch` — pre-approved in agentconfig). For every
change:

1. `./run createscratch` (from `main/`) — copy `main/` (minus `.git`/`node_modules`/`.venv`/caches)
   into a fresh `../scratch/`, bootstrap its own env (`uv sync` + `npm install`), and
   `git init` it.
2. Edit `../scratch/`.
3. `( cd ../scratch && ./run checkscratch )` — ruff + mypy + `ourapp` tests + frontend
   lint/type-check/build (the fast loop: the framework suite and Playwright stay
   in `main/`). Must finish green. When scratch edits touch framework files
   (outside `ourapp/` + `frontend/src/ours/`), it also runs the tagged
   `framework-subset` smoke tests. Run `checkframework1` in `main/` for the full gate.
4. `./run mergescratch` (from `main/`) — deploy `../scratch/` into `main/` (never overwriting
   `main/.env`). This does **not** commit.

In dev the server auto-reloads `main/` after a deploy, so the user sees the
change live. Commit in `main/` as a separate step when ready.

## User management

Users are managed under `/users/` (`djangoapp/views/users.py`). Every management
route requires a superuser; anyone else gets a 404. A user's identity in every
URL and response is `public_id` (a URL-safe UUID7); the integer `pk` is never
sent to clients.

- `/users/list` — paginated list (25/page); `?q=` trigram search; `?page=N`.
- `/users/api/search?q=` — top-20 matches across first/last name + username.
- `/users/id/<public_id>` — profile (superuser sees the admin panel).
- `/users/edit/<public_id>` — superuser-only edit.
- `/users/history/<public_id>` — superuser-only audit trail.

A superuser can't clear their own `is_superuser`/`is_active`, so the active
superuser count can never fall to zero through the UI.

## Commands

App/dev via the `run` script: `init`, `runserver`, `dev`, `console`,
`agent`, `test`,
`typecheck`, `lintfix`, `playwrighttest`, `checkscratch`, `checkframework1`,
`checkframework2`, `checkproject`, `createscratch`, `mergescratch`, `cleanscratch`,
`hueydev` (background consumer alone), `coverage`,
plus `djangomanage`/`python` passthroughs (e.g.
`./run djangomanage makemigrations`, `./run python manage.py …`).
User/management commands (via the passthrough):
`createuser <email> [--first-name …] [--last-name …] [--superuser]`,
`makeloginlink <email>` (one-time login URL),
`promotetosuperuser <email>`, `addgoogleoauth <client_id> <secret>`.
`./run console` serves the web terminal at http://localhost:7681 (also part
of `./run dev`); set `CONSOLE_URL` in `.env` to point the superuser
**Console** nav link at it.

Test-VM lifecycle via the `testvm` script: `./testvm provision [--release …]`,
`./testvm delete`.


## Logging

The whole app — backend **and** frontend-reported errors — emits one
**JSON object per line** (NDJSON) so the stream is `jq`-filterable. Configure
it once in `djangoapp/logging.py`; `LoggingContextMiddleware` (in
`djangoapp/middleware.py`) binds per-request context.

### Backend

Every logger flows through one structlog `ProcessorFormatter`, so Django's own
loggers (`django.request`/`django.security`), third-party libs (allauth,
ninja, …) and our code all come out with the same shape. Import the logger from
`djangoapp.logging`, never `structlog` directly. Pass key/value fields (not an
f-string) so each line stays `jq`-filterable:

```python
from djangoapp.logging import get_logger

logger = get_logger(__name__)
logger.warning("files fetch failed", path=path, error=str(exc))   # recovered problem
try:
    risky()
except Exception:
    logger.exception("unhandled", method=request.method)         # structured traceback
```

`LoggingContextMiddleware` binds `method`, `path`, `user_public_id`, `username`
onto every line in a request (the integer `pk` is never logged). `exception` is a structured list of stack frames (local variables redacted), not a trailing string.

```bash
jq 'select(.level=="error")'
jq 'select(.logger=="client")'                              # frontend-reported errors
jq 'select(.event=="http request" and .user_public_id=="<id>")'
```

### Frontend errors

Uncaught browser errors are captured globally (`window error`,
`unhandledrejection`, Vue `errorHandler`) by `frontend/src/utils/clientError.ts`
and POSTed (async, `await`ed) to `/client-errors`, which logs them on the
**`client`** logger (`source=client`). Each report carries the browser source
location (`client_filename`/`client_lineno`/`client_colno`, resolvable against
the emitted sourcemap), `url`, `user_agent`, Vue's `info` hint, and the
reporter's `public_id`; the backend re-derives the authoritative identity from
`request.user` (never the body) and accepts anonymous reports (`user=null`). A
`navigator.sendBeacon` fallback fires on `pagehide` only while a POST is in
flight, so an error caught right before navigation isn't lost (and isn't re-sent
once delivered). Redis is a hard dependency for the per-identity rate limit:
`REDIS_URL` (required) + `CLIENT_ERROR_RATE_LIMIT` (optional, commented in
`.env.example`; default 30 per 60s) drive it, and if redis is unreachable
the endpoint **fails
closed** (500 — the redis error propagates to the global handler) rather than
accepting an unbounded stream.

```bash
jq 'select(.source=="client")'        # every frontend-reported error
jq 'select(.source=="client" and .user_public_id=="<id>")'
```

Sourcemaps are emitted in every build (`vite.config.js` `sourcemap: true`) for
offline/server-side row:col resolution; the serving layer must deny `*.map`
under `/static/djangoapp/` so they never reach clients.

## Testing

Four tiers:

- **`checkscratch`** — the fast loop, run in `scratch/` while editing. ruff +
  mypy (whole codebase), `ourapp`'s own tests only, and the frontend
  lint/type-check/build. Skips the framework suite and Playwright (those run in
  `main/`) — unless the edit touches framework files (outside `ourapp/` +
  `frontend/src/ours/`), which adds the tagged `framework-subset` smoke tests.
- **`checkframework1`** — the full gate, run in `main/`. ruff + mypy + the whole backend
  suite + frontend lint/type-check + Playwright.
- **`checkframework2`** — the deployment gate. Rebuilds the test VM from scratch
  (`./testvm`), deploys the Books test app over the VM's `ourapp/`, and smokes
  the live stack over HTTPS from the host (login link → session, superuser
  gates, the `/agent` forward_auth gate). Destructive: the previous VM is deleted.
- **`checkproject`** — overlay validation against a real app. Two `createscratch`
  cycles:
  1. Overlays the **test app** (`djangoapp/tests/testapp/`) → runs the full suite
     with `RUN_PROJECT_TESTS=1` (project tests un-skipped: real models/git/files).
  2. Overlays the **reference app** (`docs/reference/`) → runs its own tests.

The **test app** (`djangoapp/tests/testapp/`) is a fixture: a complete `ourapp/`
with models exercising every field kind + both FK types, plus an `ours/` page. The
**reference app** (`docs/reference/`) is the user-facing example, same format,
shipping its own tests. Both are excluded from ruff/mypy (they're only valid when
overlaid onto `ourapp/`).

