# ourapp (reference)

The reference user app — three example features following the multi-file layout
(one module per feature under `models/` and `views/`; flat tests as
`test_<feature>_<layer>.py` under `tests/`). The app owns the landing page at
`/` (not the framework).

## Features

- **Facts** — random trivia, optionally scoped to a topic; seedable via a
  command. See [docs/facts.md](docs/facts.md).
- **Todos** — a signed-in user's todo list on one page. See
  [docs/todos.md](docs/todos.md).
- **Downloads** — the file-upload illustration: an admin uploads a file,
  anyone with the link downloads it until an expiry date (default one week),
  then it 404s and a daily sweep removes row + bytes. Shows the three media
  primitives — `FileField` storage under `media/`, file cleanup riding the
  tracked pair (`save_plus`/`delete_plus`), and `serve_file`-based serving.
  Behind caddy, downloads are FAST: Django gates the request, then hands
  the byte-streaming to caddy via the X-Accel-Redirect interception — the
  app process never moves file bytes. See
  [docs/downloads.md](docs/downloads.md).
- **Home** — the landing page at `/`, showing login state and links to the
  features (gated by what the viewer can open). See
  [docs/home.md](docs/home.md).

## Layout

```
ourapp/
  models/      one module per feature (facts.py, todos.py, downloads.py), imported in __init__.py
  views/       one Router per feature (home.py, facts.py, todos.py, downloads.py); __init__.py owns the NinjaAPI
  tests/       flat: test_<feature>_<layer>.py (models/views/commands/playwright)
  tasks/       Huey tasks, one file per feature (facts.py, downloads.py)
  management/commands/   seed/setup commands (seedfacts)
  docs/        one markdown file per feature, linked from this README
```
