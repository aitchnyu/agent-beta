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

`ourapp/` is a normal Django app (in `INSTALLED_APPS`). It ships empty — you add
your code:

- **Models** (`ourapp/models.py`): concrete classes subclassing
  `djangoapp.models.BaseModel`, which provides `_public_id`, `_created_by`,
  `_created_at`, `_edited_at` and `get_absolute_url()`. Give each a docstring.
  Add/change a model → `./run djangomanage makemigrations ourapp`.
- **API** (`ourapp/views.py`): a django-ninja API — page responses render via
  Inertia (`InertiaResponse(request, "ours/<Page>", {"props": …})`), data
  responses are pydantic schemas. (Recommend ninja routers for all ourapp URLs.)
- **URLs** (`ourapp/urls.py`): mounts the ninja API at the project root, so each
  route is served at its literal URL.
- **Frontend**: one Vue+Inertia app. App pages live in
  `frontend/src/pages/ours/<Name>.vue` (component name `ours/<Name>`); shared
  components in `frontend/src/components/ours/`.

See `docs/reference/` for a complete copyable example (a `Note` model with a
`User` foreign key, a ninja list + create API, a page, and a test).

## Models management (superuser)

Mounted under `/manage` (superuser-only; anyone else gets a 404). Lists every
concrete `BaseModel` subclass in `ourapp/` by class name, with its docstring and
browseable rows. A foreign-key cell links to the referenced row via that row's
`get_absolute_url()`.

- `/manage/models` — list of models (name, docstring, row count)
- `/manage/models/<model>/list` — paginated rows (sortable by created/edited)
- `/manage/models/<model>/id/<public_id>` — single-row detail

## Edit → test → deploy workflow

The repo is `main/` (with `.git`); `copy/` is a throwaway sibling under the same
parent. For every change:

1. `main/run createscratch` — copy `main/` (minus `.git`/`node_modules`/`.venv`/caches)
   into a fresh `copy/`, bootstrap its own env (`uv sync` + `npm install`), and
   `git init` it.
2. Edit `copy/`.
3. `( cd copy && ./run checkall )` — ruff + mypy + tests + frontend lint/type-check
   + Playwright. Must finish green.
4. `main/run mergescratch` — deploy `copy/` into `main/` (never overwriting
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
`playwrighttest`, `checkall`, `createscratch`, `mergescratch`, plus `djangomanage`/`python`
passthroughs (e.g. `./run djangomanage makemigrations`,
`./run python manage.py …`).
