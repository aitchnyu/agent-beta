# Repo map — put your head down and research the repo through this file.

Trust the files over the map. If the file structure changed too much,
read a live session's logs to see the missteps, then rewrite this map
streamlined.
Sync test: `ops/tests/test_repo_map.py` — every repo path named here
must exist; when the test fails, refresh this map.

## 1. Feature workflow

Six stages, each transition an explicit operator pick: [1] Mockups →
MockupGate → [2] Design docs → DocsGate → [3] Code (scratch,
`deployscratch` per batch) → [4] Agent review + doc updates →
[5] CommitOffer → [6] Final checklist → one-sentence close. Stages 3–5
run as ONE turn; compact at stage boundaries.

- Mockups: `frontend/src/app/pages/Mockup<Name>.vue`, served verbatim
  by the hatch route `/mockup/<page>` (plain view `mockup_page` in
  `ourapp/views/home.py`, routed `ourapp/urls.py`) — hardcoded markup,
  no props/backend, superuser-only, `div.mockup` wrapper.
  `?props=<base64url JSON>` presets state (`_B64JsonProps`).
  Graduation = real page + DELETE mockup + homepage link.
- Reviewers: prewarmed at stage-2 start (background `subagent`,
  reviewer-correctness / reviewer-conventions / reviewer-trace for
  big diffs, single `reviewer` otherwise); the reviewer-manager
  extension keeps them alive (`reviewers({refresh: true})` at
  DocsGate, code-stage start, FinalReport); round 2 resumes warm.

## 2. Scratch discipline

- `../scratch/` is the edit surface; `main/` reachable only via
  deploy. `./run createscratch` (wipes existing — ask first),
  `./run deployscratch` FROM `main/` (battery → rsync `--delete` →
  migrate/restart on backend diff), `./run cleanscratch`.
- Green `deployscratch` IS the whole verification — no post-deploy
  e2e, no re-runs.
- Before each deploy: `main/`'s dirty files must all be pending in
  scratch, else STOP (BlockerAsk).
- Formatting/lint ≠ deploy points — fold into the next batch;
  `cd ../scratch && ./run lintfix` after every write batch.
- Edits via `edit`, one surgical diff per spot; never script batches
  or wholesale rewrites.

## 3. Doc conventions (.pi/steer.md § Feature docs)

- One file per feature: `ourapp/docs/<feature>.md`; ~80-char wrap;
  title = feature name only; two audiences (plain front, "For
  developers" tail).
- Outline: title+para · who-can-do-what (usecase-beta d2) · the data
  (plain words then sql_table d2) · how data changes (exhaustive
  change list + safety rails) · what you see (screenshots) · history
  (optional) · for developers.
- Diagrams: d2 fences, `direction: down` top-level, actors
  `shape: person` pinned 180×160, ovals `width: 240`; mandatory
  `./run checkmarkdownd2 <file.md>` after every fence write.

## 4. BaseModel save_plus / row_version (`djangoapp/models/base.py`)

- `SKIP_ROW_VERSION_CHECK = -1`; `class BaseModel`; `row_version`
  default 0; `get_absolute_url()`.
- `save_plus(*, actor, expected_row_version)`: create (0) stamps
  audit + one `created` log; update diffs pre-edit row → one
  `updated` log (no-op = no log); mismatch → `Http404`; bumps
  `row_version`.
- `delete_plus(*, actor)`: purges field history, writes lean
  `deleted` tombstone, deletes row.
- `BaseModelUpdateLog`; `Notification.record(...)` goes INSIDE
  `transaction.atomic()`; push fan-out on `on_commit`.
- FKs: `on_delete=models.RESTRICT` always; money = DecimalField;
  never `get_user_model()` — `from djangoapp.models import User`;
  m2m changes not logged.

## 5. Endpoints + Inertia pages pattern

- Pages = PLAIN Django views in `ourapp/views/<feature>.py`, routed
  `path(...)` in `ourapp/urls.py` (see also
  `docs/reference/ourapp/urls.py`). JSON/file = `Router` endpoints
  (`@router.post("/todos/create", response=Schema)`).
- `ourapp/views/__init__.py` owns the single `NinjaAPI`, routers
  registered `api.add_router("/", <feature>.router)`; mounted last in
  urls.py so page paths win.
- Errors: `ApiError(status, *, type=, msg=, ctx=)` from
  `djangoapp.ninja_api` — never `HttpError`.
- Auth: `user_or_404(request)` / `maybe_user(request)` from
  `djangoapp.shortcuts`; ownership failure = 404 not 403.
- Payloads pk-free (`public_id` only); page data nested under `props`
  → frontend reads `props.props`; every frontend payload zod-parsed;
  HTTP via `frontend/src/system/utils/http.ts` (`postJSON`/`ninjaPost`); toasts via
  `showToast`/`showErrorToast`; inline field errors via `FieldError`
  + `errorAtPath`.
- Pages render `<PageTitle :value="…"/>`.
- zod: one component → inline; one feature →
  `frontend/src/app/schemas/<feature>.ts`; framework →
  `system/schemas/`.

## 6. Test layout

- Flat: `ourapp/tests/test_<feature>_<layer>.py` (layers: `models`,
  `views`, `commands`, `playwright`). Bases:
  `djangoapp.tests._base.BaseTestCase` / `BaseInertiaTestCase` (fast
  hashers); playwright:
  `djangoapp.tests.playwright._base.BasePlaywrightTestCase` (carries
  `playwright` tag + harness — no hand-tagging).
- Class docstring = one-line description + one bullet per test in
  declaration order.
- Run: `./run test <labels…>` (fast, keepdb) / `./run test --full`.

## 7. Copy-me trio (see also `docs/reference/`)

- Backend: `docs/reference/ourapp/models/todos.py`,
  `docs/reference/ourapp/views/todos.py`
- Tests: `docs/reference/ourapp/tests/test_todos_models.py`,
  `docs/reference/ourapp/tests/test_todos_views.py`,
  `docs/reference/ourapp/tests/test_todos_playwright.py`
- Frontend: `docs/reference/frontend/src/pages/TodosPage.vue`,
  `docs/reference/frontend/src/schemas/todos.ts`
- Wiring: `docs/reference/ourapp/urls.py` +
  `docs/reference/ourapp/views/__init__.py`

## 8. Gotchas that cost sessions time (don't rediscover)

- **Django-model queries from a script**: `export
  DJANGO_SETTINGS_MODULE=djangoproject.settings && ./run python -c
  'import django; django.setup(); from ourapp.models import Todo;
  …'`. Everything else (settings env, allowlist) already rides
  `./run`. Prefer `dbstate`/management commands when one exists.
- **JSON API surface**: introspect via the NinjaAPI instance, not the
  filesystem: `from ourapp.views import api; [p for p in
  api.urls]` (mount point + operation paths). Pages are NOT on api —
  they are plain views (§5).
- **Inertia test helpers**: read `docs/reference/frontend/` first;
  the live helpers sit in site-packages — do not go spelunking there.
- **`dbbackups/` inside main/ is a postgres-owned island.** Never
  chown/copy/write into it; pgbackrest (running as postgres) fails
  the backup when its ownership changes.
- **Gate leftover landmine**: a gate run leaves Books-era migration
  rows in `desmo_db` — if a fresh feature 500s with tables missing,
  check `django_migrations` for a colliding `0001_initial` (the
  gate-cleanup fix removes this; see plan file 20261029).
