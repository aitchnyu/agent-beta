# Foundation scaffold

Django app with allauth, user management (no UI to create users), Vue frontend. We need `./run`.

This is the **foundation only** — the per-mini-app system (`/app/folder/appname`, per-app sqlite dbs, `functions.py`) is out of scope and comes in later prompts. Goal of this prompt: a runnable project you can log into via Google, a Vue home page, and a green `./run checkall`.

Reference: `prevproject/` is the only source of truth for conventions (settings shape, custom `User`, inertia layout, `./run`, ruff/mypy strictness). Per README, do not copy anything else from it.

## Resolved decisions

- **Database:** Postgres via `psycopg2-binary`. `./run init` creates the `instant` db with `psql`, then `migrate`. Mirrors prevproject's `.env` shape (`DB_NAME`/`DB_USER`/...).
- **Frontend:** inertia-django + Vue 3 (`@inertiajs/vue3`), single `main.ts` entry, vite build output to `djangoapp/static/djangoapp/{main.js,main.css}`, inertia layout at `djangoapp/templates/inertia/base.html`. Same as prevproject.
- **Auth:** allauth social login (Google now). `accounts/` mounts `allauth.urls`; allauth's own templates render login/logout (server-rendered, not inertia) — the Vue app only handles authenticated app pages. A later prompt adds a management command to register more providers (prevproject TODO).
- **User creation:** no UI form. Users are created by allauth on first Google login. Local email/password signup is **disabled** (`ACCOUNT_LOGIN_METHODS={"email"}`, `SOCIALACCOUNT_ENABLED=True`, no local signup) so the only entry is social.
- **Custom `User`:** `AbstractUser` + a small mixin carrying a URL-safe `public_id` (uuid7), `description`, `has_public_profile`. `AUTH_USER_MODEL = "djangoapp.User"`. No integer `pk` ever sent to the client (AGENTS.md hard rule). Keep it lean — no `search_users`/history/edit endpoints yet (those are later prompts); just enough for identity + a profile display.
- **No pk/id leak:** every public URL and API response uses `public_id`. Settings/app code must never serialize `.pk`/`.id`.
- **`on_delete` default:** `RESTRICT` (AGENTS.md).
- **Strict tooling:** `pyproject.toml` carries ruff (`select=["ALL"]` + prevproject's ignores), mypy strict + django-stubs plugin, target py314. `./run checkall` runs ruff, mypy, test suite, then frontend lint/type-check. Playwright is wired but no e2e tests are required to pass for this foundation (there are none yet) — `checkall` still calls `playwrighttest` so the harness stays green; it simply runs zero tagged tests.
- **Settings loading:** `python-dotenv` `load_dotenv(override=True)`; required keys via `os.environ[...]` (fails fast if `.env` missing). `.env.example` checked in, `.env` gitignored.
- **CSP:** copy prevproject's CSP setup (DEBUG uses report-only strict + lenient enforced; prod enforces). Google login needs `accounts.google.com` in `form-action`.

## Plan

- Stand up a new Django project package `djangoproject/` and app `djangoapp/`, with the custom `User` declared in the app's first migration (a custom user model cannot be retrofitted later — it must land in migration 0001).
- Mount `accounts/` (allauth) and `djangoapp/` urls; `djangoapp/` exposes one inertia `Home` page (`/`) showing login state + a login/logout link.
- Frontend: minimal Vue 3 + inertia + a `Home.vue`; eslint + `vue-tsc` type-check; vite dev build via `npm run dev` (watch) for dev, `npm run build` for `checkall`/production.
- `./run` mirrors prevproject: `init`, `runserver`, `test`, `typecheck`, `lintfix`, `checkall`, plus `frontend`-aware lint steps. Adapt for db name `instant` and this repo's paths.
- Smoke tests: assert `User` gets a `public_id` on creation; assert Home page renders for anon and authenticated; assert local signup/login endpoints are absent/disabled. Backend lint (ruff + mypy) and frontend lint/type-check must be clean.

## Checklist

### Phase 1: Project skeleton + deps

- [x] `pyproject.toml` (deps: django>=6, django-allauth[socialaccount], inertia-django, psycopg2-binary, pydantic, python-dotenv, python-dateutil + types-python-dateutil, nh3; dev: ruff, mypy, django-stubs[compatible-mypy], coverage, playwright) — mirror prevproject's ruff/mypy/tool.django-stubs config, db name irrelevant here
- [x] `.python-version` (3.14), `.gitignore` (mirror prevproject), `.env.example` (db `instant`, postgres creds, SECRET_KEY/DEBUG/ALLOWED_HOSTS/TIME_ZONE, GOOGLE_OAUTH_CLIENT_ID/SECRET)
- [x] `manage.py` (DJANGO_SETTINGS_MODULE=djangoproject.settings)
- [x] `djangoproject/` package: `__init__.py`, `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`

### Phase 2: settings.py

- [x] `load_dotenv(override=True)`; `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/`TIME_ZONE` from env; raise if `SECRET_KEY=="fake"` in prod
- [x] `INSTALLED_APPS`: django contrib (incl `sites`, `postgres`), allauth (`allauth`, `allauth.account`, `allauth.socialaccount`, `allauth.socialaccount.providers.google`), `djangoapp`, `inertia`
- [x] `MIDDLEWARE`: django defaults + `allauth.account.middleware.AccountMiddleware`
- [x] `DATABASES` Postgres from env
- [x] `AUTH_USER_MODEL = "djangoapp.User"`, `AUTHENTICATION_BACKENDS` (ModelBackend + allauth), `SITE_ID = 1`
- [x] allauth: `SOCIALACCOUNT_ONLY=True`, `ACCOUNT_EMAIL_VERIFICATION="none"`, `SOCIALACCOUNT_EMAIL_VERIFICATION="none"`, `SOCIALACCOUNT_EMAIL_REQUIRED=True`, `LOGIN_REDIRECT_URL="/"`, `LOGOUT_REDIRECT_URL="/"`
- [x] `SOCIALACCOUNT_PROVIDERS["google"]` reading client_id/secret from env (no hardcoded creds)
- [x] `INERTIA_LAYOUT = "inertia/base.html"`
- [x] CSP (mirror prevproject; `accounts.google.com` in `form-action`; DEBUG ws for vite)
- [x] `DEFAULT_AUTO_FIELD`, static, i18n

### Phase 3: djangoapp (models, urls, views, templates)

- [x] `djangoapp/` package: `__init__.py`, `apps.py`, `admin.py`, `migrations/__init__.py`
- [x] `djangoapp/models/` with the `User` model (`AbstractUser` + manager; `public_id` uuid7 unique editable=False, `description`, `has_public_profile`; `display_name` property; no `search_users`/history yet); custom `UserManager(DjangoUserManager)` so allauth keeps working
- [x] `makemigrations djangoapp` -> single `0001_initial.py` (User first); no TrigramExtension yet (deferred until search lands)
- [x] `djangoapp/templates/inertia/base.html` (defines `{% block inertia %}`; inertia-django injects the `data-page` div via its own `inertia.html`)
- [x] `djangoapp/views/home.py`: a `home` view returning an inertia `Home` page with `{is_authenticated, display_name, public_id}` props (no pk)
- [x] `djangoapp/urls.py`: mount `home` at `/`
- [x] `djangoproject/urls.py`: `admin/`, `accounts/` (allauth), `""` -> `djangoapp.urls`

### Phase 4: Frontend

- [x] `frontend/package.json` (vue, @inertiajs/vue3, axios, zod; dev: vite, @vitejs/plugin-vue, typescript, vue-tsc, eslint, prettier, sass, npm-run-all)
- [x] `frontend/vite.config.js` (outDir `../djangoapp/static/djangoapp`, entry `src/main.ts`, `main.js`/`main.css` output names)
- [x] `frontend/eslint.config.js`, `tsconfig*.json`, `.prettierrc`, `.npmrc` (mirror prevproject)
- [x] `frontend/src/main.ts` (createInertiaApp, axios CSRF wiring, global error net), `main.scss`
- [x] `frontend/src/pages/Home.vue` (shows login state + Login (Google) / Logout (CSRF form POST); parse props via zod)
- [x] `frontend/src/schemas.ts` (`HomePropsSchema`)
- [x] `npm install` + `npm run lint:fix` + `npm run type-check` + `npm run build` clean

### Phase 5: ./run

- [x] `run` (executable) mirroring prevproject: `init` (uv sync, playwright install firefox, `psql create database instant`, migrate, frontend npm install + build), `runserver`, `test` (exclude-tag playwright), `typecheck`, `lintfix`, `checkall` (ruff, mypy, test, frontend lint+type-check, playwrighttest). Adapted db name + paths to this repo.

### Phase 6: Tests (add right after each phase)

- [x] `djangoapp/tests/test_user_model.py` — `User` auto-generates `public_id` on creation; `public_id` is unique; `display_name` joins first/last, falls back to username
- [x] `djangoapp/tests/test_home.py` `HomeViewTests` — anon GET `/` 200 with `is_authenticated=False`; authenticated GET `/` 200 with display_name + public_id
- [x] `djangoapp/tests/test_home.py` `NoPkLeakTests` — assert `id`/`pk` absent from props, only `public_id` exposed
- [x] `./run typecheck` + `./run test` green (7 tests)

### Phase 7: Lint + checkall to the finish

- [x] `./run lintfix` (backend ruff format/check + frontend eslint:fix)
- [x] `./run typecheck` (mypy) clean (19 source files)
- [x] frontend `npm run lint` + `npm run type-check` clean
- [x] `./run checkall` runs to the end (exit 0; playwright step runs zero tests, stays green)
- [x] Manual: dev server returns the Inertia Home page at `/` with anon props; static `main.js`/`main.css` served (200). Live Google login needs `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_SECRET` in `.env`.

## Phase 8: Playwright user tests + logout CSRF fix

Follow-on: "playwright tests for users". prevproject's `test_users.py` targets superuser edit/history pages (`/users/edit/`, `/users/history/`) that don't exist in instant yet, so it can't be copied verbatim. Ported the **harness** and wrote tests for the user flows instant actually has.

- [x] Logout CSRF fix: `{% csrf_token %}` in [djangoapp/templates/inertia/base.html] so the `csrftoken` cookie is issued on every Inertia GET (otherwise the logout form posts an empty token -> 403); regression unit test `test_home_issues_csrftoken_cookie` in [djangoapp/tests/test_home.py]
- [x] DEBUG-gated `login-for-test/<int:userid>` view (404 when `DEBUG=False`) in [djangoapp/views/login_for_test.py], wired in [djangoapp/urls.py] — mirrors prevproject so playwright can bypass Google OAuth
- [x] Lean `BasePlaywrightTestCase` harness in [djangoapp/tests/playwright/test_playwright.py] (headless firefox, console-error fail, pre-authenticated `logged_in_page`, `anon_page()` context manager) — prevproject's table-specific helpers dropped as not-yet-applicable
- [x] `HomeAuthE2eTestCase` + `LoginForTestGateE2eTestCase` in [djangoapp/tests/playwright/test_users.py]:
    - [x] anon `/` shows signed-out + Google login link, no logout button
    - [x] authed `/` shows display name + logout button, no login link
    - [x] full logout round-trip (POST `/accounts/logout/` -> back on signed-out home)
    - [x] `login-for-test` is 404 with `DEBUG=False`
- [x] Added stable selectors to [frontend/src/pages/Home.vue] (`home-status-signed-in/out`, `home-display-name`, `home-login-link`, `home-logout-btn`) for `wait_for_selector`/`wait_for_url`
- [x] `./run checkall` green: ruff clean, mypy 23 files, 8 non-playwright tests, **4 playwright tests pass**, frontend lint/type-check clean
