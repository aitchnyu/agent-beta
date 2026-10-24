# Reference app

A small household app with real, working features — random trivia, a
personal todo list, file sharing — and a landing page that shows today's
trivia pick. Visitors read facts and download files; signing in (Google)
unlocks a private todo list; superusers manage the file shelf.

This is the copyable example: to add a feature to the real app, copy it
from here and adapt. The agent consults this when adding a feature.

## Features

- [facts](ourapp/docs/facts.md) — random trivia by topic + a daily Fact of the
  Day (Huey cron); seedable.
- [todos](ourapp/docs/todos.md) — a signed-in user's todo list.
- [downloads](ourapp/docs/downloads.md) — files shared for anonymous download
  until expiry.
- [home](ourapp/docs/home.md) — the landing page (shows today's Fact of the
  Day).

Each doc follows the same shape: what the screen shows, the data behind it,
and how it changes — with diagrams and captures.

## Screenshots

The four captures embedded in the docs are generated from the running app —
regenerate whenever a page changes. The suite imports reference-only models
(`Fact`, `Topic`, `Download`), so it runs in an overlaid scratch copy; the
captures land in the suite's own docs subtree (`screenshot_dir` on
`ReferenceScreenshots`) and are copied back — main's `docs/screenshots/` is
never touched. From main/'s root:

    ./run createscratch
    rsync -a --delete docs/reference/ourapp/ ../scratch/ourapp/
    for d in pages components schemas styles; do
      rsync -a --delete docs/reference/frontend/src/$d/ ../scratch/frontend/src/$d/
    done
    ( cd ../scratch && ./run screenshots ourapp.tests.test_screenshots )
    cp ../scratch/docs/reference/ourapp/docs/screenshots/*.png \
       docs/reference/ourapp/docs/screenshots/
    ./run cleanscratch

## Layout

```
docs/reference/
  README.md     this file
  ourapp/       the app: models/views/tasks/management per feature,
                tests flat (test_<feature>_<layer>.py), docs/ per feature,
                screenshots in ourapp/docs/screenshots/
  frontend/     the app's own pages/components/schemas/styles (overlaid into
                the bundle)
```

## Conventions

Fat models/thin views, ninja routers + Inertia pages, zod-parsed payloads,
public ids only, tests per feature + layer — all of it is
`agentconfig/steer.md` ("Feature workflow"); this app follows it exactly
and this README doesn't restate it.

## Workflow

Edit in `scratch/`, then `./run deployscratch` from `main/` (checks +
deploy — frontend/docs-only diffs take a fast path; commit is a separate
step). These files are illustrative — excluded from ruff/mypy/eslint,
overlaid onto `ourapp/` by `checkframework1`.
