# checkproject: a real test tier (test app + reference app) for models/git/files

## Goal
Today the models/git/files functionality is tested with mocks (`test_git`) or only
in the empty state (`test_manage_views`), because the template ships an empty
`ourapp/`. Add a richer, real-data test tier — `checkproject` — that installs a
complete **test app** (and the **reference app**) into a throwaway `copy/` and
exercises models/git/files for real (backend + browser). `checkall` stays the
fast loop for `main/` + `copy/` and keeps running against the empty `ourapp/`.

## Decisions (locked across Q&A)
- **Two apps, same format** (`ourapp/` + `frontend/src/{components,pages}/ours/`):
  - **Test app** — lives at `djangoapp/tests/testapp/`; a complete `ourapp/`
    (models/views/urls/migrations) + `frontend/ours/`. Code that exercises
    models/git/files. **No own tests** — the tagged framework tests in
    `djangoapp/tests/` test against it.
  - **Reference app** — lives at `docs/reference/`; same format and **ships its
    own tests inside itself** (`ourapp/tests.py`). The user-facing example.
- **`checkall`** — unchanged role. Runs against the
  empty `ourapp/`, so it **excludes the `project`-tagged tests** (stays green with
  no models).
- **`checkproject`** — a strict superset. **Two separate `createscratch` cycles**:
  1. **Test-app cycle** — `createscratch` → overlay `djangoapp/tests/testapp/`
     (full-tree replace of `ourapp/` + add `frontend/ours/`) → run full `checkall`
     **+ the `project`-tagged framework tests** (models/git/files).
  2. **Reference-app cycle** — `createscratch` → overlay `docs/reference/`
     (full-tree) → run the reference app's **own tests** (`manage.py test ourapp`).
- **Overlay = full-tree replace** of the copy's empty `ourapp/` (models, views,
  urls, migrations) and the `frontend/src/{components,pages}/ours/` files.
- **Tagged framework tests** (`djangoapp/tests/…`, tag **`project`**): real,
  non-mock tests for models/git/files — **backend (Django test client) + browser
  (Playwright)**. They replace today's mocks/empty-state coverage. The git/files
  tests lean on the copy's own git repo (`createscratch`'s `git init` + baseline)
  and file tree.
- **Test-app models (proposed minimal-but-complete set)**: ~2 `BaseModel`
  subclasses covering each field kind (char/text/int/bool/decimal/datetime) + a FK
  to `User` + a FK to another `BaseModel` (so FK→profile and FK→`get_absolute_url`
  linking both get exercised), seeded with enough rows for pagination/sort.

## Phased checklist

### Phase 1 — Test app fixture (`djangoapp/tests/testapp/`)
- [x] `ourapp/` skeleton: `apps.py`, `__init__.py`, `models.py` (Author + Book —
      every field kind + FK→User + FK→BaseModel), `views.py`/`urls.py` (a ninja
      API serving an `ours/` list page), `migrations/0001_initial.py`, `admin.py`.
- [x] `frontend/src/pages/ours/BooksPage.vue` rendering the models.
- [x] Exclude `djangoapp/tests/testapp/` from ruff/mypy (it's only valid overlaid).

### Phase 2 — Reference app (`docs/reference/`)
- [x] Same format as the test app (`ourapp/` + `frontend/ours/`); completed
      `__init__.py`, `apps.py`, `migrations/0001_initial.py` (Note) so it can be
      overlaid + tested.

### Phase 3 — `project`-tagged framework tests (`djangoapp/tests/…`)
- [x] **models** (`test_manage_project.py`, backend): `/manage/models` list
      (names + docstrings + counts), `/manage/models/Book/list` (field kinds +
      FK→BaseModel links via `get_absolute_url` + FK→User profile),
      `/manage/models/Book/id/<pid>` detail, `/manage/models/Author/list`.
- [~] **git / files / browser**: covered by the existing **real** tests
      (`views/test_git.py` — real temp repo; `test_files.py` — real tree; the
      Playwright suite), which run inside cycle 1's full suite against the
      test-app context. Not duplicated as new `project`-tagged tests (the existing
      ones are already real, not mocks). Deferred: explicit `project`-tagged
      git/files + a `project`-tagged browser test if richer coverage is wanted.

### Phase 4 — `checkall` excludes the `project` tag
- [x] `run test`: `--exclude-tag playwright --exclude-tag project`.
- [x] `./run checkall` green in `main/` with empty `ourapp/`.

### Phase 5 — `checkproject` function (`run`)
- [x] Cycle 1 (test app): `createscratch` → overlay `djangoapp/tests/testapp/`
      (full-tree replace `ourapp/` + `frontend/ours/`) → full suite with `project`
      tests included.
- [x] Cycle 2 (reference app): `createscratch` → overlay `docs/reference/ourapp/`
      → `manage.py test ourapp` (the reference app's own tests).
- [x] Both cycles leave `copy/` disposable (no commit, no mutation of `main/`).

### Phase 6 — Docs/config
- [x] `agentconfig/opencode.json`: allowlisted `./run checkproject` +
      `main/run checkproject`.
- [x] `agentconfig/steer.md` + `README.md`: documented `checkproject`, the two
      apps, the `project` tag, and that `checkall` is the fast loop.

### Phase 7 — Final
- [x] `./run checkall` green (main, empty `ourapp/`).
- [x] `./run checkproject` green (both cycles).
