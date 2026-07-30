# Remove the apps framework; make this a single-app template

## Goal

Stop being a multi-app generator. Become a **template**: clone it, add one's own
code to a single normal Django app `ourapp/`, and drive changes through an agent
that edits a `copy/` of the repo, runs the full suite, and (after the user tries
it) promotes the change back into `main/`.

## Decisions (shared understanding, locked across Q&A)

- **Remove entirely:** `apps/` + its inner git; dynamic module loading
  (`djangoapp/apps/`); the `Application` / `ApplicationTable` /
  `ApplicationTableColumn` / `AppsGeneration` models; `dynamic.py` + `columns.py`;
  the `buildbackend` / `buildfrontend` / `applications` management commands; the
  `/apps/<app>...` endpoint router; `docs/apps/`;
  `djangoapp/tests/appfixtures/`. A migration (`0018_remove_apps_framework`) drops
  the four now-dead model tables.
- **Git viewer (repurposed, not removed):** `djangoapp/views/git.py` +
  `git_data.py` are KEPT and repointed at the project repo
  (`git_data._REPO_ROOT = settings.BASE_DIR`, `git._confined_to_repo`); the
  `/git` routes serve `main/`'s own commits/uncommitted state. `gitpython`
  stays a dependency for this.
- **`ourapp/`** is a normal Django app (in `INSTALLED_APPS`, own `models.py`,
  `views.py`, `urls.py`, `migrations/`). Ships **empty** (no sample model); the
  models-management pages render an empty state.
- **`BaseModel`** (renamed from `BaseTable`) stays in `djangoapp`, abstract,
  parent of concrete models in `ourapp/`. Built-in fields keep their
  underscore-prefixed names (`_public_id`, `_created_by`, `_created_at`,
  `_edited_at`). Adds `get_absolute_url()` returning
  `/manage/models/<ModelName>/id/<_public_id>`.
- **Models management pages** (superuser-only, under `/manage`), introspecting
  concrete `BaseModel` subclasses registered in the `ourapp` app config
  (Django app registry), routed by model `__name__`:
  - `/manage/models` — list of models with their class **docstrings**
    (replaces `AppList` + `Manage`).
  - `/manage/models/<model>/list` — paginated rows (replaces `TableRows`).
  - `/manage/models/<model>/id/<public_id>` — single-row detail (`RowDetail`).
  - Sorting stays limited to the built-ins (`_created_at` / `_edited_at`).
  - FK columns link to the referenced row via the related instance's
    `get_absolute_url()` (no more hardcoded `FkTarget` URL).
- **Frontend:** one Vue+Inertia app. Agent-editable areas are
  `frontend/src/components/ours/` and `frontend/src/pages/ours/` (Inertia
  component name `ours/<Name>` resolves via the existing `pages/**/*.vue` glob).
  Existing pages collapse: `AppList`+`Manage` → `ModelList`; `TableRows` →
  `ModelRows`; `RowDetail` kept.
- **copy/main workflow** (built now): the repo lives as `parent/main` (+ `.git`);
  per feature the agent copies `main` (minus `.git`/`node_modules`/`.venv`/caches)
  to a fresh `parent/copy/`, bootstraps its own env (`uv sync` + `npm install`),
  edits **all of `copy/`**, runs `./run checkall` there. On pass the user tries
  the app; on approval the agent syncs changed files `copy/ -> main/` and commits
  in `main`'s git (single repo). Dev auto-reloads (runserver watches `main/`);
  prod reload is future work. `./run createscratch` and `./run mergescratch` implement this.

## Resolved

- `parent/` is `/Users/jesvin/dev/ourinstant/` (the current repo's parent, a safe
  folder). `main/` stays at `/Users/jesvin/dev/ourinstant/main`; `copy/` is a
  sibling at `/Users/jesvin/dev/ourinstant/copy`. No tree relocation. opencode's
  CWD is `parent/`; scripts live in `main/run` and are invoked as
  `main/run createscratch` / `main/run mergescratch` / `cd copy && ./run checkall`.

## Phased checklist

### Phase 1 — BaseModel + ourapp scaffold (in `main/`, no relocation yet)
- [x] Move `BaseTable` out of `applications.py`; rename to `BaseModel`; place in
      `djangoapp/models/base.py`. Keep built-in fields; add `get_absolute_url()`
      (+ `__str__`, module constant `MANAGE_MODELS_URL_PREFIX`).
- [x] Update `djangoapp/models/__init__.py` exports (`BaseModel`, drop dead).
- [x] Create `ourapp/` (`apps.py`, empty `models.py`, `views.py`, `urls.py`
      with empty urlpatterns, `migrations/0001_initial.py`, `__init__.py`,
      `admin.py`). **`views.py` + `urls.py` ship wired in** as the live
      integration point for regular Django views.
- [x] Add `ourapp` to `INSTALLED_APPS`; `include("ourapp.urls")` in
      `djangoapp/urls.py` (LAST, so host routes win).
- [x] Create `frontend/src/components/ours/` + `frontend/src/pages/ours/`
      (each ships a short README note).
- [x] `./run lintfix`, `./run typecheck`.

### Phase 2 — Models management (backend + frontend)
- [x] Rewrite `djangoapp/views/manage.py`: introspect `ourapp` models; new
      routes `/manage/models`, `/manage/models/<model>/list`,
      `/manage/models/<model>/id/<public_id>`; FK cells use
      `get_absolute_url()`.
- [x] Frontend: rename/adapt `AppList`+`Manage` → `ModelList.vue`,
      `TableRows.vue` → `ModelRows.vue`; keep `RowDetail.vue`. Update
      `schemas.ts`/props to match. Empty state when no models.
- [x] Add/adjust tests under `djangoapp/tests/views/` (`test_manage_views.py`).
- [x] Backend lint chain (`lintfix`, `typecheck`, `test`); frontend lint chain.

### Phase 3 — Remove the apps framework
- [x] Delete `apps/` (incl. inner `.git`), `docs/apps/`, `djangoapp/tests/appfixtures/`.
- [x] Delete `djangoapp/apps/` (dynamic_module, shortcuts, __init__).
- [x] Delete `djangoapp/models/dynamic.py`, `columns.py`, `applications.py`
      (BaseModel already moved out).
- [x] Delete commands `buildbackend.py`, `buildfrontend.py`, `applications.py`,
      `applications_schemas.py`.
- [x] Delete `djangoapp/views/app_endpoints.py`; repurpose `git.py`/`git_data.py`
      to `main`'s git (KEPT, repointed at `BASE_DIR`). Prune `urls.py`,
      `views/__init__.py` docstrings.
- [x] Remove apps-related tests; drop the `/apps` static serving + `AppsGeneration`
      cache-bust references (`base.html`, `host_template_data`).
- [x] Migration `0018_remove_apps_framework`: remove the four framework models
      via `DeleteModel` (after dropping their unique constraints + FK fields).
      Runtime `zz_*` tables were registry-managed, not migrated.
- [x] `./run checkall`.

### Phase 4 — copy/main orchestration
- [x] `./run createscratch`: rsync `main` → fresh `copy/` (shared `_COPY_EXCLUDES`:
      `.git`, `copy/`, `node_modules`, `.venv`, caches, `dist`, `build`,
      `djangoapp/static`, `db.sqlite3`, `prevproject/`, …); then
      `uv sync` + `npm install` inside `copy/`. (No `migrate`: shared Postgres
      DB; `checkall` migrates its own test DB.) Wipes any existing `copy/`.
- [x] `./run mergescratch`: rsync `copy/` → `main/` (`--delete`, same excludes +
      `.env`), then `git -C main add` + `commit` (refuses if `main/` isn't
      clean; no-op when nothing changed).
- [x] Decide `parent/` location: `/Users/jesvin/dev/ourinstant/` — `main/`
      stays, `copy/` is a sibling. No tree relocation.

### Phase 5 — Agent config + docs
- [x] **Reference app** at `docs/reference/` (illustrative, not installed,
      excluded from ruff/mypy): copyable files mirroring the real tree —
      `ourapp/{models,views,urls,tests}.py` (a `BaseModel` model with a `User`
      FK, a list+create Django view pair, `urls.py`) +
      `frontend/src/{pages,components}/ours/*` (an Inertia page) + a `TestCase`
      + a README pattern guide. Replaces `docs/apps/reference/`.
- [x] Rewrite `agentconfig/steer.md`: scope = `ourapp/` +
      `frontend/src/{components,pages}/ours/`; describe the copy→edit→checkall→
      try→promote→commit flow; document `/files` + `/git` linking; no
      `buildbackend`/`buildfrontend`.
- [x] Update `agentconfig/opencode.json`: edit scope → `copy/**` allow; allowlist
      `createscratch`/`mergescratch`/`checkall`/`typecheck`/`test`/`lintfix`/
      `makemigrations`/`migrate` + read-only `git -C main ...`; drop the
      read-only shell utils (`ls`/`find`/`grep`) and `git -C apps`.
- [x] Rewrite `README.md` for the single-app template. (`INSTRUCTIONS.md` was
      already framework-agnostic — left as-is.)
- [x] `run` (added `createscratch`/`mergescratch`; `init` had no apps bootstrap to drop) +
      `.gitignore` (dropped `/apps/**` rules; added `.mypy_cache/`/`.ruff_cache`;
      dropped `.kilocode`. `copy/` is a sibling outside the repo, so not
      gitignored). `pyproject.toml`: kept `gitpython` (for `/git`), removed
      `networkx`, broadened ruff+mypy excludes for a gitless `copy/`.

### Phase 6 — Final
- [x] `./run checkall` green end to end (ruff + mypy + tests + frontend
      lint/typecheck + playwright).

### Review refinements (two subagent review rounds)
- [x] `base.html`: `{{ app_static_base|default:"/static/djangoapp" }}` so ours/
      pages without `template_data` still load the host bundle.
- [x] `manage.py`: `_fk_value` guards `isinstance(related, BaseModel)`;
      `_cell_value` coerces non-JSON-primitives to `str()`.
- [x] `promote`: clean-tree guard (`git status --porcelain`) + `rsync --delete`
      + no-op commit guard; `_COPY_EXCLUDES` excludes `prevproject/` + `.kilo/`.
- [x] Removed dead `.apps-manage-*` CSS; parenthesized `except (A, B):` in
      `git.py`/`git_data.py`; fixed several stale "apps" docstrings/comments.

## Follow-ups from inline markers

Collected from the live inline `aihere` comments in the codebase (excluding
`prevproject/` and the historical `prompts/` journals). Several supersede
earlier locked decisions — the inline marker is the latest word.

- [x] `steer.md`: add a bullet list of the changeable files under Role & scope.
- [x] `steer.md`: add a "Layout: parent / main / copy" section; be consistent
      about `cd` commands (always absolute, never `cd ..`).
- [x] `steer.md` workflow: test in `copy/`, **deploy** to `main/` (so the user
      sees it live), then **offer to commit** — commit is a separate, later step.
- [x] `steer.md`: recommend a django-ninja router + pydantic response schemas
      (for both API and Inertia responses) and zod on the frontend.
- [x] `steer.md`: add an `axios` example (`try/catch` + zod parse + `showErrorToast`).
- [x] `run createscratch`: `git init` the copy so the agent can see its changes
      via `/git` (copy/ becomes its own throwaway git repo).
- [x] `run mergescratch`: **deploy only** — rsync `copy/` → `main/`, drop the
      auto-commit and clean-tree guard (commit is a separate process).
- [x] `run`: "why not `./run init`?" — decided no: `init` is interactive
      (`.env` prompt) and creates the shared DB / installs firefox / migrates /
      builds; a scratch copy only needs `uv sync` + `npm install`. Comment removed.
- [x] `djangoapp/views/__init__.py`: remove `host_template_data` (base.html now
      defaults `app_static_base`) and drop all 16 call sites + 6 imports.
- [x] `README.md`: suggest ninja routers for ourapp URLs; move the underscore/
      pk note to `steer.md` (already covered there) and drop it from README.
- [x] `docs/reference/`: switch the example to a django-ninja router + pydantic
      schemas (consistency with the recommendation above).
