# Test fixture apps

Each fixture lives at `<app>/app.py` under this tree (matching the app
framework's `<apps_root>/<app>/app.py` convention); `apps_root` is patched to
this tree in the app tests. They double as runnable examples of the framework
and as the data the tests in `test_buildbackend.py` / `test_buildfrontend.py` /
`test_endpoints.py` install.

Loaded by file path (not imported as a package), so the fixture dirs have no
`__init__.py` on purpose.

Apps are installed inside the test's transaction, so created apps/tables are
rolled back automatically; `dynamic_models.reset()` + `app_modules.clear()`
keep the in-memory state clean between tests.

## Single-app fixtures (flat `<App>/app.py`)

| App | What it exercises |
| --- | --- |
| `HappyPathApp` | Install/seed fixture: `@setup` seeds an `items` table; a `@backend_test` writes a row during install (proving savepoint rollback). Feeds `test_buildbackend.py`. |
| `EndpointsApp` | Endpoint-serving fixture: one of each verb (`@get_endpoint`/`@post_endpoint`/`@put_endpoint`/`@delete_endpoint`), incl. a `@get_endpoint` returning `InertiaPage` (no built bundle — `app_bundle` is a pure path derivation). Feeds `test_endpoints.py`. |
| `BrowserApp` | Minimal app dedicated to buildfrontend's browser phase: one seeded row, a `@get_endpoint` rendered as an Inertia page with its own bundle, and `@playwright_test`s that assert the built UI via the browser (a `@post_endpoint` insert and a `@put_endpoint` modify, each rolled back per request by buildfrontend's drive). |
| `AllColumns` | Every `Column` class (char/text/integer/boolean/decimal/datetime/user/foreign_key) materialised through the framework — a `category` target table is referenced by an FK on the main `row` table, served as one typed row. |
| `HttpMockApp` | An endpoint that calls an external HTTP API via `_fetch_json`; its `@backend_test` patches that helper (`unittest.mock.patch`) so no real network call runs. |
| `FailsTestApp` | A valid install whose `@backend_test` raises — used to prove the whole install rolls back (no app/table/physical table left). |
| `FailsSetup` | `@setup` itself raises (a bad `CharColumn(max_length=0)`) — used to prove the same rollback guarantee on a setup-time failure. |
| `ZeroSetupApp` | No `@setup` (an app need not declare one); one trivial `@backend_test`. Proves `buildbackend` runs the tests + bumps but creates no `Application` row (no setup to make one). |

## Multi-step resume fixtures (nested `<tree>/MultiStepApp/app.py`)

`buildbackend` resumes from the last completed setup (forward-only; see
`prompts/20260721-multi-step-setup.md`). Three trees share the **same app
name** `MultiStepApp` so the runner resolves the same `Application` row across
installs — only the patched `_APPS_ROOT` changes which file loads (each tree is
its own root). Feeds `BuildBackendResumeTests` in `test_buildbackend.py`.

| Tree | Setups | Used by |
| --- | --- | --- |
| `multistep_step1/MultiStepApp/` | `[setup1]` (creates `alpha`) | `test_resume_runs_only_new_step` (install → `executed_setups=["setup1"]`) |
| `multistep_step2/MultiStepApp/` | `[setup1, setup2]` (`setup1` identical to step1's; `setup2` adds `beta`) | the resume leg — only `setup2` runs; `executed_setups` → `["setup1","setup2"]` |
| `multistep_renamed/MultiStepApp/` | `[setup1, setup_two]` (same length, position-1 renamed) | `test_prefix_mismatch_refuses_resume` → `CommandError` |

The resume test's proof of the skip is structural: step2's `setup1` does
non-idempotent `create_application` work, so if it were re-run it would
`IntegrityError`; the step2 install succeeding + the captured "Remaining
setups" output listing only `setup2` together prove `setup1` was skipped.

## The framework contract

Each `app.py` tags its functions with standalone decorators (`@setup` /
`@get_endpoint` / `@post_endpoint` / `@put_endpoint` / `@delete_endpoint` /
`@backend_test` / `@playwright_test`); an app may declare several `@setup`s (run
in source order) or none. The loader builds a `DynamicModule` from the imported
module. See [`djangoapp/apps/dynamic_module.py`](../../apps/dynamic_module.py)
and the [app framework](../../../README.md#app-framework) section of the main
README.
