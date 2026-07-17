# opencode integration — manual testing notes

Empirical findings from manual browser testing of the opencode web-chat
integration (`djangoapp/views/opencode.py` + `frontend/src/pages/OpencodeChat.vue`
+ `agentconfig/`). Use this as the verified contract and a test playbook — it
records what the opencode 1.18.0 daemon actually does (several things differ from
the online docs / OpenAPI spec).

## Setup

- Daemon: `./run opencode` (default port **4196**; use `OPENCODE_PORT=4197` for a
  throwaway alongside a real one). 4096 is taken by the Kilo extension server.
- Config: `agentconfig/opencode.json` (loaded via `OPENCODE_CONFIG` +
  `OPENCODE_CONFIG_DIR`), `agentconfig/steer.md` (instructions). `./run opencode`
  **refuses to start** if any other opencode config exists (global
  `~/.config/opencode/opencode.json{,c}`, `config.json`, project `./opencode.json`,
  or `$OPENCODE_CONFIG_CONTENT`) — opencode merges all sources, so this is enforced
  to keep `agentconfig/` authoritative.
- Validate config without serving:
  `OPENCODE_CONFIG=$PWD/agentconfig/opencode.json OPENCODE_CONFIG_DIR=$PWD/agentconfig opencode debug config`
  (exit 0 = valid, 1 = invalid). `./run opencode` runs this as a fail-fast pre-flight.
- Model: `zai-coding-plan/glm-5.2`. (`glm-5v-turbo` errored/retried on tool-calling
  turns; `opencode/big-pickle` also works.)
- Inspect the spec: `GET /doc` with `Accept: application/json` returns the OpenAPI
  JSON (the HTML at `/doc` is the Swagger UI).

## Verified API contract

All of these are registered in `/doc` (real, return JSON). **Any path not in
`/doc` is the web-UI SPA catch-all → `200` HTML (false positive).** Always cross-
check a path against `/doc` before trusting a 200.

| Purpose | Call | Result |
|---|---|---|
| Health | `GET /global/health` | `{healthy, version}` |
| Create session | `POST /session` `{title?}` | `{id}` |
| Fire prompt (async) | `POST /session/{sid}/prompt_async` `{model, parts:[{type:"text",text}]}` | `204` |
| Event stream | `GET /event` | SSE; first `server.connected`, then bus events |
| Permission reply | `POST /session/{sid}/permissions/{permid}` `{response:"once"\|"always"\|"reject"}` | `bool` |
| Abort turn | `POST /session/{sid}/abort` | `bool` |
| Question reply | `POST /question/{requestID}/reply` `{answers:[[...labels]]}` | `"true"` |
| Question reject | `POST /question/{requestID}/reject` | `bool` |

⚠️ **Question endpoints are TOP-LEVEL (`/question/{requestID}/…`), not session-
scoped.** `/session/{sid}/question/{rid}/reply` is the SPA catch-all (200 HTML,
no effect) — this caused a "stuck at waiting" bug. `/api/session/{sid}/question/
{rid}/reply` exists but returns `404 QuestionNotFoundError` (questions are global).

## Event shapes (`GET /event`)

Each SSE frame is `data: {id, type, properties}`. `/event` is **global** — filter
every event by `properties.sessionID`.

Drive the UI:
- `message.part.delta` → `{sessionID, messageID, partID, field, delta}` —
  **incremental** append to `field` of `partID` (both text and reasoning use
  `field:"text"`; route by `partID`).
- `message.part.updated` → `properties.part`:
  - `text` → `{text}`
  - `reasoning` → `{text, time:{start}}`
  - `step-start` / `step-finish` → agentic step markers
  - `tool` → `{tool, callID, state:{status: pending→running→completed|error,
    input, output, metadata}}` (`metadata`: `preview`, `truncated`,
    `display{type,path,text,lineStart,lineEnd,totalLines}`, `title`)
- `session.status` → `properties.status.type`: `busy`, `retry` (transient model
  error), then **`idle` = turn done → close the stream**.
- `permission.asked` → `{id (per_…), sessionID, permission, patterns (the parsed
  sub-commands), metadata.command, always[], tool{messageID,callID}}`.
- `permission.replied` → `{requestID, reply}`.
- `question.asked` → `{id (que_…), sessionID, questions:[{question, header,
  options:[{label,description}], multiple?, custom?}], tool}`.
- `question.replied` / `question.rejected`.

Noise (filter out): `server.connected`, `session.updated`, `message.updated`,
`session.diff`, `plugin.added`, `catalog.updated`, `reference.updated`,
`integration.updated`, `server.heartbeat`.

## Manual test scenarios

### Daemon-only (opencode API directly)
Best for isolating opencode behavior from Django. In a browser at the daemon
origin (`http://127.0.0.1:4197/`), run in devtools/console:
1. `POST /session` `{title}` → keep `id`.
2. `fetch('/event')` and start a `ReadableStream` reader (parse `data:` frames).
3. `POST /session/{sid}/prompt_async` `{model, parts:[{type:"text",text:"…"}]}`.
4. Read events until `session.status` `idle`.

### Streaming prompt renders
Prompt "List three cat breeds." → expect `message.part.delta` text deltas
(incremental), `message.part.updated` `text`, then `idle`. Stream closes on idle.

### Permission flow (write/bash)
Prompt "Use bash to run exactly: echo hi > /tmp/x" → `permission.asked` with
`permission:"bash"`, `metadata.command`, `patterns:["echo hi > /tmp/x"]`,
`always:["echo *"]`. Reply `POST /session/{sid}/permissions/{permid}
{response:"once"}` → `permission.replied`, tool runs (`tool` part `completed`),
then `idle`. (read-only commands like `git status` are auto-allowed — see below.)

### Question flow
Prompt "Use the question tool to ask a single-choice question with options Red,
Green, Blue." → `question.asked` `{id:"que_…", questions:[{options:[…]}]}`.
Reply `POST /question/{id}/reply {answers:[["Red"]]}` → `"true"`,
`question.replied`, `idle`.
Modes to cover: single-choice, `multiple` (multi-select), free-text
(`options:[]`), and several questions in one `asked`.

### Django end-to-end (real stack)
1. `./run opencode` (4196) and `./run runserver` (8000).
2. Create a superuser; log in via `/login-for-test/<pk>` (DEBUG only).
3. At `/agent/`: the page `fetch`es `POST /api/opencode/prompt/` (SSE,
   `text/event-stream`) and reads it with `getReader()`; permission/question
   decisions go to `/api/opencode/permission/<permid>/` and
   `/api/opencode/question/<rid>/{reply,reject}/` via axios (CSRF via
   `getCsrfToken` on the streaming fetch).
4. Confirm: answering a question → `question.replied` → `idle` → spinner clears.

## Critical gotchas (each cost real debugging time)

- **Question reply path is `/question/{rid}/reply` (top-level).** Session-scoped
  `/session/{sid}/question/{rid}/reply` is the SPA (200 HTML, no effect) → the
  turn hangs forever ("stuck at waiting for server").
- **SPA false-positive 200:** any opencode path not in `/doc` returns `200` HTML.
  Distrust 200s; verify the path is in `/doc` and the response is JSON.
- **opencode merges every config source** (global → custom → project → managed).
  A global `~/.config/opencode/opencode.json` with `"git *":"allow"` overrides the
  project's `"*":"ask"`. `./run opencode` refuses to start if another config
  exists; or set `XDG_CONFIG_HOME` to an empty dir (auth lives in the **data**
  dir `~/.local/share/opencode/auth.json`, so it's safe).
- **bash `*: ask` does not mean "ask for everything".** opencode built-in auto-
  approves read-only commands (`git status`, `ls`, `cat`, …); pipelines are
  decided by their **first** sub-command (`pwd | cat` runs if `pwd` is allowed).
- **Free-text questions have `options: []` and NO `custom` flag** (glm-5.2 doesn't
  set `custom`). Show the text box when `options` is empty or `custom` is set.
  Don't always show it (the model then adds placeholder options like "I'll type
  below").
- **`subagent_depth` is not a valid key in 1.18.0** (docs are ahead) — it
  invalidates the whole config (400 on every request). Use `"task":"deny"`.
- **`opencode serve` does not validate config at startup** — it starts fine and
  only 400s per request. Hence the `opencode debug config` pre-flight in `./run`.
- **Django `runserver` is threaded by default** (`--nothreading` disables it), so
  the long-lived SSE stream and the short permission/question POST run on separate
  threads (no deadlock — the stream waits on the answer).
- **Stale test DB:** `./run test` without `--keepdb` prompts to delete the test DB
  → `EOFError` non-interactively. Use `--noinput` to recreate, or `--keepdb`.

## Model quirks (glm-5.2)

- Sometimes frames open-ended questions as a 1-option choice ("Prefer not to
  say" / "I'll type below") instead of free-text. `agentconfig/steer.md` now
  instructs: open-ended → no options; multiple-choice → options.
- Replies in HTML when steered (`steer.md`); otherwise markdown.
- Tool calls work reliably (read runs auto; bash/edit/external prompt).
