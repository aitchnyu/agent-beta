# opencode daemon + web chat POC

Run opencode headless as a long-running server and prompt it from the Django
app. The browser renders the **whole turn** — reasoning, tool calls and their
results, and interactive permission/command confirmations — streamed from a
single Django endpoint. A second endpoint carries the user's permission
decision back to opencode.

## Daemon

Start with the new `./run opencode` command, which runs
`opencode serve --hostname 127.0.0.1 --port 4196`. Port **4196**, not
opencode's default 4096 (collides with the Kilo extension's `kilo serve` in
this session); override via `OPENCODE_PORT` / `OPENCODE_HOSTNAME`.

Currently unsecured (`OPENCODE_SERVER_PASSWORD` unset) — fine for localhost; for
production set the password and have Django send Basic auth (user `opencode`).

## Verified opencode 1.18.0 API (REST; OpenAPI 3.1 at `/doc` — returns JSON with `Accept: application/json`)

Core endpoints:

| Purpose | Call | Result |
|---|---|---|
| Create session | `POST /session` body `{title?}` | `Session{id}` |
| Fire prompt (async) | `POST /session/:id/prompt_async` body `{model?, parts:[{type:"text",text}]}` | `204` |
| Event stream | `GET /event` | SSE; `server.connected`, then bus events |
| Respond to permission | `POST /session/{sessionID}/permissions/{permissionID}` body `{"response":"once"\|"always"\|"reject"}` | `boolean` |

Working model for the POC: **`zai-coding-plan/glm-5.2`** — verified doing tool
calls cleanly and fast (pending→running→completed, status busy→idle, no
retries). (`glm-5v-turbo` retried/errored on tool turns; `opencode/big-pickle`
also worked.) Other providers configured: openrouter, zai, opencode.

### Event shapes (verified) — each SSE `data:` line is `{id, type, properties}`

**Streaming deltas (incremental — append `delta` to `field` of `partID`):**
- `message.part.delta` → `{sessionID, messageID, partID, field, delta}`. `field` is `text` for both assistant text and reasoning text; route by `partID` (see the matching `message.part.updated` part).

**Parts (full state) — `message.part.updated` → `properties.part`:**
- `text` → `{text}`
- `reasoning` → `{text, time:{start}}`
- `step-start` → `{snapshot}` (start of an agentic step)
- `step-finish` → end of an agentic step
- `tool` → `{tool:<name>, callID, state:{status, input, output, metadata, time, raw}}`
  - `status`: `pending` → `running` → `completed` | `error`
  - `input` e.g. `{command:"…"}` (bash) or `{filePath, limit}` (read)
  - on `completed`: `output` (string) + `metadata` (`preview`, `truncated`, `display{type,path,text,lineStart,lineEnd,totalLines}`, `title`) + `time.end`

**Lifecycle / control:**
- `session.status` → `properties.status.type`: `busy` (and `retry` on transient model errors), then `idle` = turn complete (**close the stream**)
- `permission.asked` → `{id (per_…), sessionID, permission (bash|edit|webfetch|…), patterns, metadata (e.g. {command}), always (suggested always-allow patterns), tool:{messageID, callID}}`
- `permission.replied` → `{sessionID, requestID, reply}` (reply = `once`|`always`|`reject`) — use to dismiss the confirm card

Noise to filter out: `server.connected`, `session.updated`, `message.updated`,
`session.diff`, `plugin.added`, `catalog.updated`, `reference.updated`,
`integration.updated`, `server.heartbeat`. `/event` is global — filter every
event by `properties.sessionID`.

## Architecture

```
                          ┌─ POST /api/opencode/permission/<sid>/<permid>/  (Allow once / Always / Reject)
                          │     Django → POST /session/{sid}/permissions/{permid} {"response"}
Vue ──POST {message,sid}──┴─▶ Django (streaming)
   ▲                          create-or-reuse session → open /event (filter by sid)
   │                          fire /session/:id/prompt_async
   └── SSE (one long-lived conn per turn):
        message.part.delta            ─▶ append text/reasoning (per partID)
        message.part.updated {tool}   ─▶ render tool card (name + input + output + state)
        permission.asked              ─▶ render confirm card (until permission.replied)
        session.status idle           ─▶ close
```

The streaming connection stays open across the permission round-trip: the user
answers via the separate permission endpoint, opencode proceeds, and the rest of
the turn keeps streaming on the same open connection.

## Plan

### Backend (`djangoapp`) — two endpoints

1. `POST /api/opencode/prompt/` → `StreamingHttpResponse(text/event-stream)`:
   - parse + validate `{message, session_id?}`; if absent, `POST /session` and
     emit an SSE `session` event with the new id
   - open SSE to opencode `/event`, filter by `sessionID`
   - fire `/session/:id/prompt_async {model, parts:[{type:text,text}]}`
   - re-emit: `message.part.delta`, `message.part.updated` (text/reasoning/step-start/tool), `permission.asked`, `permission.replied`, `session.status`
   - close on `session.status` idle/complete; on opencode 5xx/stream drop emit an SSE `error` and close cleanly
2. `POST /api/opencode/permission/<session_id>/<permission_id>/`:
   - body `{response: once|always|reject}` → proxy verbatim to opencode `POST /session/{sid}/permissions/{permid}` (no extra fields — schema is `additionalProperties:false`)

Transport: async views (ASGI) + `httpx.AsyncClient`. Sync `runserver` blocks the
stream — verify the project's ASGI entry. Add `httpx` if missing.

POC scope: no user/auth binding, in-memory session map, model hard-coded to
`zai-coding-plan/glm-5.2`, `session_id` carried client-side for multi-turn.

### Frontend (`frontend`)

- Transcript rendering one card per turn:
    - reasoning + assistant text via `message.part.delta` appends (routed by `partID` to the right part)
    - tool card: tool name + input + state + output (from `tool` parts)
    - permission card on `permission.asked`: show permission type + command (metadata) + suggested always-pattern; buttons **Allow once / Allow always / Reject**; disable + clear on `permission.replied`
- Prompt send: raw `fetch('POST /api/opencode/prompt/', {body})` + `response.body.getReader()` + `TextDecoder`, parse SSE frames, stop on `session.status` idle. This call uses `fetch` (axios can't stream bodies); wrap errors → `showErrorToast(e, fallback)`. All other calls stay axios-with-zod.
- Permission decision: axios `POST /api/opencode/permission/<sid>/<permid>/` (try/catch + zod), `{response}`
- Persist `session_id` for multi-turn; close reader on completion/unmount
- Styles in `main.css` (no inline/scoped)

## Checklist

### Daemon + `./run` command
- [x] Add `opencode()` to `./run` → `command opencode serve --hostname "$OPENCODE_HOSTNAME" (127.0.0.1) --port "$OPENCODE_PORT" (4196)`
- [ ] Daemon lifecycle: foreground `./run opencode` for POC; later wrap in launchd/systemd
- [ ] Auth policy: set `OPENCODE_SERVER_PASSWORD`, Django sends Basic auth (production only)

### Backend
- [x] Streaming transport: kept it sync (`httpx` sync stream + `StreamingHttpResponse`); `runserver` is threaded by default so the long-lived stream and the permission POST don't deadlock — no ASGI needed (verified e2e)
- [x] Add `httpx` dependency
- [x] Create-or-reuse session helper (POST `/session`, reuse `session_id` from the client)
- [x] Streaming view: open `/event`, fire `prompt_async`, filter by `sessionID`, re-emit `message.part.delta` + `message.part.updated` + `permission.asked` + `permission.replied` + `session.status`, close on status idle
- [x] Permission proxy view `POST /api/opencode/permission/<sid>/<permid>/` → opencode `POST /session/{sid}/permissions/{permid} {response}`
- [x] Server-side validation of `{message, session_id?}` and `{response}` (pydantic, 422 on bad input)
- [x] Error path: opencode HTTP error / stream-drop → SSE `error` event, close cleanly
- [x] Superuser gate (404) on the page + both endpoints — the daemon runs shell in the project
- [x] Tests (`djangoapp/tests/views/test_opencode.py`: gating, validation, mocked stream + permission proxy)

### Frontend
- [x] Transcript + input + Send
- [x] `fetch` + ReadableStream SSE parser; route `message.part.delta` by `partID`
- [x] Render text + reasoning deltas
- [x] Render tool cards (name, input, state, output)
- [x] Render permission confirm card on `permission.asked` (Allow once / Allow always / Reject) → axios POST to permission proxy; dismiss on `permission.replied`
- [x] Persist `session_id` for multi-turn; stop reader on completion/unmount
- [x] Manual error toast on fetch failure (reuse `showErrorToast`)
- [x] Styles in `main.scss`

### Lint and verify
- [x] Backend: `./run lintfix`, `./run typecheck`, `./run test`
- [x] Frontend: `cd frontend && npm run lint:fix`, `npm run type-check`, `npm run lint`
- [x] `./run checkall`
- [x] E2E smoke test: browser → Django streaming → opencode daemon streamed 12 part-updates + 18 deltas, closed on idle (verified, then cleaned up)

## Confirmed during probing
- Completion marker: `session.status` → `idle` closes the stream (no separate "completed" variant).
- `tool` completed part: `state.output` (string) + `state.metadata` (`preview`, `truncated`, `display{type,path,text,lineStart,lineEnd,totalLines}`, `title`) + `state.time.end`.
- Delta routing: each `message.part.delta` carries a `partID` matching its `message.part.updated` part; append `delta` to that part's `field` (reasoning and assistant text both use `field:"text"`, so route by `partID`).
- `read` is auto-approved (no `permission.asked`); `bash`/`edit`/etc. require it.

## Review follow-ups (20260719)

Surfaces from a self-review of commit `5990eed` ("Chat"). Backend lives in
`djangoapp/views/opencode.py`; frontend in `frontend/src/pages/opencode/`.

### Backend robustness
- [x] **`prompt_async` failure swallowed**: the POST that fires the prompt is
      sent inside `_event_stream` with its response status unchecked. A non-2xx
      (bad model, stale session, opencode config drift) leaves `/event` open,
      waiting for an `idle` that never arrives → the browser spinner hangs.
      Check `resp.is_success`; on failure emit an SSE `error` and return.
- [x] **Stream end without `idle` is silent**: if opencode's `/event` closes
      without `session.status idle` (daemon crash, network drop), the generator
      returns without telling the client. Track a `saw_idle` flag; emit a
      trailing `error` if the for-loop exits naturally without it.
- [x] **Committed log artifact**: `.playwright-mcp/console-2026-07-17…log`
      was committed in the same commit that gitignored `.playwright-mcp/`.
      `git rm --cached` it (the ignore only stops new files).

### Tests
- [x] **Streaming core uncovered**: `_iter_sse`, `_is_relevant`, `_is_idle`,
      `_event_stream` had no direct unit tests — `test_streams_for_superuser`
      stubs `_event_stream` entirely. Add parser + filter + end-of-stream
      tests given the many documented gotchas.

### Frontend
- [x] **Drop raw `fetch` for axios**: the streaming call in
      `useOpencodeChat.ts` was the only source-code `fetch(` (Sweetalert in
      `main.js` is vendored). axios ≥1.7 supports browser streaming via the
      fetch adapter (`responseType: "stream"`, `adapter: "fetch"`); this also
      lets us drop the manual `X-CSRFTOKEN` header (set globally via
      `axios.defaults` in `main.ts`).
- [x] **Stale docstring** at `test_opencode.py` (`OpencodeQuestionTests`):
      referenced `/api/opencode/question/<sid>/<rid>/`, but the route is
      `/question/<rid>/` (questions are top-level in opencode 1.18.0).
- [x] **Placeholder copy** in `OpencodeChat.vue`: "We should introduce the
      agent to you." → replace with a real one-line intro.

## Review follow-ups (20260719, pass 2 — full audit)

From a three-way review of commit `698bc6a` ("foo"): backend-only,
frontend-only, and frontend↔backend integration. Integration-only findings
are flagged **[integ]**; the rest are per-side.

**Implemented in the same day's follow-up commit.** Verification:
`./run test djangoapp.tests.views.test_opencode` (36 tests),
`./run typecheck`, `./run lintfix`, and `cd frontend && npm run type-check &&
npm run lint && npm run build` all green.

### Backend robustness (`djangoapp/views/opencode.py`)

- [x] **`_create_session()` failure → 500** (opencode.py:103): daemon-down
      raises `httpx.HTTPError` *before* the `StreamingHttpResponse` is built,
      bypassing the in-stream `error` design and surfacing as a generic 500.
      Move session creation into `_event_stream` so the failure becomes an
      SSE `error` event, or `try/except httpx.HTTPError` and return 502.
- [x] **`_iter_sse` drops the final frame** **[integ]** (opencode.py:235-249):
      flush only triggers on a blank line; if opencode's last write (often the
      `session.status idle` marker) lacks a trailing blank line the event is
      lost → spurious "stream ended without idle" error. Append a final flush
      after the `for` loop. No current test exercises this.
- [x] **Raw path interpolation** (opencode.py:125,143,156,168,193): `session_id`
      /`permission_id`/`request_id` are spliced into f-strings unencoded. A
      value containing `/` rewrites the upstream URL. Use
      `urllib.parse.quote(sid, safe="")`.
- [x] **`{ok: bool}` conflates success and failure** (opencode.py:129,147,159,
      171): return `status=502` (or mirror upstream status) when
      `not is_success`. No test covers the `is_success=False` path.
- [x] **`Http404` for wrong-method superuser requests** (opencode.py:94,117,
      135,153,165): after the auth gate, return `HttpResponseNotAllowed` (405)
      so a superuser debugging gets a useful code; non-superusers still hit the
      auth gate first and see 404.
- [x] **`json.loads(exc.json())` round-trip** (opencode.py:99,122,140): use
      `exc.errors()` directly — clearer and cheaper.
- [x] **`line[5:].lstrip(" ")` over-strips** (opencode.py:241): SSE strips
      exactly one leading U+0020. Use `line[5:]` then strip one space
      conditionally. The frontend parser already does this correctly
      (useOpencodeChat.ts:102) — the two ends have drifted.
- [x] **`_MODEL` hardcoded** (opencode.py:43): pull the default from env for
      per-deployment override.
- [x] **`error` not in `_RELEVANT_TYPES`** **[integ]** (opencode.py:46-57):
      works today only because Django generates its own `error` events
      downstream of the filter; if opencode ever emits `type:"error"` (tool
      failures, rate limits) it's silently dropped. Add `error` to the set, or
      rename Django's synthetic events to `proxy.error` to avoid collision.

### Tests (`djangoapp/tests/views/test_opencode.py`)

- [x] **Hardcoded daemon URL** (test_opencode.py:196,227,278,295): asserts hit
      `http://127.0.0.1:4196`, but `_OPENCODE_BASE` is env-driven. Assert
      against `opencode._OPENCODE_BASE + "..."` so `OPENCODE_PORT`/`OPENCODE_
      BASE_URL` don't silently break four tests.
- [x] **Missing `assertComponentUsed`** (test_opencode.py:97-101): sibling page
      tests (`test_applications_views.py:55`, `test_home.py:22`) all pin the
      rendered component — add `self.assertComponentUsed(response,
      "OpencodeChat")`.
- [x] **Inconsistent mock targets** (test_opencode.py:188,223,270,291 vs :424):
      half patch global `httpx.post`, half patch `djangoapp.views.opencode.
      httpx.post`. Standardize on the targeted form so unrelated `httpx.post`
      callers aren't affected.
- [x] **`InertiaTestCase` for non-Inertia tests** (test_opencode.py:152,202,
      232): proxy tests only check status + outgoing httpx call; `TestCase`
      would suffice and skip the Inertia/DB overhead.
- [x] **Uncovered: `_create_session` failure, `_iter_sse` trailing-frame edge
      case, `id` ↔ `requestID` round-trip.** Add unit tests for each — the last
      verifies the load-bearing C1 assumption below.

### Frontend (`frontend/src/pages/opencode/`)

- [x] **No `onUnmounted` cleanup** (useOpencodeChat.ts:27-327): navigating
      away mid-turn (especially with a pending permission) leaves the fetch
      pulling and the closure alive. `RichTextEditor.vue:86-91` cleans up;
      this doesn't. Register `onUnmounted(() => controller.value?.abort())`
      and gate `handleEvent` on an `isAlive` flag.
- [x] **`consume()` never releases the reader** **[integ]** (useOpencodeChat.ts:
      86-112): no `try/finally`; on throw (abort, network drop) the reader
      keeps its lock and the fetch isn't torn down. Wrap in
      `try {…} finally { await reader.cancel().catch(()=>{}) }`.
- [x] **`OpencodeEventSchema` is a black box** (schemas.ts:253-256): validates
      only the envelope, forcing every field read into an unchecked `as` cast
      (useOpencodeChat.ts:124,127,133,…). Mirror opencode's per-type shapes as
      a discriminated zod union; a malformed event should log loudly, not
      mutate state with `undefined`. Every other schema in `schemas.ts` already
      does this.
- [x] **Late `message.part.updated` doesn't fix a mis-typed block**
      (useOpencodeChat.ts:165-181,190-194): `appendDelta` creates blocks as
      `text` by default; `upsertPart` later overwrites `text` but not `kind`
      → early reasoning deltas render as `opencode-text` HTML. Set
      `existing.kind = type` when it differs.
- [x] **`v-for :key="i"` with stateful children** (OpencodeChat.vue:38;
      QuestionCard.vue:16-17 initializes local state from props at setup):
      any future reorder/splice reuses a `QuestionCard` for a different block
      and leaks local selections. Use stable keys (`partID`/`id`/
      `crypto.randomUUID()` for user blocks).
- [x] **`stop()` does double-duty** **[integ]** (useOpencodeChat.ts:76-84):
      `controller.abort()` (closes the Django stream → backend `finally:
      client.close()`) *and* `postAbort` — redundant and races stream
      teardown. Pick one (prefer the server-side `/abort/`).
- [x] **Schema vs action state writes are uncoordinated** **[integ]**
      (useOpencodeChat.ts:239-258 vs 262-304): both flip the same block's
      `state`. Works today but fragile; pick one source of truth (prefer
      waiting for the SSE confirmation so daemon agreement is guaranteed).
- [x] **`TextDecoder` never flushed** **[integ]** (useOpencodeChat.ts:88-111):
      uses `{stream:true}` but no final `decoder.decode()`. A multi-byte UTF-8
      sequence split on the last chunk boundary is dropped — and corrupts the
      containing JSON frame, silently dropping the last event of a turn.
- [x] **`session_id` not persisted across refresh** **[integ]**
      (useOpencodeChat.ts:29): refresh mid-turn loses the id, the next prompt
      creates a new session, and opencode's old session runs unattended
      (tokens, file locks, possibly blocking on a permission forever).
      Persist to `localStorage` on the `session` event.
- [x] **`partKind` grows unbounded** (useOpencodeChat.ts:34): never pruned
      across turns; prune with the transcript or clear on new session.
- [x] **Permission "answered" view renders the raw enum** (PermissionCard.vue:
      50-52): "Answered: once" / "Answered: reject" — map to human labels as
      `QuestionCard.vue:77` does.
- [x] **`submit()` emits an all-empty answer array if nothing selected**
      (QuestionCard.vue:32-42): no guard. Disable Send until ≥ one question
      has a non-empty selection, or short-circuit with a toast.
- [x] **Auto-scroll only on new blocks, not deltas** (useOpencodeChat.ts:36-43):
      as text streams the page doesn't follow. Throttled scroll-on-delta when
      the user is already near the bottom.
- [x] **SCSS inlined into `main.scss`** (main.scss:52-180): convention is
      `styles/<page>.scss` pulled in via `@use` (cf. `styles/users.scss`).
      Move to `styles/_opencode.scss` and `@use` it.
- [x] **Hardcoded hex colors** (main.scss:66,71,80,84,…): bypass the design
      tokens (`$gray-*`, `$blue-500`, `$amber-500`, `$radius-md`,
      `$border-light`) defined in `styles/_variables.scss` and used elsewhere.
- [x] **`pushPermission`/`pushQuestion` dedup drops updates silently**
      (useOpencodeChat.ts:223-237): if opencode re-emits `permission.asked`
      with the same `id` (re-prompt after a tool retry) the new metadata is
      discarded. Either update the fields or change the dedup key.
- [x] **`parsePermissionBlock` null-metadata hazard** (types.ts:68):
      `(p.metadata as Record<string, unknown>) ?? {}` — if opencode emits
      `"metadata": null` the cast produces a null-deref at runtime. Guard with
      `Record<…> | null`.

### Integration (frontend ↔ backend seam)

- [x] **`permission.asked.id` ↔ `permission.replied.requestID` unverified
      [integ]**: `markReplied`/`markQuestionAnswered`/`markQuestionRejected`
      look up blocks stored under `id` using `requestID`. If opencode uses a
      separate request-tracking id, every SSE-driven state flip no-ops. Action
      POST path masks this for the single-admin case; multi-tab and any
      "another admin answered" UI are dead. Add a wire-shape test.
- [x] **Two different casings of "session id" in the contract** **[integ]**:
      the Django-synthesized `session` event uses `properties.session_id`
      (opencode.py:182); opencode's own events use `properties.sessionID`
      (opencode.py:255). A future contributor will "fix" one. Comment both
      sites naming these as opencode's wire names.
- [x] **Two drifted SSE parsers** **[integ]**: `_iter_sse` (opencode.py:235)
      and the `consume` loop (useOpencodeChat.ts:94-108) independently
      implement the same protocol and disagree on trailing-frame handling and
      leading-space stripping. Extract one shared parser (or import a tiny SSE
      lib on each side) so the contract is enforced by construction.
- [x] **Card state goes stale across abort** **[integ]**: if the user clicks
      Stop while a permission is `asked`, no `permission.replied` ever arrives
      and the card stays interactive; clicking it POSTs to a stale
      `permission_id` and produces a spurious toast. Freeze `asked` cards when
      `streaming` flips to false without resolution.

### Config / scripts (`./run`, `.env.example`, `agentconfig/`)

- [x] **Missing `opencode` binary misreported as invalid config** (run:69-76):
      `command not found` from `opencode debug config` triggers the
      "config invalid" branch. Preflight with `command -v opencode` first.
- [x] **Premature success banner** (run:77): "opencode serve on host:port"
      prints before `opencode serve` binds; on a port collision the user sees
      the announcement followed by the bind error. Swap the order or trap
      serve failure.
- [x] **Stale comment** (run:60): "Remove it so only `$config_file` is used" —
      the script *refuses*, doesn't remove. Reword.
- [x] **`opencode()` skips `setenv`** (run:47-80): every sibling subcommand
      calls `setenv`; add a comment explaining why this one doesn't (or call
      it for parity).
- [x] **Global-config guard misses `OPENCODE_CONFIG_CONTENT`** (run:62):
      `prompts/20260719-opencode-manual-testing.md` calls this out as a merge
      source; the guard doesn't check it. Error when non-empty.
- [x] **`OPENCODE_BASE_URL` undocumented** (.env.example:11-14): Django honors
      it (opencode.py:41) as a full override, but only `OPENCODE_HOSTNAME`/
      `OPENCODE_PORT` are listed. Add a commented example line.
- [x] **Stale `.gitignore` comment** (.gitignore:32): "ignore nothing else
      here" now sits below a freshly added `.playwright-mcp/` entry.
- [x] **`AGENTS.md` → `INSTRUCTIONS.md` rename leaves stale refs**
      (prompts/20260626-foundation-scaffold.md:15,17;
      20260628-google-oauth-command.md:88;
      20260629-models-and-management.md:99-100,307,431;
      20260717-endpoint-e-dispatch-four-verbs.md:206): historical prompts
      still link to `AGENTS.md` → 404. Optional: add a one-line rename note at
      the top of `INSTRUCTIONS.md`, or leave as historical record.

## Review follow-ups (20260720, pass 3 — six-facet subagent review)

From a six-facet parallel subagent review of commit `6493d308` ("Opencode
frontend crap…"): backend-security, backend-tests, FE-logic, FE-UI/a11y,
build/config, cross-cutting. Findings de-duplicated across facets; items
found independently by two or more facets are flagged **[corroborated]**.
Where a pass-2 `[x]` turned out not to have fully landed, the item is
reinstated with a note. Overall: contract-coherent for the single-admin dev
scope — mergeable now, address the corroborated Majors + a11y before exposing
broadly. The commit-message-quality finding is intentionally omitted.

### Integration (frontend ↔ backend seam)

- [ ] **`permission.asked.id` ↔ `permission.replied.requestID` still unverified
      [corroborated]** (useOpencodeChat.ts:354-433; schemas.ts:286-312):
      `markReplied`/`markQuestionAnswered`/`markQuestionRejected` look up blocks
      stored under `id` using `requestID`; if the two ids ever diverge every
      SSE-driven card flip silently no-ops and the user's answer appears lost.
      The pass-2 item (line 329) was marked `[x]`, but this review found
      `test_opencode.py` still stubs `_event_stream` entirely — no wire-shape
      round-trip test exists. Confirm against opencode's event docs and add a
      test that drives `_event_stream` with a real `permission.asked` then
      `permission.replied` pair (and the question equivalents); or key cards by
      both `id` and `requestID`.
- [ ] **`if(!res.ok)` / `OpencodeActionResponseSchema` is dead code
      [corroborated]** (api.ts:22,36,43,50; schemas.ts:323-325): `_forward`
      returns HTTP 502 on failure (opencode.py:189-194), so axios throws before
      `.parse()` runs and the schema only ever sees `{ok:true}`. Either drop the
      check or define a 200-with-`ok:false` path that doesn't exist yet.
- [ ] **Two SSE parsers still drift; frontend mishandles `\r\n\r\n`
      [corroborated]** (useOpencodeChat.ts:169-208; opencode.py:276-311): the
      pass-2 "extract one shared parser" item (line 340) was marked `[x]`, but
      only "keep in sync" comments were added — no extraction. Separately, the
      TS parser frames on `\n\n` only; if any intermediary (dev proxy, nginx)
      normalizes to CRLF the spinner hangs forever. Normalize
      `buffer.replace(/\r\n/g, "\n")` before framing, or share one parser.

### Frontend (`frontend/src/pages/opencode/`)

- [ ] **Re-emit leaves permission/question cards frozen [corroborated]**
      (useOpencodeChat.ts:324-352): `pushPermission`/`pushQuestion` refresh an
      existing block's metadata but never reset `state` back to `"asked"`, so a
      re-emitted `permission.asked` (tool retry) or `question.asked` (new round)
      stays `"answered"`/`"rejected"` and later `*.replied` events are dropped
      by the `state === "asked"` gate. The pass-2 dedup item (line 318) was
      marked `[x]` for the metadata-drop case but didn't fix the state reset.
      On refresh, flip `state` back to `"asked"` and clear `answer`/`pending`.
- [ ] **`appendDelta`/`upsertPart` race blanks text or duplicates a `partID`**
      (useOpencodeChat.ts:259-322): `upsertPart` does
      `existing.text = text` unconditionally — an empty/missing `part.text`
      (the schema doesn't require it) clobbers delta-built text; and
      `appendDelta` falls through when `existing.kind === "tool"` and pushes a
      second text block with the same `partID` → `v-for` key collision. Only
      overwrite `text` when non-empty; early-return `appendDelta` for tool
      blocks.
- [ ] **Three event branches are still untyped despite the "fail loudly" claim**
      (schemas.ts:254-257,275-299): `permission.asked`/`question.asked`/
      `message.part.updated` use `z.record(z.string(), z.unknown())` and every
      field is then `as`-cast — a numeric `id` passes `safeParse` then lies to
      TS, and a `part.updated` without `id` makes every such event collide on
      the empty-string key. The pass-2 "OpencodeEventSchema is a black box"
      item (line 268) was marked `[x]` but these three branches were left
      loose. Tighten to real `z.object({...})` per type and drop the casts.
- [ ] **QuestionCard local state desyncs on re-ask [corroborated]**
      (QuestionCard.vue:16-17; useOpencodeChat.ts:341-352): `selected`/
      `customText` are sized once from `props.block.questions` at setup, so a
      re-ask that changes the question count leaves stale/undefined entries and
      misroutes answers. `watch(() => props.block.questions, …)` and rebuild,
      or key per-question state by id rather than index.
- [ ] **a11y: contrast, live region, focus, labels (only Blocker tag)**
      (_opencode.scss:27; OpencodeChat.vue:39,74; PermissionCard.vue:21;
      QuestionCard.vue:56,79): `.opencode-reasoning` color `#9ca3af` on white is
      ~2.85:1 (below WCAG AA 4.5:1); the transcript has no `aria-live`/
      `role="log"` so streamed text is invisible to SRs; prompt cards have no
      `role="alertdialog"`/focus management and focus falls to `<body>` on
      resolve; the message and custom-answer inputs have no labels (placeholder
      is not a label). For the single-admin dev tool this is P0 follow-up, not
      merge-blocking; it becomes a Blocker the moment anyone else uses it.
- [ ] **`/e/home` is not a guaranteed route** (Manage.vue:49): endpoints are
      dispatched by function name; apps without a `home` endpoint 404 when
      "Open {app_name}" is clicked. Link to bare `/e`, or guard on a known
      endpoint list. Also switch the link from `<a>` to Inertia `<Link>`
      (Manage.vue:47) to avoid a full reload.
- [ ] **O(n) lookups per delta → O(n²) over long turns**
      (useOpencodeChat.ts:251-277): every `message.part.delta` `Array.find`s
      the transcript; maintain a `Map<partID, PartBlock>` and
      `Map<id, PermissionBlock|QuestionBlock>` index.
- [ ] **`clear()` mid-stream leaves `streaming === true`** (useOpencodeChat.ts:
      142-156): `controller.abort()` is fire-and-forget; set `streaming.value =
      false` inside `clear()` so the Stop button/input-disabled state updates
      immediately instead of waiting for the fetch to reject.
- [ ] **Stale `session_id` survives a daemon restart** (useOpencodeChat.ts:51,
      217-218): the persisted id is never invalidated; after a daemon restart
      the next prompt errors until the user hits Clear. Drop the stored id on
      an unrecoverable error or when a `session` event carries a different id.

### Backend robustness (`djangoapp/views/opencode.py`)

- [ ] **Upstream error bodies / exception strings echoed to the browser**
      (opencode.py:189,192,214,248,271): `_forward` returns
      `{"detail": opencode_resp.text}` and the stream interpolates `str(exc)`,
      leaking filesystem paths/config keys/partial request echo. Cap length
      (`[:500]`) and route detail to `logger.warning` while returning a generic
      message.
- [ ] **No client-disconnect detection in the stream loop** (opencode.py:254-
      260): when the browser closes the tab, the generator only aborts on its
      next `yield`; until then the view keeps consuming opencode's `/event` and
      the daemon keeps the turn running (including a pending permission). Check
      `request.is_closed()` (Django 4.1+) inside the loop and forward an
      `/abort/` on early exit.
- [ ] **`_event_stream` only catches `httpx.HTTPError`** (opencode.py:270):
      `_iter_sse`/`iter_lines()` can raise non-httpx exceptions
      (`UnicodeDecodeError`, bare `BaseException`) → 500 with a stack trace.
      Broaden to `except Exception` for the streaming path, emit a synthetic
      `error` SSE, and return.
- [ ] **No wall-clock cap on the stream** (opencode.py:227): `timeout=None` is
      intentional for permission waits, but a runaway turn (no idle ever
      emitted) pins a worker thread + a daemon `/event` connection forever. Add
      a hard cap (e.g. 10 min) that emits a synthetic `error` and returns.
- [ ] **`error` events without a matching `sessionID` are dropped**
      (opencode.py:314-317): `_is_relevant` requires
      `properties.sessionID == session_id` for every type including `error`, so
      a session-scoped error missing that field (auth/rate-limit) leaves the
      browser on a hung spinner. Pass `error` events through when they carry no
      `sessionID`.

### Tests (`djangoapp/tests/views/test_opencode.py`)

- [ ] **Happy-path session creation untested** (test_opencode.py:543):
      `test_create_session_failure_emits_error` passes `session_id=None` and
      stubs `_create_session` to raise, but no test passes `None` and lets it
      return a real id — the most common flow (new id propagating into the
      synthetic `session` frame and `_is_relevant`'s filter) is unexercised.
- [ ] **`prompt_async` request shape never asserted** (test_opencode.py:520):
      the `httpx.post` mock only checks its return value; nothing pins the URL
      (`/session/<sid>/prompt_async`), body (`{model, parts:[{type:"text",
      text}]}`), or `timeout`. A regression that drops `parts` passes tests.
- [ ] **`_forward` transport-exceptions → 502 uncovered** (opencode.py:188):
      every 502 test uses `is_success=False`; the `except httpx.HTTPError` path
      (conn refused/DNS/timeout) has zero coverage across permission, abort,
      question_reply, question_reject.
- [ ] **Non-superuser API authz untested** (test_opencode.py:156,226,258):
      only `/agent/` has a `test_non_superuser_404`; the four API test classes
      have no `plain` user, so weakening `_require_superuser` to `is_staff`/
      `is_authenticated` is caught by the page test but not the API tests.
- [ ] **`_q` URL-encoding untested**: every proxy test uses safe ids
      (`ses_x`/`per_x`); `quote(value, safe="")` is the path-injection guard
      but no test sends `ses/a%2Fb` to confirm it. Add one per path param.
- [ ] **Streaming headers and `client.close()` unasserted** (test_opencode.py:
      141, 520): neither `Cache-Control: no-cache` / `X-Accel-Buffering: no`
      (load-bearing for SSE through nginx/dev-server buffering) nor the
      `finally: client.close()` cleanup (prevents pool exhaustion) is checked.
      Add `response["Cache-Control"]` and `client.close.assert_called_once()`.
- [ ] **405 + copy-paste cleanup** (test_opencode.py:156-327): no test sends a
      non-POST to a POST-only API endpoint as a superuser; and the four proxy
      test classes duplicate setUp/anon-404/mock-assert — a shared mixin or
      `subTest` would cut ~80 lines and make the gaps above one-liners each.

### Config / scripts (`./run`, `.env.example`, `agentconfig/`)

- [ ] **Broad permissions for a proxied chat agent** (agentconfig/opencode.json:
      6-9,24-25): `read`/`glob`/`grep`/`list` are allow-all (the agent can read
      `.env`, `db.sqlite3`, anything reachable by relative traversal) and
      `webfetch`/`websearch` are allow (no per-call approval) — a real exfil
      surface through the Django proxy. Document the threat model in `steer.md`
      and consider scoping `read`/`list` to `apps/`, `docs/`, `INSTRUCTIONS.md`.
- [ ] **No port pre-check or startup-order coordination** (run:84-87, 39-47):
      a half-started daemon can leave a process lingering on bind failure, and
      starting `runserver` before `opencode` means `/api/opencode/*` 502s until
      the daemon is up. Optional `lsof -iTCP:"$port" -sTCP:LISTEN` preflight,
      and a note (or a `run dev` wrapper) that `opencode` must start first.

## Design changes (20260720)

Two decisions from post-implementation discussion. Not review-driven; recorded
here because they reshape the wrapper.

### Drop structured questions; clarify via ordinary chat

The model should ask clarifications as **prose and stop** (idle), the user
replies as the next `prompt_async` in the **same session**, and the model
iterates until satisfied — i.e. normal multi-turn chat, which session reuse
already supports. The structured `question` mechanism goes away.

**Why:** removes a whole subsystem, lets the stream cap become a clean runaway
guard (turns end on idle, no long pending-question pauses pinning a worker),
and matches how ChatGPT-style UXes handle clarification.

**Critical distinction — permissions stay.** A permission grant (allow-once /
always for a specific tool call) is a *security primitive*: the daemon needs a
machine-readable authorization tied to that call, and the security model depends
on an explicit grant — not free-text "yeah sure" the agent could misread as
consent to `rm -rf`. Only `question.*` collapses into chat; `permission.*` is
unchanged.

**What gets removed** (once the agent is proven not to use questions):
- `frontend/src/components/opencode/QuestionCard.vue`
- the question proxy endpoints + tests: `question_reply`, `question_reject`
  (`djangoapp/views/opencode.py`, `djangoapp/urls.py`,
  `djangoapp/tests/views/test_opencode.py`)
- the `question.asked` / `question.replied` / `question.rejected` branches in
  `frontend/src/schemas.ts`
- `pushQuestion` / `markQuestionAnswered` / `markQuestionRejected` /
  `findQuestion` / `questionIndex` in `useOpencodeChat.ts`
- the question half of the `requestID ↔ id` correlation concern (item 1)
- the QuestionCard re-ask / local-state / a11y bugs (items 7, 8-partial) — moot

**What's traded:** structured option buttons / multi-select / "Other" box and
in-turn tool-result semantics (the answer arrives as a fresh turn with a fresh
generation, not mid-reasoning). Acceptable for clarifications; only "pick
exactly one of N constrained options" degrades, and the model re-asks on
ambiguity (the iterate loop).

**Steps** (in order):
- [ ] **(1) Instruct** — add a `steer.md` line: never use the question tool;
      ask clarifications in prose and stop. Zero code; question infra goes
      dormant. Validate the UX on a real turn first.
- [ ] **(2) Deny the tool** — confirm the question tool's name in opencode's
      permission taxonomy, then set it `deny` in `agentconfig/opencode.json` so
      the agent *can't* ask structurally (enforced, not just instructed).
- [ ] **(3) Prune** — remove the infra listed above (endpoints, card, schema
      branches, composable handlers, tests) once (1)+(2) hold.
- [ ] **(4) Backstop a stray `question.asked`** — the agent may still call the
      tool by mistake (instruction ignored, or `question` turns out not to be a
      deny-able permission in opencode's taxonomy). After pruning the FE card,
      a stray `question.asked` would be silently dropped by `OpencodeEventSchema`
      (no matching branch) — but the agent is suspended on the tool call waiting
      for a result, so the turn **hangs** until idle/timeout/disconnect. Close
      that in `_run_turn` (`djangoapp/views/opencode.py`): on a relevant
      `question.asked`, do NOT forward it to the client — instead POST
      `/question/<id>/reject` to the daemon (the tool call returns a rejection,
      the agent unblocks and can retry in prose) **and** emit a synthetic
      `error` SSE so the user sees "question tool disabled; ask in chat."
      Recoverable + observable, not a Python exception (that would 500 the
      stream). Keep this even after (3) — it's defense-in-depth against a
      misconfigured deny or an opencode version that re-enables the tool.

### Lower `_STREAM_MAX_SECS` to 300s, with reset on human touchpoints

- [ ] **Reduce the constant** (`djangoapp/views/opencode.py`): `_STREAM_MAX_SECS`
      600 → 300. A noisy runaway (agent emitting forever without idle) is now
      capped at 5 min instead of 10.
- [ ] **Reset the clock on human touchpoints** — currently `start` is fixed at
      turn-start and never reset, so a bare 300s wall-clock cap would *kill the
      turn right after a >5-min permission answer*: the check lives inside the
      event loop, which is parked on `iter_lines()` during a pending permission
      (no events → check never runs mid-wait), but the clock keeps accruing and
      trips on the **first event after the user replies**. Lowering to 300 makes
      this false-positive *more* likely, so the reset is effectively required at
      this value, not optional. Restart `start` when `permission.asked`,
      `permission.replied`, or any `question.*` event flows, so the cap measures
      *agent-compute time between human interactions* rather than wall-clock-
      since-start. (Pairs naturally with dropping questions: once questions are
      gone, only `permission.*` touchpoints need to reset it.)
- [ ] **Update tests** — the existing stream tests pass `request=None` and run
      fast, so they don't exercise the cap; add a test that a `permission.asked`
      mid-stream resets the deadline (assert a turn that would otherwise exceed
      300s survives because the timer restarted at the permission).
- [ ] **Document the cap's real coverage** in a comment: it only fires on
      *incoming events*, so it catches a **noisy** runaway (continuous output,
      no idle) but **cannot** catch a **silent** hang (daemon emits nothing, no
      idle) — that would need an event-independent watchdog (separate timer
      thread / async task), out of scope for a single-admin dev tool. The Stop
      button + `request.is_closed()` (under uvicorn/ASGI) cover the rest.

## aihere markers (20260720)

A sweep of `# aihere` markers in the opencode feature (per the convention in
`INSTRUCTIONS.md`): each is an instruction left in the code. Resolutions below
— addressed markers were removed; deferred ones are kept with a plan.

- [x] **opencode.py — `_OPENCODE_HOST`/`_OPENCODE_PORT`** ("check if we can get
      away without these"): **investigated, kept.** They sync Django's
      `_OPENCODE_BASE` to the daemon's bind host/port (set by `./run opencode`
      via the same env vars) without requiring a separate `OPENCODE_BASE_URL`.
      Dropping them would break the custom-port case unless `OPENCODE_BASE_URL`
      is also set. Replaced the marker with a comment explaining the sync.
- [x] **opencode.py — `_PROVIDER`/`_MODEL_ID`** ("move these to .env"): **already
      done.** Env-driven (`OPENCODE_PROVIDER`/`OPENCODE_MODEL`) with fallback
      defaults and documented in `.env.example`. Marker removed.
- [x] **opencode.py:134 — "potential ninja endpoints, manual parsing"**:
      **done.** `prompt`/`permission`/`abort` are now ninja ops on `opencode_api`
      (mounted at `api/opencode/`): pydantic body params auto-validate (422),
      wrong method auto-405s, and the manual `model_validate_json` / method-check
      / `ValidationError` boilerplate is gone. `prompt` keeps streaming via
      `response=None`. **Behaviour change:** ninja validates the body and
      dispatches the method *before* the op runs, so an anonymous GET is now 405
      (was 404) and an anonymous POST with an *invalid* body is 422 (was 404) —
      an anonymous POST with a valid body still 404s via `_require_superuser`.
      Marker removed.
- [x] **opencode.py:158 — `_q`** ("inline / avoid quoting if url-safe"):
      **no-op.** `quote(value, safe="")` already passes URL-safe strings through
      unchanged, so "avoid quoting if safe" gains nothing; `_q` stays as a named
      function (6 call sites + a docstring on the path-injection guard beats
      inlining). Marker removed.
- [x] **opencode.py:195 — `_abort_turn`** ("dont we have another function using
      /abort"): **intentional.** Yes — the `abort` view (user Stop) and
      `_abort_turn` (client-disconnect) both POST `/session/{sid}/abort`, but
      with different wrapping (`JsonResponse` vs best-effort `suppress`); kept
      separate deliberately. Marker removed.
- [x] **opencode.py:412 — `_sse`** ("input should be a union of pydantic
      models"): **done.** Defined `_SseError` / `_SseSession` (with `_SseErrorProps` /
      `_SseSessionProps`) and `_SseEvent = _SseError | _SseSession`; `_sse` now takes
      `_SseEvent | dict[str, Any]` and `model_dump()`s models while passing forwarded
      daemon dicts through unchanged. The six synthetic call sites
      (`_fire_prompt`, `_resolve_session`, `_relay_events` ×2, `_event_stream` ×2)
      now build typed models, so a typo like `{"type": "eror"}` is caught at the
      model level instead of silently serialising. Marker removed.
- [x] **urls.py:19 — "add these to an openapi"**: **done (with the ninja
      conversion above).** `opencode_api` serves the schema at
      `/api/opencode/openapi.json` and docs at `/api/opencode/docs`; a test pins
      that all three endpoints appear in the schema. Marker removed.
- [x] **useOpencodeChat.ts:115 — "consume would yield messages, route from
      here"**: **stale design note.** Routing IS done from `consume` via
      `handleEvent`, exactly as the note intended. Marker removed.
- [x] **api.ts:13 — "move these functions out of this file"**: **intentional
      separation.** `api.ts` is deliberately the pure-HTTP layer (no Vue/toast/
      state); the composable owns state. Merging would worsen coupling. Marker
      removed.

Non-opencode markers (not added here — wrong file; left in place):
`run:47` (format the check section with numbered comments) and
`djangoapp/tests/appfixtures/README.md:35` (keep updated).
