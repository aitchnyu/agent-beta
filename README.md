# Instant

A Django **single-app template**: clone it, build your app in `ourapp/`, and drive
changes through an agent that edits a throwaway.

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
row is created.

## Promote a user to superuser

Social-login users can't be superuser at creation. Promote an existing user by
email (matched case-insensitively; sets both `is_superuser` and `is_staff` so
`/admin` works):

```bash
./run python manage.py makesuperuser alice@example.com
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

The repo is `main/` (with `.git`); `scratch/` is a throwaway sibling under the same
parent. For every change:

1. `main/run createscratch` — copy `main/` (minus `.git`/`node_modules`/`.venv`/caches)
   into a fresh `scratch/`, bootstrap its own env (`uv sync` + `npm install`), and
   `git init` it.
2. Edit `scratch/`.
3. `( cd scratch && ./run checkscratch )` — ruff + mypy + `ourapp` tests + frontend
   lint/type-check/build (the fast loop: the framework suite and Playwright stay
   in `main/`). Must finish green. Run `checkall` in `main/` for the full gate.
4. `main/run mergescratch` — deploy `scratch/` into `main/` (never overwriting
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

All via the `run` script: `init`, `runserver`, `test`, `typecheck`, `lintfix`,
`playwrighttest`, `checkscratch`, `checkall`, `checkproject`, `createscratch`,
`mergescratch`, `cleanscratch`, plus `djangomanage`/`python` passthroughs (e.g.
`./run djangomanage makemigrations`, `./run python manage.py …`).


## Logging

The whole app — backend **and** frontend-reported errors — emits one
**JSON object per line** (NDJSON) so the stream is `jq`-filterable. Configure
it once in `djangoapp/logging.py`; `LoggingContextMiddleware` (in
`djangoapp/middleware.py`) binds per-request context.

### Backend

Every logger flows through one structlog `ProcessorFormatter`, so Django's own
loggers (`django.request`/`django.security`), third-party libs (allauth, httpx,
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
`REDIS_URL` (defaults to the local redis) + `CLIENT_ERROR_RATE_LIMIT` (in
`.env.example`) drive it, and if redis is unreachable the endpoint **fails
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

Three tiers:

- **`checkscratch`** — the fast loop, run in `scratch/` while editing. ruff +
  mypy (whole codebase), `ourapp`'s own tests only, and the frontend
  lint/type-check/build. Skips the framework suite and Playwright (those run in
  `main/`).
- **`checkall`** — the full gate, run in `main/`. ruff + mypy + the whole backend
  suite + frontend lint/type-check + Playwright.
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

