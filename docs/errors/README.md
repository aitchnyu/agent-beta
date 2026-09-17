# Error-log samples (deliberate)

Real log lines gathered on 2026-09-16 from the test VM's systemd journal,
produced by three param-gated bugs that existed temporarily on the VM (never
committed): `?boom` raised in `ourapp/views/home.py`, `?hueyboom` enqueued the
always-failing `ourapp.tasks.boom`, and `?jsboom`/`?jsreject` threw from
`Home.vue`'s `onMounted` (frontend rebuilt → entry `main-CjayHrlg.js`).

Queries and sourcemap decoding live in **docs/logging.md** — every command
there was verified against these files. The huey journal here is NDJSON-only
(the `huey` logger fix in `djangoproject/settings.py`).

| file | what it is | how it was collected |
| --- | --- | --- |
| `granian.ndjson` | the web unit's app records from the exercise window | `journalctl -u app_granian.service -o cat --since …` piped through `grep '^{'` |
| `huey.ndjson` | the huey unit's records: task Executing → warning → Unhandled exception | same, over `-u app_huey.service` |
| `granian.raw.log` / `huey.raw.log` | unfiltered `journalctl -o cat` — includes systemd's own unit-status markers | the `grep` input, before the cut |
| `client-errors.ndjson` | the `source == "client"` subset — frontend errors as recorded by the backend `/client-errors` handler | `grep '"source": "client"'` over `granian.ndjson` |
| `maps/main-CjayHrlg.js.map` | sourcemap of the exact build every client stack references | copied from the VM's `djangoapp/static/djangoapp/` before the clean rebuild |
| `maps/manifest.json` | vite manifest of that build | same |
| `vite-build.txt` | full `npm run build` output of that build (hash ↔ map ↔ stack correspondence) | captured from the VM build run |

Quirks kept on purpose: the authed browser run produced a duplicate
client-error record per error (the `pagehide` sendBeacon re-sends the
in-flight payload on navigation), and rejections carry no
`client_filename`/`client_lineno` — group those by message instead.
