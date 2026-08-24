# Superuser-gate /agent via caddy forward_auth → Django

Planned 2026-08-24. Research done; design below (implemented the same
evening — as-built notes at the bottom).

## Why

/agent (the ttyd console behind caddy `handle_path /agent/*`) currently
has NO auth ("LAN-trusted" decision). Anyone on the LAN who reaches
app.local gets a root-equivalent shell (console has NOPASSWD sudo).
The app already renders the Console nav link ONLY for superusers
(Layout.vue `isSuperuser && consoleUrl`) — the link was the only gate,
and the URL itself wasn't. steer.md:762 already CLAIMS "You run behind
a superuser-only Django proxy" — aspirational until now.

## Design

**Caddy `forward_auth`** (VM only — dev `./run console` on
localhost:7681 is untouched, "nothing for local"):

```
handle_path /agent/* {
    forward_auth 127.0.0.1:8000 {
        uri /agent/auth
    }
    reverse_proxy 127.0.0.1:7681
}
```

- forward_auth sends the ORIGINAL request (headers incl. the session
  cookie, original method) to granian with the URI rewritten to
  /agent/auth. 2xx → request proceeds to ttyd; anything else → caddy
  relays the auth response to the client as the verdict.
- Same-origin cookie: the sessionid cookie (path=/) rides the browser's
  /agent requests, so Django resolves the viewer exactly as on any app
  page. Host is preserved (app.local ∈ ALLOWED_HOSTS).
- WebSocket: the WS handshake is a GET — it goes through forward_auth
  once; frames after the upgrade never re-enter caddy. Reconnects
  re-auth, so a session that expires mid-terminal dies on the next
  reconnect (desired).
- The auth request goes straight to granian (127.0.0.1:8000), NOT
  through caddy's site routing — no loop.

**Django endpoint** — `djangoapp/views/__init__.py`:

```python
def agent_auth(request): ...   # require_superuser(request); return HttpResponse("")
```

- Reuses `require_superuser` (the house gate: anonymous AND
  non-superuser both 404 — existence stays hidden, never 403).
- 200 with empty body on success.
- Route: `path("agent/auth", agent_auth)` in djangoapp/urls.py —
  deliberately NO trailing slash: Django's APPEND_SLASH would 301
  /agent/auth → /agent/auth/, and caddy does NOT follow redirects —
  it would relay the 301 to the CLIENT as the auth verdict (browser
  ends up on a bare /agent/auth/ page). Slashless = no redirect, ever.
- CSRF: GET-only consumers (ttyd page fetch + WS handshake). If ttyd
  ever POSTs, CsrfViewMiddleware 403s it — acceptable (blocks); no
  csrf_exempt.

**Caddyfile.site.in** — the forward_auth block inside handle_path
/reagent/*, plus the header comment updated ("No ttyd auth by
decision" is superseded by the superuser gate).

## Tests

`djangoapp/tests/views/test_agent_auth.py` — mirrors
test_manage_views.py's pattern (force_login):
- anon → 404
- plain user → 404
- superuser → 200 empty
- trailing-slash URL → 404 (guards the APPEND_SLASH trap: the route
  must never exist WITH a slash)

## Files touched

1. djangoapp/views/__init__.py — agent_auth view
2. djangoapp/urls.py — slashless route
3. deploy/Caddyfile.site.in — forward_auth + comments
4. djangoapp/tests/views/test_agent_auth.py — 4 tests
5. steer.md — the "superuser-only Django proxy" line becomes true
   (no wording change needed; the /agent bullets in Commands section
   unaffected)
6. Prompt-file record (this file)

## Verification (VM)

- anon: `curl -k https://app.local/agent/` → 404
- superuser w/ session cookie: → 200 ttyd HTML (and the WS handshake
  passes)
- non-superuser session: 404
- app pages unaffected (no forward_auth outside the /agent block)

## As-built (2026-08-24 evening)

All implemented per design. VM verification, through caddy + real
sessions (makeloginlink redeem → cookie jar):

- anon `/agent/` → 404 (gate denies)
- frank.einstien (superuser; recreated — the last rebuild had wiped
  him) → `/agent/` 200 (ttyd HTML through the gate)
- plain user mallory → `/agent/` 404, app home 200 (gate scoped to
  /agent only)
- direct GET `/agent/auth` through the SITE → 404 from TYTD (post-strip
  /auth): the Django route is reachable ONLY via caddy's internal
  forward_auth rewrite to granian — existence hiding holds end-to-end.
- Django tests: 4/4 local AND on the VM (`./run test …test_agent_auth`).

Collateral fixes surfaced by verification (all pre-existing breakage,
not caused by the gate):

1. **checkproject env plumbing**: both cycles ran `uv run manage.py
   test` with NO env (each ./run child is a separate process; setenv
   doesn't leak) — settings' required os.environ[...] indexing made
   every run die on KeyError: SECRET_KEY. Both cycles now use
   `RUN_PROJECT_TESTS=1 ./run test` / `./run test` (test() re-sources
   the env itself). checkproject fully green again (168 + 42 tests) —
   first time since the required-indexing settings change.
2. **355ff15 regression restored**: that commit removed the four
   documented django-stubs `# type: ignore[misc]` on lazy
   apps.get_model("ourapp", …) as "stale" (they look unused under
   checkproject's overlay, where ourapp resolves) — silently breaking
   the MAIN typecheck (masked by mypy's incremental cache until a new
   file shook it loose). Restored the 4 ignores + a pyproject mypy
   override (`warn_unused_ignores = false` for exactly those two test
   modules) so BOTH contexts pass — with a comment telling the next
   agent not to delete them again.

Notes for the record:
- steer.md:762 "You run behind a superuser-only Django proxy" is now
  TRUE (was aspirational).
- Dev untouched: ./run console (localhost:7681) has no gate, per
  "nothing for local".
- The WS handshake re-auths on every (re)connect; session expiry kills
  the terminal on the next reconnect.
