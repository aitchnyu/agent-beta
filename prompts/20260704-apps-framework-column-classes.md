# Apps framework + typed column classes

TODO.md described a new direction: typed column classes, keyword-only registry
signatures, and a decorator-based app framework (`@setup` / `@get_endpoint` /
`@backend_test`) installed via `./run djangomanage setup`. This prompt
implements it; README.md is the reference for the implemented API.

## Decisions (resolved)

- `create_application(*, collection, name, description="", tables=None, script)` — keyword-only, creates tables inline when `tables` is given, **keeps `description`** (rich text, sanitized on save).
- `create_application_table(*, collection, application, table, columns)` — keyword-only.
- **Add `DecimalColumn`** (decimal stays a supported type).
- `script` is a **file path** (`collection/app/app.py`), stored on a new `Application.script` field (+ migration).
- **Replace dict specs entirely** — only `Column` objects accepted; update every dict-spec caller.
- `@backend_test` lives **in the same `app.py`** as `@setup` (not a separate script).
- The committed example app is a **fixture under `djangoapp/tests/`** (`apps/` is gitignored).
- **No CLI for creating apps/tables** — creation is registry-only, inside setup scripts.
- **Rollback on `@backend_test` failure** rolls back the whole script (DB changes + DDL reverted, registry cache reset).

## Plan

### Phase 1 — Column classes + new signatures
- New `djangoapp/models/columns.py`: a `Column` base (validates `name` against
  `COLUMN_NAME_RE`, stores common kwargs) and `CharColumn`, `TextColumn`,
  `IntegerColumn`, `BooleanColumn`, `DecimalColumn`, `DateTimeColumn`,
  `UserColumn`. `name` is positional; everything else keyword-only. Each class
  validates its own kwargs (e.g. `DecimalColumn` requires `max_digits`/
  `decimal_places`; `CharColumn` requires `max_length`) and exposes its
  `ColumnType` so the registry can build the right Django field.
- Rewrite `DynamicModelRegistry.create_application` / `create_application_table`
  to the keyword-only signatures above. `create_application` with `tables`
  creates each table in the same transaction. Internally convert `Column`
  objects into `ApplicationTableColumn` rows + Django fields (replacing the
  dict-based `_create_column_row`).
- Add `Application.script` (`CharField`, the file path) + migration. `full_clean`
  / save unchanged otherwise.
- Update `add_application_table_columns` / `delete_application_table_columns`
  (the latter takes `names=` kwarg list) to the keyword-only style and Column
  inputs where columns are passed.
- Update callers: `applications.py` / `applications_schemas.py` commands
  (describe still reads; no creation CLI), `_create_column_row`, and **all
  tests** (`test_dynamic`, `test_row_views` x2, `test_applications_views`,
  `test_applications_command`) to Column
  objects + keyword-only calls.

### Phase 2 — App framework (decorators + registry)
- New `djangoapp/apps/` package:
  - `decorators.py`: `@setup`, `@get_endpoint`, `@backend_test` — register the
    module's functions into a per-module `AppRegistration` (setup fn, endpoints
    keyed by function name, backend tests).
  - `context.py`: `RequestContext` (wraps the Django request + viewer user) and
    a `fake_context()` helper for backend tests.
  - `registry.py`: collects registrations; resolves an endpoint by
    `(collection, app, function_name)` using the `script` path the runner passes
    (works for both `apps/` installs and the `tests/` fixture).
- Return-type convention: each `@get_endpoint` function returns a Pydantic
  model; the endpoint view serializes it to JSON.

### Phase 3 — `djangomanage setup` + endpoint serving
- New management command `setup <path>` (invoked via `./run djangomanage setup`):
  - Import the module (its dir on `sys.path` so decorators register).
  - Run `@setup` inside one `transaction.atomic()` (Postgres transactional DDL
    means created tables roll back too). `@setup` calls `create_application`,
    so the runner knows the resulting `Application` (collection + name) and
    binds that module's endpoints to it.
  - Run every `@backend_test` (call the endpoint functions in-process with
    `fake_context()`).
  - On any failure (`@setup` raise or a `@backend_test` failure/raise): roll
    back the transaction and `dynamic_models.reset()` so nothing is left
    installed. Exit non-zero with the failure for the agent feedback loop.
- New URL route + view `/apps/a/<collection>/<app>/endpoint/get/<func>`:
  resolve the `Application` by (collection, app), read its `script` path,
  import that module (cached), look up the `@get_endpoint` function by name,
  build `RequestContext`, call it, validate the return against its Pydantic
  schema, return JSON. Unknown collection/app/func → 404. (So endpoint binding
  is DB-driven via `Application` + `script`, not the filesystem layout — the
  same path serves `apps/` installs and the `tests/` fixtures.)

### Phase 4 — stub apps, tests, README
- Committed stub apps as fixtures under `djangoapp/tests/apps/` (see
  [Tests & stub apps](#tests--stub-apps) below). More than one, each exercising
  a distinct scenario.
- README: already updated to the new API in this change; verify column classes
  + dynamic-model methods are fully documented after implementation.

## Tests & stub apps

Stub apps are real `app.py` modules under `djangoapp/tests/apps/<name>/`,
imported by the `setup` runner via their `script` path. Each has `@setup`
(create the app + table(s)) + `@get_endpoint`(s) + `@backend_test`(s). Four
stubs cover the framework's surface:

- `facts/` — the canonical "random animal fact" app. A `facts` table seeded
  with rows; `@get_endpoint random_fact` returns one row at random. Backend
  tests assert a fact is returned and that two calls can differ. Covers the
  happy-path install + endpoint + randomness.
- `alltypes/` — a table spanning every column class (char/text/integer/
  boolean/decimal/datetime/user). `@get_endpoint row` returns a typed row.
  Backend tests assert each column type round-trips. Covers all `Column`
  classes end-to-end through the framework.
- `fails_backend_test/` — installs cleanly but a `@backend_test` raises/fails.
  Used to assert rollback: after the failed run, no `Application`,
  `ApplicationTable`, or physical `zz_*` table remains and the registry cache
  is reset.
- `fails_setup/` — `@setup` raises (e.g. bad column). Used to assert the same
  rollback guarantee on a setup-time failure.

Test files / classes:

- `djangoapp/tests/models/test_columns.py` — `ColumnClassTests`
    - each class accepts positional `name` + keyword-only extras; rejects
      non-keyword args
    - `CharColumn` requires `max_length`; `DecimalColumn` requires
      `max_digits` + `decimal_places`
    - name validation against `COLUMN_NAME_RE` (rejects leading digit /
      underscore / punctuation); nullable default; each class reports its
      `ColumnType`
- `djangoapp/tests/models/test_dynamic.py` — extend existing classes for the
  new signatures
    - `create_application(*, collection, name, description="", tables=..., script=)`
      is keyword-only; `tables` creates each table in one transaction; rejects
      positional args
    - `create_application_table(*, collection, application, table, columns=...)`
      keyword-only, Column objects only (dict rejected)
    - `Application.script` is set to the passed file path
- `djangoapp/tests/apps/test_setup_runner.py` — `SetupRunnerTests`
    - install `facts` → app + table + physical table exist; `Application.script`
      stored
    - install `alltypes` → every column type materialises a physical column
    - `fails_backend_test` → runner exits non-zero; nothing left (app/table/
      physical table gone, registry reset)
    - `fails_setup` → same rollback guarantee
- `djangoapp/tests/apps/test_endpoints.py` — `EndpointViewTests`
    - GET `/apps/a/Facts/Animals/endpoint/get/random_fact` → 200 JSON with a
      `fact` field; two calls may differ
    - GET `alltypes` endpoint → 200, typed values serialised
    - unknown collection / unknown app / unknown function → 404 each

## Checklist

- [x] Phase 1 — columns + signatures
    - [x] `djangoapp/models/columns.py`: `Column` base + 7 typed classes (incl. `DecimalColumn`), positional `name`, keyword-only rest, self-validating
    - [x] `create_application(*, collection, name, description="", tables=None, script)` keyword-only; inline table creation in one transaction
    - [x] `create_application_table(*, collection, application, table, columns)` keyword-only, Column objects
    - [x] `add_application_table_columns` / `delete_application_table_columns(*, ..., names=...)` keyword-only
    - [x] `Application.script` field + migration (required field; no default)
    - [x] Replace dict-spec `_create_column_row` with Column-object path
    - [x] Update all callers: commands, all tests
- [x] Phase 2 — app framework
    - [x] `djangoapp/apps/decorators.py`: `@setup`, `@get_endpoint`, `@backend_test`
    - [x] `djangoapp/apps/context.py`: `RequestContext` + `fake_context()`
    - [x] `djangoapp/apps/registry.py`: endpoint resolution by `(collection, app, func)` via the `Application` created by `@setup` + its `script` path
- [x] Phase 3 — runner + endpoints
    - [x] `setup` management command: import → `@setup` (atomic) → `@backend_test`s; rollback + registry reset on failure; non-zero exit (all failures wrapped in `CommandError`)
    - [x] Invoked via `./run djangomanage setup`
    - [x] URL route + view `/apps/a/<collection>/<app>/endpoint/get/<func>` → JSON (`model_dump(mode="json")`); 404 on miss
- [x] Phase 4 — stub apps + tests + docs
    - [x] `djangoapp/tests/apps/facts/app.py` — random-fact happy path + randomness backend tests
    - [x] `djangoapp/tests/apps/alltypes/app.py` — every column class via the framework
    - [x] `djangoapp/tests/apps/fails_backend_test/app.py` — backend-test failure → rollback
    - [x] `djangoapp/tests/apps/fails_setup/app.py` — setup raise → rollback
    - [x] `test_columns.py` (`ColumnClassTests`): per-type validation, keyword-only, name regex
    - [x] extend `test_dynamic.py`: new keyword-only signatures, inline `tables`, `Application.script`
    - [x] `test_setup_runner.py` (`SetupRunnerTests`): install facts/alltypes; rollback on both failure modes
    - [x] `test_endpoints.py` (`EndpointViewTests`): facts JSON + randomness; alltypes; 404s
    - [x] Verify README column classes + dynamic-model methods coverage
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

---

# Notes / open details

- Endpoint binding is DB-driven: `@setup` creates the `Application`
  (collection + name + `script`), and that module's `@get_endpoint` functions
  are bound to it. At request time the view resolves the `Application` by
  (collection, app) and imports its `script` module. So the same mechanism
  serves `apps/` installs and the `tests/` fixtures regardless of filesystem
  layout.
- `@backend_test` runs are in-process (call the endpoint fn directly with
  `fake_context()`), not over HTTP; the HTTP route is covered separately by a
  view test.
- "No json when creating app" (TODO.md): `create_application` takes Python
  objects (Column classes, the script path), not a JSON payload — confirmed by
  the keyword-only signature above.
- TODO.md "Track setup runs - skip the completed ones" and "post/inertia
  endpoints" are **out of scope** for this prompt (deferred).

---

# Per-app Vue + Inertia frontends

Apps gain their own Vue+Inertia frontend, built to a per-app static folder and
served by an `@inertia_endpoint`. `setup` installs the app (DB + endpoints); a
separate playwright phase drives the built UI. Captures the design agreed in
the planning discussion; implementation is separate.

## Decisions (resolved)

- **Separate Vue project per app.** Each app's frontend lives at
  `apps/<collection>/<app>/frontend/` (gitignored install dir); a committed
  reference app lives in `docs/`. No shared npm modules — apps adopt the shell
  (Layout, Bootstrap, toasts, current-user) from the reference app by copy.
- **`@inertia_endpoint` on `DynamicModule`.** Returns
  `InertiaPage(component: str, props: BaseModel)`; served at
  `/apps/a/<collection>/<app>/endpoint/inertia/<function_name>`.
- **View builds the InertiaResponse** from `InertiaPage` and passes
  `template_data={"app_static_base": app.static_folder, "app_asset_version": <mtime>}`;
  `InertiaResponse` already accepts `template_data` (merged into the template
  context on first load), so no InertiaResponse changes are needed.
- **`base.html` parameterized** (currently hardcodes `/static/djangoapp/main.*`):
  `<script type="module" src="{{ app_static_base }}/main.js?cache_buster={{ app_asset_version }}">`
  and the same for `main.css`. A context processor defaults
  `app_static_base` to `/static/djangoapp` and `app_asset_version` to the host
  `main.js` mtime, so host pages are unchanged. App pages load **only** their
  own bundle (no double Bootstrap).
- **`Application.static_folder` field** (create-time, source of truth, absolute
  path). Derivable from names but stored so apps can override the location.
- **`buildapp <collection/app>`** — one arg; resolves `Application.static_folder`
  and runs the app's `vite build` into it (with `emptyOutDir`). No second path
  arg (the stored field is the single source).
- **Cache-busting via query string.** Constant `main.js`/`main.css` path +
  `?cache_buster=<mtime of the built main.js>`. No hashed filenames, no Inertia-version
  coupling. The inertia endpoint view reads the mtime and injects
  `app_asset_version`; `buildapp` rebuilding changes the mtime → browsers refetch.
- **Invalidation = generation counter (no server reload).** A generation token
  (DB singleton or Django cache) is bumped by `setup` on success. A middleware
  compares the worker's last-seen generation to the live one and, on mismatch,
  calls `dynamic_models.reset()` + `apps.registry.clear_cache()` — so a running
  devserver or gunicorn worker picks up the latest installed app/models without
  a restart. Chosen because the requirement is "load latest without reloading
  either devserver or gunicorn."
- **Playwright is a second phase, not part of `setup`.** `setup` = install +
  `@backend_test`s only (commits to the dev DB). Browser tests are collected
  `StaticLiveServerTestCase`s that `call_command("setup", …)` in `setUp`, build
  the frontend, launch the browser, `page.goto` the inertia URL, and assert on
  DOM. Run under `./run playwrighttest`. (Reverses the earlier "setup runs them"
  idea — browser tests need test-DB isolation, and `setup`'s backend loop stays
  fast.) `@playwright_test` funcs are registered on `DynamicModule`.
- **"Fix only frontend" assumption** holds only if `@backend_test`s assert the
  endpoint contract (props shape, seed data) — be disciplined, or playwright
  starts catching backend regressions.
- `djangoapp/static/djangoapp/apps/` is gitignored (build artifacts).

## Plan

### Phase 1 — static folder + base.html
- Add `Application.static_folder` (`CharField`, create-time, absolute path) + migration.
- Parameterize `djangoapp/templates/inertia/base.html`: script/css via
  `{{ app_static_base }}` + `?cache_buster={{ app_asset_version }}`.
- Context processor: default `app_static_base="/static/djangoapp"` and
  `app_asset_version = mtime(host main.js)`; wire into the inertia template chain.

### Phase 2 — `@inertia_endpoint` + InertiaPage + view
- `DynamicModule.inertia_endpoint` decorator + `.inertia_endpoints` (dict).
- `InertiaPage(component, props: BaseModel)` (generic-friendly; view serializes
  `props.model_dump(mode="json")`).
- Route `/apps/a/<collection>/<app>/endpoint/inertia/<func>` (parallel to
  `/endpoint/get/<func>`); view resolves the fn via the registry, calls it with
  `RequestContext`, reads `Application.static_folder` + `main.js` mtime, returns
  `InertiaResponse(request, stuff.component, {"props": ...}, template_data=...)`.
  Unknown collection/app/function → 404.

### Phase 3 — generation-counter invalidation
- Generation token (DB singleton row or Django cache key).
- `setup` bumps it on successful install.
- Middleware (alongside the existing inertia shared-props middleware) checks
  worker-last-seen vs live gen; on mismatch `dynamic_models.reset()` +
  `apps.registry.clear_cache()` and update last-seen.

### Phase 4 — `buildapp`
- `./run djangomanage buildapp <collection/app>`: resolve
  `Application.static_folder`, run the app's `vite build --emptyOutDir --outDir
  <static_folder>` (absolute), confirm output `main.js`/`main.css`. Errors →
  non-zero exit.

### Phase 5 — playwright second phase
- The app is **already installed** by the prior `setup` run (Phase 1 of the
  workflow) — playwright tests do **not** re-run `setup`. They run against the
  installed app: they may read the existing seeded data, or create extra rows
  for the scenario that are **rolled back** after the test. The app install
  itself is the baseline fixture and is not rolled back per test.
- `@playwright_test` funcs are collected as `StaticLiveServerTestCase`s that
  assume the install, optionally seed rolled-back rows, drive the browser
  (`page.goto` the inertia URL), and assert on DOM (`wait_for_selector`/
  `wait_for_url` only). `dynamic_models.reset()`/`clear_cache()` in
  setUp/tearDown keep in-memory state clean.
- Run order (documented for the agent): first `./run djangomanage setup
  <app>` (install), then `./run djangomanage buildapp <collection/app>` (build
  the frontend), then `./run playwrighttest` (browser tests). CI/checkall must
  run setup+buildapp for every app-with-frontend fixture before playwrighttest.

### Phase 6 — reference app + docs
- Committed reference app in `docs/` with Bootstrap, toast error handling, a
  Layout that shows the current logged-in user, and a "go home" link — the
  template apps copy/adopt. README section documenting `@inertia_endpoint`,
  `buildapp`, the static-folder field, and the invalidation model.
- Reference-app docs must include a **commands + context** section so an agent
  (or human) can build/run an app end to end:
    - **Context**: an app is `app.py` with a module-level `dynamic_module =
      DynamicModule()` whose decorators tag `@setup` (creates the
      collection/app/tables via `create_application(..., script=,
      static_folder=...)`), `@get_endpoint` / `@inertia_endpoint` (served at
      `/apps/a/<collection>/<app>/endpoint/{get,inertia}/<func>`), and
      `@backend_test` / `@playwright_test`. Frontend lives at
      `apps/<collection>/<app>/frontend/` (gitignored; the reference copy is
      committed under `docs/`); `buildapp` writes to
      `djangoapp/static/djangoapp/apps/<collection>/<app>/` (gitignored
      artifacts).
    - **Commands** (in workflow order):
        - `./run djangomanage setup <app.py path>` — import the app, run `@setup`
          (creates app+tables, commits), then `@backend_test`s; rolls back the
          whole install on any failure. No CLI for creating apps/tables — that
          is `@setup`'s job.
        - `./run djangomanage buildapp <collection/app>` — resolve the app's
          stored `static_folder` and run its `vite build` there (empties the dir
          first). Constant `main.js` path; cache-bust via `?cache_buster=<mtime>`.
        - `./run playwrighttest` — run `@playwright_test`s as browser tests
          against the already-installed app (assumes setup+buildapp ran).
        - `./run djangomanage applications list_application_collections` /
          `list_application_collection --name <c>` /
          `describe_application_table --appcollection <c> --app <a> --name <t>`
          — read-only inspection of what's installed.
    - Note the dev loop: edit `app.py`/Vue → `setup`/`buildapp` → refresh; the
      generation-counter middleware keeps a running devserver/gunicorn fresh
      after `setup` without a restart.
- README **mandatory-shell checklist** (a "definition of done" the agent must
  verify for every app frontend):
    - [x] wraps every page in the shared `Layout`
    - [x] shows the current logged-in user (via the shared `viewer` prop)
    - [x] global error handling surfaces as a toast (`showErrorToast`), no
          silent `console.error` / bare `catch`
    - [x] axios calls wrapped in try/catch + zod-parse + `showErrorToast`
    - [x] "go home" / back-to-host navigation works
    - [x] loads Bootstrap (no double-load with host CSS on app pages)

## Checklist (frontends)

- [x] Phase 1 — static folder + base.html
    - [x] `Application.static_folder` (property, not a field; migrations 0010 add → 0012 remove)
    - [x] `base.html` uses `{{ app_static_base }}/main.js?cache_buster={{ app_asset_version }}` (+ css)
    - [x] `host_template_data` defaults `app_static_base` + `app_asset_version` (host empty version)
- [x] Phase 2 — inertia endpoint
    - [x] `DynamicModule.inertia_endpoints` + `call_inertia_endpoint`
    - [x] `InertiaPage(component, props)` type
    - [x] `/endpoint/inertia/<func>` route + view → `InertiaResponse` with `template_data`; 404 on miss
- [x] Phase 3 — generation-counter invalidation
    - [x] `AppsGeneration` counter bumped by `installorupdate` on success
    - [x] per-call `sync_app_caches` resets `dynamic_models` + app-module cache on
          gen change (no middleware; each load/registry call syncs)
- [x] Phase 4 — `buildapp`
    - [x] `./run djangomanage buildapp <collection/app>` resolves `static_folder`, runs vite build (emptyOutDir)
    - [x] after building, drives the app's `@playwright_test` funcs in a browser against the live install; fails the build on any failure (`--skip-playwright` builds only)
- [x] Phase 5 — playwright second phase
    - [x] `@playwright_test` → `StaticLiveServerTestCase`s that assume the install, use existing/rolled-back data, drive browser + assert DOM
    - [x] documented run order: `setup` → `buildapp` → `./run playwrighttest`
    - [x] example app with a frontend (fixture) + its playwright test
- [x] Phase 6 — reference app + docs
    - [x] `docs/` reference app: Bootstrap, toasts, Layout, current user, home link
    - [x] README: `@inertia_endpoint`, `buildapp`, static-folder, invalidation model
    - [x] README mandatory-shell checklist (Layout / current user / toast error handling / axios try-catch+zod / home nav / Bootstrap no double-load)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

---

# Notes / open details (frontends)

- **Re-install / idempotency** (deferred "track setup runs" TODO): re-running
  `setup` on an installed app errors on collection/app unique constraints; with
  a frontend it also needs a rebuild. Must be solved before the dev loop
  ("setup once, iterate") can recover from an `app.py` edit.
- **CI build step**: build-only means every app-with-frontend fixture must be
  built before its playwright test runs; `./run checkall` needs a step that runs
  `buildapp` for those fixtures (parallel to the host `npm run build` before
  `./run playwrighttest`).
- **`app_asset_version` source — nothing is written**: the version is read
  **live** via `os.path.getmtime(<static_folder>/main.js)` by the inertia
  endpoint view (and the context processor for the host's `main.js`). It is not
  stored on the model or in a file. `buildapp` rebuilding overwrites `main.js`
  → its mtime bumps → `?cache_buster=` changes → browsers refetch. (Alternative if stat-ing
  per render is unwanted: `buildapp` writes a `build.txt` timestamp the view
  reads — but live mtime needs no extra state.)
- **Playwright run order**: `setup` (install) → `buildapp` (frontend) →
  `./run playwrighttest` (browser). The app is installed once and assumed
  present; tests use its existing data or add rolled-back rows.
- **Orphaned dynamic classes**: gen-counter `reset()` clears the cache but old
  model classes linger in `apps.all_models` until swept by `reset()` (which does
  sweep `*dynamicmodel`) — acceptable; full restart only if GC pressure appears.
- **`buildapp` dev loop**: constant path + `?cache_buster=mtime` means you edit Vue →
  `buildapp` → refresh; no dev-server story (accepted).

---

# Redesign: marker decorators + DynamicModule-from-module + derived static folder

Three cleanups to the app framework, agreed 2026-07-07.

## Why
- App authors shouldn't write `dynamic_module = DynamicModule()` boilerplate —
  the decorators should just mark a function as a kind.
- `Application.static_folder` is redundant: the folder is fully derivable from
  the collection/app names, so storing it is a second source of truth.
- `spec =` in `AppModuleLoader._import` is unexplained.

## Changes

### 1. Standalone marker decorators (no instance in app.py)
Replace `@dynamic_module.setup` / `.get_endpoint` / `.inertia_endpoint` /
`.backend_test` / `.playwright_test` with standalone decorators that tag the
function (set `fn._app_marker = "<kind>"`) and return it unchanged. app.py
becomes:

```python
from djangoapp.apps import (
    backend_test, get_endpoint, inertia_endpoint, playwright_test, setup,
)

@setup
def setup_app() -> None: ...

@inertia_endpoint
def facts_page(ctx: RequestContext) -> InertiaPage[FactsPageProps]: ...
```

No `DynamicModule()` is instantiated anywhere in an app. A function carries one
marker (it is one kind).

### 2. DynamicModule built from a module (only by the loader)
`DynamicModule.__init__(self, module)` scans `vars(module).values()` for
callables tagged by the markers and populates its attributes:
- `setup_function` — the one `@setup` callable (None if absent)
- `endpoints` — dict `name -> @get_endpoint`
- `inertia_endpoints` — dict `name -> @inertia_endpoint`
- `backend_tests` — list of `@backend_test` (definition order)
- `playwright_tests` — list of `@playwright_test` (definition order)

`AppModuleLoader.load` returns `DynamicModule(module)`; `DynamicModule` is
constructed nowhere else. (The current per-instance registry + decorator
methods are removed.)

### 3. Derive the static folder (drop Application.static_folder)
- Remove `Application.static_folder` (+ a removal migration).
- `create_application` drops the `static_folder` kwarg.
- Everything that read `application.static_folder` derives it instead via
  `_default_static_folder(collection, app)` (already in `dynamic.py`) →
  `djangoapp/static/djangoapp/apps/<collection>/<app>`. The inertia view's
  `_app_bundle` and `buildapp` take the collection/app (or the Application) and
  derive.

### 4. Explain `spec =` in `_import`
Add a one-line comment: `spec` is the importlib `ModuleSpec` (loader + origin)
for the file path, used to build and exec the module from disk rather than via
a normal package import.

## File-by-file impact
- `djangoapp/apps/dynamic_module.py`:
    - add standalone marker decorators (`@setup`/`@get_endpoint`/`@inertia_endpoint`/`@backend_test`/`@playwright_test`) tagging `fn._app_marker`
    - `DynamicModule` → `__init__(self, module)` introspector (scan `vars`, populate attrs); drop the decorator methods + per-instance registry
    - `AppModuleLoader.load` → returns `DynamicModule(module)`
    - comment the `spec =` line in `_import`
- `djangoapp/apps/registry.py`: resolvers unchanged (still use `app_modules.load` → DynamicModule).
- `djangoapp/models/applications.py`: drop `static_folder` field.
- `djangoapp/models/dynamic.py`: `create_application` drops `static_folder` kwarg; keep `_default_static_folder`.
- `djangoapp/views/app_endpoints.py`: `_app_bundle` derives the folder from collection/app names (not `application.static_folder`).
- `djangoapp/management/commands/buildapp.py`: derive the folder from names.
- migration: remove `static_folder`.
- app fixtures (`facts`, `alltypes`, `fails_backend_test`, `fails_setup`, `http_mock`, `inertia_demo`) + `docs/apps/reference`: switch to standalone decorators; drop `dynamic_module = DynamicModule()` and `@dynamic_module.X`.

## Checklist
- [x] Standalone marker decorators tag `fn._app_marker` (`@setup`/`@get_endpoint`/`@inertia_endpoint`/`@backend_test`/`@playwright_test`)
- [x] `DynamicModule(module)` introspector scans `vars(module)` and populates setup_function/endpoints/inertia_endpoints/backend_tests/playwright_tests
- [x] `AppModuleLoader.load` returns `DynamicModule(module)`; DynamicModule is not instantiated elsewhere
- [x] app fixtures + `docs/apps/reference` use standalone decorators (no `DynamicModule()` instance)
- [x] Drop `Application.static_folder` field + add a removal migration (`0012`)
- [x] `create_application` drops the `static_folder` kwarg
- [x] `_app_bundle` + `buildapp` derive the folder from collection/app names (`default_static_folder`); single spanned lookup (`application_collection__name`)
- [x] Explain `spec =` in `_import`
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

---

# Refactor: Application as the app API + generation-based asset cache-bust

Driven by the aihere markers + consolidating app-derived paths/lookups onto the
`Application` model. Planned 2026-07-07; not yet implemented.

## aihere inventory (all to be addressed, then removed)
- `views/app_endpoints.py:46` — `Application.app_or_404(collection, app)`; find
  every `Application.DoesNotExist` site; `module = application.module()`;
  `module.has_endpoint(name)`; `result = module.call_endpoint(request, user)`;
  "we may not need registry.py".
- `views/app_endpoints.py:95` — `application.app_bundle()` instead of `_app_bundle`.
- `docs/apps/reference/app.py:15` — re-export the decorators/context into a
  `shortcuts` module so app.py has one import.
- `docs/apps/reference/app.py:41` — use the new `Application` model API here.
- `docs/apps/reference/app.py:43` — `app.get_table(TABLE)` returning the typed model.

## Decision: mtime → Generation for cache-bust
- Today `_app_bundle` returns the built `main.js` mtime as `?cache_buster=`.
- Switch to `AppsGeneration.current()`: **`buildapp` bumps `AppsGeneration` on
  success** (in addition to `setup`), and the cache-bust value is the generation.
- Removes the per-render filesystem stat. Tradeoffs accepted: generation is
  global (one app's rebuild bumps the value for all apps → harmless extra
  refetch); buildapp bumping also trips `sync_app_caches`'s model/module reset
  (unnecessary after a static-only build, harmless). The host bundle is not an
  app and `npm run build` doesn't bump generation, so it keeps no cache-bust
  (current behavior).

## Move logic onto `Application` (instance-based paths/values)
- `@classmethod app_or_404(cls, collection_name, app_name) -> Application` —
  `get(application_collection__name=…, name=…)` raising `Http404` on
  `DoesNotExist`. Replaces the try/except in both endpoint views + `manage_page`.
- `@property script_path -> Path` — `(BASE_DIR / self.script).resolve()`.
  (`_script_to_path` STAYS in the loader — it runs with only a script string,
  before any `Application` instance exists.)
- `@property static_folder -> Path` — `BASE_DIR/djangoapp/static/djangoapp/apps/<collection>/<app>`
  (absorbs `default_static_folder`; drop the function).
- `@property frontend_dir -> Path` — `self.script_path.parent / "frontend"`
  (absorbs `_frontend_dir`).
- `@property app_bundle -> tuple[str, str]` — `(static_url, generation)` where
  `static_url = STATIC_URL + static_folder.relative_to(BASE_DIR/djangoapp/static)`
  (absorbs `_app_bundle`; mtime → generation).
- `module() -> DynamicModule` — `app_modules.load(self.script)` (absorbs
  registry `_resolve`).
- `get_table(name) -> type[BaseTable]` — resolve the `ApplicationTable` + return
  `as_model()` (typed), for app authors.

## `DynamicModule` call API (aihere #1)
- `has_endpoint(name) -> bool` / `call_endpoint(name, request, user) -> object`
  (builds `RequestContext`, calls, returns).
- `has_inertia_endpoint(name) -> bool` / `call_inertia_endpoint(name, request, user) -> InertiaPage`.
- Endpoint views become:
  `app = Application.app_or_404(…); module = app.module(); result = module.call_endpoint(…)`.

## `registry.py` fate
- With `application.module()` + the DynamicModule call methods,
  `endpoint_for`/`inertia_endpoint_for`/`_resolve` collapse into the views →
  drop `registry.py` (or leave a thin shim).

## `shortcuts` module (aihere #3)
- `djangoapp/apps/shortcuts.py` re-exports `setup, get_endpoint, inertia_endpoint,
  backend_test, playwright_test, RequestContext, fake_context, InertiaPage` so an
  app.py imports them in one statement.

## `Application.objects.get` sites — treatment
- `views/applications.py:244 manage_page` → `Application.app_or_404`.
- `views/app_endpoints.py` (both endpoints) → `app_or_404` + `module.call_*`.
- `apps/registry.py` → removed (resolution moves to `Application.module()`).
- `management/commands/buildapp.py` → fetch + `CommandError` (not 404; reuse a
  shared fetch or keep its own — domain error differs from 404).
- `management/commands/applications_schemas.py:99` → domain `ValueError`; keep
  (different error semantics).
- `models/dynamic.py:305 _resolve_application` → domain `TableNotFoundError`; keep.
- tests/fixtures `_model()` (`facts`, `alltypes`, `http_mock`, `inertia_demo`)
  → `app.get_table(TABLE)` (aihere #5).

## Path/script consolidation summary
- `_script_to_path` → stays in loader (no instance); add `Application.script_path`
  for instance callers.
- `default_static_folder` → `Application.static_folder`.
- `_frontend_dir` → `Application.frontend_dir`.
- `_app_bundle` → `Application.app_bundle`.

## Checklist
- [x] `Application.app_or_404` classmethod; replace view try/except sites
- [x] `Application.script_path` property (`_script_to_path` inlined into `_import`)
- [x] `Application.static_folder` property (dropped `default_static_folder`)
- [x] `Application.frontend_dir` property (dropped buildapp `_frontend_dir`)
- [x] `Application.app_bundle` property (dropped `_app_bundle`); mtime → generation
- [x] `Application.module()` + `Application.get_table()`
- [x] `DynamicModule.has_endpoint/call_endpoint/has_inertia_endpoint/call_inertia_endpoint`
- [x] `buildapp` bumps `AppsGeneration` on success
- [x] drop `registry.py` (resolution onto Application.module() + DynamicModule)
- [x] `djangoapp/apps/shortcuts.py` one-import re-export
- [x] fixtures `_model()` → `app.get_table(TABLE)`
- [x] remove all 5 aihere comments
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

---

# New aihere markers (2026-07-07, not yet addressed)

Captured from the codebase; the comments are instructions to modify it. Address
each then remove the comment.

- [x] `djangoapp/tests/apps/alltypes/app.py:18` — `Application` and each `Column`
      class should also be re-exported from `djangoapp.apps.shortcuts` (so an app
      imports everything from one place).
- [x] `djangoapp/tests/apps/alltypes/app.py:50` — replace all
      `Application.objects.get(...)` (and similar) with the new `Application`
      methods across the codebase; search for every site. (Added `get_by_names`.)
- [x] `djangoapp/tests/apps/test_endpoints.py:38` — wrap the
      `call_command("setup", …)` invocation in a helper function instead of
      calling the command directly. (`tests/apps/helpers.install_app`.)
- [x] `djangoapp/tests/apps/facts/app.py:61` — inline `_model()` (and the other
      fixtures' `_model()`).
- [x] `djangoapp/models/applications.py:136` — reconsider storing `script`:
      documented why it is stored (install path varies, not derivable).
- [x] `djangoapp/templates/inertia/base.html:7` — remove the
      `|default:'/static/djangoapp'` filter; always supply `app_static_base`
      (`host_template_data()` on every host render).
- [x] `djangoapp/apps/dynamic_module.py:163` — `call_endpoint` /
      `call_inertia_endpoint` keyword-only (`*, name, request, user`).
- [x] `djangoapp/apps/dynamic_module.py:230` — `force_reload` kept + commented
      (setup re-imports after an edit, often in-process).
- [x] `djangoapp/apps/dynamic_module.py:258` — `sync_app_caches` docstring brief
      + both sections (compare / reset) commented.
- [x] `djangoapp/middleware.py:2` — moved module docstring content into
      `SharedPropsMiddleware` docstring.

---

# Plan: drop `script`, derive the app path from a mockable apps root

Today `Application.script` stores the project-relative `app.py` path because the
install location varies (`apps/...` at runtime, `djangoapp/tests/apps/...` for
fixtures). Fix a convention instead — every app lives at
`<apps_root>/<collection>/<app>/app.py` (+ a `frontend/` sibling) — and make
`apps_root` a single, mockable value the import + frontend machinery reads.
Then `script` is fully derivable and need not be stored.

## Mechanism
- `apps_root()` (or a module-level `APPS_ROOT`) in
  `djangoapp/apps/dynamic_module.py`, default `BASE_DIR / "apps"`. This is "the
  base dir the mechanism sees"; tests mock/patch it at the fixture tree. Kept in
  the loader module (not `settings.py`) so it's trivially mockable.
- `Application.script_path` → `apps_root() / collection.name / name / "app.py"`.
- `Application.frontend_dir` → `script_path.parent / "frontend"` (off the
  derived path).
- Remove `Application.script` + a removal migration; `create_application` drops
  the `script=` kwarg.

## Callers
- `Application.module()` → `app_modules.load(self.script_path)` (loader takes
  the derived `Path`).
- `buildapp <collection>/<app>` unchanged (already resolves the app + uses
  derived `frontend_dir` / `static_folder`).
- `setup` changes input: `setup <collection>/<app>` derives
  `<apps_root>/<c>/<a>/app.py` and imports it (replaces today's
  `setup <script path>`). The imported `@setup` calls
  `create_application(collection=<c>, name=<a>, …)` with the same names, so the
  derived re-import path always matches.

## Fixtures + tests
- Reorganize fixtures to the convention: `djangoapp/tests/apps/<collection>/<app>/`
  (e.g. `…/Facts/Animals/app.py`, `…/Schema/AllTypes/app.py`, …), moving the
  `inertia_demo/frontend/` with it.
- The three app test classes patch `apps_root` →
  `BASE_DIR / "djangoapp/tests/apps"` (the mock); `install_app` takes
  `<collection>/<app>`.
- Drop the dead `SCRIPT =` constants from fixtures.

## Decisions / risks
- Convention enforced by layout, not validated — running `setup` against a path
  not at `<apps_root>/<c>/<a>/app.py` breaks the later derived re-import.
  Acceptable (apps_root is deployment-constant; tests set it explicitly).
- `setup`'s arg changes (path → `<collection>/<app>`) — update `install_app`,
  the inertia_demo harness, and docs/run references.
- Removal migration for `script` (currently NOT NULL); the path is re-derivable
  from names + apps_root.
- `static_folder` already derives from names, so unchanged; only fixture source
  dirs move.

## Checklist
- [x] `apps_root()` (mockable, default `BASE_DIR/apps`) in `dynamic_module`
- [x] `Application.script_path` / `frontend_dir` derive from `apps_root` + names
- [x] Drop `Application.script` + removal migration (`0013`); `create_application` drops `script=`
- [x] `Application.module()` loads the derived path; loader takes a `Path`
- [x] `setup <collection>/<app>` derives the path (replaces `<script path>`)
- [x] Reorganize fixtures to `<tests/apps>/<collection>/<app>/`; move inertia_demo frontend
- [x] App tests patch `apps_root` → `BASE_DIR/djangoapp/tests/apps`; `install_app` takes `<c>/<a>`
- [x] Drop `SCRIPT =` constants from fixtures
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

---

# New aihere markers (2026-07-07, batch 2)

- [x] `djangoapp/views/app_endpoints.py:54` — `call_json_endpoint` returns a
      Pydantic model or dict; the view asserts/validates the return type.
- [x] `djangoapp/views/app_endpoints.py:55` — renamed `call_endpoint` →
      `call_json_endpoint` and `has_endpoint` → `has_json_endpoint`; storage
      `endpoints` → `json_endpoints`.
- [x] `djangoapp/views/app_endpoints.py:92` — `isinstance(result, InertiaPage)`
      guard replaced with `assert`.
- [x] `djangoapp/apps/dynamic_module.py:178` — folded `_dynamic_module_of`'s
      empty-check into `DynamicModule.__init__` (removed the helper).
- [x] `djangoapp/apps/dynamic_module.py:257` — `_seen_generation` is now a plain
      `int | None` mutated via `global` (list hack gone).

---

# Pending follow-ups captured from code markers (2026-07-08, batch 3)

Collected from `# aihere ...` comments in the code; each is an instruction to
modify the codebase. Address each, then remove the comment.

## Commands

- [x] setup: use `Application` model methods (`script_path` / `module()` etc.)
      instead of recomputing the path from `apps_root()` by hand
      — N/A: no `Application` row exists at `setup` time (the `@setup` creates
      it), so the path is derived from `apps_root()` + names; documented why
      [djangoapp/management/commands/setup.py:46]
- [x] setup: the `force_reload` note says "re-run after edits re-imports fresh";
      justified — needed for in-process re-runs via `call_command` in the test
      suite (a second install of the same path re-imports rather than reuses the
      cached module)
      [djangoapp/management/commands/setup.py:49]
- [x] setup: the `setup_function is None` check — decided: the bare `is None`
      check is right (a `has_setup` property can't narrow the type for the call,
      so it'd need an extra assert); kept the direct check
      [djangoapp/management/commands/setup.py:55]
- [x] setup: run each `@backend_test` in its own savepoint that rolls back after,
      and add a test proving the per-test rollback
      [djangoapp/management/commands/setup.py:63]
- [x] buildapp: `application.static_folder` is a property; decided to **keep** it
      a property — it's a pure path derivation, a peer of `frontend_dir` /
      `app_bundle` (also properties); `.module()` is a method because it does
      import work
      [djangoapp/management/commands/buildapp.py:84]
- [x] buildapp: use `application.module()` instead of `app_modules.load(...)`
      directly (same import path as setup)
      [djangoapp/management/commands/buildapp.py:129]
- [ ] buildapp drive: wrap each `@playwright_test` in a savepoint so its DB
      writes roll back after the test — plan + checklist moved to
      `prompts/20260708-playwright-test-savepoint-isolation.md`
      [djangoapp/management/commands/buildapp.py:187]
- [ ] buildapp drive: change the `@playwright_test` contract to receive a browser
      `context` (+ `base_url`), letting each test create its own page/users/login
      instead of receiving a pre-authenticated page — pair with the savepoint work
      in `prompts/20260708-playwright-test-savepoint-isolation.md`
      [djangoapp/management/commands/buildapp.py:190]
- [x] a failing test case halts the whole run and prints the error: a
      `@backend_test` (json endpoint) in `setup` or a `@playwright_test` in
      `buildapp` stops the process at once and prints which test failed + its
      traceback (buildapp's drive now stops on the first failure instead of
      collecting all)
      [djangoapp/management/commands/buildapp.py:190]
      [djangoapp/management/commands/setup.py:63]

## Framework

- [x] `apps_root()`: docstring should explain why it is a function (mockable
      module global) rather than a constant
      [djangoapp/apps/dynamic_module.py:200]
- [x] `@get_endpoint` return-type contract: decided it stays in the view, one
      place, co-located with the `model_dump`/dict serialization branch
      [djangoapp/views/app_endpoints.py:57]

## Reference app (`docs/apps/reference/`)

- [x] reference app: import via the `shortcuts` module (one import statement;
      added `dynamic_models` to shortcuts so it covers everything)
      [docs/apps/reference/app.py:15]
- [x] reference app: add a `@playwright_test` (drives the built UI: render + Refresh)
      [docs/apps/reference/app.py]
- [x] reference app frontend: satisfy the mandatory-shell checklist in
      `../README.md` — Layout (current user + Home link), axios try/catch + zod +
      `showErrorToast`, Bootstrap (app bundle only, no host double-load)
      [docs/apps/reference/frontend/src/]

## Tests / fixtures

- [x] rename the apps-root patch var `_APPS_ROOT` → `_APPS_ROOT_PATCH` (clearer)
    - [x] test_app_playwright [djangoapp/tests/apps/test_app_playwright.py:28]
    - [x] test_setup_runner [djangoapp/tests/apps/test_setup_runner.py:20]
    - [x] test_endpoints [djangoapp/tests/apps/test_endpoints.py:14]
- [x] test_app_playwright: keep `dynamic_models.reset()` in setUp — needed: it
      clears the process-wide registry that TransactionTestCase's DB flush
      doesn't touch
      [djangoapp/tests/apps/test_app_playwright.py:49]
- [x] helpers: `install_app` calls `run_setup()` directly instead of
      `call_command("setup", ...)` (the setup core is extracted to a callable;
      the command is a thin styled wrapper)
      [djangoapp/tests/apps/helpers.py]
- [x] fixtures: consolidated Facts/Animals + Demo/Page into one comprehensive
      app (`Demo/Page`) — seeded `items` table, `current_code`/`random_code`
      endpoints, `@inertia_endpoint`, backend tests (incl. rollback), and a
      `@playwright_test`; deleted `Facts/Animals`
      [djangoapp/tests/apps/Demo/Page/app.py]
- [x] fixtures: audited all apps for convention consistency — every fixture now
      imports via the `shortcuts` module (one statement); removed the audit marker
      [djangoapp/tests/apps/Broken/FailsTest/app.py]

---

# Renames + single-collection fixtures (2026-07-08, batch 4)

> Deferred elsewhere: the buildapp-drive savepoint-per-`@playwright_test` + the
> `context`-contract change are tracked in
> `prompts/20260708-playwright-test-savepoint-isolation.md` (see batch-3 items
> `buildapp.py:187` / `:190`).

## Rename the `setup` command to `installorupdate`

The command installs an app today and errors on re-install (collection/app unique
constraints). Renaming it to `installorupdate` signals the intended
install-or-update semantics — make re-running it idempotent (update an installed
app in place), the deferred "Re-install / idempotency" item in Notes.

- [x] rename `djangoapp/management/commands/setup.py` → `installorupdate.py`;
      command name `setup` → `installorupdate`; `run_setup` → `install_or_update`
- [x] update callers: tests call `install_or_update` directly (no `install_app`
      helper — removed); the `run` script + docs (`./run djangomanage setup` →
      `installorupdate`), and `docs/apps/README.md`
- [ ] (paired) make re-install idempotent: update in place instead of erroring on
      the unique constraint (the "Re-install / idempotency" open item)

## Rename `tests/apps` → `tests/appfixtures`

The fixture tree dir name (`apps`) collides with the runtime `apps/` install dir;
`appfixtures` is unambiguous.

- [x] move `djangoapp/tests/apps/` → `djangoapp/tests/appfixtures/`
- [x] update `_APPS_ROOT_PATCH` in `test_app_playwright`, `test_setup_runner`,
      `test_endpoints` (`djangoapp/tests/apps` → `djangoapp/tests/appfixtures`)
- [x] update test-module paths + imports: `djangoapp.tests.apps.*` →
      `djangoapp.tests.appfixtures.*` (the test modules, the package `__init__`)
- [x] update `djangoapp/tests/apps/README.md` path + doc references
      (`docs/apps/README.md`, the app-framework README section)

## Put all fixture apps under one collection

Fixtures currently span collections `Demo` / `Schema` / `Http` / `Broken` /
`Broken2`. Move them all under a single collection (e.g. `Tests`) so the fixture
tree is one collection dir of apps, not five.

- [x] pick one collection name; set every fixture's `COLLECTION` constant to it
- [x] reorganize the fixture tree to `<collection>/<app>/app.py` for all apps
- [x] update tests asserting on collection names
      (`Application.get_by_names("Tests", "Page")`, etc.) in `test_setup_runner`,
      `test_endpoints`, `test_app_playwright`
- [x] update the fixtures README table + doc references
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

## Review follow-ups (deferred)

Findings from the 2026-07-08 local review, resolved:

- [x] the `@get_endpoint`/`@inertia_endpoint` contract asserts were moved into
      `call_json_endpoint`/`call_inertia_endpoint` (dynamic_module.py) at the call
      boundary — kept as asserts (runtime contract check); views no longer assert
- [x] the `_drive_playwright_tests` smoke-user username is now unique per run
      (`buildapp.py`, `buildapp-smoke-{pid}`) so a leaked row can't block the next
      `create_user`
