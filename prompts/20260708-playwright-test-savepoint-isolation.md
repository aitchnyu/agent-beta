# Playwright-test savepoint isolation (share the DB connection with the live server)

`buildapp`'s browser phase runs each `@playwright_test` against a short-lived
`LiveServerThread` (`djangoapp/management/commands/buildapp.py`,
`_drive_playwright_tests`, near the `# aihere each test will run in savepoint`
marker). The goal: each test's DB writes roll back after it (savepoint
isolation), mirroring what `setup` now does for `@backend_test`.

## Problem

A `transaction.savepoint()` on the command's connection is invisible to the live
server: the server thread opens its **own** DB connection, and Postgres
read-committed means it can't see uncommitted savepoint data. So a test that
writes a row and then verifies it via the browser would fail — the row isn't
committed, so the server thread's connection doesn't return it.

(This is precisely why `LiveServerTestCase` is a `TransactionTestCase` — commit,
then flush between tests — instead of savepoint-based.)

## Plan

Make the live server **share** the command's connection, the way Django already
does for in-memory sqlite in `LiveServerTestCase._make_connections_override`:

1. Build `connections_override = {"default": connections["default"]}` and call
   `conn.inc_thread_sharing()` on it (so it's safe to use off-thread).
2. Pass it to
   `LiveServerThread(host, StaticFilesHandler, port=0, connections_override=connections_override)`.
   The server thread then services requests on the **same** connection, so it
   sees uncommitted savepoint data.
3. Wrap each `@playwright_test` in `transaction.savepoint()` → run →
   `savepoint_rollback(sid)` + `savepoint_commit(sid)` in a `finally` (mirrors
   the `@backend_test` loop in `setup.py`). A test's writes are visible to the
   browser during the test and rolled back after.

## Why this is safe

Connection access is **serialized**: the command's main thread blocks on
playwright I/O (`page.goto` / `.click`) while the server thread handles that one
request on the shared connection. The two never touch the connection
concurrently. (This differs from the playwright harness `AppPlaywrightTests`,
which deliberately gives the server its own connection so its tests can be a
`TestCase` with savepoint semantics of their own.)

## Caveats

- Only matters for tests that **write** data they then verify via the browser;
  read-only tests (Demo/Page) are unaffected — this is forward-looking.
- Nested transactions: if `ATOMIC_REQUESTS` is on, each request wraps in its own
  atomic (a savepoint nested inside the test's savepoint). A failed request
  rolls back only its own savepoint, not the test's.
- The throwaway login user created in `_drive_playwright_tests` can move inside
  the per-test savepoint so it rolls back too (then `user.delete()` cleanup can
  go), or stay outside if it should span the whole run.

## Checklist

- [ ] `_drive_playwright_tests`: build `connections_override` for the default
      connection + `inc_thread_sharing()`, pass to `LiveServerThread`
      [djangoapp/management/commands/buildapp.py:187]
- [ ] wrap each `@playwright_test` in `transaction.savepoint()` rolled back in
      `finally` (success and failure)
- [ ] add a `@playwright_test` that writes a row then verifies it via the
      browser, and assert it's gone after (proves isolation end-to-end)
- [ ] decide: login user inside the savepoint (auto-rolled-back) or kept for the
      run; drop `user.delete()` if moved inside
- [ ] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall`

---

# Detailed implementation plan (verified against the code + Django 6.0 API)

Refines the brief Plan/Checklist above with the concrete design, the verified
Django API, and testable structure. The brief items are the goal; this is how to
get there.

## Verified facts (ground the plan)

- Driver today: `_drive_playwright_tests`
  (`djangoapp/management/commands/buildapp.py:145-208`) starts
  `LiveServerThread(host, StaticFilesHandler, port=0)` with **no** connection
  sharing and runs each test with **no** savepoint
  (`# aihere each test will run in savepoint`, `buildapp.py:190`).
- Pattern to mirror: the `@backend_test` savepoint loop in `install_or_update`
  (`djangoapp/management/commands/installorupdate.py:84-100`) —
  `savepoint()` → run → `savepoint_rollback(sid)` + `savepoint_commit(sid)` in
  `finally`.
- DB: Postgres; `ATOMIC_REQUESTS` is **not** set
  (`djangoproject/settings.py:98-107`) → the live server opens no per-request
  atomic, so the only transaction is the one we open. **This means the
  "Nested transactions / ATOMIC_REQUESTS" caveat above does not apply here.**
- `buildapp` runs against the **default/dev DB** (it's a management command, not
  a test) → every write persists unless we roll it back. This is why the whole
  phase must roll back, not just per-test writes.
- Django API confirmed in the installed source
  (`.venv/.../django/test/testcases.py:1737,1816-1865`):
    - `LiveServerThread(host, static_handler, connections_override=None, port=0)`
      — add `connections_override=`. (Django only shares in-memory sqlite by
      default in `_make_connections_override`; for Postgres we build the dict +
      share it ourselves, which is the supported internal path.)
    - `conn.inc_thread_sharing()` / `conn.dec_thread_sharing()` bracket the
      server's lifetime (balance them in a `finally`).
    - `transaction.set_rollback(True, using="default")` forces an `atomic` block
      to roll back on a clean exit — used to roll the phase back.

## Design — two layers of rollback

1. **Phase atomic (rolled back):** wrap the entire browser phase — login user +
   all tests — in one `transaction.atomic(using="default")` marked
   `set_rollback(True)`. Nothing it writes reaches the dev DB. Because the
   connection is shared, the server thread serves `login-for-test` on the *same*
   connection and sees the uncommitted user → the login user can move **inside**
   the phase atomic and `user.delete()` is dropped (resolves the open "decide"
   item: login user inside, auto-rolled-back).
2. **Per-test savepoint (rolled back):** inside the phase, each `@playwright_test`
   runs in `transaction.savepoint()` → run → `savepoint_rollback(sid)` +
   `savepoint_commit(sid)` in `finally`. This gives inter-test isolation (test B
   never sees test A's writes) and guarantees a **failing** test's partial
   writes are undone — the "rollback on failure" requirement.

The phase atomic is needed because per-test savepoints alone (without an
enclosing transaction) have nothing to roll back *into* on Postgres, and they
would not undo the login user or any direct server-thread writes.

## Testability refactor

Pull the savepoint loop out of the browser/server machinery so it is unit-testable
without playwright:

- `_run_tests_in_savepoints(tests, *, page, base_url, err_write)` — opens the
  phase `atomic` (`set_rollback(True)`), then iterates the tests with the
  per-test savepoint loop. Pure DB + `page`; no server/browser.
- `_drive_playwright_tests(tests, *, err_write, host)` — keeps the shared
  connection + live server + playwright + login, then delegates the test loop to
  `_run_tests_in_savepoints(...)`.

Unit tests drive `_run_tests_in_savepoints` with a **fake `page`** (stub
`goto`/`locator`) and real DB writes, asserting each test saw its own write, the
next test did not, and the DB is empty afterward — no browser required.

## Call sequence (in `_drive_playwright_tests`)

1. `conn = connections["default"]`; `conn.inc_thread_sharing()`.
2. `server = LiveServerThread(host, StaticFilesHandler,
   connections_override={"default": conn}, port=0)`; `server.daemon = True`.
3. `try:` start server, wait `is_ready`, raise on `server.error`; enter
   `modify_settings(ALLOWED_HOSTS) + override_settings(DEBUG=True,
   SECURE_CSP_REPORT_ONLY=None)`; build the playwright page.
4. Call `_run_tests_in_savepoints(...)`, which internally does:
   `with transaction.atomic(using="default"):` → `set_rollback(True)` → create
   the login user → `page.goto(login-for-test/{user.pk})` → per-test savepoint
   loop.
5. `finally:` close page/context/playwright; `server.terminate()`; **then**
   `conn.dec_thread_sharing()`. No `user.delete()`.

## Risks / verify while implementing

- **Serialization assumption** (from "Why this is safe" above): the main thread
  blocks on playwright I/O while the server handles one request on the shared
  connection. Never issue concurrent browser requests in a single test.
- **`close_old_connections` on the server thread**: Django's own
  `LiveServerTestCase` relies on this same shared-connection path, so it is the
  supported mechanism — but watch for any connection reset mid-transaction and
  confirm `set_rollback(True)` survives the round-trip.
- **Leave `AppPlaywrightTests` / `BasePlaywrightTestCase` alone**: it deliberately
  gives the server its own connection (TestCase-style savepoints). Only the
  `buildapp` command path shares.

## Checklist (implementation)

- [ ] extract `_run_tests_in_savepoints(tests, *, page, base_url, err_write)`:
      phase `transaction.atomic` + `set_rollback(True)` + per-test
      `savepoint`/`savepoint_rollback`/`savepoint_commit` loop
      [djangoapp/management/commands/buildapp.py:145]
- [ ] share the default connection: `connections["default"]` +
      `inc_thread_sharing()`, pass `connections_override={"default": conn}` to
      `LiveServerThread` [djangoapp/management/commands/buildapp.py:165]
- [ ] move login-user creation inside the phase atomic; drop `user.delete()`
      [djangoapp/management/commands/buildapp.py:169,208]
- [ ] balance `inc_thread_sharing()` with `dec_thread_sharing()` in `finally`
      after `server.terminate()` [djangoapp/management/commands/buildapp.py:205-208]
- [ ] tests for `_run_tests_in_savepoints` (fake page, real DB):
    - [ ] a test's write is visible to it while it runs
    - [ ] the next test does not see the previous test's write
    - [ ] after the drive, the written rows are gone (phase rolled back)
- [ ] end-to-end `@playwright_test` fixture:
    - [ ] one test writes a row via the app and verifies it via the browser
    - [ ] a second test asserts that row is absent (proves rollback end-to-end)
- [ ] update the `_drive_playwright_tests` docstring: shared-connection +
      savepoint model; drop the now-stale "TransactionTestCase / savepoint not
      visible to the server thread" caveat [djangoapp/management/commands/buildapp.py:151-162]
- [ ] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall`

---

# Revised direction — commit + per-test cleanup (the savepoint plan is blocked)

Investigating the Django 6.0 source showed the "share the connection + phase
`atomic` + `set_rollback` + per-test savepoints" design **cannot work on
Postgres**. The `# aihere each test will run in savepoint` marker in
`buildapp.py` is therefore **deferred (blocked)**, not implemented — it stays in
place per the aihere rule.

## Why the shared-connection + atomic path is blocked (verified)

1. The outermost `transaction.atomic()` calls `set_autocommit(False)`
   (`transaction.py:216-219`), so inside the phase `get_autocommit()` is `False`
   while `settings_dict["AUTOCOMMIT"]` stays `True`.
2. Every server request fires `close_old_connections` on `request_started` /
   `request_finished` (`django/db/__init__.py:62-63`).
3. The shared connection **is** visible to the request thread: `__setitem__`
   sets the attr, so `connections.all(initialized_only=True)` returns it
   (`connection.py:66-81`).
4. `close_if_unusable_or_obsolete` then sees `get_autocommit() != settings
   AUTOCOMMIT` (`False != True`) → `close()` (`base.py:600`).
5. `close()` while `in_atomic_block` calls `_close()` (kills the psycopg conn),
   sets `closed_in_transaction=True`, and `ensure_connection` refuses to
   reconnect inside an atomic block (`base.py:344-361`, `271-279`). The command
   thread's transaction is dead after the **first** request.
6. `ThreadedWSGIServer.close_request` → `close_all()` → `close()` compounds it
   every request (`basehttp.py:106-112`).

Django's own `LiveServerTestCase` avoids this only because it is a
**`TransactionTestCase`** (autocommit stays ON — commit, then flush). The
codebase's `BasePlaywrightTestCase` extends `StaticLiveServerTestCase` →
`LiveServerTestCase` → `TransactionTestCase`, confirming the working pattern is
commit+flush, never in-transaction savepoint sharing. The only ways around it
fight the framework (custom `ThreadedWSGIServer` that skips `close_request`'s
`close_all` + disconnecting `close_old_connections` signals + a `settings_dict`
autocommit hack) — fragile and internal-dependent, rejected.

## Chosen direction: commit + per-test cleanup

The driver stays on the live server's **own** connection (current behaviour — no
`connections_override`, no `inc_thread_sharing`, no `transaction.atomic`, no
`set_rollback`). A `@playwright_test`'s writes **commit** to the DB and are
visible to the server's separate connection (read-committed sees committed
data) — that is how the browser observes a write. Isolation is the **test's**
responsibility: a test that writes cleans up its own rows in a `finally` (runs
even on failure). The throwaway login user is already create+delete in the
driver's `finally`.

Trade-off vs. the original goal: no automatic rollback if a test's own cleanup
fails or the process is hard-killed. Acceptable for a buildapp smoke phase.

## Checklist (revised — supersedes the implementation checklist above)

The savepoint/connection-sharing items above are **N/A** (blocked):

- [~] extract `_run_tests_in_savepoints` — N/A, no savepoints (blocked)
- [~] share the default connection + `inc_thread_sharing` — N/A (blocked)
- [~] move login user inside the phase atomic; drop `user.delete()` — N/A; the
      user stays create+delete in the driver `finally` (current behaviour)
- [~] balance `inc_thread_sharing` with `dec_thread_sharing` — N/A (blocked)

Revised work:

- [x] `_drive_playwright_tests` docstring: document the commit + per-test-cleanup
      model and why savepoint/connection-sharing is blocked (keep the
      `# aihere each test will run in savepoint` + `# aihere pass context…`
      markers in place — deferred, not removed)
      [djangoapp/management/commands/buildapp.py:151-162]
- [x] end-to-end `@playwright_test` fixture in Tests/Page:
    - [x] add a `row_count` `@get_endpoint` (returns `{"count": N}`) so the
          browser can observe a write
    - [x] one test writes a row via the app's model (commits), verifies via the
          browser that `row_count` rose, and deletes the row in a `finally`
    - [x] a second test asserts via the browser that `row_count` is back to the
          seeded count (proves the prior test cleaned up → inter-test isolation)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 19 playwright tests pass)

---

# Follow-up: skipped no-sharing rollback demo class

A separate, **normally-skipped** class that runs an app's `@playwright_test`
under a rolled-back transaction (the no-sharing rollback variant). Enable with
`SAVEPOINT_PLAYWRIGHT=1`; default is skipped so CI stays green.

- [x] `SavepointRollbackPlaywrightTests` in
      `djangoapp/tests/appfixtures/test_savepoint_rollback.py` (own file):
      `StaticLiveServerTestCase`
      (server on its own connection) + one `transaction.atomic()` with
      `set_rollback(True)` + per-test `savepoint`/`savepoint_rollback`/`savepoint_commit`.
      Proves rollback by writing a probe row inside the atomic and asserting it's
      gone after. Skips the write-verify-browser pair (`_SKIP_UNDER_ROLLBACK`) —
      those need the write committed (commit + cleanup path), not a rolled-back
      savepoint.
- [x] gotcha fixed: `set_rollback(True)` must be the **last** statement inside the
      `atomic` block — it sets `needs_rollback`, which makes every later query raise
      `TransactionManagementError` via `validate_no_broken_transaction`. Putting it
      first (initial attempt) broke `savepoint()`/`create()`. Mirrors
      `TestCase._rollback_atomics`, which calls it right before `atomic.__exit__`.
- [x] verified: passes with `SAVEPOINT_PLAYWRIGHT=1`; skipped by default
      (`checkall` -> `OK (skipped=1)`).

---

# Follow-up: arbitrary app support (no hardcoded Tests/Page)

`SavepointRollbackPlaywrightTests` hardcoded `IDENTITY = "Tests/Page"` and the
`"Tests"`/`"Page"` literals in `setUp`/`tearDown`/`_build_frontend`. The sibling
`AppPlaywrightTests` already selects the app via the `APP_IDENTITY` env var
("Collection/App", default `Tests/Page`); the savepoint demo should do the same
so it can run any app's `@playwright_test` under a rolled-back transaction.

## Checklist

- [x] read `APP_IDENTITY` env var in `test_savepoint_rollback.py`
      (default `Tests/Page`), validate `<Collection>/<App>` in `setUp`, split
      into `self.collection`/`self.app_name` [test_savepoint_rollback.py:34,79-82]
- [x] replace hardcoded `"Tests"`/`"Page"` in `setUp`, `tearDown`,
      `_build_frontend` with `self.collection`/`self.app_name`
      [test_savepoint_rollback.py:85-86,93-95,108]
- [x] generalize class docstring + the `IDENTITY` comment away from Tests/Page
      [test_savepoint_rollback.py:30-34,44-57]
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 20 playwright, skipped=1)

---

# Final direction: rolled-back savepoint drive as buildapp's default

The commit + per-test cleanup model was a workaround after the *shared*-connection
savepoint plan was blocked. But the non-shared rollback variant (server on its own
connection; the rolled-back `atomic` + per-test savepoints on the command's
connection) is unaffected by the `close_old_connections` poisoning that blocked
sharing — per-request cleanup runs on the *server* thread's connection, never the
command's. `SavepointRollbackPlaywrightTests` already proved this works; the drive
in `buildapp` is the right home for it (the install is committed by the time the
browser phase runs, so the server can see it — unlike `install_or_update`, whose
uncommitted atomic install a separate-connection server can't observe).

`install_or_update` stays atomic + in-process for `@backend_test` (same connection
sees the uncommitted install); the live server can't live there.

## Decisions

- Rolled-back savepoint drive is now `buildapp`'s **default** (not env-gated).
- `SavepointRollbackPlaywrightTests` is **kept** (test-runner-side harness on the
  test DB; distinct from `buildapp`'s dev-DB drive, same technique).
- The commit + per-test-cleanup write-verify Tests/Page tests are removed: under a
  rolled-back savepoint a write is uncommitted, so the server's separate connection
  can't observe it — write-then-verify-via-browser is impossible here.

## Checklist

- [x] `_drive_playwright_tests`: wrap the test loop in one
      `transaction.atomic()` + per-test `savepoint`/`savepoint_rollback`/
      `savepoint_commit`, with `set_rollback(True)` as the last statement; login
      user stays created-before-atomic (committed) + deleted in `finally`
      [buildapp.py:145]
- [x] drop the now-addressed `# aihere each test will run in savepoint`; keep
      `# aihere pass context to browser...` (deferred) [buildapp.py]
- [x] rewrite the `_drive_playwright_tests` docstring for the rolled-back model
      (why the server keeps its own connection; why writes are invisible to the
      browser; why sharing was blocked) [buildapp.py:151]
- [x] Tests/Page/app.py: remove `CountOut`/`row_count`/`WRITE_CODE`/
      `_row_count_via_browser` + the two write-verify tests + the `json` import;
      add `ROLLBACK_PROBE` + `test_inprocess_write_is_visible_to_self` (writes a
      probe in-process, asserts it's visible to itself; rollback proven post-drive)
      [Tests/Page/app.py]
- [x] `SavepointRollbackPlaywrightTests`: remove `_SKIP_UNDER_ROLLBACK` + the skip
      filter (the write-verify pair is gone); update docstring
      [test_savepoint_rollback.py]
- [x] `BuildappDrivesPlaywrightTests.test_buildapp_drives_demo_page`: after
      `call_command("buildapp", ...)`, assert the `rbprobe` probe is absent
      (end-to-end proof the drive's atomic rolled the write back)
      [test_app_playwright.py]
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 20 playwright, skipped=1)

---

# Context API + dedicated buildapp sample + rename

Implements the `# aihere pass context to browser instead of page, let user
create page and users and login explicitly` marker (now removed from buildapp).

## Decisions

- `@playwright_test` contract: `fn(context, base_url)` — the test builds its own
  page (and users/login if ever needed); the driver owns server + browser only.
- **Fresh** `BrowserContext` per test (closed after) — per-test session/storage
  isolation matching the per-test savepoint DB isolation; login, if ever needed,
  is scoped to that one test (no leak). Applied uniformly across all three
  drivers (`_drive_playwright_tests`, `AppPlaywrightTests`,
  `SavepointRollbackPlaywrightTests`).
- **Defer** a login helper (`viewer_page`): no fixture needs auth (app endpoints
  are anon-readable).
- New minimal app **`Tests/Browser`** is the dedicated buildapp sample (Tests/Page
  stays the comprehensive demo). `test_setup_runner.py` **split** into
  `test_installorupdate.py` (`InstallOrUpdateTests`) + `test_buildapp.py`
  (`BuildappCommandTests` + `BuildappPlaywrightPhaseTests`).

## Checklist

- [x] `_drive_playwright_tests`: drop the throwaway user/page/auto-login; call
      `fn(context=context, base_url=base_url)` with a fresh
      `browser.new_context()` per test (closed in finally); drop the now-unused
      `User`/`os` imports + the addressed aihere; rewrite the docstring
      [buildapp.py:145]
- [x] all `@playwright_test` call sites pass a fresh `context` per func and close
      it after: `_drive_playwright_tests`, `AppPlaywrightTests`,
      `SavepointRollbackPlaywrightTests`
- [x] fixture app signatures `(context, base_url)`, each creates its own page:
      `Tests/Page/app.py` (render test; the buildapp-rollback probe moved out),
      `docs/apps/reference/app.py`; `Page` -> `BrowserContext` type import
- [x] new `Tests/Browser` app: `app.py` (setup + `@inertia_endpoint` +
      `@get_endpoint` + render + rollback-probe `@playwright_test`s) + mirrored
      `frontend/` (package.json/vite.config.js/src/main.ts/BrowserPage.vue)
- [x] `BuildappDrivesPlaywrightTests`: target `Tests/Browser`; assert bundle
      (`main.js`) written + the `smoke` rollback probe absent post-drive
- [x] rename/split `test_setup_runner.py` -> `test_installorupdate.py` +
      `test_buildapp.py`; update the `FailsTest`/`FailsSetup` docstring refs +
      the `appfixtures/README.md` (Tests/Browser row + fixed file ref)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 20 playwright, skipped=1)

---

# Consolidation: drop the redundant rollback demo

Once `buildapp` adopted the rolled-back savepoint drive, `SavepointRollbackPlaywrightTests`
(the skipped-by-default standalone demo of that technique) became redundant —
`BuildappDrivesPlaywrightTests` already proves the rollback end to end (the
`smoke` probe assertion). So:

- **Dropped** `test_savepoint_rollback.py` (`SavepointRollbackPlaywrightTests`).
- **Moved** `BuildappDrivesPlaywrightTests` from `test_app_playwright.py` into
  `test_buildapp.py` (it's a buildapp command test, not an app-centric one); the
  now-unused `TransactionTestCase`/`override_settings`/`tag` import left
  `test_app_playwright.py`.
- **Kept** `AppPlaywrightTests` in `test_app_playwright.py` (app-centric,
  `APP_IDENTITY`-configurable browser harness — not a buildapp test).

## Checklist

- [x] move `BuildappDrivesPlaywrightTests` -> `test_buildapp.py` (+ `subprocess`/
      `shutil`/`apps_root`/`TransactionTestCase`/`override_settings`/`tag` imports;
      reuses `test_buildapp.py`'s `_APPS_ROOT_PATCH`)
- [x] remove it from `test_app_playwright.py` + drop the now-unused `django.test`
      import line
- [x] delete `test_savepoint_rollback.py`
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall`

---

# DRY: buildapp owns `npm install`

`npm install` (ensure `node_modules`) was duplicated across two harnesses
(`AppPlaywrightTests._build_frontend`, `BuildappDrivesPlaywrightTests.setUp`) —
and they disagreed on the npm-missing case (raise vs silent-skip). Dep-install
is part of building, so it moved into `buildapp` itself; both harnesses now just
call `buildapp` (which self-sufficiently installs deps, then builds). Bonus:
standalone `buildapp <app>` no longer fails on a cold cache.

## Checklist

- [x] `buildapp.handle`: if `(frontend_dir / "node_modules")` is absent, run
      `npm install` before the build; both install + build share a `_run_npm`
      helper (subprocess + `CommandError` on `CalledProcessError`)
- [x] drop the npm-install block from `AppPlaywrightTests._build_frontend` (now
      just `call_command("buildapp", ..., skip_playwright=True)`); remove the
      now-unused `shutil`/`subprocess` imports
- [x] drop the npm-install block from `BuildappDrivesPlaywrightTests.setUp`;
      remove `shutil`/`subprocess`/`apps_root` imports
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 19 playwright, 0 skipped).
      `_run_npm` proven via the build step; the install call reuses it.

---

# Drop `AppPlaywrightTests`; trim `Tests/Page`'s `@playwright_test`

`AppPlaywrightTests` (the `APP_IDENTITY`-configurable harness that drove an app's
`@playwright_test`s via its own loop) is now redundant — `buildapp <app>` does the
same (build + rolled-back drive), proven by `BuildappDrivesPlaywrightTests`. Removed
it and `Tests/Page`'s now-redundant `@playwright_test` (covered by `Tests/Browser`).

`Tests/Page` stays the comprehensive fixture for the **install + endpoint-serving**
paths (`test_installorupdate.py`, `test_endpoints.py`); `app_bundle` is a pure path
derivation (no file stat), so the inertia-bundle URL test needs no built file.

## Checklist

- [x] delete `test_app_playwright.py` (the `# aihere remove this IDENTITY thing`
      marker with it — addressed)
- [x] trim `Tests/Page/app.py`: drop its `@playwright_test` + `playwright_test`
      import + `BrowserContext` TYPE_CHECKING import + docstring bullet
- [x] fix stale refs: `test_buildapp.py` docstrings (3 spots),
      `appfixtures/README.md` (drop the file + reword the Tests/Page row),
      `docs/apps/README.md` (`APP_IDENTITY … playwrighttest` → `buildapp`),
      `TODO.md` (drop "Remove test_app_playwright")
- [x] fix the test-ordering regression: `BuildappDrivesPlaywrightTests` (a plain
      `TransactionTestCase`) had been relying on `AppPlaywrightTests`
      (a `BasePlaywrightTestCase`, alphabetically earlier) setting
      `DJANGO_ALLOW_ASYNC_UNSAFE` process-wide; once removed, `test_buildapp` ran
      first and `transaction.atomic()` inside `sync_playwright` tripped the
      async-unsafe guard. Added       `setUpClass` to set it itself (order-independent)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 18 playwright, 0 skipped)

---

# Split `Tests/Page` into install vs endpoint fixtures

`Tests/Page` was a kitchen-sink feeding two test modules (install + endpoint) and
bundling four concerns (seed, backend-rollback, random get, inertia). Split it so
each test module owns one lean fixture:

- **`Tests/Page`** → install/seed + backend-rollback only (`@setup` seeds an
  `items` table; a `@backend_test` writes a row during install → savepoint
  rollback proof). Feeds `test_installorupdate.py`.
- **`Tests/Endpoints`** (new) → endpoint serving (`random_code` `@get_endpoint` +
  `endpoint_page` `@inertia_endpoint`). Feeds `test_endpoints.py`. No `frontend/`:
  `app_bundle` is a pure path derivation, so the inertia-URL test needs no built
  bundle (Vue rendering is `Tests/Browser`'s job).
- Deleted the orphaned `Tests/Page/frontend/` (its `demo_page` moved out).

## Checklist

- [x] new `Tests/Endpoints/app.py` (setup + `random_code` + `endpoint_page` +
      the two random backend_tests)
- [x] slim `Tests/Page/app.py` to `setup` + `test_backend_test_writes_roll_back`;
      drop endpoints/inertia + unused imports (`BaseModel`/`InertiaPage`/etc.)
- [x] `git rm -r Tests/Page/frontend` (orphaned after `demo_page` moved)
- [x] `test_endpoints.py`: point the 5 tests at `Tests/Endpoints`
      (`endpoint_page`, component `EndpointPage`, prop `code`, bundle URL)
- [x] update `test_installorupdate.py` docstring + `appfixtures/README.md`
      (Tests/Page row + new Tests/Endpoints row)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 18 playwright, 0 skipped)

---

# Per-request rollback middleware: all playwright changes revert on the dev DB

Goal (2026-07-10): guarantee `buildapp`'s browser drive reverts **every** DB
change a `@playwright_test` causes — writes made in-process by the test body
(command thread) **and** writes triggered over HTTP by the browser (server
thread) — on the dev DB, **without flush**. The rolled-back savepoint drive only
covers the in-process path; browser-caused writes currently commit on the live
server's own connection and persist. This closes that gap.

## Why the obvious mechanisms don't work (verified vs Django 6.0 source)

- **Share the connection + one rolled-back atomic** (the original plan): blocked.
  `close_old_connections` fires on `request_started`/`request_finished`
  (`django/db/__init__.py:62-63`); `close_if_unusable_or_obsolete` closes any
  connection whose autocommit differs from the setting (`base.py:591-602`).
  Inside `atomic`, autocommit is off → the shared connection is force-closed on
  the first request. This is exactly why `LiveServerTestCase` is a
  `TransactionTestCase` (commit + flush), never in-transaction.
- **Flush** (`LiveServerTestCase`'s real mechanism): deletes every row in every
  table. `buildapp` runs on the real/dev DB → flush would nuke dev data.
  Acceptable only on a throwaway test DB, not here.

## Plan: a request-scoped rollback middleware on the server's own connection

Add a new-style sync middleware that wraps each request in a rolled-back
`atomic`, installed **only during the drive** via `modify_settings(prepend)`:

```python
class RollbackEveryRequestMiddleware:
    def __init__(self, get_response: Callable[..., object]) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:  # noqa: ANN401 # Django request is untyped
        with transaction.atomic():
            response = self.get_response(request)
            transaction.set_rollback(True)
        return response
```

Why this dodges the `close_old_connections` wall: the atomic is **fully contained
within one request**. `request_started` fires before the middleware (autocommit
on → not closed); the middleware does BEGIN→view→ROLLBACK (autocommit back on);
`request_finished` fires after (autocommit on → not closed). No sharing, no
flush, works on the dev DB. Each request's writes revert automatically, pass or
fail.

## Two layers of rollback (both kept)

1. **In-process (existing):** the drive's outer `transaction.atomic()` +
   `set_rollback(True)` on the command's connection reverts writes a
   `@playwright_test` body makes [buildapp.py:223,241].
2. **Browser (new):** the prepended middleware reverts writes triggered over HTTP,
   on the server thread's own connection.

Independent (different connections); neither sees the other's uncommitted data,
but **both revert**, so the drive leaves the DB unchanged.

## Scoping: why the middleware runs only in `_drive_playwright_tests`

Three reinforcing guarantees (all verified):

1. **Time** — added via `modify_settings(MIDDLEWARE={"prepend": <dotted>})` inside
   the existing `with` block [buildapp.py:195]; a context manager, so restored on
   exit (clean or exception). Every line outside the block sees the normal
   `MIDDLEWARE`.
2. **Instance** — `WSGIHandler.__init__` calls `load_middleware()` once and caches
   `_middleware_chain` (`wsgi.py:118`, `base.py:103`). The `LiveServerThread`
   builds its own `WSGIHandler()` inside `run()` (hence inside the block); that
   handler serves only this short-lived thread, terminated at drive end
   [buildapp.py:244].
3. **Process** — `./run buildapp` is its own process; the dev server / prod are
   separate processes that never receive the patch.

**Prepend, not append** (`base.py:40` iterates `reversed(MIDDLEWARE)`, so index 0
is outermost): the middleware must be outermost to also wrap response-phase writes
— notably the session save `SessionMiddleware` does on the response.

## Constraint (worth recording)

Per-**request** rollback, not per-test: a write made in request N is gone by
request N+1, so a POST-then-separate-GET-verify pattern won't see the write
(within-request write+verify works). Acceptable for buildapp's smoke phase.

## Test: ensure the playwright run didn't modify the DB

The headline proof — browser-triggered writes (both an **insert** and a **modify
of an existing row**) that are visible within their request but revert after,
plus the post-drive "DB unchanged" assertion.

- `Tests/Browser` adds two test-fixture-only side-effecting GETs (the framework
  exposes only `@get_endpoint` GETs):
    - `create_row` — inserts a row with a known code (`BROWSER_WRITE`, within the
      `code` column's `max_length`) and returns it.
    - `modify_seed` — sets the seeded row's code to `MODIFY_TO` and returns the
      new value.
- Two `@playwright_test`s, each hitting its endpoint via `context.request.get`
  (a real live-server request through the middleware) and asserting the response
  shows the changed value — proving the change is visible **for the lifetime of
  that request**:
    - `test_browser_insert_round_trips` → response shows `BROWSER_WRITE`.
    - `test_browser_modify_round_trips` → response shows `MODIFY_TO`.
- Keep `ROLLBACK_PROBE` / `test_inprocess_write_is_visible_to_self` (in-process
  path).
- `BuildappDrivesPlaywrightTests.test_buildapp_drives_browser_app`: after
  `call_command("buildapp", ...)`, assert the `items` table is **unchanged** —
  exactly the one seed row at its original `SEED` value: the inserted
  `BROWSER_WRITE` row is absent (insert reverted), the seed is **not** `MODIFY_TO`
  (modify reverted), the in-process `smoke` probe is absent, and `count() == 1`.
  This is the "didn't modify the DB" guarantee, proven for insert, modify, and
  in-process paths.

## Decisions

- Middleware lives in `buildapp.py` (the drive's private middleware), referenced
  by dotted path `djangoapp.management.commands.buildapp.RollbackEveryRequestMiddleware`.
- Keep the in-process atomic + per-test savepoints (unchanged); the middleware is
  purely additive.
- `Tests/Browser` keeps its read-only render test; the write test is added
  alongside it.

## Checklist

- [x] add `RollbackEveryRequestMiddleware` middleware (new-style sync: `__init__` +
      `__call__` wrapping `get_response` in `atomic` + `set_rollback(True)`,
      annotated) [buildapp.py]
- [x] install it during the drive: `modify_settings(MIDDLEWARE={"prepend":
      "djangoapp.management.commands.buildapp.RollbackEveryRequestMiddleware"})` inside the
      existing `with` block [buildapp.py:195]
- [x] `Tests/Browser/app.py`: add `BROWSER_WRITE` + `MODIFY_TO` constants; add
      `@get_endpoint create_row` (insert + return) and `@get_endpoint modify_seed`
      (update the seed + return the new value); add `CreatedOut`/`ModifiedOut`
      schemas [Tests/Browser/app.py]
- [x] `Tests/Browser/app.py`: add `@playwright_test test_browser_insert_round_trips`
      and `test_browser_modify_round_trips` (each `context.request.get` → assert
      the changed value is in the response, i.e. visible for the request's
      lifetime) [Tests/Browser/app.py]
- [x] `BuildappDrivesPlaywrightTests.test_buildapp_drives_browser_app`: assert
      `items` is unchanged post-drive — one row, the seed at its original value:
      `BROWSER_WRITE` absent (insert reverted), seed not `MODIFY_TO` (modify
      reverted), `smoke` absent, `count() == 1` [test_buildapp.py]
- [x] rewrite the `_drive_playwright_tests` docstring: two-layer rollback
      (in-process atomic + per-request middleware), why the server keeps its own
      connection, and the per-request (not per-test) constraint [buildapp.py:182]
- [x] README: state that `@playwright_test` DB changes are all rolled back
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`,
      `./run checkall` — all green (152 backend + 18 playwright, 0 skipped)
