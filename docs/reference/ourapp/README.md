# ourapp (reference)

The reference user app — two example features following the multi-file layout
(one module per feature under `models/` and `views/`; flat tests as
`test_<feature>_<layer>.py` under `tests/`). The app owns the landing page at
`/` (not the framework).

## Features

- **Facts** — random trivia, optionally scoped to a topic; seedable via a
  command. See [docs/facts.md](docs/facts.md).
- **Todos** — a signed-in user's todo list on one page. See
  [docs/todos.md](docs/todos.md).
- **Home** — the landing page at `/`, showing login state and links to the
  features (gated by what the viewer can open). See
  [docs/home.md](docs/home.md).

## Layout

```
ourapp/
  models/      one module per feature (facts.py, todos.py), imported in __init__.py
  views/       one Router per feature (home.py, facts.py, todos.py); __init__.py owns the NinjaAPI
  tests/       flat: test_<feature>_<layer>.py (models/views/commands/playwright)
  management/commands/   seed/setup commands (seedfacts)
  docs/        one markdown file per feature, linked from this README
```
