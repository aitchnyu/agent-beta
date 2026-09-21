# ourapp

The single user app — a normal Django app (in `INSTALLED_APPS`). Features are
split into modules (one per feature under `models/`, `views/`, and `tests/`,
where tests are flat `test_<feature>_<layer>.py`) and combined into a whole; see
`docs/` for each feature.

This is the **placeholder**: it ships only the landing page so the project is
runnable out of the box. Add your features following the checklist in
`agentconfig/steer.md`.

## Features

- **Home** — the landing page at `/`, showing login state. See
  [docs/home.md](docs/home.md).
- **Mockup todos (demo)** — `/mockup-todos`, the shipped, permanent example of
  the mockup convention (superuser-only, static markup, crosshatch wrapper;
  `?final=1` shows it without the overlay); the README's mockup screenshots
  come from it.

## Layout

```
ourapp/
  models/      one module per feature, imported in models/__init__.py
  views/       one Router per feature; views/__init__.py owns the NinjaAPI
  tests/       flat: test_<feature>_<layer>.py (models/views/commands/playwright)
  docs/        one markdown file per feature, linked from this README
  management/commands/   seed/setup commands (one module per command; added with the first command)
```
