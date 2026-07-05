# Test fixture apps

Each fixture lives at `Tests/<app>/app.py` under this tree (matching the app
framework's `<apps_root>/<collection>/<app>/app.py` convention — all fixtures
share one collection, `Tests`); `apps_root` is patched to this tree in the app
tests. They double as runnable examples of the framework and as the data the
tests in `test_setup_runner.py` / `test_endpoints.py` / `test_app_playwright.py`
install.

Loaded by file path (not imported as a package), so the fixture dirs have no
`__init__.py` on purpose.

Apps are installed inside the test's transaction, so created collections/apps/
tables are rolled back automatically; `dynamic_models.reset()` +
`app_modules.clear()` keep the in-memory state clean between tests.

| Collection/App | What it exercises |
| --- | --- |
| `Tests/Page` | The comprehensive app: `@setup` + seeded `items` table, `current_code` + `random_code` `@get_endpoint`s, an `@inertia_endpoint` page with a built Vue frontend, backend tests (incl. one proving writes roll back), and a `@playwright_test` driving the browser. |
| `Tests/AllTypes` | Every `Column` class (char/text/integer/boolean/decimal/datetime/user) materialised through the framework, served as one typed row. |
| `Tests/Mock` | An endpoint that calls an external HTTP API via `_fetch_json`; its `@backend_test` patches that helper (`unittest.mock.patch`) so no real network call runs. |
| `Tests/FailsTest` | A valid install whose `@backend_test` raises — used to prove the whole install rolls back (no app/table/physical table left). |
| `Tests/FailsSetup` | `@setup` itself raises (a bad `CharColumn(max_length=0)`) — used to prove the same rollback guarantee on a setup-time failure. |

Each `app.py` tags its functions with standalone decorators (`@setup` /
`@get_endpoint` / `@inertia_endpoint` / `@backend_test` / `@playwright_test`);
the loader builds a `DynamicModule` from the imported module. See
[`djangoapp/apps/dynamic_module.py`](../../apps/dynamic_module.py)
and the [app framework](../../../README.md#app-framework) section of the main
README.
