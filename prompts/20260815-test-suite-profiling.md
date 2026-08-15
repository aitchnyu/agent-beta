# Test-suite profiling findings — what worked, what didn't

Measured on this machine (darwin), 2026-08-14, via `time ./run …` and
`manage.py test --durations N`. Final state verified green: unit suite,
playwright pass (twice), ruff, mypy, format.

## Results

| Gate                                     | Before    | After       | Win   |
|------------------------------------------|-----------|-------------|-------|
| Unit suite (`./run test`, 195→196 tests) | 35.5s     | ~1.5–1.6s   | ~22x  |
| Playwright pass (25 tests)               | 41.4s     | ~13.3–14.1s | ~3.0x |
| ruff / mypy / eslint / vue-tsc / vite    | 1–3s each | unchanged   | —     |

(`./run playwrighttest` adds a fixed `npm run build` ~7s before the suite —
command overhead, not suite time.)

## What worked

### 1. MD5 password hasher via a shared test base (unit suite, -30s)

Nearly every test's `setUp` calls `create_user(password=…)` — 3+ users per
test, dozens in the pagination/N+1 tests — and PBKDF2 costs ~0.1s per hash
(~24s of pure hashing across the suite). No test authenticates by password
(all `force_login` / the DEBUG-only `/login-for-test/<pk>` e2e view), so the
suites swap `PASSWORD_HASHERS` for MD5.

Final mechanism: `djangoapp/tests/_base.py` defines
`BaseTestCase` (`@override_settings(PASSWORD_HASHERS=[MD5])`, the documented
Django idiom) and `BaseInertiaTestCase(BaseTestCase, InertiaTestCase)`. All
roots were re-pointed (`QueryBudgetMixin`, and every direct
`InertiaTestCase`/bare-`TestCase` class — 20 classes across 14 files), and
`BasePlaywrightTestCase` carries the same override in its own decorator.
Because class-scoping relies on inheritance discipline instead of being
automatic, `djangoapp/tests/test_test_conventions.py` walks both test
packages and **fails naming any `TestCase` descendant missing the override**
(proven: a planted stray class fails the run with its module path). Settings
stay production-pure.

History: first shipped as settings.py argv sniffing (`test` after
`manage.py` in `sys.argv`), hardened after review to avoid false-fires on
literal "test" tokens (fixture names), then moved wholesale to the base
class per review — same speed (4.1s vs 4.0s suite), no detection logic at
all, enforced by the guard test instead of argv shapes. One portability
note discovered en route: Django 6 pre-declares `_overridden_settings =
None` on undecorated classes, so the guard reads it with an explicit
`or {}`.

### 2. One firefox for the whole playwright run (~-4s)

`djangoapp/tests/playwright/_base.py`: the harness launched playwright +
headless firefox **per test class** (8 classes ≈ 8 cold launches). Now a lazy
`_SharedBrowser` holder starts one playwright/firefox per test process on
first use. (Superseded by §8: since then there is ONE context + ONE page for
the whole run — the per-class contexts/close described here no longer exist.)
The browser itself is never explicitly closed: the runner
is a one-shot process and playwright's driver exits on stdin EOF when the
interpreter does, taking firefox with it — verified empirically (no
`ms-playwright` processes survive the run).

### 3. Dropped `wait_until="networkidle"` from 17 of 19 gotos (~-15s)

`networkidle` waits for ≥500ms of network silence, paid per navigation. The
files/git/client-errors tests used it on every goto (measured: 0.67–0.81s per
goto); the users-module tests already proved the fast pattern: default `goto`
(the `load` event — `main.js` has executed and Inertia mounts synchronously
from the embedded props) + auto-waiting locators (`wait_for_selector` /
`wait_for(state="visible")` / `click`). Phase profiling (below) then showed
the four `test_client_errors` gotos alone cost ~3.1s — their error POSTs are
awaited via `expect_request`, not quiescence — so those converted too.
Typical load-goto now measures 250–310ms.

### 4. Killed the double login per test (setUp 7.11s → 3.93s)

Phase profiling showed setUp as the biggest block (296ms/test): 16 of 24
tests logged in **twice** — the harness logged in a plain user per test, then
files/git/users classes immediately logged in admin/root on top (users
classes even opened a *second* page for it, leaving the harness page unused).
First fix: a ``requires_default_user = False`` opt-out so superuser-only
classes skip the plain login. Two adjacent fixes fell out:

- **Masked cookie leak**: "anonymous" 404 tests used
  ``self.context.new_page()`` — but cookies are context-level, so those pages
  carried whatever session the previous login left. They only passed because
  the per-test plain login kept resetting the cookie. Now they use
  ``anon_page()`` (separate context) and are genuinely anonymous.
- **Stacked init scripts**: ``context.add_init_script`` ran in per-test
  setUp, so each class context accumulated N redundant copies (24 suite-wide)
  — moved to ``setUpClass``, one per context.

Later, §7 (login via in-process cookie injection) made the default login
cost two INSERTs instead of a page load, and ``login_as`` simply replaces
the session cookie — so the opt-out flag bought nothing and was **removed**
entirely. Kept here as the lifecycle record: the flag was scaffolding for a
waste that the better login mechanism eliminated.

### 5. Class-scoped git fixture (unit suite 4.1s → 1.6s; playwright ~-0.7s)

The unit-suite cProfile had flagged it all along: `GitRepoMixin.setUp` built
the identical `main`+`scratch` temp repos **per test** — 2.7s across 25
git-view tests (~110ms of `git init/config/add/commit` subprocesses each) —
even though the `/git` viewer is strictly read-only. The build moved to
`setUpClass` (one build per class, `addClassCleanup` for tempdir + patch,
commits as `ClassVar`s); the mixin docstring now demands read-only use, and
the three tests that need repo *states* already build their own temp repos
in context managers. Playwright's git setUp dropped too (phase table:
setUp 3.93s → 3.20s).

### 6. The last 2 networkidle gotos → content polls

The two file-preview tests that legitimately needed quiescence (content
arrives after mount; raw `assertIn` doesn't poll) now wait on the CONTENT
instead: `wait_for_selector(".files-code:has-text('BaseModel')")` polls
until the text is there — deterministic like networkidle but ~0.45s faster
per goto. Zero `networkidle` remains suite-wide; slowest goto is now a
~300ms real page load.

### 7. Login without navigation — in-process cookie injection (~-1.4s)

Even after §4, ~20 of the remaining 48 gotos were logins (~270ms each):
navigating to `/login-for-test/<pk>` just to get a session cookie. The
harness gained ``login_as(user)``: it mirrors that view server-side
(``auth_login(request, user, backend=ModelBackend)``) but in-process — a
fresh session store, one save, then the session cookie is injected straight
into the browser context via ``add_cookies``. The next navigation is already
authenticated; login navs dropped 48 → 26 total gotos and setUp settled at
~135ms/test (two INSERTs, no page load). A subsequent ``login_as`` REPLACES
the cookie (same name), which is also what made ``requires_default_user``
(§4) unnecessary — the flag was removed once the default login stopped
costing a page load. The DEBUG-only `/login-for-test` view stays for manual
debugging and its own gate test; the harness sanity-asserts the cookie name
landed in the context instead of the old "Logged in as …" body check.
Safe here because the live server is plain http with default (non-secure)
cookie flags; a `SESSION_COOKIE_SECURE` deployment would need the cookie
injection to match.

### 8. ONE context + ONE page for the whole run (setUp 3.23s → 0.39s)

The remaining per-test setup was page creation + cookie work inside 7
per-class contexts (asset re-downloads per context, cold page each test).
Cookie injection had already made per-test contexts unnecessary — auth
isolation only needs the cookie to be wiped, and a context reset gives
exactly that: ``setUp`` now does ``context.clear_cookies()`` +
``login_as(user)`` on the SUITE-WIDE context/page (created lazily in
``_SharedBrowser.ensure``, console handlers attached exactly once).
Tests needing a truly separate viewer still use ``anon_page`` (own context).
setUp landed at 16ms/test (two INSERTs + cookie), and the shared context
keeps one HTTP cache + warm page across every class.

Two traps surfaced, both fixed:

- **Event misattribution (deterministic)**: playwright's sync API dispatches
  queued console/pageerror callbacks only while a playwright call runs on
  the main thread. ``ClientErrorReportingE2e`` fires async errors
  (``setTimeout`` throw) whose pageerror IPC message outlives the test's
  last call (``expect_request``) — the next test's first ``goto`` pumped it
  into ITS freshly reset sink, failing an unrelated files test.
  Per-test pages had masked this (page close dropped in-flight events).
  Fix: ``tearDown`` pumps the queue with one no-op round trip
  (``page.wait_for_timeout(0)``) while the current test still owns the sink.
- **CSP audited, not the culprit**: the harness runs ``DEBUG=True`` +
  ``SECURE_CSP_REPORT_ONLY=None`` (the permissive dev policy, report-only
  off), and the suite-wide fail-on-console-error default reported zero CSP
  violations — the leak above was the only console error in the run. No
  policy change needed.

### 9. Post-review round: deterministic waits/isolation

Four-agent review of the committed state produced several robustness fixes.
The one speed lever it found — a narrowed `_fixture_teardown` (skip catalog
tables + post_migrate, ~77ms → ~20ms/test) — was implemented, measured, then
REVERTED on review: overriding Django's flush machinery trades correctness
margin for ~1.4s and its excluded-table bookkeeping drifts from Django's own
semantics; the stock flush is the safer default at this suite size.

- **`set_default_timeout(5000)` deleted everywhere** (5 subclass setUps):
  probed empirically at the base 1s — every suite passes with ≥6x headroom;
  the original "too tight for Inertia reloads" rationale was wrong. Base
  `setUp` now also resets the shared page to 1000 per test so a future
  legitimate raise can't leak to later classes via execution order.
- **`data-files-state` component state**: FileViewer exposes
  `data-files-state="loading|rendered"` + `aria-busy` on its root (an
  explicit `previewReady` flag, NOT `rendered !== ''` — empty files render
  `""` legitimately). The two `:has-text()` content polls (and the markdown
  test's latent race) now wait on
  `.files-page[data-files-state="rendered"]` — component lifecycle, not file
  magic strings.
- **Stale-document kill at class boundaries**: `tearDownClass` navigates the
  shared page to about:blank BEFORE the live-server thread dies — a stale
  document (timers, requestIdleCallback chunk preloads) left alive across a
  class boundary would fetch from the dead server port and misattribute the
  unhandled rejections. Within a class the server stays alive, so the cheap
  1ms event-queue pump in tearDown suffices (a per-test about:blank was
  measured at ~+0.8s and split out again).
- **Conventions guard widened**: collects `SimpleTestCase` descendants from
  ALL modules of both test packages (not just `test*` files) — the playwright
  tree and helper-module bases (`query_budget`) were previously invisible to
  it.
- **login_as gate test strengthened**: full authenticated round trip (loads
  `/`, asserts the signed-in marker + username) instead of asserting only the
  cookie's presence — catches a session the server would reject.

Net wall time ≈ unchanged (13.3–14.3s; the reverted flush win aside, the
round's changes were determinism/isolation, not seconds — the extra gate
test's page load and the class-boundary navigations roughly offset each
other).

## What didn't work (measured/rejected)

- **`--parallel 4` on playwright**: 51.4s vs 48.1s serial — a *regression*.
  The per-test cost is live-server + page setup, which doesn't distribute
  across in-process workers here. Not adopted.
- **Narrowed `_fixture_teardown`** (adopted then REVERTED): truncating only
  data tables + skipping post_migrate measured ~77ms → ~20ms/test, but
  overriding Django's flush machinery duplicates table-selection semantics
  that drift from Django's own (excluded-table list is a maintenance trap;
  CASCADE-vs-stray-tables was already fragile) — the stock flush is the
  safer default for ~1.4s at this suite size.
- **Parallelizing the unit suite**: post-hasher it runs 4–7s total; DB-clone
  overhead would eat the win. Not adopted.
- **Frontend gate dedupe**: `npm run build` already runs `type-check` and
  `vite build` concurrently via `run-p` — splitting saves ~0. Dropped.
- **Sharing an HTTP cache across playwright contexts**: would fix the
  per-context re-download of `main.js` (~435KB) + lazy chunks (highlight.js /
  mermaid, up to ~2.4MB) through Django's DEBUG static handler, but Playwright
  doesn't support it. Dead end.
- **Blind `networkidle` removal — partially wrong, caught by tests**: the
  first conversion stripped it from ALL 15 gotos and 2 tests failed
  (`test_text_file_preview`, `test_text_preview_is_html_escaped`): the
  `.files-code` `<pre>` renders visible-but-EMPTY and the content only
  arrives after mount (async highlight.js chunk; no deterministic
  loaded-selector, and those tests use raw `assertIn` which doesn't poll).
  Initially patched by keeping `networkidle` on exactly those two gotos;
  later superseded by the `:has-text()` content polls (§6), which are both
  faster and deterministic. Lesson: `load`-event readiness holds only when
  content is SSR'd/embedded at load — otherwise wait on the content itself.
- **Hasher detection via argv sniffing (both iterations)**: `"test" in
  sys.argv` false-fired on any literal `test` token; the hardened
  subcommand-slot check fixed that but still put test-only logic + detection
  heuristics in production settings. Both were ultimately replaced by the
  class-scoped `BaseTestCase` override — no detection at all, guarded by the
  conventions meta-test.
- **`global`-statement browser singleton**: first implementation used module
  globals + `global` rebinding; ruff (PLW0603) rejected it. Rewritten as the
  `_SharedBrowser` holder (mutated, never rebound) — no `global` needed.
- **Refcounted browser teardown**: second iteration counted classes and
  closed playwright/firefox when the last class finished — unnecessary
  bookkeeping with its own failure mode (a `setUpClass` failure between
  acquire and context creation skips `tearDownClass`, leaking the count).
  The test process is one-shot and playwright's driver dies with it (stdin
  EOF), so the holder is now lazy-start + never-closed; verified no orphaned
  `ms-playwright` processes after a full run.
- **Shared live server across classes**: measured directly — each
  `_start_server_thread` costs 2ms; the 1.1s attributed to "per-class server"
  was actually the first class paying the one-time playwright/firefox stack.
  Nothing to amortize; not adopted.
- **`context.route` serving `/static/**` from disk**: made navigations
  SLOWER (264ms vs 215ms — the driver round trip exceeds Django's
  page-cached static serving). Rejected on measurement.
- **`wait_until="domcontentloaded"`**: only ~5ms/nav — main.js is a module
  script that executes before DCL, so `load` ≈ DCL here. Not worth the churn.
- **Per-test `about:blank` kill**: +0.8s suite-wide (26 extra navigations).
  The dead-server fetch risk only exists across CLASS boundaries (within a
  class the server is alive); split into a per-class `tearDownClass`
  navigation + the 1ms per-test event pump.

## Process notes

- Phase instrumentation paid for itself twice: it caught that the four
  `test_client_errors` networkidle gotos (kept on speculation that error-POST
  timing needed quiescence) cost ~3.1s and were convertible — the POSTs are
  awaited by `expect_request`, so `load` suffices. Measure before assuming a
  wait is load-bearing.

- A shell `for` loop used to verify the argv matrix printed PBKDF2 for every
  shape — a quoting/`$argv` (zsh positional-params) artifact, not real
  behavior. Re-verified by setting `sys.argv` in-process and by wall-clock
  through the real `./run test` path (6.8s ⇒ MD5) before trusting it.
- Verification gap to avoid: checking settings in a fresh `python -c` process
  proves nothing about a `coverage run` child — the child's argv is what
  matters; assert in-process.

## Deep profiles (cProfile + phase instrumentation)

### Unit suite — `python -m cProfile manage.py test --exclude-tag playwright`

6.89s under the profiler. Where it goes:

| Block                     | Time  | Notes                                                                                                                                                                |
|---------------------------|-------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `test_git.py` setUp       | 2.91s | 25 tests × real git fixtures: 100 `git commit` subprocesses (1.5s in GitPython `_call_process`, 0.5s `poll`, 0.46s `file_contents_ro`) — inherent to no-mock git e2e |
| psycopg2 `cursor.execute` | 1.20s | 3,491 queries across the suite (~6ms/test amortised)                                                                                                                 |
| runner + test-DB creation | ~1.2s | discovery, migrations, teardown                                                                                                                                      |
| everything else           | ~1.6s | 195 test bodies                                                                                                                                                      |

Conclusion at the time: hashing was the only algorithmic waste. One more
algorithmic waste was hiding in this same table, though — the 2.91s of
per-test git-fixture builds was *not* inherent, just per-test by habit; §5
(class-scoping) reclaimed ~2.5s of it. The current floor really is runner +
DB (~1.2s) + psycopg2 (~0.3s of genuine queries) + real test bodies.

### Playwright suite — per-phase wall instrumentation

Monkeypatched timers around setUp/setUpClass/tearDown/`_fixture_teardown`
plus every `Page.goto` (`/tmp/kilo/prof_pw.py` pattern), tagged suite:

| Phase                       | Round 1                                     | Round 2                      | Round 3            | Round 4                         | Round 5                     | Round 6 (final)                                                                                                                                               |
|-----------------------------|---------------------------------------------|------------------------------|--------------------|---------------------------------|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `page.goto`                 | 9.91s (avg 152ms; 6 networkidle 0.67–0.81s) | 7.79s (2 networkidle remain) | ~7.8s              | 6.19s / 48 navs (0 networkidle) | 5.80s / 26 navs (avg 223ms) | 5.62s / 26 navs (avg 216ms)                                                                                                                                   |
| setUp (user+page+login)     | 7.42s (309ms/test)                          | 7.11s (296ms/test)           | 3.93s (164ms/test) | 3.20s (133ms/test)              | 3.23s (135ms/test)          | **0.39s (16ms/test)**                                                                                                                                         |
| fixture_teardown (DB flush) | 1.61s (67ms/test)                           | 1.89s (79ms/test)            | 1.65s (69ms/test)  | 1.66s (69ms/test)               | 1.54s (64ms/test)           | ~1.5s (64ms/test; narrowed variant reverted §9)                                                                                                               |
| setUpClass (server+context) | 1.29s                                       | 0.83s                        | 0.88s              | 0.85s                           | 1.18s                       | ~1.1s — mostly the FIRST class paying the one-time browser stack (playwright+firefox ≈ 0.9s standalone); the per-class live-server thread itself measured 2ms |
| tearDown/teardownClass      | 0.13s                                       | 0.13s                        | 0.12s              | 0.11s                           | 0.11s                       | 0.11s                                                                                                                                                         |

Reading it: navigation is now purely the tests' own real page loads (~216ms
avg — live server + Inertia boot; login navs are gone, §7); setUp's 16ms/test
is two INSERTs + cookie injection (§8); the narrowed flush is ~20ms/test (§9).
Nothing left worth trading isolation for.

## Remaining floor

- Playwright ~0.53s/test: real page loads (~216ms avg — Firefox parsing the
  ~435KB main.js per document; cutting it means frontend code-splitting, not
  harness work), the ~20ms narrowed flush, and fixed runner/DB costs. The
  live-server-per-class theory was disproven by measurement (2ms/thread).
- Unit suite ~1.5s: runner + test-DB creation (~1.2s, fixed cost) and ~0.3s
  of genuine queries. Only parallel workers could shrink the fixed cost —
  and the DB-clone overhead exceeds the win at this size.
