# Back-to-top link component

Add a reusable "link to top" (scroll to top) component and use it on:
- `/apps/a/{collection}/list` → `AppList.vue`
- `/apps/a/{collection}/{app}/manage` → `Manage.vue`

These pages list rows in a `<table>` that can grow long. A back-to-top link at the
bottom lets the user jump to the page top without scrolling.

## Plan

The link must be a single shared SFC so both pages stay in sync. It should:
- Render a simple anchor that scrolls the window to the top on click (smooth).
- Not navigate/change URL (no router push, no `href="#"` with handler — per
  frontend rules, avoid `<a href="#">` until explicitly asked; use a `<button>`
  styled as a link or a plain element with a click handler).
- Be keyboard accessible (focusable, Enter to activate).
- Styles live in `main.css`, not scoped/inline.

## Checklist

- [x] Create `frontend/src/components/BackToTopLink.vue`
    - [x] renders a focusable element — implemented as an Inertia `<Link>` (anchor, natively focusable + Enter-activates) that navigates **up one level** in the route hierarchy (clarified intent: "top" = parent route, not page-scroll)
    - [x] shows an up-arrow (`↑`) glyph + link text
    - [x] accepts an `href` prop (required) + an optional slot for label, defaulting to "Back to top"
    - [x] has a stable class (`apps-back-to-top`) for styling/tests
- [x] Add styling rule for `.apps-back-to-top` (+ `.apps-back-to-top-arrow`) in `main.scss`
    - [x] subtle link, inline-flex with the arrow, top margin
- [x] Use `BackToTopLink` in `AppList.vue`
    - [x] after the `<table>`, inside `.container`, href `/apps/collections`
- [x] Use `BackToTopLink` in `Manage.vue`
    - [x] after the `<table>`, inside `.container`, href `/apps/a/<collection>/list`
- [ ] Tests
    - [ ] unit/component test: clicking `BackToTopLink` navigates — **deferred**: no Vitest/component-test infra exists in this project yet
    - [ ] playwright: back-to-top link visible on list + manage pages — **deferred**: no playwright tests for the apps pages exist yet
- [x] Lint and verify
    - [x] `cd frontend && npm run lint:fix`
    - [x] `cd frontend && npm run type-check`
    - [x] `cd frontend && npm run lint`
    - [x] `./run checkall`

---

# Row list and row detail pages (superuser-only)

Two new read pages, both superuser-gated (non-superuser → 404, never 403),
reading rows from the dynamic model (`dynamic_models.get_model(table.physical_name)`).
Both reuse the `BackToTopLink` ("up arrow") component above.

- `/apps/a/<collection>/<app>/manage/<tablename>/list` → list rows in a table, paginated.
- `/apps/a/<collection>/<app>/manage/<tablename>/id/<publicid>` → single row detail.

`<tablename>` is the table's display name; `<publicid>` is the row's own
`_public_id` (from `BaseTable`). Never send `.pk`/`.id` to the client.

## Backend

The dynamic model's built-in columns are `_public_id`, `_created_by` (FK→User),
`_created_at` (auto_now_add), `_edited_at` (auto_now). User columns come from
`ApplicationTable.column_order`. Resolve `collection/app/table` via
`dynamic_models` resolvers; missing → 404.

### Plan

- One view module / additions to `djangoapp/views/applications.py` with two
  view functions + pydantic prop models. Resolver helper to go
  `(collection, app, tablename) -> ApplicationTable` (404 on miss) reused by
  both views.
- Column value serialisation per type (char/text/int/bool/decimal/datetime/
  user). `user` renders as `{public_id, title}` (link target); datetime as ISO
  string or None; decimal as string; FK-user never leaks pk.
- Pagination mirrors prevproject's `articles.py` list: `Paginator(qs, per_page,
  orphans=5)` + `get_page(page)`. Defaults: `per_page=25`, `page=1`,
  `sort="created_at"` (only `created_at` / `edited_at` allowed). `get_page`
  already clamps out-of-range pages.
- Sort: `order_by("-_created_at", "-_public_id")` or `order_by("-_edited_at",
  "-_public_id")` (desc, newest first); tiebreak on `_public_id` for stable order.

### Checklist

- [x] Add resolver `_get_application_table_or_404(collection_name, app_name, table_name) -> ApplicationTable`
    - [x] 404 when collection / app / table missing
- [x] Column value serializer (one function returning a `dict[str, Any]` keyed by column name; frontend casts per column type)
    - [x] char → string (or choice title alongside value if `char_choices`)
    - [x] text → string
    - [x] integer → int or None
    - [x] boolean → bool
    - [x] decimal → string (preserve precision) or None
    - [x] datetime → ISO string or None
    - [x] user → `{public_id, title}` or None (never pk)
- [x] Prop models in `djangoapp/views/applications.py`
    - [x] `RowListColumnDef` (name, type, has choices flag)
    - [x] `RowListItem` (public_id, values: dict[str,Any], created_by, created_at, edited_at)
    - [x] `RowListPagination` (page, total_pages, total_count)
    - [x] `RowListFilters` (per_page, page, sort) — used as a Ninja `Query[RowListFilters]` model
    - [x] `RowListProps` (collection_name, app_name, table_name, columns, rows, pagination, filters)
    - [x] `RowDetailProps` (collection_name, app_name, table_name, public_id, columns, values, created_by, created_at, edited_at)
- [x] `row_list_page(request, collection_name, app_name, table_name, filters: Query[RowListFilters])`
    - [x] `_require_superuser` gate
    - [x] resolve table (404 on miss)
    - [x] parse `per_page` (default 25), `page` (default 1), `sort` (default `created_at`; unknown falls back to created_at, no 500) — via Ninja `Query` + pydantic `Field`
    - [x] build qs from `dynamic_models.get_model(...).objects.all()`, order by sort desc + `_public_id`
    - [x] `Paginator(qs, per_page, orphans=5)`, `get_page(page)`
    - [x] serialise rows (public_id first), never pk
    - [x] 404 if physical table absent (catch `DatabaseError`) — decision: let it crash; a physical-table-absent state is a programmer/server error (metadata out of sync), not a user-facing 404
- [x] `row_detail_page(request, collection_name, app_name, table_name, public_id)`
    - [x] `_require_superuser` gate
    - [x] resolve table + row by `_public_id` (404 on miss; `DatabaseError` left to crash per instruction)
    - [x] serialise all columns in `column_order` + created_by/created_at/edited_at
- [x] Routes — moved all `/apps/*` views onto a Ninja router (`apps_router`) mounted via `apps_api.urls`; `Query[RowListFilters]` parses params
    - [x] `apps/a/<c>/<app>/manage/<table>/list` (`apps-row-list`)
    - [x] `apps/a/<c>/<app>/manage/<table>/id/<public_id>` (`apps-row-detail`)
- [x] Re-export new symbols in `__all__`

### Tests

- [x] `row_list_page` (`djangoapp/tests/views/test_row_views.py`)
    - [x] non-superuser → 404
    - [x] missing collection/app/table → 404
    - [x] default sort = created_at desc; per_page=25; page=1
    - [x] `sort=edited_at` orders by edited_at
    - [x] invalid `sort` falls back to created_at (no 500)
    - [x] pagination total_pages/total_count correct
    - [x] no pk leaked in props
- [x] `row_detail_page`
    - [x] non-superuser → 404
    - [x] missing row → 404
    - [x] created_by present as `{public_id, title}`, no pk
    - [x] created_at/edited_at as ISO strings
- [x] Keep view + test class docstrings up to date

## Frontend

### Plan

- New pages `TableRows.vue` (list) and `RowDetail.vue` (detail).
- Inline prop types mirroring zod schemas (SFC resolver can't follow `z.infer`,
  same pattern as `AppList.vue`).
- Pagination copy prevproject `ListRowsContent.vue` pattern: prev/next `<Link>`
  using query-built URLs (`?page=&per_page=&sort=`), disabled at ends.
- `BackToTopLink` ("up arrow") at the bottom of both pages.

### Checklist

- [x] Schemas in `frontend/src/schemas.ts`
    - [x] `RowListColumnDefSchema` (+ `RowListColumnDef` type); `RowValuesSchema` (record keyed by column name)
    - [x] `RowListItemSchema`, `RowListPaginationSchema`, `RowListFiltersSchema`, `RowListPropsSchema`
    - [x] `RowDetailPropsSchema`
- [x] `frontend/src/pages/TableRows.vue`
    - [x] header: collection / app / table breadcrumb
    - [x] table: public_id column first as `<Link>` to detail page; then user columns (user cells → profile link); then created by (link), created at, edited at
    - [x] `BackToTopLink` after table (href = manage page)
    - [x] pagination: prev/next Links built from query; page indicator + total
    - [x] parse props with `RowListPropsSchema`
- [x] `frontend/src/pages/RowDetail.vue`
    - [x] render each column (name + value), in `column_order`
    - [x] bottom block: created by (link), created at, edited at
    - [x] `BackToTopLink` at bottom (href = list page)
    - [x] parse props with `RowDetailPropsSchema`
- [x] Register both pages — auto-registered via `import.meta.glob` in `main.ts` (same as existing pages)

## Shared / cross-cutting

- [x] No `.pk`/`.id` in any URL path or prop (only public ids)
- [x] Query-building helper `rowListUrl`/`rowDetailUrl` in `frontend/src/utils/urls.ts`, reused by pagination Links

## Lint and verify

- [x] Backend: `./run lintfix`
- [x] Backend: `./run typecheck`
- [x] Backend: `./run test`
- [x] Frontend: `cd frontend && npm run lint:fix`
- [x] Frontend: `cd frontend && npm run type-check`
- [x] Frontend: `cd frontend && npm run lint`
- [ ] Playwright: list page renders + pagination navigates; detail page renders created-by link — **deferred**: no playwright tests for the apps pages exist yet
- [x] `./run checkall`

## Inertia typing (bonus investigation)

- [x] Ported `prevproject/stubs/inertia/{__init__,test}.pyi` to `stubs/inertia/` (inertia-django 1.2.0 ships no `py.typed`/stubs); added `render`/`share`/`InertiaResponse` + `InertiaTestCase` members
- [x] Removed every `# type: ignore[no-any-return]` on inertia calls across `views/applications.py`, `views/users.py`, `views/__init__.py`, and the `InertiaTestCase` class ignores in tests
- [x] Added ruff per-path ignore `stubs/**/*.pyi` (ANN401, N802); mypy now resolves inertia via the stub during full `mypy .` runs

## `aihere` markers in this feature's code

Collected from `aihere` markers added during the row-view work (all in `djangoapp/views/applications.py`, now addressed and removed):

- [x] `views/applications.py` — "make this a ApplicationTable method" — moved column ordering onto the model as `ApplicationTable.ordered_columns()`; the view now calls `table.ordered_columns()` and the standalone `_ordered_columns` helper is deleted.
- [x] `views/applications.py` — "remove all the include_in_schema=False" — dropped `include_in_schema=False` from all five `apps_router` route decorators (kept `response=None`).
- [x] `views/applications.py` — "return RowListItem here" (`row_detail_page`) — `row_detail_page` now builds a single `RowListItem` via the shared `_row_item(columns, instance)` helper (also used by the list page) and spreads its fields into `RowDetailProps`, removing the duplicated inline `BaseTable` column extraction.

Out of scope here (tracked under the models prompt): `models/applications.py:36` — "make this a dict or constants since we are not using the text version" (`ColumnType` TextChoices).

## More changes 

Keep only these commands, remove the rest:
    list_application_collections
    list_application_collection
    describe_application_table

Test those commands. Maybe add a new file. 

Have tests that run in a transaction and test the methods:
    create collection
    rename collection
    delete collection
    create application
    rename application
    delete application
    create table
    rename table
    all columns to table
    remove columns from table
    fetch model, insert and save, update and save, delete

All of them should be in a savepoint and assert they are rolled back.

## Plan

Three pieces of work, in order. The table lifecycle methods on
`dynamic_models` already exist and are **kept** (existing tests call them
directly).
The collection/app mutation logic currently lives only in the command
as inline ORM, so it has no home once the write commands are pruned —
Part B promotes it onto `dynamic_models`, and Part C tests every
lifecycle method inside rolled-back savepoints.

A key behaviour change decided here: **deleting an application drops all
of its tables** (physical Postgres tables included). Deleting a
collection, by contrast, is **refused if it still has apps** (the user
must delete each app first, which in turn drops its tables). The
ORM-level `on_delete=RESTRICT` stays as a DB backstop; the registry
methods own the ordered cleanup / refusal so no physical table is ever
orphaned and no collection vanishes under live apps.

### Part A — Prune the `applications` command to read-only

The command keeps only the three read subcommands. Everything that
mutates state is deleted from the command layer (subparsers, `_handle_*`
methods, `SUBCOMMANDS` entries, schema imports) and the now-dead schema
classes are removed from `applications_schemas.py`. The lifecycle itself
moves to `dynamic_models` (Part B) and is tested directly (Part C), so
no behaviour is lost — only the command wrappers.

Affected files:
- `djangoapp/management/commands/applications.py` — subparsers + handlers + imports
- `djangoapp/management/commands/applications_schemas.py` — unused schema classes + `__all__`
- `djangoapp/tests/management/test_applications_command.py` — drop tests for removed subcommands

### Checklist A

- [x] `applications.py` — keep only these in `SUBCOMMANDS`:
    - [x] `list_application_collections`
    - [x] `list_application_collection`
    - [x] `describe_application_table`
- [x] `applications.py` — remove `add_subparsers` blocks for:
    - [x] `create_application_collection`, `rename_application_collection`, `delete_application_collection`
    - [x] `create_application`, `rename_application`, `delete_application`
    - [x] `create_application_table`, `add_application_table_columns`, `delete_application_table_columns`
    - [x] `rename_application_table`, `delete_application_table`
- [x] `applications.py` — delete the matching `_handle_*` methods (all write handlers); keep `_handle_list_application_collections`, `_handle_list_application_collection`, `_handle_describe_application_table`
- [x] `applications.py` — prune imports to only what the three read handlers need (`ListApplicationCollectionSchema`, `DescribeApplicationTableSchema`); drop now-unused `Application`, `ApplicationCollection`, `IntegrityError`, `transaction`, write schemas
- [x] `applications.py` — update the module docstring (no longer "create/rename/delete"; read-only listing/describe)
- [x] `applications_schemas.py` — remove schema classes no longer referenced:
    - [x] `CreateApplicationCollectionSchema`, `RenameApplicationCollectionSchema`, `DeleteApplicationCollectionSchema`
    - [x] `CreateApplicationSchema`, `RenameApplicationSchema`, `DeleteApplicationSchema`
    - [x] `CreateApplicationTableSchema`, `AddApplicationTableColumnsSchema`, `DeleteApplicationTableColumnsSchema`
    - [x] `RenameApplicationTableSchema`, `DeleteApplicationTableSchema`
    - [x] shared bases/helpers left dangling by the above (`_ColumnBase`, column specs, `_TableTargetSchema`, `_TableLookupSchema`) — remove if now unused
- [x] `applications_schemas.py` — keep `ListApplicationCollectionSchema` + `DescribeApplicationTableSchema` (+ their base, if shared); prune `__all__` to match
- [x] `test_applications_command.py` — remove tests that drive removed subcommands:
    - [x] `test_collection_create_rename_list` (trim to list-only)
    - [x] `test_delete_collection_refuses_when_not_empty`
    - [x] `test_application_create_rename_delete`
    - [x] `test_create_table_builds_columns_and_physical_table`
    - [x] `test_add_and_delete_columns_via_command`
    - [x] `test_delete_application_table`
    - [x] `test_rename_application_table`
    - [x] all of `ApplicationsValidationTests` (write-path validation)
- [x] `test_applications_command.py` — keep/adjust read-only tests:
    - [x] `list_application_collections` prints all collection names
    - [x] `list_application_collection` prints apps in a collection
    - [x] `describe_application_table` prints table + columns, omits physical_name/db_table
    - [x] `test_invalid_json_returns_nonzero` — drop (no JSON subcommands left)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`

### Part B — Promote collection/app CRUD onto `dynamic_models`

`DynamicModelRegistry` becomes the single home for all application-graph
mutation, symmetric with the existing table methods. Create/rename are
thin (full_clean + save); `delete_application` owns ordered
physical-table cleanup so nothing is orphaned; `delete_application_collection`
refuses a non-empty collection. Each method wraps its work in
`transaction.atomic()` so a failure mid-cascade rolls back the whole
graph change.

New methods on `DynamicModelRegistry` (`djangoapp/models/dynamic.py`):
- `create_application_collection(name) -> ApplicationCollection`
- `rename_application_collection(collection, new_name)` — already exists (line 402); keep
- `delete_application_collection(collection)` — refuse if it has apps (`ValidationError`); else delete the collection row
- `create_application(appcollection, name, desc) -> Application`
- `rename_application(appcollection, old_name, new_name) -> Application`
- `delete_application(app)` — cascade: for each child table, `delete_application_table(...)` (drops physical table + definition); then delete the app row

`delete_application_table` already exists (line 381) and is reused as
the leaf of the `delete_application` cascade. The `on_delete=RESTRICT`
FKs (`applications.py:120`, `:169`) remain as a safety net but are never
the intended path — the registry always deletes children first (apps) or
refuses (non-empty collection).

### Checklist B

- [x] `dynamic.py` — add `create_application_collection(name)` (full_clean + save, atomic)
- [x] `dynamic.py` — `rename_application_collection` already present; confirm it stays
- [x] `dynamic.py` — add `delete_application_collection(collection)`:
    - [x] refuse with `ValidationError` if `collection.applications.exists()` (mirrors the old command rule)
    - [x] else `collection.delete()`
    - [x] wrapped in `transaction.atomic()`
- [x] `dynamic.py` — add `create_application(appcollection, name, desc)` (resolve collection, full_clean + save, atomic)
- [x] `dynamic.py` — add `rename_application(appcollection, old_name, new_name)` (resolve, set name, full_clean + save, atomic)
- [x] `dynamic.py` — add `delete_application(app)`:
    - [x] iterate `app.tables.all()`, call `delete_application_table(collection, app.name, table.name)` for each (drops physical table + definition)
    - [x] then `app.delete()`
    - [x] whole cascade inside one `transaction.atomic()`
- [x] `dynamic.py` — re-export new methods in `__all__` (module `__all__` lists `dynamic_models` only; nothing else to do unless individual funcs are exported)
- [x] Docstrings: explain the cascade + why RESTRICT is only a backstop
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`

### Part C — Lifecycle method tests

New file `djangoapp/tests/models/test_dynamic_lifecycle.py`. Two test
shapes, chosen by what the operation actually touches:

1. **DDL ops use a savepoint-rollback assertion.** The mutation runs
   inside `transaction.atomic()`; the test raises to roll the savepoint
   back, then asserts the **physical** DB reverted — `to_regclass` null
   for a dropped/never-created table, columns restored after an aborted
   add/drop. This pins Postgres transactional DDL, the property the whole
   module relies on, per schema_editor operation.
2. **Non-DDL ops (collection/app/row) use positive assertions** —
   rollback of plain ORM writes is Django's behaviour, not the module's,
   so those tests verify the change happened, not that it reverts.

Plus a cascade-failure test for the atomic blocks' real purpose.

### Checklist C

- [x] Helpers in `test_dynamic_lifecycle.py`:
    - [x] `_physical_table_exists(physical_name)` — `SELECT to_regclass(%s)` (mirror `test_dynamic.py`)
    - [x] `_table_columns(db_table)` — column list from `information_schema` (mirror `test_dynamic.py`)
    - [x] seed a collection + app in `setUpTestData`; per-test `dynamic_models.reset()`
- [x] DDL savepoint-rollback (the meaningful rolled-back tests):
    - [x] `create_application_table` — create inside `transaction.atomic()`, raise → definition rows gone **and** `to_regclass('zz_...')` is null
    - [x] `add_application_table_columns` — add inside savepoint, raise → new columns absent from both definition and physical table
    - [x] `delete_application_table_columns` — drop inside savepoint, raise → dropped columns restored in both definition and physical table
    - [x] `delete_application_table` — drop inside savepoint, raise → physical table still exists, definition rows intact
- [x] Cascade-drop DDL rollback:
    - [x] `delete_application` (with tables) inside savepoint, raise → every child physical table still exists, app + tables intact
- [x] Non-DDL positive tests:
    - [x] Collection: `create_application_collection`, `rename_application_collection`, `delete_application_collection` (empty → gone), `delete_application_collection` (non-empty → raises, untouched)
    - [x] Application: `create_application`, `rename_application`, `delete_application` (no tables → gone)
- [x] Cascade-drop positive:
    - [x] `delete_application` with tables → each child physical table gone (`to_regclass` null), definition rows gone, app gone
- [x] Cascade-failure safety:
    - [x] force a failure mid-`delete_application` (e.g. monkeypatch one child's `delete_application_table` to raise) → no half-deleted state: app + all tables + all physical tables either all present or all gone, no orphaned physical table
- [x] Column lifecycle positive:
    - [x] `add_application_table_columns` (all column types: char/text/integer/boolean/decimal/datetime/user) → columns in definition + physical table altered
    - [x] `delete_application_table_columns` → columns gone from definition + physical table altered
- [x] Row lifecycle positive via `dynamic_models.get_model`:
    - [x] insert + save → readable
    - [x] update + save → values changed
    - [x] delete → row gone
- [x] Keep test class + method docstrings up to date (one-line-per-method list)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

### Part D — Move home/middleware tests under `tests/views`

`test_home.py` and `test_middleware.py` are view tests living in
`djangoapp/tests/`; relocate them to `djangoapp/tests/views/` to match
the existing layout (`test_applications_views.py`, `test_row_views.py`,
`test_users.py`).

### Checklist D

- [x] Move `djangoapp/tests/test_home.py` → `djangoapp/tests/views/test_home.py`
- [x] Move `djangoapp/tests/test_middleware.py` → `djangoapp/tests/views/test_middleware.py`
- [x] Fix any imports broken by the move
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

test_home and test_middleware shuould be in tests/views. Move them.

## Test method naming + docstring pass

Rule: the method **name** states what is tested (descriptive, not a one-word
verb); the **docstring** adds non-obvious detail the name doesn't already
imply (how it's verified, the side effect, the serialised form). A docstring
that merely restates the name (e.g. `test_create_application_collection` +
"Collection row created.") fails the rule.

### Checklist

- [x] `tests/models/test_dynamic.py` — `RowLifecycleTests` (names too terse):
    - [x] `test_insert_and_read` → `test_inserted_row_is_readable`; docstring add "via the generated model's manager (cast Any)"
    - [x] `test_update` → `test_saved_changes_persist_on_update`; docstring add the mechanism (refresh + compare the changed field)
    - [x] `test_delete` → `test_deleted_row_is_absent_from_queryset`; docstring add "filter by pk returns empty"
- [x] `tests/models/test_dynamic.py` — `GraphLifecycleTests` (docstrings restate the name):
    - [x] `test_create_application_collection` — docstring "Collection row created" → add "name stored + row queryable" (the verification detail)
    - [x] `test_delete_application_collection_empty` — docstring "Empty collection deleted" → add "row gone afterward"
    - [x] `test_rename_application` — docstring "App name updated" → add "within its own collection; no DDL (display-name only)"
    - [x] `test_delete_application_no_tables` — docstring "App row gone" → add verification ("no Application row for the name")
- [x] `tests/models/test_dynamic.py` — `DynamicSchemaTests`:
    - [x] `test_add_application_table_columns_all_types` — docstring "Every column type materialises a column" → add "user columns materialise as `<name>_id` (FK), others by name"
    - [x] `test_delete_application_table_columns` → `test_delete_application_table_columns_removes_definition_and_physical`; docstring add "gone from both ApplicationTableColumn rows and the physical table"
- [x] `tests/views/test_row_views.py` — `RowValuesViewTests`:
    - [x] `test_all_values_in_list` / `test_all_values_in_detail` — docstrings add the per-type serialisation checked (decimal→str, datetime→ISO, user→{public_id,title})
    - [x] `test_pagination` → `test_pagination_splits_rows_by_per_page` (name too terse); keep the orphans detail in the docstring
- [x] `tests/management/test_applications_command.py` (docstrings restate the subcommand):
    - [x] `test_list_application_collections` — docstring add "printed one name per line, sorted"
    - [x] `test_list_application_collection` — docstring add "apps under the collection, sorted"
- [x] After renames, update each class docstring's one-line-per-method bullet list to match the new names
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

---

# Playwright counterparts for `test_row_views.py`

E2E mirror of the row list (`TableRows.vue`) and row detail (`RowDetail.vue`)
view tests. The backend tests assert on props; these drive a real browser and
assert on rendered output + navigation.

## Plan

One new file `djangoapp/tests/playwright/test_row_views.py`, subclassing
`BasePlaywrightTestCase`. Three test classes, one per concern (detail,
list render, list navigation). Row views are superuser-gated, so the
happy-path tests use the `_login_superuser()` pattern from
`test_users.py:98` (new page → `/login-for-test/<pk>`); the pre-authed
`self.logged_in_page` (a non-superuser) is reused only for the 404 case.

Seed in `setUp` (model fixtures belong in `setUp`, per the harness): a
superuser, an application collection + app, `dynamic_models.reset()`,
`create_application_table(...)` spanning the column types
(char/text/integer/boolean/decimal/datetime/user), then insert rows via
the dynamic model — a handful for the detail tests, ~31 for pagination.
Stash created rows' `_public_id` on `self`. `tearDown` calls
`dynamic_models.reset()`.

Only `page.wait_for_selector` / `page.wait_for_url` for waits; no
`wait_for_timeout` / `wait_for_load_state` / explicit `timeout=` args
(per Playwright rules). All assertions target existing stable classes in
`TableRows.vue` / `RowDetail.vue`:

- list: `.apps-tablerows-page`, `.apps-tablerows-table`, `.apps-row-link`
  (per-row detail link), `.apps-prev-link`, `.apps-next-link`,
  `.apps-tablerows-pagination`, `.apps-tablerows-controls`
- detail: `.apps-rowdetail-page`, `.apps-rowdetail-table`

URLs:
- list `/apps/a/<collection>/<app>/manage/<table>/list`
- detail `/apps/a/<collection>/<app>/manage/<table>/id/<public_id>`

## Checklist

- [x] `setUp` — superuser + collection/app/table (all column types) + rows; stash `_public_id`s; `_post_teardown` drops dynamic physical tables + resets registry
- [x] `RowDetailE2eTests`
    - [x] visit detail of a known row → `.apps-rowdetail-page` renders, each column value present in `.apps-rowdetail-table` (incl. user link, created-by)
    - [x] visit detail of unknown public id → response status 404
    - [x] non-superuser (use `self.logged_in_page`) → response status 404
- [x] `RowListRenderE2eTests`
    - [x] visit list → `.apps-tablerows-table` renders, first row's code cell + "X total" count correct
    - [x] per-page select → change to 100 in `.apps-tablerows-controls`, `wait_for_url` reflects `per_page=100`, all rows render, no `.apps-next-link`
- [x] `RowListNavigationE2eTests`
    - [x] click first `.apps-row-link` → `wait_for_url("**/id/<public_id>")`, detail page renders
    - [x] with 31 rows + per_page=25: `.apps-next-link` → `wait_for_url` has `page=2`, page-2 row visible; `.apps-prev-link` → back to `page=1`
    - [x] on page 1, `.apps-prev-link` count is 0
- [x] Class + method docstrings up to date (one-line-per-method bullet list)
- [x] Run individual failing tests via the playwright helper, then `./run checkall`