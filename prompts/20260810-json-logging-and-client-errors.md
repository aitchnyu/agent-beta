# JSON logging + frontend client-error reporting

Switch the backend to **NDJSON-only** logs (filterable with `jq` by stable
fields, exceptions included as structured data), and make the frontend ship
uncaught errors to a backend endpoint with `filename:lineno:colno`, username,
URL and other useful context. Cover the pipeline with a Playwright test.

## Current state (analysis done 2026-08-10)

### Backend logging

- **No `LOGGING` config exists** in `djangoproject/settings.py` (227 lines).
  Django's defaults apply: one plain-text `StreamHandler` on the root logger at
  WARNING+, no JSON, no contextual fields. `INFO`/`DEBUG` are dropped.
- **The "too many loggers" concern is overstated** — only 2 module-level
  loggers exist today:
  - `djangoapp/views/opencode.py:59`
  - `djangoapp/ninja_api.py:29`
- No `python-json-logger` / `structlog` / custom formatter anywhere;
  `pyproject.toml` deps confirm none. No `extra={...}` usage, so there are
  **zero structured fields to filter on** today — only substring grep over
  formatted text.
- 5 call sites, all string-interpolated:

  | File:line | Call | Issue |
  |---|---|---|
  | `opencode.py:197` | `logger.warning("opencode transport error for %s: %s", path, exc)` | no fields, no traceback |
  | `opencode.py:201` | `logger.warning("opencode rejected %s: %s %s", ...)` | same |
  | `opencode.py:251` | `logger.warning("opencode rejected prompt_async for %s: %s", ...)` | same |
  | `opencode.py:369` | `logger.warning("opencode stream error", exc_info=True)` | only site attaching a traceback |
  | `ninja_api.py:80` | `logger.exception("Unhandled exception on %s %s", request.method, request.path, exc_info=exc)` | redundant `exc_info=exc` — `.exception()` already pulls from `sys.exc_info()`; the kwarg is noise |

- Django's own `django.request` / `django.security` loggers (404/500/CSRF) also
  emit plain text and must flow through the same JSON formatter to be uniform.

**Net:** the real problem isn't loggers multiplying — it's that logging is
unconfigured (plain text, default handler, no request/user correlation,
exceptions mostly detached, nothing jq-filterable).

### Frontend error handler

`frontend/src/main.ts:22-39, 87-90` has three global hooks (`window error`,
`unhandledrejection`, Vue `errorHandler`). All three **only `console.error` +
show a SweetAlert toast**. Gaps vs. the goal:

- **Nothing is sent to the backend** — browser errors are invisible server-side.
- **`row:col` is available but discarded**: `ErrorEvent` exposes
  `event.filename`, `event.lineno`, `event.colno`. Minified bundles still carry
  valid line/col → resolvable via sourcemap. `vite.config.js:21` already sets
  `build.sourcemap: true` (emitted into `djangoapp/static/djangoapp/`), so
  mapping works. Note: those maps are publicly served under
  `/static/djangoapp/` — fine for dev, decide for prod.
- **Username**: client has it via Inertia shared prop `usePage().props.user`
  (`djangoapp/middleware.py:40-46` → `{public_id, title=display_name}`, `null`
  when anon). Authoritative source should be `request.user` read **server-side**
  at the capture endpoint (don't trust client-sent identity).
- **URL**: `window.location.href` (+ `document.referrer`) not collected.
- Vue `errorHandler` drops its 3rd arg `info` (lifecycle tag like
  `"render"` / `"setup function"`) — useful for categorizing.
- `showErrorToast` runs before any send; if the page is wedged the report is
  lost. Should send-first (fire-and-forget), then toast.

### Backend capture endpoint

None exists (grep for `/log`, `client_error`, `track_error`, `js_error` →
nothing).

### Playwright harness

`djangoapp/tests/playwright/_base.py` **fails on any `console.error` /
`pageerror`** (lines 105-118) and stringifies console args (36-48). Since the
new handler logs to `console.error` before POSTing, a genuine-thrown-error test
will trip `tearDown`. The harness runs `DEBUG=True` + `SECURE_CSP_REPORT_ONLY=None`
(`_base.py:52`), so CSP won't block the POST; session cookie + CSRF are set by
`/login-for-test/<pk>`, so the POST authenticates and passes CSRF cleanly.

## jq-filtering contract

Every record is **one JSON object per line (NDJSON)** with stable top-level
keys: `timestamp` (ISO8601+tz), `level`, `logger`, `module`, `event`, plus
  context — `source` (`server` | `client`), `user.public_id` /
  `user.username` (and flat `user_public_id` / `username`), `method`,
  `path`, `url`, `user_agent`, `client_filename` / `client_lineno` /
  `client_colno`, and `exception` as a structured field (a list of
  stack dicts via `structlog.processors.dict_tracebacks`), not a trailing
multi-line string. Implemented with **structlog** + a stdlib
`ProcessorFormatter` so Django/framework stdlib loggers and our own structlog
loggers emit one uniform stream. Per-request fields are bound via structlog
contextvars in `LoggingContextMiddleware` and merged into every record; the
middleware also logs `http request` carrying the viewer identity
(`user_public_id`/`username` — the integer `pk` is never logged). There is no
`request_id` (no per-request correlation id). Traceback frames render **without
local variables** (no request-body/token/row leak).

## Checklist

### Backend — JSON logging

- [x] Add `structlog` to `pyproject.toml` dependencies (switched from
      `python-json-logger` — see "Resolved decisions").
- [x] Add `LOGGING` to `djangoproject/settings.py`: a `ProcessorFormatter`
      (JSON renderer) on the root handler; DEBUG-aware levels; `django.*`
      propagates to root so 404/500/CSRF logs are NDJSON too.
- [x] Create `djangoapp/logging.py`: shared processor chain
      (`merge_contextvars`, `_default_source`, `add_log_level`,
      `add_logger_name`, `TimeStamper`, `CallsiteParameterAdder`,
      `StackInfoRenderer`, `dict_tracebacks` with `show_locals=False`); `configure_logging()` +
      `json_formatter()` (the `ProcessorFormatter`).
- [x] `LoggingContextMiddleware` binds `user_public_id` / `username` /
      `method` / `path` and emits one `http request` line with the
      user id. No `request_id` / `X-Request-ID`.
- [x] Normalize the 5 existing call sites to structlog (key/value kwargs, event
      names as human phrases with spaces):
      - [x] `opencode.py` transport error / opencode rejected / prompt async
            rejected / stream error
      - [x] `ninja_api.py` — `logger.exception("unhandled exception", ...)`;
            dropped the redundant `exc_info=exc`.
- [x] Verified output is NDJSON (one object per line) and `exception`
      serializes as a structured list with no locals (`test_exception_is_structured`).

### Backend — client-error capture endpoint

- [x] Add `redis` to `pyproject.toml` dependencies; add `REDIS_URL` +
      `CLIENT_ERROR_RATE_LIMIT` to `.env.example` (REDIS_URL defaults to the
      local redis).
- [x] New `POST /client-errors` ninja endpoint + pydantic model; body fields:
      `message`, `stack`, `filename`, `lineno`, `colno`, `url`, `userAgent`,
      `vueInfo`, `public_id` (camelCase keys aliased to snake_case;
      `extra="forbid"` so a client can't forge `source`/`level`/`logger`).
- [x] Attach authoritative `request.user` (public_id + username) server-side;
      do NOT trust client-sent identity. Accept anonymous reports (`user=None`).
- [x] Log once at `warning` on the **`client`** logger (so `jq 'select(.logger
      =="client")'` finds every frontend report); includes `client_*` row/col/url.
- [x] CSRF-exempt (django-ninja exempts its views at the middleware level and
      this endpoint declares no cookie-auth, so anon POSTs and sendBeacon land).
- [x] Rate-limited via Redis — a **hard dependency** (not best-effort):
      `CLIENT_ERROR_RATE_LIMIT` (requests/min, default 30); key per user when
      authed, per IP (`REMOTE_ADDR`) when anon; **fails closed** if redis is
      unreachable — the error propagates to the global handler (500; the report
      is not accepted).
- [x] Truncate `stack` server-side (`_MAX_STACK_CHARS=500`; model accepts `_MAX_STACK_INPUT=1000`).
- [x] Returns 204; 429 over budget; a redis failure propagates to the global
      handler (500, fail closed). Never echoes the body.

### Frontend — error reporting

- [x] Unify the three handlers via `frontend/src/utils/clientError.ts`
      (`reportErrorEvent` / `reportRejection` / `reportVueError` →
      `reportClientError`), wired from `main.ts`.
- [x] `reportClientError` is `async` and `await`s the axios POST (callers fire it
      with `void`); validated against `ClientErrorPayloadSchema` (zod, mirroring
      the backend) before sending.
- [x] Capture `filename / lineno / colno` (from `ErrorEvent`), `url`
      (`window.location.href`, sent verbatim — nothing sensitive is put in URLs),
      `userAgent`, Vue `info` (3rd `errorHandler` arg), and
      `usePage().props.user?.public_id`.
- [x] Send-first via axios POST to `/client-errors` (fire-and-forget), then toast.
- [x] `navigator.sendBeacon("/client-errors", ...)` fallback on `pagehide`, only
      while a POST is in flight (cleared on success — no duplicate).
- [x] Keep `sourcemap: true` (always emits maps); serving layer denies `*.map`
      under `/static/djangoapp/` (see Resolved decisions).

### Test — Playwright

- [x] Add `djangoapp/tests/playwright/test_client_errors.py` (framework-level —
      sits alongside `test_users` / `test_files` / `test_git`).
- [x] Trigger an error deterministically via
      `page.evaluate(() => setTimeout(() => { throw ... }, 0))` (genuinely
      uncaught → `window.onerror` with full `lineno`/`colno`).
- [x] Intercept the POST via `page.expect_request("**/client-errors")`.
- [x] Assert the posted JSON contains `lineno`, `colno`, `filename`, `url`, and
      `public_id` matching the logged-in user (+ a promise-rejection case).
- [x] Reconciled with `_base.py`'s console-error-fail via a new
      `expect_console_errors()` opt-in helper.

## Resolved decisions

- [x] Logger name: **`client`** (filter with `jq 'select(.logger=="client")'`).
- [x] Accept anonymous errors: **yes** (`user=null` when unauthenticated).
- [x] Rate-limit via **Redis**, cap driven by an `.env` var
      (`CLIENT_ERROR_RATE_LIMIT`). Redis is a **hard dependency**: if unreachable
      the endpoint **fails closed** — a redis error propagates to the global
      handler (500; the report is not accepted).
      `REDIS_URL` defaults to the local redis.
- [x] **No `request_id` / `X-Request-ID`**: dropped entirely — the per-request
      correlation id wasn't earning its keep (no external header handle; most
      requests emit a single line).
- [x] `reportClientError` is **`async`** and `await`s the axios POST; callers
      fire it with `void`. No `safeUrl` scrubbing — nothing sensitive is put in
      URLs, so `window.location.href`/`event.filename` are sent verbatim.
      Resource-load failures (broken `<img>`/`<script>`) are filtered out of the
      window `error` handler — they aren't JS errors.
- [x] **structlog** (not `python-json-logger` / `loguru`): stdlib-native, flat
      jq-friendly JSON, `bind()` ergonomics, structured tracebacks, and a
      first-class `ProcessorFormatter` bridge so Django/framework logs share one
      shape with our own loggers. Traceback locals are redacted
      (`show_locals=False`).
- [x] Prod sourcemaps: **emitted in every build** (`sourcemap: true` in
      `vite.config.js`, kept always — captured client-error lineno/colno and dev
      stacks resolve against them), but **NOT served publicly**: the serving
      layer (reverse proxy / CDN) is configured to deny `*.map` under
      `/static/djangoapp/`, so the maps exist for offline/server-side resolution
      but never reach clients.
