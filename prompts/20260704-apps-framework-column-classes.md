# Apps framework + typed column classes

APPS.md (priority over AGENTS.md) and TODO.md describe a new direction: typed
column classes, keyword-only registry signatures, and a decorator-based app
framework (`@setup` / `@get_endpoint` / `@backend_test`) installed by
`./run setup`. This prompt implements it. APPS.md and README.md have already
been made consistent with the decisions below.

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
  `test_applications_command`) + `scripts/20260630_seed-facts.py` to Column
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

### Phase 3 — `./run setup` + endpoint serving
- New management command `setup <path>` (wired into `run` as `./run setup`):
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

- [ ] Phase 1 — columns + signatures
    - [ ] `djangoapp/models/columns.py`: `Column` base + 7 typed classes (incl. `DecimalColumn`), positional `name`, keyword-only rest, self-validating
    - [ ] `create_application(*, collection, name, description="", tables=None, script)` keyword-only; inline table creation in one transaction
    - [ ] `create_application_table(*, collection, application, table, columns)` keyword-only, Column objects
    - [ ] `add_application_table_columns` / `delete_application_table_columns(*, ..., names=...)` keyword-only
    - [ ] `Application.script` field + migration
    - [ ] Replace dict-spec `_create_column_row` with Column-object path
    - [ ] Update all callers: commands, all tests, `scripts/20260630_seed-facts.py`
- [ ] Phase 2 — app framework
    - [ ] `djangoapp/apps/decorators.py`: `@setup`, `@get_endpoint`, `@backend_test`
    - [ ] `djangoapp/apps/context.py`: `RequestContext` + `fake_context()`
    - [ ] `djangoapp/apps/registry.py`: endpoint resolution by `(collection, app, func)` via the `Application` created by `@setup` + its `script` path
- [ ] Phase 3 — runner + endpoints
    - [ ] `setup` management command: import → `@setup` (atomic) → `@backend_test`s; rollback + registry reset on failure; non-zero exit
    - [ ] `./run setup` wired into the `run` script
    - [ ] URL route + view `/apps/a/<collection>/<app>/endpoint/get/<func>` → validated JSON; 404 on miss
- [ ] Phase 4 — stub apps + tests + docs
    - [ ] `djangoapp/tests/apps/facts/app.py` — random-fact happy path + randomness backend tests
    - [ ] `djangoapp/tests/apps/alltypes/app.py` — every column class via the framework
    - [ ] `djangoapp/tests/apps/fails_backend_test/app.py` — backend-test failure → rollback
    - [ ] `djangoapp/tests/apps/fails_setup/app.py` — setup raise → rollback
    - [ ] `test_columns.py` (`ColumnClassTests`): per-type validation, keyword-only, name regex
    - [ ] extend `test_dynamic.py`: new keyword-only signatures, inline `tables`, `Application.script`
    - [ ] `test_setup_runner.py` (`SetupRunnerTests`): install facts/alltypes; rollback on both failure modes
    - [ ] `test_endpoints.py` (`EndpointViewTests`): facts JSON + randomness; alltypes; 404s
    - [ ] Verify README column classes + dynamic-model methods coverage
- [ ] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

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
