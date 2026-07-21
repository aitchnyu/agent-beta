# Remove collections: one flat app namespace

Drop the `ApplicationCollection` model entirely. Applications live in a single
flat namespace; the collection segment disappears from every path, every
filesystem layout, every model FK, and every `dynamic_models`/command API.

**Status:** Parts A–H + Part J (collection-word cleanup, `InstallDemo`→`HappyPathApp`)
are implemented and green (220 tests, ruff, mypy, frontend lint/type-check all
clean; migration applied; stale apps cleaned). **Part I (routing revision) is
the remaining work** — it supersedes the `/manage` mount that Part C shipped with.

## Final URL surface (target after Part I)

Every app route lives under `/apps/{app}/`: endpoints under `/e`, admin under
`/manage`. The app-name floor (≥10 chars) makes the `e`/`manage` seg-2 literals
unambiguous, and the route shapes differ by segment count, so there is no
collision.

- `GET /apps`                              → list all apps (index, superuser)
- `GET /apps/{app}/e`                      → default endpoint (public)
- `*   /apps/{app}/e/{function}`           → named endpoint (public)
- `GET /apps/{app}`                        → redirect to `/apps/{app}/e`
- `GET /apps/{app}/manage`                 → app's tables (superuser)
- `GET /apps/{app}/manage/{table}/list`    → row list
- `GET /apps/{app}/manage/{table}/id/{public_id}` → row detail

---

## Decisions (locked)

- **App names ≥10 chars.** Validator is `^[A-Za-z][A-Za-z0-9]{9,}$`
  (letter-first, 10+ chars). This is what reserves the `/e` and `/manage`
  literals (a 1–9-char name can't be `e`/`manage`), so no reserved-word list
  is needed. Implemented + applied to the migration. The floor stays at 10:
  a `HappyPath` (9) name was requested and rejected in favor of
  `HappyPathApp` (12).
- **Routing = per-app uniform layout (Part I).** Default endpoint returns to
  the bare `/e` (it is "the endpoint named `default`", same model as named
  endpoints — this is the *original* pre-removal shape); admin moves under
  `/apps/{app}/manage` (read as "manage this app"); the app-list index lives
  at bare `GET /apps`. This supersedes Part C's separate `/manage` mount,
  which was a valid but less-uniform choice. No collision because `{app}` ≥10
  chars and route shapes differ by segment count.
  - **Open choice (Part I):** bare `GET /apps/{app}` — redirect to `/e`
    (recommended) vs 404. Flag if you want 404.
- **DB is disposable.** Migration `0015_remove_collections` drops the
  `application_collection` table + FK and makes `Application.name` globally
  unique. Applied to the dev DB; stale orphaned apps (`Animals`/`Facts`/`Page`)
  deleted via the registry. Physical app tables (`zz_<physical_name>`) were
  never collection-keyed, so untouched.
- **Inertia pages.** `Collections.vue` + `AppList.vue` collapsed into one
  `AppList.vue` (props: just `apps`). `Manage.vue`, `TableRows.vue`,
  `RowDetail.vue` keep their component names; props/URLs change.
- **`ApplicationTable.clean()`** keeps a pre-DDL app-scoped uniqueness check
  (nice `ValidationError` before DDL), scoped to `application` (the DB
  `application_table_app_name_unique` constraint is the backstop).

---

## URL migration map (old → final)

| Old (pre-removal) | Final (after Part I) |
|---|---|
| `/apps/collections` | `/apps` (AppList index) |
| `/apps/a/{collection}/list` | `/apps` (merged index) |
| `/apps/a/{collection}/{app}/manage` | `/apps/{app}/manage` |
| `/apps/a/{collection}/{app}/manage/{table}/list` | `/apps/{app}/manage/{table}/list` |
| `/apps/a/{collection}/{app}/manage/{table}/id/{public_id}` | `/apps/{app}/manage/{table}/id/{public_id}` |
| `/apps/a/{collection}/{app}/e` (default endpoint) | `/apps/{app}/e` |
| `/apps/a/{collection}/{app}/e/{function}` | `/apps/{app}/e/{function}` |

Props lose `collection_name` everywhere; `FkTarget` is `{app_name, table_name}`.

> Note: Part C currently ships the admin at `/manage/apps…` (a separate mount).
> Part I moves it to `/apps/{app}/manage…` and the index to bare `/apps`.

---

## Detailed plan

### Part A — Model: drop `ApplicationCollection`  ✅ done

`djangoapp/models/applications.py`:

- [x] Delete `class ApplicationCollection`.
- [x] `Application`: remove FK `application_collection`; `name` is
      `unique=True` (global namespace); drop the
      `application_collection_name_unique` constraint.
- [x] `Application.app_or_404(app_name)` — single-name lookup via
      `cls.objects.get(name=app_name)`. (`get_by_names` removed; a transient
      `get_by_name` helper was added then dropped per review — callers use
      `Application.objects.get(name=…)` directly.)
- [x] `Application.script_path()` → `apps_root() / self.name / "app.py"`.
- [x] `Application.static_folder()` → `…/static/djangoapp/apps/{app}`.
- [x] `ApplicationTable.collection` property: deleted.
- [x] `ApplicationTable.clean()`: app-scoped uniqueness check (pre-DDL
      `ValidationError`), backed by the `application_table_app_name_unique`
      DB constraint.
- [x] New `app_name_validator` = `^[A-Za-z][A-Za-z0-9]{9,}$` (≥10 chars);
      `alphanumeric_validator` kept for table names.
- [x] Fixed the stale `zz_<collection>_<table>` docstring (physical name is
      `<tablename><unix-seconds>`).
- [x] `__init__.py` exports: removed `ApplicationCollection`, added `APP_NAME_RE`.
- [x] Migration `0015_remove_collections` (drops FK + table + constraint;
      `AlterField` name → unique + ≥10 regex). `makemigrations --check` clean.

### Part B — Filesystem: flatten apps/fixtures/static  ✅ done

Apps/fixtures now live at `<apps_root()>/<app>/` and
`djangoapp/static/djangoapp/apps/<app>/`.

- [x] On-disk: `apps/Trivia/Facts` → `apps/TriviaFacts` (gitignored; plain `mv`).
- [x] Built static: `Tests/{Browser,Page}` → `BrowserApp/HappyPathApp`,
      `Trivia/Facts` → `TriviaFacts` (gitignored build output).
- [x] Fixtures: `appfixtures/Tests/<App>` → `appfixtures/<App>` (git tracked).
- [x] Fixture `app.py`s: dropped `COLLECTION`/`create_application_collection`/
      `collection=`; `ForeignKeyColumn` targets are `(APP, TABLE)` 2-tuples;
      app URLs flattened.
- [x] App names raised to ≥10 chars: `Facts`→`TriviaFacts`, `Page`→`HappyPathApp`
      (via `InstallDemo`), `AllTypes`→`AllColumns`, `Browser`→`BrowserApp`,
      `Endpoints`→`EndpointsApp`, `FailsTest`→`FailsTestApp`, `Mock`→`HttpMockApp`
      (`FailsSetup` already 10).
- [x] Removed the unused `Relations` fixture (no `app.py`, unreferenced).

### Part C — Backend: views + URLs  ✅ done (ships `/manage` mount; Part I revises)

- [x] `app_endpoints.py`: `_ENDPOINT_PATH = "/{app_name}/e/{function_name}"`,
      default at `/{app_name}` (bare root); handlers take `app_name` only,
      resolve via `Application.app_or_404(app_name)`.
- [x] New `djangoapp/views/manage.py` with `manage_router` + `manage_api`
      (namespace `manage-http`); `applications.py` trimmed to just the public
      `apps_api` + endpoint router.
- [x] `apps_page` / `manage_page` / `row_list_page` / `row_detail_page` under
      `/manage/apps…`; `_get_application_table_or_404(app_name, table_name)`.
- [x] All prop models dropped `collection_name`; `FkTarget` →
      `{app_name, table_name}`.
- [x] `urls.py`: added `path("", manage_api.urls)`.

### Part D — `dynamic_models` API  ✅ done

- [x] Deleted `create_application_collection`, `delete_application_collection`,
      `rename_application_collection`, `_resolve_collection`.
- [x] `create_application(*, name, description="", tables=None)` /
      `rename_application(*, old_name, new_name)` — no `collection=`.
- [x] `create/add/delete_application_table(_columns)` — no `collection=`.
- [x] `_table_label` → `f"{app}/{table}"`; `DependencyGraph.from_db` /
      `from_application_tables(app, tables)` use 2-tuple FK targets.
- [x] `select_related("application__application_collection")` →
      `select_related("application")`.

### Part E — Management commands  ✅ done

- [x] `list_application_collections` + `list_application_collection` → one
      `list_applications`.
- [x] `describe_application_table`: dropped `--appcollection`; resolves by `--app`.
- [x] `export_fk_graph`: label `app:table`; `select_related("application")`.
- [x] `applications_schemas.py`: dropped `ListApplicationCollectionSchema`;
      `DescribeApplicationTableSchema` drops `appcollection`.
- [x] `buildfrontend.py` + `buildbackend.py`: identity is a single app name
      (reject identities containing `/`); resolve via
      `Application.objects.get(name=identity)`.

### Part F — Frontend  ✅ done (Part I revises URL builders)

- [x] `schemas.ts`: dropped `collection_name` from `RowListProps`,
      `RowDetailProps`, `ManageProps`, `AppListProps`, `FkTarget`.
- [x] `utils/urls.ts`: `rowListUrl(app, table)`, `rowDetailUrl(app, table, id)`,
      `appEndpointUrl(app)` (currently → `/apps/{app}`; Part I → `/apps/{app}/e`).
- [x] `AppList.vue` merged with `Collections.vue` (deleted); `Manage.vue`,
      `TableRows.vue`, `RowDetail.vue`, `RowCell.vue`, `Layout.vue`,
      `BackToTopLink.vue` updated.
- [x] `npm run type-check` + `npm run lint` clean.

### Part G — Tests  ✅ done (Part I revises URLs)

- [x] `test_applications_views.py`, `test_row_views.py`,
      `test_applications_command.py`, `test_dynamic.py`, `test_columns.py`,
      `test_endpoints.py`, `test_buildbackend.py`, `test_buildfrontend.py`,
      `playwright/test_row_views.py` all rewritten (drop collection; ≥10-char
      app names e.g. `OrdersData`/`BillingData`/`FkTargetApp`; `/manage/apps…`
      URLs). 220 tests pass.

### Part H — DB cleanup + verify  ✅ done

- [x] `0015_remove_collections` applied to the dev DB.
- [x] Deleted stale orphaned apps (`Animals`/`Facts`/`Page`) via the registry.
- [x] Smoke: `buildbackend TriviaFacts` installs (3 tests);
      `GET /apps/TriviaFacts/e/random_fact` → 200; unknown app/fn → 404;
      `/manage/apps` anon → 404. (`/apps/TriviaFacts` root 404s correctly —
      TriviaFacts defines `home`, not `default`; Part I makes the root redirect.)

### Part I — Routing revision: per-app uniform layout  ⏳ pending

Supersedes Part C's `/manage` mount. Everything app-scoped moves under
`/apps/{app}/`, endpoints under `/e`, admin under `/manage`; the app-list
index moves to bare `/apps`.

`djangoapp/views/app_endpoints.py`:
- [ ] `_DEFAULT_PATH = "/{app_name}/e"` (default endpoint back to `/e`, not the
      bare root). Keep the GET-only guard.
- [ ] Add a redirect for the bare root: `GET /{app_name}` → 301/302
      `/apps/{app_name}/e` (so `/apps/{app}` is not a dead 404).

`djangoapp/views/manage.py` → move onto the `apps_api` router (no separate
mount) under `/apps/{app}/manage`:
- [ ] `manage_router` paths: `/{app_name}/manage`, `/{app_name}/manage/{table_name}/list`,
      `/{app_name}/manage/{table_name}/id/{public_id}`.
- [ ] App-list index: `GET /` on `apps_endpoint_router` (i.e. bare `/apps`) →
      `AppList` page.
- [ ] Remove the standalone `manage_api` / `urls.py` mount (or keep the
      NinjaAPI but re-path it); `applications.py` adds `manage_router`.

`frontend/src/`:
- [ ] `utils/urls.ts`: `rowListUrl` → `/apps/{app}/manage/{table}/list`;
      `rowDetailUrl` → `/apps/{app}/manage/{table}/id/{id}`;
      `appEndpointUrl(app)` → `/apps/{app}/e` (default) and add a named-endpoint
      helper `/apps/{app}/e/{fn}` if any caller needs it.
- [ ] `Layout.vue` nav href `/manage/apps` → `/apps`.
- [ ] `Manage.vue`/`TableRows.vue`/`RowDetail.vue` breadcrumbs + back-links:
      `/manage/apps/{app}` → `/apps/{app}/manage`; collection-free already.
- [ ] App frontends (TriviaFacts, BrowserApp, docs reference): named-endpoint
      fetches stay `/apps/{app}/e/{fn}` (unchanged); any default-endpoint fetch
      moves `/apps/{app}` → `/apps/{app}/e`.

Tests:
- [ ] `test_applications_views.py`, `test_row_views.py`,
      `test_endpoints.py`, `playwright/test_row_views.py`: rewrite URLs from
      `/manage/apps/{app}/…` → `/apps/{app}/manage/…`; default-endpoint test
      from `/apps/{app}` → `/apps/{app}/e`; add a bare-root redirect test.

Verify:
- [ ] `./run test`, `ruff`, `mypy`, `frontend npm run type-check && npm run lint`.
- [ ] Smoke: `GET /apps/TriviaFacts` → redirect; `GET /apps` lists TriviaFacts;
      `/apps/TriviaFacts/manage` lists tables.

### Part J — Collection-word cleanup + HappyPathApp rename  ✅ done

After A–I, sweep lingering uses of the word "collection" (the concept is gone)
and normalize the demo fixture name.

- [x] Removed stale "collection" references in docstrings/comments:
      `dynamic_module.py` (the `/apps/<app>/e/<function>` route + apps-root
      layout lines), `BackToTopLink.vue` ("app/table route hierarchy"),
      `TriviaFacts/app.py` (setup docstrings). `manage.py:3`'s "no collections"
      kept (it describes the new state).
- [x] Renamed the demo fixture `InstallDemo` → `HappyPathApp` (≥10 chars; the
      requested `HappyPath` is 9 and fails the floor). Moves: fixture dir,
      static build output, `APP` const, `test_buildbackend.py`, the
      `buildbackend` help-text example.
- [x] `./run test` — 220 passed; `ruff` — clean.

---

## Lint and verify (final)

- [x] `./run test` — 220 passed
- [x] `ruff check` — clean
- [x] `mypy` — clean (83 files)
- [x] `frontend npm run type-check && npm run lint` — clean
- [ ] Re-run after Part I.

---

## Open decisions

1. **App-name length:** resolved — floor stays ≥10 chars (`{9,}`). `HappyPath`
   (9) rejected → demo fixture is `HappyPathApp` (Part J).
2. **Admin mount:** resolved — per-app `/apps/{app}/manage` (Part I), not the
   `/manage` mount.
3. **Bare `/apps/{app}` root:** redirect to `/e` (recommended) vs 404 — confirm.
4. **DB approach:** resolved — migration applied, stale apps cleaned.
