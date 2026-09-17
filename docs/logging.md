# Error logs: query (mlr) and decode (sourcemaps)

How to pull error logs out of the journal with
[miller](https://miller.readthedocs.io) (`mlr`) and decode minified frontend
stacks back to source. Every command streams — `journalctl` to stdout, `grep`
cut, mlr JSON out — no intermediate files. All outputs below are real, from
deliberate, param-gated bugs (backend raise, failing huey task, browser
throw) run on the test VM. A frozen sample corpus from that exercise lives in
`docs/errors/` (see its README).

## The log stream

Every process (granian web, huey consumer) writes **one JSON object per line**
to stderr; systemd puts it in the journal. Huey output is NDJSON-only because
`djangoproject/settings.py` owns the `huey` logger — `run_huey` attaches its
plain-text handler only when that logger has none. Non-JSON lines **can**
appear in `journalctl -o cat` output — systemd's own unit-status markers
("Stopping…/Started…"), and, on setups predating the `huey` logger fix,
huey's plain-text duplicates — which is exactly what the `grep '^{'` cut in
every query below drops.

Common fields: `timestamp`, `level`, `logger`, `source` (`server`/`client`),
`event`, `method`, `path`, `user_public_id`, `username`. Plus:

- backend errors: `exception` — a list of traces, each with `exc_type`,
  `exc_value`, and `frames` (outermost → innermost; the raise site is the
  LAST frame).
- frontend errors (`source == "client"`, logged by the `/client-errors`
  handler): `client_message`, `client_stack` (minified frames), and for
  window errors also `client_filename`/`client_lineno`/`client_colno`
  (rejections carry no location).

The shape, across levels below error (real lines, copied from
[docs/errors/granian.ndjson](errors/granian.ndjson)):

```json
{"method": "GET", "path": "/", "user_public_id": null, "username": null, "event": "http request", "source": "server", "level": "info", "logger": "djangoapp.request", "timestamp": "2026-09-16T11:47:09.072016Z", "module": "middleware", "filename": "middleware.py", "lineno": 98}
{"viewer": "errors", "event": "home viewed", "path": "/", "method": "GET", "username": "errors", "user_public_id": "01a0a9eb-d40e-7542-9bb2-44fb9d764a5a", "source": "server", "level": "info", "logger": "ourapp.views.home", "timestamp": "2026-09-16T11:47:09.545033Z", "module": "home", "filename": "home.py", "lineno": 41}
{"timestamp": "2026-09-16T11:47:31.785058Z", "username": "errors", "client_message": "deliberate frontend boom for log collection", "client_stack": "setup/</<@https://localhost/static/djangoapp/main-CjayHrlg.js:67:21008 …", "client_filename": "https://localhost/static/djangoapp/main-CjayHrlg.js", "client_lineno": 67, "client_colno": 21008, "url": "https://localhost/?jsboom=1", "user_agent": "Mozilla/5.0 … Firefox/150.0", "vue_info": "", "user": {"public_id": "01a0a9eb-d40e-7542-9bb2-44fb9d764a5a", "username": "errors"}, "event": "client error", "level": "warning", "logger": "client", …}
```

Errors add the structured `exception` (frames outermost → innermost, locals
redacted):

```json
{"event": "Internal Server Error: /", "user_public_id": "01a0a9eb-…", "level": "error", "logger": "django.request", "exception": [{"exc_type": "RuntimeError", "exc_value": "deliberate backend boom for log collection", "frames": [{"filename": "/srv/app/main/ourapp/views/home.py", "lineno": 44, "name": "home_page"}, …]}], …}
```

## Example queries

Run inside the VM (`multipass exec app -- sudo bash -c '…'`). `--since` and
`--until` accept absolute local time (`'2026-09-16 17:17:04'`), ISO 8601 with
timezone (`2026-09-16T17:17:04+05:30`), or relative spans (`-1h`, `-15min`);
omit `--until` for an open window. Combine units by passing both `-u` flags
to one `journalctl`. Three DSL facts that matter: field names need their `$`
sigil in expressions, boolean operators are `||`/`&&` (not `or`/`and`), and
arrays are 1-up — so `$exception[1]` is the first trace and
`["frames"][-1]` is the raise site.

### Backend errors

```bash
journalctl -u app_granian.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$level=="error"' then cut -o -f timestamp,username,event
```

```json
{"timestamp": "2026-09-16T11:47:09.413977Z", "username": null, "event": "Internal Server Error: /"}
{"timestamp": "2026-09-16T11:47:09.545425Z", "username": "errors", "event": "Internal Server Error: /"}
```

### Huey errors

```bash
journalctl -u app_huey.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$level=="error" || $level=="warning"' then cut -o -f timestamp,level,event
```

```json
{"timestamp": "2026-09-16T11:47:09.710950Z", "level": "warning", "event": "huey boom task starting"}
{"timestamp": "2026-09-16T11:47:09.711473Z", "level": "error", "event": "Unhandled exception in task c18d1245-f076-40cd-879e-36e878039d08."}
```

### Frontend errors

Recorded by the backend `/client-errors` handler, so they live in the
granian journal too:

```bash
journalctl -u app_granian.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$source=="client"' then cut -o -f timestamp,username,client_message,client_filename,client_lineno,client_colno
```

```json
{"timestamp": "2026-09-16T11:47:31.785058Z", "username": "errors", "client_message": "deliberate frontend boom for log collection", "client_filename": "https://localhost/static/djangoapp/main-CjayHrlg.js", "client_lineno": 67, "client_colno": 21008}
{"timestamp": "2026-09-16T11:47:33.456695Z", "username": "errors", "client_message": "deliberate frontend boom for log collection", "client_filename": "https://localhost/static/djangoapp/main-CjayHrlg.js", "client_lineno": 67, "client_colno": 21008}
{"timestamp": "2026-09-16T11:47:33.581019Z", "username": "errors", "client_message": "deliberate frontend rejection for log collection", "client_filename": "", "client_lineno": null, "client_colno": null}
```

## Example aggregation queries

### Backend errors grouped by raise site

Deepest frame of the traceback, both units merged:

```bash
journalctl -u app_granian.service -u app_huey.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter 'is_present($exception)' \
    then put '$raise_site = $exception[1]["exc_type"] . " " . $exception[1]["frames"][-1]["filename"] . ":" . string($exception[1]["frames"][-1]["lineno"])' \
    then count-distinct -f raise_site
```

```json
{"raise_site": "RuntimeError /srv/app/main/ourapp/views/home.py:44", "count": 2}
{"raise_site": "RuntimeError /srv/app/main/ourapp/tasks.py:18", "count": 1}
```

### Frontend errors grouped by crash site

```bash
journalctl -u app_granian.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$source=="client" && !is_null($client_lineno)' \
    then put '$site = sub($client_filename, "^.*/", "") . ":" . string($client_lineno)' \
    then count-distinct -f site
```

```json
{"site": "main-CjayHrlg.js:67", "count": 2}
```

### Frontend errors grouped by message

Rejections carry no line/col, so message is their grouping axis:

```bash
journalctl -u app_granian.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$source=="client"' then count-distinct -f client_message
```

```json
{"client_message": "deliberate frontend boom for log collection", "count": 2}
{"client_message": "deliberate frontend rejection for log collection", "count": 1}
```

### All errors grouped by user

Backend + frontend together (client records are `level=warning`, so the
filter takes both):

```bash
journalctl -u app_granian.service -u app_huey.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$level=="error" || $source=="client"' \
    then put '$who = (is_null($username) || is_absent($username)) ? "anonymous" : $username' \
    then count-distinct -f who
```

```json
{"who": "anonymous", "count": 2}
{"who": "errors", "count": 4}
```

### Every error for one user

Swap the username in the second filter:

```bash
journalctl -u app_granian.service -u app_huey.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$level=="error" || $source=="client"' \
    then filter '!(is_null($username) || is_absent($username)) && $username=="errors"' \
    then cut -o -f timestamp,source,level,event,client_message
```

```json
{"timestamp": "2026-09-16T11:47:09.545425Z", "source": "server", "level": "error", "event": "Internal Server Error: /"}
{"timestamp": "2026-09-16T11:47:31.785058Z", "source": "client", "level": "warning", "event": "client error", "client_message": "deliberate frontend boom for log collection"}
{"timestamp": "2026-09-16T11:47:33.456695Z", "source": "client", "level": "warning", "event": "client error", "client_message": "deliberate frontend boom for log collection"}
{"timestamp": "2026-09-16T11:47:33.581019Z", "source": "client", "level": "warning", "event": "client error", "client_message": "deliberate frontend rejection for log collection"}
```

### All logs for one user

No level filter — every record the user produced, error and lower (huey
records carry no user identity, so only web-request records match):

```bash
journalctl -u app_granian.service -u app_huey.service -o cat --since '…' --until '…' \
  | grep '^{' \
  | mlr --jsonl filter '$username=="errors"' then cut -o -f timestamp,level,source,event
```

```json
{"timestamp": "2026-09-16T11:47:09.544341Z", "level": "info", "source": "server", "event": "http request"}
{"timestamp": "2026-09-16T11:47:09.545033Z", "level": "info", "source": "server", "event": "home viewed"}
{"timestamp": "2026-09-16T11:47:09.545425Z", "level": "error", "source": "server", "event": "Internal Server Error: /"}
…
{"timestamp": "2026-09-16T11:47:31.785058Z", "level": "warning", "source": "client", "event": "client error"}
{"timestamp": "2026-09-16T11:47:33.456695Z", "level": "warning", "source": "client", "event": "client error"}
{"timestamp": "2026-09-16T11:47:33.581019Z", "level": "warning", "source": "client", "event": "client error"}
```

## Decoding minified stacks

Client stacks point at hashed, minified bundles (`main-<hash>.js:67:21008`).
vite writes the matching `.map` files next to the bundles
(`djangoapp/static/djangoapp/`), Caddy never serves them, and the maps embed
the original sources — so decoding is an offline disk read.
`frontend/scripts/decode-stack.mjs` does it with node's builtin
`node:module.SourceMap` (no dependencies) — pass the position (the record's
`client_filename`/`client_lineno`/`client_colno`, or any frame's
`file:line:col` from the stack text; rerun for deeper frames):

```bash
node frontend/scripts/decode-stack.mjs https://localhost/static/djangoapp/main-B07sfg8A.js 67 21008
```

```
main-B07sfg8A.js:67:21008
  → frontend/src/ours/pages/Home.vue:22:14
```

The tool searches **only the current dist** (`djangoapp/static/djangoapp/`).
A stack's hash names the exact build it came from, and the map for that hash
dies with the next `npm run build`/`collectstatic --clear` — so decode while
the build that produced the log is still current. Older hashes fail loudly
instead of passing frames through:

```
map not found for main-CjayHrlg.js in …/djangoapp/static/djangoapp — log older than the current build?
```
