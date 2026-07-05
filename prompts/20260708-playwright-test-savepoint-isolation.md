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
