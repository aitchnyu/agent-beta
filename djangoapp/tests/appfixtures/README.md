# Test fixture apps

Each fixture lives at `Tests/<app>/app.py` under this tree (matching the app
framework's `<apps_root>/<collection>/<app>/app.py` convention — all fixtures
share one collection, `Tests`); `apps_root` is patched to this tree in the app
tests. They double as runnable examples of the framework and as the data the
tests in `test_buildbackend.py` / `test_buildfrontend.py` / `test_endpoints.py`
install.

Loaded by file path (not imported as a package), so the fixture dirs have no
`__init__.py` on purpose.

Apps are installed inside the test's transaction, so created collections/apps/
tables are rolled back automatically; `dynamic_models.reset()` +
`app_modules.clear()` keep the in-memory state clean between tests.

| Collection/App | What it exercises |
| --- | --- |
| `Tests/Page` | Install/seed fixture: `@setup` seeds an `items` table; a `@backend_test` writes a row during install (proving savepoint rollback). Feeds `test_buildbackend.py`. |
| `Tests/Endpoints` | Endpoint-serving fixture: a random `@get_endpoint` + an `@inertia_endpoint` (no built bundle — `app_bundle` is a pure path derivation). Feeds `test_endpoints.py`. |
| `Tests/Browser` | Minimal app dedicated to buildfrontend's browser phase: one seeded row, an `@inertia_endpoint` rendered with its own bundle, and `@playwright_test`s that assert the built UI via the browser (incl. an in-process write that buildfrontend's rolled-back drive reverts). |
| `Tests/AllTypes` | Every `Column` class (char/text/integer/boolean/decimal/datetime/user/foreign_key) materialised through the framework — a `category` target table is referenced by an FK on the main `row` table, served as one typed row. |
| `Tests/Mock` | An endpoint that calls an external HTTP API via `_fetch_json`; its `@backend_test` patches that helper (`unittest.mock.patch`) so no real network call runs. |
| `Tests/FailsTest` | A valid install whose `@backend_test` raises — used to prove the whole install rolls back (no app/table/physical table left). |
| `Tests/FailsSetup` | `@setup` itself raises (a bad `CharColumn(max_length=0)`) — used to prove the same rollback guarantee on a setup-time failure. |

Each `app.py` tags its functions with standalone decorators (`@setup` /
`@get_endpoint` / `@inertia_endpoint` / `@backend_test` / `@playwright_test`);
the loader builds a `DynamicModule` from the imported module. See
[`djangoapp/apps/dynamic_module.py`](../../apps/dynamic_module.py)
and the [app framework](../../../README.md#app-framework) section of the main
README.
