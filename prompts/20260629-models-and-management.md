Have ApplicationCollection model - just have name field (alphanumeric, upto 100 chars)

Have Application model
    appication_collection - fk
    name - (alphanumeric, upto 100 chars)
    desc - rich text, like user

Have ApplicationTable model
    application - fk
    name
    column_order - json ['col1', 'col2'] of all columns

Have ApplicationTableColumn model
    name
    type: char/text/integer/boolean/decimal/datetime/user (fk)
    char_choices - json list[str] - ['choice1', 'choice2']
    text_default - text (char and text)
    text_min_length - int, default 0 (char and text)
    text_max_length - int, default 1000 (char and text)
    nullable - same for int/decimal/datetime/user
    int_default
    decimal max_digits=10, decimal_places=2
    decimal_default
    date

## Commands
Have these django management comments
./run djangomanage applications <subcommand> --named-param x --named-param x
./run djangomanage applications <subcommand> '{"json_data"}'
Try to use subparsers to implement commands. We must parse all inputs to be correct. Use Pydantic schemas to parse all schemas and print input errors. Else have a 0 return code and print success message and any relavent info. 
The commands are meant to be run by agents, no need to make it ergonomic to humans.
Operate these commands in atomic transactions
Add these to readme


### List of subcommands
create_application_collection - params: name 
rename_application_collection - params: old_name, new_name
delete_application_collection - params: name (ensure its empty)
list_application_directories - just all directories, separate by newline
list_application_collection - params: name - show applications within name collection, separate by newline

create_application - params: appcollection, name
rename_application -params: old_appcollection, old_name, new_appcollection, new
delete_application appcollection name (ensure its empty of models)

create_application_table - takes json params
    appcollection
    app
    name
    columns - [
        {type: char, name:, choices:, min_length:, max_length:}, 
        {type: text, name:, min_length:, max_length:},
        {type: integer, name:, default:, nullable},
        {type: decimal, name:, default:, nullable, max_digits:, decimal_places},
        {type: datetime, name:, nullable},
        {type: user, name:, nullable,},
    
    colnames starts with alphabet, no _ either
    when we create, ensure ApplicationTable.column_orders is updated
add_application_table_columns - json, similar params as createapplicationtable
delete_application_table_columns - takes json with `columns` params - list[str]
describe_application_table - params: appcollection and name
delete_application_table - params: appcollection and name

## 
These endpoints are available to superuser:
/apps/collections - shows a list of collections
/apps/a/list - list apps in a collection

/apps/a/collection/app/manage - show list of tables and rows 
    table1 - 800 
    table2 = 400

Use https://medium.com/@baserow/how-baserow-lets-users-generate-django-models-ee97a20c4398
Ensure that tablename is zz_collectionname_tablename, and type CollectionTablenameDynamicModel
for /manage, we can use model = application_table('collection', 'table') and it will get a model

Its a child of BaseTable model
    public id - char(100) - indexed
    created_by - user/None
    created_at - datetime
    edited_at - datetime

Use schema_editor with to create models, adding/removing columns etc. Like .create_model(Project)

---

# Plan

## Resolved decisions (from review)

- **Scope:** models + `applications` management command AND the superuser `/apps/...` endpoints + `/manage` row page are all in this prompt.
- **Identity vs display:** collection/app/table each carry an immutable `slug` (set at creation) used to build the physical `db_table = zz_<collection_slug>_<table_slug>`. The `name` field is mutable display-only; renames never touch the DB table. No `alter_db_table` on rename.
- **Table-name collision:** physical name omits the app level, so `ApplicationTable.name`/`slug` is enforced unique within a **collection** (across all its apps), not per-app.
- **Column name charset:** user columns are `[A-Za-z][A-Za-z0-9]*` (start with a letter, no underscore anywhere). `BaseTable` built-in columns are underscore-prefixed — `_public_id`, `_created_by`, `_created_at`, `_edited_at` — so user and built-in columns can never collide.
- **`Application.desc`:** nh3-sanitized rich text (HTML stored after sanitization on write).
- **Column defaults:** `boolean_default` exists; no `datetime_default` (datetime supports only `nullable`). decimal carries per-column `decimal_max_digits` + `decimal_places`.
- **Public-id rule:** names/slugs are the public ids in URLs/API; integer `pk`/`id` never leaks (AGENTS.md).
- **on_delete:** `RESTRICT` default (AGENTS.md).

## Models — `djangoapp/models/applications.py`

- `ApplicationCollection`: `name` (alnum, ≤100, unique), `slug` (alnum, ≤100, unique, immutable, editable=False), `public_id` (uuid7).
- `Application`: FK `application_collection` (RESTRICT), `name` (alnum, ≤100, unique-together collection+name), `slug` (immutable, unique-together collection+slug), `desc` (rich text, nh3-sanitized on save), `public_id`.
- `ApplicationTable`: FK `application` (RESTRICT), `name` (alnum, ≤100, unique-together **collection**+name), `slug` (immutable, unique-together collection+slug), `column_order` (`JSONField` default `[]`), `public_id`.
- `ApplicationTableColumn`: FK `application_table` (RESTRICT), `name` (`[A-Za-z][A-Za-z0-9]*`, unique-together table+name), `type` (choices: char/text/integer/boolean/decimal/datetime/user), `char_choices` (JSON list[str], char only), `text_default` (text, char+text), `text_min_length` (int, default 0, char+text), `text_max_length` (int, default 1000, char+text), `nullable` (bool, default False, for int/decimal/datetime/user), `int_default` (int, nullable), `boolean_default` (bool, default False), `decimal_default` (decimal, nullable), `decimal_max_digits` (int, default 10), `decimal_places` (int, default 2), `public_id`.
- `BaseTable` (abstract): `_public_id` (CharField ≤100, indexed), `_created_by` (FK User, null=True, RESTRICT), `_created_at` (DateTimeField auto_now_add), `_edited_at` (DateTimeField auto_now).
- **Dynamic-model factory** `application_table(collection_slug, table_slug) -> Model`: builds a `Model` class named `CollectionTablenameDynamicModel` (camel-cased from slugs), subclassing `BaseTable`, `Meta.db_table = zz_<collection_slug>_<table_slug>`, `app_label="djangoapp"`, with one field per `ApplicationTableColumn` (char→CharField with choices/min/max, text→TextField, integer→IntegerField, boolean→BooleanField, decimal→DecimalField, datetime→DateTimeField, user→FK User). Cached per (collection_slug, table_slug).

## Schema operations — `djangoapp/db/schema.py`

Use `schema_editor` (Baserow-style) under `transaction.atomic`:
- `create_application_table`: `create_model` with `BaseTable` fields + user columns; persist `ApplicationTableColumn` rows; set `column_order`.
- `add_application_table_columns`: `add_field` per new column; append names to `column_order`.
- `delete_application_table_columns`: `remove_field` per column; drop from `column_order`; delete `ApplicationTableColumn` rows.
- `delete_application_table`: `delete_model`; cascade-check empty (only allowed when 0 rows? prompt says delete app only when empty of tables; table deletion — confirm whether row-count guard applies — default: allow).

## Management command — `djangoapp/management/commands/applications.py`

Single command `applications` with argparse subparsers. Each subcommand parses via a Pydantic schema (ValidationError → printed error, non-zero exit). On success: atomic transaction, exit 0, print success + relevant info.

Subcommands (param fixes from review applied):
- `create_application_collection --name`
- `rename_application_collection --old-name --new-name` (display name only; slug unchanged)
- `delete_application_collection --name` (refuses if it contains any Application)
- `list_application_collections` (newline-separated; was `list_application_directories`)
- `list_application_collection --name` (newline-separated apps)
- `create_application --appcollection --name` (+ optional `--desc` JSON)
- `rename_application --old-appcollection --old-name --new-appcollection --new-name`
- `delete_application --appcollection --name` (refuses if it contains any ApplicationTable)
- `create_application_table` (JSON: appcollection, app, name, columns[]) + creates physical table
- `add_application_table_columns` (JSON: appcollection, app, columns[])
- `delete_application_table_columns` (JSON: appcollection, app, columns[list[str]])
- `describe_application_table --appcollection --app --name` (was missing `--app`)
- `delete_application_table --appcollection --app --name` (was missing `--app`)

## Endpoints (superuser-only) — `djangoapp/views/applications.py` + `urls.py`

- `/apps/collections` — list collections.
- `/apps/a/list?collection=<slug>` — list apps in a collection.
- `/apps/a/<collection_slug>/<app_slug>/manage` — list tables with row counts (via `application_table(...)` factory + `.count()`); render via inertia.

## README

Document each `applications` subcommand with example invocations.

## Open items to confirm during implementation

- `delete_application_table`: guard on row count (only when empty) or always allowed? Default: always allowed.
- Rich-text sanitization: nh3 allowlist mirror prevproject's if present, else a conservative default.
- Whether `/manage` needs create/edit row UI now or just read+counts (default: read + counts only this prompt; row CRUD in a later prompt).

## Pending code instructions (from code comments)

Collected from every `aihere` marker in the codebase (excluding `prevproject`, which is a reference project). Detailed plans for the dynamic-singleton and validator-split items appear further below.
- [x] `frontend/src/pages/AppList.vue:16` — `aihere` marker removed in the round-2 shared-props middleware work (it was still present when this line was first written; see "Review: follow-up findings (round 2)" §1). The hardcoded `:is-superuser="true"` it flagged is gone across all pages.
- [x] `djangoapp/tests/views/test_applications_views.py:10` — tests now parse the Inertia `data-page` payload and assert props mirror the DB (collections, apps, /manage row counts); no integer pk/id leak.
- [x] `djangoapp/management/commands/applications_schemas.py` — split each long model-validator into multiple `@model_validator(mode="after")` methods (one check each, source order). NOTE: `mode="after"` could not be dropped — pydantic 2.13 requires `mode=` (bare `@model_validator` raises `TypeError` at runtime). Plan in the "Refactor" section.
- [x] `djangoapp/management/commands/applications_schemas.py:58` — inlined the one-liner duplicate-name set comprehension at both call sites; helper removed.
- [x] `djangoapp/models/dynamic.py` — turned the `_DYNAMIC_CACHE` + functions into a `DynamicModelRegistry` class with one instance (`dynamic_models`); methods replace the functions; mutating ops expire/unregister; `get_model` is the only retrieval point. Design in the section below.
- [x] `djangoapp/models/dynamic.py` — `app_table.save(update_fields=["column_order"])`: kept `update_fields` and documented why ("Only column_order changed").
- [x] `djangoapp/views/applications.py:85` — `app_list_page` now takes the collection as a path param (`/apps/a/<collection_name>/list`); URL, Collections.vue link, README, and tests updated.
- [x] `README.md:56` — marker no longer present in code (resolved/removed).

## Design: `DynamicModelRegistry` (singleton)

Replaces the module-level `_DYNAMIC_CACHE` + loose functions in `djangoapp/models/dynamic.py`. Exactly one instance is created at module level (`dynamic_models = DynamicModelRegistry()`) and every caller uses that instance. It owns the dynamic-model cache and is the **only** way to retrieve a generated model.

### Class shape

```python
class DynamicModelRegistry:
    def __init__(self) -> None:
        # (collection_name, table_name) -> generated concrete model class
        self._cache: dict[tuple[str, str], type[BaseTable]] = {}
```

### What stays module-level (pure, no state)

These don't act on the registry, so they remain module-level functions the class calls:

- `dynamic_db_table(collection_name, table_name) -> str` — `zz_<collection>_<table>`.
- `_dynamic_class_name(collection_name, table_name) -> str` — PascalCase `CollectionTableDynamicModel`.
- per-type field builders `_char_field`/`_text_field`/`_integer_field`/`_boolean_field`/`_decimal_field`/`_datetime_field`/`_user_field`, the `_COLUMN_FIELD_BUILDERS` dispatch, and `_column_field(col)`.
- `TableNotFoundError`.

### Methods on the instance

**Retrieval (single entry point — "only way to retrieve models"):**
- `get_model(collection_name, table_name) -> type[BaseTable]` — return cached; else if a class survived in `apps.all_models["djangoapp"]`, reuse + cache it; else build + register + cache. Raises `TableNotFoundError`. This replaces the module-level `application_table(...)`.

**Build / registry plumbing (private):**
- `_build_model_class(collection_name, table_name) -> type[BaseTable]` — read the `ApplicationTable` + its `ApplicationTableColumn`s, construct a concrete model via `ModelBase(name, (BaseTable,), attrs)` with `Meta.db_table = dynamic_db_table(...)`, `app_label="djangoapp"`, one field per column; register it.
- `_existing_registered(class_name) -> type[Model] | None` — lookup in `apps.all_models["djangoapp"]`.
- `_unregister(model) -> None` — `apps.all_models[app_label].pop(model_name)` so a same-named class can be rebuilt.
- `expire_model(collection_name, table_name, model) -> None` — pop cache **and** `_unregister` (popping the cache alone is not enough: `get_model` would reuse a surviving registry entry and return a stale field set).

**Full reset (test helper / behavior change):**
- `reset() -> None` — clear `_cache` and unregister every dynamic model whose name ends with `dynamicmodel`. Replaces `reset_dynamic_models()`.

**DB resolvers (instance methods, may be static — they only read the DB, not the cache):**
- `_resolve_collection(name)`, `_resolve_application(appcollection, app)`, `_get_application_table_for(application, table_name)` — each raises `TableNotFoundError` on miss.

**Schema operations (instance methods; all wrap `transaction.atomic`; keep `column_order` in sync; expire affected models so `get_model` rebuilds):**
- `create_application_table(appcollection, app, name, columns)` — `full_clean` + save the table row, persist columns, `_build_model_class` + cache, `schema_editor.create_model`.
- `add_application_table_columns(appcollection, app, table, columns)` — per column: persist row, `field.set_attributes_from_name`, `schema_editor.add_field`; append to `column_order`; `expire_model`.
- `delete_application_table_columns(appcollection, app, table, columns)` — per column: `schema_editor.remove_field`, delete row; trim `column_order`; `expire_model`.
- `delete_application_table(appcollection, app, table)` — `schema_editor.delete_model` (tolerate `ProgrammingError`), `_unregister`, delete column rows (RESTRICT FK), delete table row.
- `rename_application_collection(collection, new_name)` — for every table under the collection: `schema_editor.alter_db_table(old, new)` then `expire_model(old_name, table.name, model)`; then rename + save the collection.

### Reset guarantees (every behavior-changing op resets affected state)

- create → builds + caches a fresh class.
- add/remove columns → `expire_model` (unregister) so the next `get_model` rebuilds with the new field set.
- rename collection → `alter_db_table` + `expire_model` per table.
- delete table → unregister + cache pop.
- `reset()` → wipes everything (tests).

### Caller migration

- `applications.py` (command): `from djangoapp.models.dynamic import dynamic_models`; call `dynamic_models.create_application_table(...)`, `dynamic_models.rename_application_collection(...)`, `dynamic_models.db_table(...)` (module-level pure fn).
- `views/applications.py`: `dynamic_models.get_model(...)`.
- tests: `dynamic_models.reset()` in setUp/tearDown; `dynamic_models.get_model(...)` for row round-trips.
- Delete the old module-level `application_table`, `_build_model_class`, `_expire_model`, `_unregister_model`, `reset_dynamic_models`, and the schema-op function aliases once callers are repointed.

# Plan: immutable physical table name `<tablename><unix-seconds>`

## Problem
The physical `db_table` (`zz_<collection>_<table>`) and generated class name (`<Collection><Table>DynamicModel`) are derived from the **current** collection/table display names. So renaming a collection (today) forces a per-table `schema_editor.alter_db_table`, and renaming a table would force a DDL rename too. We want collection/table display `name`s to be free to rename with **zero DDL** and no physical-table churn.

## Decision
Each `ApplicationTable` gets a **stable, immutable, creation-time physical name** of the form `<tablename><unix-seconds>` (the table's name-at-creation, then the current unix timestamp in seconds). Collection and table display names then rename trivially.

## Steps

### Step 1 — `ApplicationTable.physical_name` field
- New field `physical_name: CharField(max_length=200, unique=True, editable=False)`.
- Generated once at creation: `f"{name}{int(time.time())}"` (lowercased alnum — the table name is already alphanumeric-starting-with-letter, and the timestamp is digits, so the result is a valid identifier; it stays valid even if the display `name` is later renamed).
- Guard against second-granularity collisions across collections with the field's `unique=True` + a regenerate-on-collision retry (loop a few times, incrementing/re-rolling until unique).

### Step 2 — Decouple the dynamic layer from display names
- `dynamic_db_table(physical_name)` → `f"zz_{physical_name}"` (collection drops out entirely).
- `_dynamic_class_name(physical_name)` → PascalCase(`physical_name`) + `"DynamicModel"`.
- `get_model` / `_build_model_class` and all schema ops key on `table.physical_name`, **not** on `(collection_name, table_name)`.
- The registry cache key becomes `physical_name` (immutable), so display-name renames never invalidate the cache.
- The factory entrypoint still resolves the table row by display names (collection+app+table), then uses its `physical_name` for all DDL/model work.

### Step 3 — Simplify renames (the payoff)
- `rename_application_collection`: just updates `collection.name` — **no `alter_db_table`, no `reset()`**; physical names are untouched.
- Add a new `rename_application_table` command (doesn't exist today): just updates `table.name`, also zero DDL/zero reset.
- `reset()` stays only for **column** add/remove (those genuinely change the model's field set).

### Step 4 — Display-name uniqueness stays
- Display `name` remains unique within its scope (collection for tables), so name-as-identity in URLs stays consistent.
- `physical_name` is globally unique and immutable.

### Step 5 — Migration
- Add `physical_name` nullable → backfill existing rows `physical_name = name` → set non-null + unique. This feature is pre-prod (no rows expected), so backfill is trivial.

### Step 6 — Tests
- Assert `physical_name` is set at create and is immutable (survives a rename unchanged); physical table = `zz_<physical_name>`.
- Rename collection (and table) changes only the display name; the physical table and its rows are untouched (no DDL).
- Column add/remove still work and still `reset()`.

## Concerns / out of scope
- **URLs still use display names**, so renaming a collection/table still changes its URL — inherent to name-as-identity, separate from the physical-table fix; this plan does not change URL behavior.
- **Class-name collisions** in the app registry are prevented by `physical_name` global uniqueness.
- This **supersedes** the current `rename_application_collection` `alter_db_table` loop — that whole loop is removed (simpler + faster + no per-table DDL on rename).
- Column names still map directly to physical columns, so a column rename would still need DDL — there's no column-rename command today, so out of scope.

## Checklist
- [x] `ApplicationTable.physical_name` field + `<tablename><unix-seconds>` generator (unique; on collision bump the timestamp by 1 second, no suffix)
- [x] `dynamic_db_table` / `_dynamic_class_name` key on `physical_name`; cache key = `physical_name`
- [x] schema ops + factory resolve by display names, DDL via `physical_name`
- [x] `rename_application_collection` becomes a plain row update (drop the alter_db_table loop + reset)
- [x] add `rename_application_table` command (display-name only, zero DDL)
- [x] `reset()` retained only for column add/remove
- [x] migration `0007_physical_name`: add + backfill + enforce `physical_name` unique/non-null
- [x] tests: physical_name set/immutable; rename = no DDL; column ops still reset
- [x] `./run lintfix`, `./run typecheck`, `./run test` (97), `./run checkall` green

# Checklist

### Phase 1: Models + migration
- [x] `djangoapp/models/applications.py`: `ApplicationCollection`, `Application`, `ApplicationTable`, `ApplicationTableColumn`, `BaseTable` (abstract, underscore-prefixed built-in cols)
    - [x] alnum validators + `[A-Za-z][A-Za-z0-9]*` validator for column names
    - [x] unique constraints (collection name/slug; app within collection; table within collection; column within table)
    - [x] `desc` nh3-sanitization on save
    - [x] `public_id` uuid7 on all four
- [x] register in `djangoapp/models/__init__.py`
- [x] `makemigrations djangoapp` → new migration (`0004_applications`); `./run lintfix` + `./run typecheck` clean

### Phase 2: Dynamic-model factory + schema ops
- [x] `djangoapp/models/dynamic.py`: `create_application_table`, `add_application_table_columns`, `delete_application_table_columns`, `delete_application_table` via `schema_editor`, all atomic, keeping `column_order` in sync
- [x] `application_table(collection_slug, table_slug)` factory building the `CollectionTablenameDynamicModel` subclass of `BaseTable`, cached (+ `reset_dynamic_models` test helper)
- [x] unit tests: create table → physical table + columns exist; add/remove columns; column_order updated; delete table drops it

### Phase 3: Management command
- [x] `djangoapp/management/commands/applications.py` with subparsers + per-subcommand Pydantic schemas (`applications_schemas.py`)
    - [x] discriminated-union column specs (one schema per type)
    - [x] validators carry existence/clash/old≠new checks; multi-point docstrings on substantive validators
- [x] atomic transactions; success prints + exit 0; input errors print + non-zero (via `SystemExit(1)`)
- [x] tests for each subcommand (create/rename/delete/list for collection, app, table; describe; add/delete columns) incl. refusal-when-non-empty and validation cases

### Phase 4: Superuser endpoints + /manage
- [x] `djangoapp/views/applications.py`: `/apps/collections`, `/apps/a/list`, `/apps/a/<c>/<app>/manage` (superuser-only; 404 for non-superuser per AGENTS.md access rule)
- [x] inertia pages (`Collections.vue`, `AppList.vue`, `Manage.vue`) in `frontend/src/pages/` with zod schemas
- [x] `/manage` row counts via factory + `.count()`
- [x] tests: superuser sees pages, non-superuser 404, no pk/id leak, live row count

### Phase 5: README + final
- [x] README section for `applications` subcommands
- [x] `./run lintfix`, `./run typecheck`, `./run test` green (92 tests)
- [x] frontend `npm run lint:fix`, `npm run type-check`, `npm run lint` clean
- [x] `./run checkall` green end-to-end

# Refactor: split validators into sequential bare `@model_validator` methods

## Rule
- NOTE: pydantic 2.13's `model_validator` **requires** `mode=` (the signature is `(*, mode: Literal['wrap','before','after'])` with no default; bare `@model_validator` raises `TypeError: ... takes 0 positional arguments but 1 was given`). So `mode="after"` is **not** useless here — it is mandatory. Keep `@model_validator(mode="after")` on every after-validator. (An earlier note that `mode="after"` was the removable default was wrong for this version.)
- Split each long `_validate`/`_resolve`/`_no_*` model-validator into several small `@model_validator(mode="after")` methods, one per check. They run automatically in **source (definition) order**, so sequence them top-to-bottom exactly as the rules must apply.
- Each method must `return self` (or `raise ValueError`, which still surfaces as the printed non-zero-exit error — no behavior change).
- Sequential validators may share state: a resolve step sets `self._application` / `self._collection` / `self._application_table` (PrivateAttr); later clash steps read them. Order guarantees the resolve runs first.
- For inherited schemas (`AddApplicationTableColumnsSchema`/`DeleteApplicationTableColumnsSchema` extend `_TableTargetSchema`), parent validators run before child validators, so resolution precedes the child's clash checks automatically.
- Leave `@field_validator` alnum checks as-is (they already have no `mode`).

## Per-schema decomposition

- `CreateApplicationCollectionSchema._no_clash` → keep one bare `@model_validator` (`_reject_name_clash`); no split (single check).
- `RenameApplicationCollectionSchema._validate` →
    - `_reject_noop` (old_name == new_name)
    - `_resolve_collection` (sets `self._collection`)
    - `_reject_new_name_clash`
- `DeleteApplicationCollectionSchema._resolve` → `_resolve_collection` (sets `self._collection`).
- `ListApplicationCollectionSchema._resolve` → `_resolve_collection`.
- `CreateApplicationSchema._validate` →
    - `_resolve_collection` (sets `self._collection`)
    - `_reject_app_name_clash`
- `RenameApplicationSchema._validate` →
    - `_resolve_source_collection`
    - `_resolve_source_app` (sets `self._application`)
    - `_resolve_new_collection` (sets `self._new_collection`)
    - `_reject_collection_move`
    - `_reject_noop`
    - `_reject_destination_clash`
- `DeleteApplicationSchema._resolve` →
    - `_resolve_collection`
    - `_resolve_app` (sets `self._application`)
- `CreateApplicationTableSchema._validate` →
    - `_resolve_parent_application` (sets `self._application`)
    - `_reject_table_name_clash`
    - `_reject_invalid_columns` (empty list + duplicate column names)
- `AddApplicationTableColumnsSchema._no_column_clash` →
    - `_reject_empty_columns`
    - `_reject_duplicate_columns_in_payload`
    - `_reject_existing_columns`
- `DeleteApplicationTableColumnsSchema` (extends `_TableTargetSchema`) → keep `_columns_exist` as one bare `@model_validator` (table already resolved by the parent steps).
- `_TableTargetSchema._resolve_table` →
    - `_resolve_collection`
    - `_resolve_application` (sets `self._application`)
    - `_resolve_table` (sets `self._application_table`)
- `_TableLookupSchema._resolve_table` →
    - `_resolve_collection`
    - `_resolve_application`
    - `_resolve_table` (sets `self._application_table`)
- `CharColumnSpec._max_gte_min`, `TextColumnSpec._max_gte_min`, `DecimalColumnSpec._places_le_digits` → keep each as one bare `@model_validator` (single check; just drop `mode="after"`).

## Checklist
- [x] strip every `mode="after"` → bare `@model_validator` across `applications_schemas.py` (REVERTED: pydantic 2.13 requires `mode=`; bare raises `TypeError`)
- [x] decompose each `_validate`/`_resolve`/`_no_*` per the list above, sequenced top-to-bottom (kept `mode="after"`)
- [x] keep PrivateAttr state-sharing correct (resolve-before-clash order)
- [x] `./run lintfix`, `./run typecheck`, `./run test` green after the change
- [x] `./run checkall` green

# Review: post-commit findings (2026-06-30)

Findings from reviewing commit `5bd78cd` against this prompt. Ranked by severity. Implemented 2026-06-30; remaining unchecked items are accepted as-is.

## High — stale/contradictory docstrings & comments (mislead future readers)

The `physical_name` refactor decoupled physical tables from collection/table display names, but several docstrings still describe the old collection-keyed design:
- [x] `djangoapp/models/dynamic.py:4-5` — module docstring says `db_table is zz_<collection_name>_<table_name>`. It is now `zz_<physical_name>` (`dynamic_db_table`).
- [x] `djangoapp/models/dynamic.py:220` — `reset()` docstring says it's "Called after any schema mutation (create/add/remove/**rename**/delete)". Rename no longer resets by design.
- [x] `djangoapp/management/commands/applications.py:8-10` — module docstring: "renaming a collection also renames every underlying physical table." Now false.
- [x] `djangoapp/management/commands/applications.py:188-189` — `_handle_rename_application_collection` comment repeats the same false claim.
- [x] `djangoapp/management/commands/applications_schemas.py:15-19` — docstring says validators are "bare `@model_validator` methods (`mode="after"` is the default, so it is omitted)". Every validator actually uses `mode="after"` (pydantic 2.13 requires it). Contradicts both the code and the "Refactor" note above.
- [x] `djangoapp/models/dynamic.py:55-59` — `_dynamic_class_name` docstring/plan say "PascalCase from slugs"; the impl just uppercases the first char of `physical_name` (e.g. `tasks1730000000DynamicModel`). Not PascalCase.

## High — design: moving tables/apps between collections is not supported (intentional)

- [x] Keep `RenameApplicationSchema._reject_collection_move` (`applications_schemas.py:276-285`) — moving an app (and its tables) between collections is **not** a supported feature. Rewrite the rationale message: the current text ("its tables are bound to the original collection's physical table name") is stale — `physical_name` omits the collection. The real reason is app identity / URL stability (name-as-identity is scoped to a collection). The block stays; only the message is wrong.

## Medium — `IntegrityError` not handled for agent-driven robustness

- [x] `Command.handle()` (`applications.py:159-171`) catches only `PydanticValidationError`, `DjangoValidationError`, `TableNotFoundError`, `ValueError`. DB unique constraints are the last line of defense in `_handle_create_application_collection`, `_handle_create_application`, `_handle_rename_application`, and `ApplicationTable.make_physical_name`'s collision loop. Under concurrent/agent use a race or missed pre-check surfaces as a raw traceback. Catch `IntegrityError` and render via `_format_django_error`.

## Medium — `reset()` is a full wipe by design (correctness over surgical expiry)

- [x] `add_application_table_columns` / `delete_application_table_columns` call `self.reset()` (`dynamic.py:337, 369`), clearing **every** cached dynamic model. This is intentional: `reset()` is done for correctness — a broad wipe is simpler and safer than surgically invalidating one model, and the rebuild cost is acceptable. Document this explicitly in the `reset()` docstring (it already says "correctness is simpler than surgically invalidating one model"; keep/expand that note). No behaviour change expected; the original "expire_model" design in §"Design: DynamicModelRegistry" is superseded by the full-reset approach.

## Medium — `make_physical_name` second-granularity race

- [x] `ApplicationTable.make_physical_name` (`applications.py:217-222`) checks `.exists()` then the caller saves. Two concurrent `create_application_table` calls in the same second can both pass; the second `table.save()` raises `IntegrityError` inside the atomic block. Now relayed as a clean non-zero exit via the `IntegrityError` handler above; the race is no longer a traceback. (A truly race-free generator would need a DB-level unique constraint retry loop — out of scope here.)

## Low — minor inconsistencies

- [x] `RenameApplicationCollectionSchema._reject_noop` (`schemas:99-104`) is case-insensitive, but the app/table rename no-op checks use exact `==`. Names are case-sensitive everywhere else, so `Foo`→`foo` is rejected at collection level but allowed at app/table level. Pick one rule. → Made exact `==` to match app/table.
- [ ] `ApplicationTableColumn.clean` (`applications.py:281-292`) re-checks `text_max_length >= text_min_length` and decimal places, which the discriminated-union schemas already enforce. Defense-in-depth, just noting the duplication.

# Review: follow-up findings (2026-06-30, round 2)

Findings from a second review pass of commit `001f45f`. All four (#1–#4) are addressed in this pass.

## High — shared viewer props via middleware (finding #1, FIXED)

The `aihere` at `frontend/src/pages/AppList.vue:16` is still in the committed code, and the earlier checklist (line 157) marked it "resolved/removed" incorrectly. The real problem it flags is broader than one page: every Inertia page passes `user` to `<Layout>` per-view and hardcodes `:is-superuser="true"` (`Collections.vue:15`, `Manage.vue:16`, `AppList.vue:17`, `UserList.vue:68`, `UserHistory.vue:87`, `UserEdit.vue:54`), with `UserDetails.vue:15` the lone outlier using `p.viewer_is_superuser`. Hardcoding `true` is wrong: the superuser flag must reflect the actual viewer, and the viewer's profile should come from one shared source, not be threaded through every view's Pydantic props.

The fix uses Inertia's shared-props mechanism: a middleware calls `inertia.share(request, ...)` to inject props available to **every** Inertia page, which `Layout.vue` reads via `usePage().props` instead of receiving them as per-page props. The instant project previously had **no** `djangoapp/middleware.py` and nothing in `MIDDLEWARE` beyond Django defaults (`djangoproject/settings.py:58-69`).

### Plan

- Create `djangoapp/middleware.py` with one `SharedPropsMiddleware`:
    - `__init__(self, get_response)` / `__call__(self, request)`.
    - For an authenticated non-anonymous user, `inertia.share(request, user=UserProfile(public_id=user.public_id, title=user.display_name).model_dump(), viewer_is_superuser=user.is_superuser)`. For anonymous, share `user=None`, `viewer_is_superuser=False`.
    - Reuse the existing pk-free `UserProfile` (`{ public_id, title }`) from `djangoapp.models`.
- Register it in `djangoproject/settings.py` `MIDDLEWARE` after `AuthenticationMiddleware` (it reads `request.user`).
- `frontend/src/components/Layout.vue`: drop the `user` and `isSuperuser` props; read `user` / `viewer_is_superuser` from `usePage().props` (typed via a small `SharedPropsSchema` in `schemas.ts`). The "Users" link gates on `viewer_is_superuser`.
- Drop `:user` / `:is-superuser` (and the per-view `user` prop + `viewer_profile` plumbing) from every page: `Collections.vue`, `AppList.vue`, `Manage.vue`, `UserList.vue`, `UserDetails.vue`, `UserEdit.vue`, `UserHistory.vue`, and any others. Pages keep only their page-specific props.
- Backend: remove the `user` field from the per-view Pydantic props models in `djangoapp/views/applications.py` (`CollectionsProps`, `AppListProps`, `ManageProps`) and `djangoapp/views/users.py` (the list/details/edit/history props), since the viewer profile now comes from shared props.
- Remove the `aihere` comment from `AppList.vue:16` as part of the implementation (AGENTS.md: never remove an `aihere` before addressing it).
- Tests:
    - Update existing Inertia tests (`test_home.py`, the users view tests) to account for the shared `user`/`viewer_is_superuser` props and to stop asserting on the dropped page-level `user` field.
    - Add a test asserting the middleware injects the right profile for a superuser, a plain user, and an anonymous request.

### Open decisions (resolved)
- **Collapse `UserDetailsProps.viewer_is_superuser` into the shared `viewer_is_superuser`** — done. They are the same value, so the page-level field is removed; `UserDetails.vue` derives admin gating from the shared flag via `usePage()`.
- **Shared key names** — `user` (viewer profile) and `viewer_is_superuser` (flag). `viewer_is_superuser` is kept distinct from any target-user `is_superuser` page prop (e.g. `UserDetailsProps.is_superuser`), since Inertia merges shared props under page props and a bare `is_superuser` would be shadowed on the details page.

### Checklist
- [x] create `djangoapp/middleware.py` `SharedPropsMiddleware` sharing `user` + `viewer_is_superuser`
- [x] register in `MIDDLEWARE` after `AuthenticationMiddleware`
- [x] `Layout.vue` reads shared props via `usePage()`; drop `user`/`isSuperuser` props
- [x] drop `:user`/`:is-superuser` and per-view `user` prop from
    - [x] `Collections.vue` + `CollectionsProps`
    - [x] `AppList.vue` + `AppListProps`
    - [x] `Manage.vue` + `ManageProps`
    - [x] `UserList.vue` + `UserListProps`
    - [x] `UserDetails.vue` + `UserDetailsProps`
    - [x] `UserEdit.vue` + `UserEditProps`
    - [x] `UserHistory.vue` + `UserHistoryProps`
- [x] collapse `UserDetailsProps.viewer_is_superuser` into the shared `viewer_is_superuser`
- [x] remove `aihere` from `AppList.vue:16`
- [x] tests updated (`test_home`, `test_users`) + new `test_middleware.py` (superuser / plain / anonymous)
- [x] `./run lintfix`, `./run typecheck`, `./run test` (100), frontend `npm run lint:fix`/`type-check`/`lint`, `./run checkall` green

## High — README stale physical-table sentence (finding #2, FIXED)

- [x] `README.md` (applications section) first sentence says tables are named `zz_<collection_name>_<table_name>`; that is the pre-`physical_name` design. Reworded to state tables are named `zz_<physical_name>` (the next sentence already did; the lead sentence contradicted it).

## Medium — `test_no_pk_leak` only covers one endpoint (finding #3, REVERTED)

- [x] ~`djangoapp/tests/views/test_applications_views.py:test_no_pk_leak` only hit `/apps/collections`. Extended to also assert no `"id":`/`"pk":` leak on `/apps/a/<collection>/list` and `/apps/a/<collection>/<app>/manage`.~ Reverted: the test was removed entirely at the author's request. The no-leak guarantee still holds structurally (the per-view Pydantic props models declare only `name`/`row_count`, so `.model_dump()` cannot emit pk/id), but it is no longer asserted by a dedicated test.

## Medium — `describe_application_table` leaks `physical_name`/`db_table` (finding #4, FIXED)

- [x] `djangoapp/management/commands/applications.py:_handle_describe_application_table` printed `physical_name` and `db_table`. Those are internal physical-schema names; agents address tables by display name (collection/app/table), so they are dropped. Output now shows `table`, `column_order`, and the column list only.