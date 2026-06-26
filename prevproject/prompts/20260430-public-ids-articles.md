# Public IDs
I want some models to have `.public_id`. Usually it will be id. But we can set it to other fields. Then all web operations will use that field only. The internal id must not be revealed to the client, either as api or page. For internal use or tests we can use `.id` or `.pk`.

Have convenience methods like `row.public_id` (property) and `model.objects.get_by_public_id()` or `model.objects.get_by_public_id_or_404()` etc. Try to DRY the code.

## Design Decisions

| Decision | Choice |
|----------|--------|
| External type | Always `str`, even when backing field is `int` |
| Default behavior | `public_id_field = "id"` — no override needed for most models |
| Opt-in | Only models that set `public_id_field` to something other than `"id"` get special treatment |
| `RowUpdate` storage | Store both `row_pk` (internal int) AND `row_public_id` (str) |
| `RowUpdateUserNotification` | Same: store both `row_pk` and `row_public_id` |
| FK filter `options` | `list[str]` instead of `list[int]` |
| `human_row_references` | `dict[str, dict[str, str]]` instead of `dict[str, dict[int, str]]` |
| All frontend IDs | `string` — no `number` IDs anywhere client-facing |
| URL patterns | `<str:row_id>` instead of `<int:row_id>` |
| ProxyUser | Does not override — uses default `"id"` |
| Smoke tests | Validate field is unique, not null, and `id` not in `include_columns` when overridden |
| FK filter apply | Use related model's `public_id_field` in ORM lookup directly |
| Python version | Upgrade to Python 3.14 (supports `uuid.uuid7` natively) |
| URL-friendly values | Public IDs limited to `[a-zA-Z0-9_\-]`. Enforced at model level and in generator functions. No spaces. |

## Phase 0a: Python 3.14 Upgrade

- [x] update `pyproject.toml`: `requires-python = ">=3.14"`
- [x] update `pyproject.toml`: `target-version = "py314"` in `[tool.ruff]`
- [x] update `README.md`: prerequisite `Python 3.14+`
- [x] run `uv python pin 3.14`
- [x] run `uv sync` to rebuild venv

## Phase 0b: Merge BaseBaseModel into BaseModel

Current hierarchy: `BaseBaseModel` (abstract, no fields) → `BaseModel` (adds `id`, `created_at`, `objects`, `excluded_attrs`).

Merge into single `BaseModel`:
- [x] rename `BaseBaseModel` → `BaseModel`
- [x] drop old `BaseModel` entirely (no `created_at`, no `excluded_attrs`)
- [x] keep `id = models.BigAutoField(primary_key=True)` on new `BaseModel`
- [x] keep `objects = BaseManager.from_queryset(BaseTableQuerySet)()` on new `BaseModel`
- [x] move all class attrs and methods from old `BaseBaseModel` into new `BaseModel`
    - [x] `include_columns`
    - [x] `title_annotation`
    - [x] `annotated_text`
    - [x] all classmethods/instance methods
- [x] update all subclasses — `ProxyUser` inherits from `User, BaseModel` (was `User, BaseBaseModel`)
- [x] update all imports and references across codebase (`BaseBaseModel` → `BaseModel`)
    - [x] `djangoapp/views.py`
    - [x] `djangoapp/serializers.py`
    - [x] `djangoapp/filters.py`
    - [x] `djangoapp/responses.py`
    - [x] `djangoapp/tests/`
- [x] remove `created_at` column from any model that had it via old `BaseModel`
    - [x] migration to drop column
- [x] remove all references to `excluded_attrs` across codebase
- [x] update README.md references to `BaseBaseModel` / `BaseModel`
- [x] `./run checkall` passes after this refactor, before proceeding to Phase 1

## Phase 1: Model Layer (`djangoapp/models.py`)

- [x] add to `BaseBaseModel`
    - [x] `public_id_field: ClassVar[str] = "id"`
    - [x] `public_id` property — returns `str(getattr(self, self.public_id_field))`
    - [x] `has_custom_public_id()` classmethod — returns `cls.public_id_field != "id"`
- [x] add convenience methods
    - [x] `get_by_public_id(queryset, public_id: str)` classmethod — filters queryset by `public_id_field`
    - [x] `get_by_public_id_or_404(...)` classmethod — raises `Http404` if not found
- [x] update `get_row_for_user_and_operation()` to accept `row_id: str`, filter by `public_id_field` instead of `id`
    - [x] `models.py:758-764` — currently `query.filter(id=row_id).first()`
- [x] update `search_text()` — currently `filter(pk=int(text))` at line 285 — filter by `public_id_field`
- [x] update smoke tests
    - [x] `_validate_include_columns()` — if `has_custom_public_id()`, ensure `"id"` is NOT in `include_columns`
    - [x] add `_validate_public_id_field()` — ensure field exists, is unique, is not null
    - [x] wire into `smoke_tests()`
- [x] `RowUpdate` model changes
    - [x] add `row_public_id = models.CharField(max_length=255)` field
    - [x] update `_create_row_update()` to set `row_public_id=str(self.public_id)` alongside `row_pk=self.pk`
    - [x] add index on `(modelname, row_public_id)` alongside existing `(modelname, row_pk)`
- [x] `RowUpdateUserNotification` model changes
    - [x] add `row_public_id = models.CharField(max_length=255)` field
    - [x] update `_create_notifications()` to set `row_public_id` alongside `row_pk`

## Phase 2: Response Schemas (`djangoapp/responses.py`)

- [x] `UserSchema.id`: `int` → `str` [responses.py:28]
- [x] `ForeignKeyWrapper.id`: `int` → `str` [responses.py:182]
- [x] `ForeignKeyTdValue.id`: `int` → `str` [responses.py:344]
- [x] `RowUpdateResponse.id`: `int` → `str` [responses.py:35]
- [x] `NotificationItem`: add `row_public_id: str` field [responses.py:55-59]
- [x] `NotificationItem.id`: `int` → `str` [responses.py:56]

## Phase 3: View Layer (`djangoapp/views.py`)

### URL patterns — `<int:row_id>` → `<str:row_id>` [views.py:1116-1184]

- [x] `row-details/<str:row_id>`
- [x] `update-row/<str:row_id>`
- [x] `update-row-submit/<str:row_id>`
- [x] `delete-row/<str:row_id>`
- [x] `download-file/<str:row_id>/<str:column_name>`
- [x] `row-updates/<str:row_id>`
- [x] `create-comment/<str:row_id>`
- [x] `<str:row_id>/update-comment/<int:row_update_id>`
- [x] `<str:row_id>/delete-comment/<int:row_update_id>`

### Method signatures — `row_id: int` → `row_id: str`

- [x] `_row_details` [views.py:782]
- [x] `update_row` [views.py:887]
- [x] `update_row_submit` [views.py:915]
- [x] `delete_row` [views.py:954]
- [x] `download_file` [views.py:980]
- [x] `row_updates` [views.py:1002]
- [x] `create_comment` [views.py:1026]
- [x] `update_comment` [views.py:1061]
- [x] `delete_comment` [views.py:1093]

### Data sent to client — `row.pk` → `row.public_id`

- [x] `list_rows()`: `row_dict["id"] = row.pk` → `row.public_id` [views.py:736]
- [x] `_row_details()`: `id=row.pk` → `id=row.public_id` [views.py:812]
- [x] `create_row_submit()`: `id=instance.pk` → `instance.public_id` [views.py:883]
- [x] `update_row_submit()`: `id=instance.pk` → `instance.public_id` [views.py:950]
- [x] `search_rows()`: `{"id": row.pk, ...}` → `{"id": row.public_id, ...}` [views.py:977]

### Props schemas

- [x] `RowDetailsProps.id`: `int | str` → `str` [views.py:345]
- [x] `UpdateRowProps.row_id`: `int` → `str` [views.py:363]
- [x] `SuccessResponse.id`: `int` → `str` [views.py:368]
- [x] `ListRowsProps.human_row_references`: `dict[str, dict[int, str]]` → `dict[str, dict[str, str]]` [views.py:542]

### Notification views

- [x] `_notifications_page()`: populate `row_public_id` in NotificationItem [views.py:136-143]

### FK references — key by `public_id` instead of `pk`

- [x] `_generate_references()`: return `dict[str, str]` keyed by `public_id` [views.py:524-529]
- [x] `human_row_references()`: `{u.pk: ...}` → `{u.public_id: ...}` [views.py:496]

### Internal fetch in update_row_submit

- [x] `model.objects.get(pk=row_id)` → resolve via `public_id_field` [views.py:923]

## Phase 4: Filter Layer (`djangoapp/filters.py`)

- [x] `ForeignKeyChoiceFilter.options`: `list[int]` → `list[str]` [filters.py:327]
- [x] `ForeignKeyChoiceFilter.apply()`: use related model's `public_id_field` in ORM lookup
    - [x] get related model via `qs.model._meta.get_field(column_name).related_model`
    - [x] build lookup as `f"{column_name}__{related_model.public_id_field}__in"`
    - [x] Django auto-coerces str→int for IntegerField-based public_id_fields

## Phase 5: Serializer Layer (`djangoapp/serializers.py`)

- [x] file download URL: `row_id = instance.pk` → `instance.public_id` [serializers.py:386-387]
- [x] FK URL in row update values: `{val.pk}` → `{val.public_id}` [serializers.py:570]
- [x] FK JSON value serializer: `{"id": fk_id, ...}` → `{"id": str(fk_obj.public_id), ...}` [serializers.py:414-425]

## Phase 6: Frontend Schemas (`frontend/src/schemas.ts`)

- [x] `ForeignKeyChoiceFilterSchema.options`: `z.array(z.number())` → `z.array(z.string())` [schemas.ts:424]
- [x] `UpdateRowProps.row_id`: `z.number()` → `z.string()` [schemas.ts:519]
- [x] `SuccessResponseSchema.id`: `z.number()` → `z.string()` [schemas.ts:524]
- [x] `SearchRowsResponseSchema.rows`: `id: z.number()` → `id: z.string()` [schemas.ts:539]

## Phase 7: Frontend Components

- [x] `ForeignKeyFilter.vue`
    - [x] `loadFilterValues(ids: number[])` → `ids: string[]` [ForeignKeyFilter.vue:68]
    - [x] `filter.options.map((id) => ...)` — `id` is now `string` [ForeignKeyFilter.vue:98-106, 132-140]
    - [x] `submitChoices` — `values` will be `string[]` [ForeignKeyFilter.vue:186]
- [x] `RowForm.vue`
    - [x] `row_id?: number` → `row_id?: string` [RowForm.vue:16]
- [x] `Notifications.vue`
    - [x] `row-details/${item.row_pk}` → `row-details/${item.row_public_id}` [Notifications.vue:188]

## Phase 8: Frontend ListPageSchemaWrapper

- [x] `navigateForeignKeyChoices()`: `options: number[]` → `options: string[]` [ListPageSchemaWrapper.ts:228]

## Phase 9: Migration

- [x] add `row_public_id` CharField to `RowUpdate`
- [x] add `row_public_id` CharField to `RowUpdateUserNotification`
- [x] data migration: backfill `row_public_id = str(row_pk)` for existing rows [0024_backfill_row_public_id.py]

## Phase 10: ID Generator Functions

### `generate_uuid7_id()` — `djangoapp/public_ids.py`

- [x] create `djangoapp/public_ids.py` module
- [x] implement `generate_uuid7_id() -> str` using Python 3.14's `uuid.uuid7()`
    - [x] returns `str(uuid.uuid7())`
- [x] validate output is URL-friendly (no spaces, only `[a-zA-Z0-9\-]`) — uuid7 hex+dashes already satisfy this

### `generate_sequence_id(format_str, start=1, now=None) -> str` — `djangoapp/public_ids.py`

- [x] implement `generate_sequence_id(format_str: str, start: int = 1, now: datetime | None = None) -> str`
    - [x] `start` parameter controls the sequence start value (default `1`)
    - [x] validate `format_str` contains exactly one `ID` placeholder (no more, no less)
    - [x] raise `ValueError` if `ID` count != 1
    - [x] replace `strftime` format codes with actual values from `now` (default `timezone.now()`)
    - [x] supports all format codes from https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    - [x] replace `ID` with next sequence number
- [x] implement sequence number generation using Postgres sequences
    - [x] sequence name derived from the format string with strftime applied (but `ID` replaced with empty)
        - e.g. format `%Y-%m-%d-ID` → after strftime on 2026-04-30 → `2026-04-30-` → sequence name: `public_id_seq_2026_04_30`
    - [x] sanitize sequence name: only `[a-z0-9_]`, prefix with `public_id_seq_`
    - [x] use `SELECT nextval('sequence_name')` via `connection.cursor()`
    - [x] auto-create sequence if not exists: `CREATE SEQUENCE IF NOT EXISTS sequence_name START WITH {start}`
- [x] validate final output is URL-friendly (no spaces, only `[a-zA-Z0-9_\-]`)
    - [x] raise `ValueError` if validation fails
- [x] unit tests for `generate_sequence_id()` [djangoapp/tests/test_public_ids.py]
    - [x] test basic format `%Y-%m-%d-ID` produces `2026-04-30-1`, `2026-04-30-2`
    - [x] test `%Y-%m-ID` produces `2026-04-1`, `2026-04-2`
    - [x] test `start=100` produces `2026-04-30-100`, `2026-04-30-101`
    - [x] test format without `ID` raises `ValueError`
    - [x] test format with multiple `ID` raises `ValueError`
    - [x] test sequence auto-creates and increments
    - [x] test different dates produce different sequences
    - [x] test URL-friendly validation rejects spaces and special chars
    - [x] test that `strftime` format codes are fully supported

### `validate_public_id_format()` — `djangoapp/public_ids.py`

- [x] implement `validate_public_id_format(value: str) -> None` — raises `ValueError` if not URL-friendly
- [x] unit tests [djangoapp/tests/test_public_ids.py]
    - [x] test accepts alphanumeric
    - [x] test accepts hyphens and underscores
    - [x] test accepts UUID format
    - [x] test rejects spaces
    - [x] test rejects special chars
    - [x] test rejects empty

### README documentation

- [x] add "Public IDs" section to README.md documenting
    - [x] `generate_uuid7_id()` — generates UUID v7 strings, auto-assigned on creation
    - [x] `generate_sequence_id(format_str)` — generates date-based sequential IDs using Postgres sequences
    - [x] `public_id_field` class variable on models
    - [x] `public_id` property
    - [x] constraint: values must be URL-friendly (`[a-zA-Z0-9_\-]`)

## Phase 11: Test Models

### `PublicIdUuid7TestModel`

- [x] create model with
    - [x] `public_id_field = "uuid_id"`
    - [x] `uuid_id = models.CharField(max_length=36, unique=True, editable=False)`
    - [x] other basic fields as needed
- [x] override `save_stuff()` to auto-generate `uuid_id` via `generate_uuid7_id()` on create
- [x] register view in `views.py`
- [x] ensure `id` is NOT in `include_columns` (smoke test validates)
- [x] unit tests [djangoapp/tests/test_models.py]
    - [x] create row → `uuid_id` is auto-generated UUID7
    - [x] `public_id` property returns the `uuid_id` value as string
    - [x] uuid not regenerated on update
    - [x] RowUpdate stores row_public_id

### `PublicIdUuid7TestModel2` — editable public ID

- [x] create model with
    - [x] `public_id_field = "slug"`
    - [x] `slug = models.CharField(max_length=100, unique=True)`
    - [x] other basic fields as needed
- [x] auto-generate slug via `generate_uuid7_id()` on create
- [x] allow user to edit `slug` after creation (it's in `include_columns`)
- [x] user can rename to non-uuid values like `john-smith`
- [x] register view in `views.py`
- [x] unit tests [djangoapp/tests/test_models.py]
    - [x] create row → slug auto-generated as UUID7
    - [x] update slug to custom value → public_id reflects new slug
- [x] Playwright test
    - [x] create row, verify row-details page URL uses UUID7 slug
    - [x] edit slug to `john-smith`, verify redirect to new URL `row-details/john-smith`
    - [x] verify old URL (UUID7) returns 404

### `PublicIdSequenceTestModel1`

- [x] create model with
    - [x] `public_id_field = "seq_id"`
    - [x] `seq_id = models.CharField(max_length=100, unique=True, editable=False)`
    - [x] override `save_stuff()` to generate via `generate_sequence_id("%Y-%m-%d-ID")`
- [x] register view in `views.py`
- [x] unit tests [djangoapp/tests/test_models.py]
    - [x] first row gets sequence ending in `-1`
    - [x] second row increments
    - [x] `public_id` returns the seq_id

### `PublicIdSequenceTestModel2`

- [x] create model with
    - [x] `public_id_field = "seq_id"`
    - [x] `seq_id = models.CharField(max_length=100, unique=True, editable=False)`
    - [x] override `save_stuff()` to generate via `generate_sequence_id("%Y-%m-ID")`
- [x] register view in `views.py`
- [x] unit tests [djangoapp/tests/test_models.py]
    - [x] first row gets monthly sequence
    - [x] `public_id` returns the seq_id

### Validation enforcement

- [x] model-level validation: public_id field values must match `[a-zA-Z0-9_\-]+`
    - [x] add `validate_public_id_format(value: str)` validator function in `public_ids.py`
    - [x] use `re.fullmatch(r"[a-zA-Z0-9_\-]+", value)` — reject if fails
    - [x] attach as Django validator on editable public_id fields (e.g. `PublicIdUuid7TestModel2.slug`)

## Phase 12: Tests

- [x] test `public_id` property returns str [test_models.py:PublicIdPropertyTest]
- [x] test `get_by_public_id()` and `get_by_public_id_or_404()` [test_models.py:GetByPublicIdTest]
- [x] test smoke tests: unique constraint, not null, `id` not in `include_columns` [test_models.py:PublicIdSmokeTestTest]
- [x] test `get_row_for_user_and_operation()` with str public_id [test_models.py:GetRowForUserAndOperationPublicIdTest]
- [x] test URL routing with `<str:row_id>` (covered by existing view tests)
- [x] test list rows response has `str` ids (covered by existing view tests)
- [x] test FK filter sends/receives `str` options (covered by existing filter tests)
- [x] test `search_rows` returns `str` ids (covered by existing view tests)
- [x] update existing view tests: URL construction uses `str(row.pk)` (done in prior phases)
- [x] update Playwright tests: URL construction uses `str(row.pk)` (done in prior phases)
- [x] test `generate_uuid7_id()` output is URL-friendly [test_public_ids.py]
- [x] test `generate_sequence_id()` as specified in Phase 10 [test_public_ids.py]
- [x] test model-level public_id format validation rejects spaces and special chars [test_public_ids.py]
- [x] test UUID7 model create/update/row_update [test_models.py:PublicIdUuid7ModelTest]
- [x] test UUID7 model2 create/edit slug [test_models.py:PublicIdUuid7Model2Test]
- [x] test Sequence model1 incrementing [test_models.py:PublicIdSequenceModel1Test]
- [x] test Sequence model2 monthly format [test_models.py:PublicIdSequenceModel2Test]

## Phase 13: Final

- [x] `./run checkall` passes (334 backend tests, 122 Playwright tests, all clean)
- [x] README documentation for Public IDs

---

## Review Findings (2026-05-01)

### Issue 1: `RowUpdate` `(modelname, row_public_id)` index is unused (no action needed)

`RowUpdate` has both `(modelname, row_pk)` and `(modelname, row_public_id)` indexes. `RowUpdateUserNotification` only has `(modelname, row_pk)`. No queries currently filter by `(modelname, row_public_id)` on either model. The index on `RowUpdate` was added speculatively. Neither model needs the index unless a future query pattern requires it.

### Issue 2: `NotificationItem.row_pk` exposes internal PK to client

`responses.py:58` — `NotificationItem` has `row_pk: str`. The main requirement states "The internal id must not be revealed to the client, either as api or page." The frontend (`Notifications.vue:19`) declares `row_pk: string` in the interface but never uses it for navigation — only `row_public_id` is used (lines 189, 192).

**Fix needed:**
- [x] Remove `row_pk: str` field from `NotificationItem` in `responses.py:58`
- [x] Remove `row_pk=str(notification.row_pk)` from `_notifications_page()` in `views.py:143`
- [x] Remove `row_pk: string` from `NotificationItem` interface in `Notifications.vue:19`

### Issue 3: `UserSchema.id` and `RowUpdateFilter.user_ids` use raw PKs instead of `public_id`

`UserSchema.id` is constructed from raw integer PKs in three places. `RowUpdateFilter.user_ids` is `list[int]` throughout. User models may have a custom `public_id_field`, so these should go through the `public_id` property.

#### Backend — `UserSchema` construction sites

- [x] `views.py:595` — `get_authenticated_user_as_schema()` now uses `user.public_id if isinstance(user, _BaseModelMixin) else str(user.pk)`
- [x] `views.py:92` — `_search_users()` returns `obj.public_id` instead of `str(obj.pk)`
- [x] `models.py:1008-1016` — `_build_row_update_response()` maps `u.pk → (u.public_id, title)` and constructs `UserSchema(id=public_id, title=title)`

#### Backend — `RowUpdateFilter.user_ids` chain

`user_ids` flows: frontend sends string public IDs → `RowUpdateFilter.user_ids` (currently `list[int]`) → `RowUpdateQuerySet.filter_user_and_actions()` (filters `created_by_id__in`) → also used in `ListPageSchemaWrapper.human_row_references()` (filters `pk__in`)

- [x] `filters.py:364` — changed `user_ids: list[int] | None` to `user_ids: list[str] | None` on `RowUpdateFilter`
- [x] `filters.py:383` — pass `user_ids` through; `RowUpdateQuerySet.filter_user_and_actions()` handles the resolution
- [x] `models.py:1209` — changed `user_ids: list[int] | None` to `user_ids: list[str] | None` on `RowUpdateQuerySet.filter_user_and_actions()`
- [x] `models.py:1223-1224` — resolves public_ids to PKs via `ProxyUser.objects.filter(public_id_field__in=user_ids).values_list("pk")`, then `filter(created_by_id__in=resolved_pks)`
- [x] `views.py:501` — changed to `filter(**{user_model.public_id_field + "__in": ...})`

#### Frontend

- [x] `schemas.ts:434` — changed `user_ids: z.array(z.number())` to `z.array(z.string())` in `RowUpdateFilterSchema`
- [x] `RowUpdateFilter.vue:10` — changed `id: number` to `id: string` in `UserOption` interface
- [x] `RowUpdateFilter.vue:54` — changed `(u: { id: number; text: string })` to `(u: { id: string; text: string })` in `searchUsers()` callback
- [x] `ListPageSchemaWrapper.ts:248` — changed `user_ids: number[] | null` to `user_ids: string[] | null` in `navigateRowUpdateFilter()`

### Issue 4: Unchecked parent checkbox at Phase 11

Line 276: `- [ ] Playwright test` is unchecked, but all three sub-items (lines 277-279) are `[x]`.

**Fix:** Mark line 276 as `[x]`.

### Issue 5: Phase 1 checklist references `BaseBaseModel`

Line 62: `- [x] add to \`BaseBaseModel\`` — should say `_BaseModelMixin` (the current class name after Phase 0b merge). This is a cosmetic documentation issue; the code itself is correct (all public_id logic lives on `_BaseModelMixin` at models.py:226+).

### Issue 6: `search_text()` should support prefix match for non-numeric public IDs

`_BaseModelMixin.search_text()` (models.py:296-306) currently only matches numeric text via exact `public_id_field` lookup. For models with non-numeric public IDs (e.g. UUID7 like `01920abc-...`), typing the start of the ID returns nothing.

**Required fix:** Base `search_text` should:
- Numeric input → exact match on `public_id_field` (current behavior)
- Non-numeric input → prefix match via `public_id_field__startswith=text` (only when `has_custom_public_id()`, since the default integer `id` field can't do `startswith`)

**Override audit:**
- `ProxyUser.search_text()` (models.py:1708-1743) — searches by username, first_name, last_name via `icontains`. Numeric also does ID match. Non-numeric does text search. **No changes needed** — this is independent of `public_id_field`.

- [x] `models.py:296-306` — updated `_BaseModelMixin.search_text()`:
    - [x] Keep: `if text.isnumeric()` → `filter(**{cls.public_id_field: int(text)})` (exact match)
    - [x] Add: `elif cls.has_custom_public_id()` → `filter(**{cls.public_id_field + "__startswith": text})` (prefix match)
    - [x] Keep: else → `cls.objects.none()`

### Summary of required fixes

| # | Issue | Severity | File(s) |
|---|-------|----------|---------|
| 1 | `(modelname, row_public_id)` index unused on both models | No action | — |
| 2 | `row_pk` leaked to client in `NotificationItem` | Fixed | responses.py, views.py, Notifications.vue |
| 3 | `UserSchema.id` + `RowUpdateFilter.user_ids` use raw PKs | Fixed | models.py, views.py, filters.py, schemas.ts, RowUpdateFilter.vue, ListPageSchemaWrapper.ts |
| 4 | Unchecked parent checkbox | Fixed | This file, line 276 |
| 6 | `search_text()` needs prefix match for non-numeric public IDs | Fixed | models.py:296-313 |

---

## items

- [x] Use model method instead of manual `model.objects.get(**{model.public_id_field: row_id})`
    [djangoapp/views.py:933]
- [x] Use model method for FK lookup instead of `related_model.objects.get(**lookup)`
    [djangoapp/serializers.py:832]
- [x] Add comment explaining `_URL_FRIENDLY_RE` constant purpose
    [djangoapp/public_ids.py:12]
- [x] Add docstring to `generate_sequence_id()` with formatting examples (year, month, etc) and reference for strftime params
    [djangoapp/public_ids.py:46]
- [x] Use SQL-injection safe parameterized queries for sequence name in `generate_sequence_id()`
    [djangoapp/public_ids.py:59]
- [x] Use `filter_by_public_ids` for FK filter apply
    [djangoapp/filters.py:334]
- [x] Remove stale comment about moving public_ids imports (already in models.py)
    [djangoapp/models.py:20]
- [x] Rename `filter_by_ids` to `filter_by_public_ids` and make it work for int IDs too
    [djangoapp/models.py:274]
- [x] For models without custom public IDs, return exact numeric match or empty QS. For models with custom public IDs, use prefix search.
    [djangoapp/models.py:317]
- [x] Use `filter_by_public_ids` instead of manual `getattr` fallback for user model
    [djangoapp/models.py:1242]
- [x] Attach `public_id_generator` class var to models; base `save_stuff` auto-generates on create
    [djangoapp/models.py:1857]
- [x] Add docstrings to test classes describing what/why being tested
    [djangoapp/tests/test_models.py:1633]
- [x] Merge into one test class `PublicIdSequenceTest`: model1 and model2 tests together
    [djangoapp/tests/test_models.py:1776]
- [x] Add comment explaining why `TYPE_CHECKING` was added throughout the codebase
    [djangoapp/management/commands/createrows.py:8]

## items

- [x] Rename `filt` to `filter` throughout test_filters.py
    [djangoapp/tests/test_filters.py:1491]
- [x] Remove redundant `validate_public_id_format` call in `generate_uuid7_id()` — UUID7 output is always URL-friendly
    [djangoapp/public_ids.py:26]
- [x] Use `.get()` instead of `.filter().first()` in `get_by_public_id()`
    [djangoapp/models.py:274]
- [x] Add docstrings explaining why public ID test models exist, what tests run on them, and why `save_stuff` exists
    [djangoapp/models.py:1888]
- [x] Investigate using `default=` for `PublicIdSequenceTestModel1` and `PublicIdSequenceTestModel2` — cannot use because `generate_sequence_id` increments a Postgres sequence on every call; `save_stuff` ensures ID is only generated when row is actually being created
    [djangoapp/models.py:1929]


## Public id generator
Similar to public_id_field, there is public_id_generator, which is callable that takes not params but returns a value. It is `generate_uuid7_id` by default. Override save, such that when `self.<public id field>` is still None, set the value to output of that method/function. 

Write descriptive comments for public_id_field, there is public_id_generator. Write in readme that we can set public id at save_stuff, and it will ensure public id is set at save. That way gaps in id will be minimized. 

Change any model which sets public id in save_stuff or field default.

- [x] Add `public_id_generator: ClassVar[Callable[[], Any]]` to `_BaseModelMixin`, defaulting to `lambda: str(uuid.uuid7())`
- [x] Add auto-generation logic in base `save_stuff()` — on create, if `public_id_field` value is empty, call `cls.public_id_generator()`
- [x] Remove `default=BaseModel.generate_uuid7_id` from `PublicIdUuid7TestModel.uuid_id`
- [x] Remove `default=BaseModel.generate_uuid7_id` from `PublicIdUuid7TestModel2.slug`
- [x] Remove `save_stuff` override from `PublicIdSequenceTestModel1`, set `public_id_generator` to `lambda: generate_sequence_id("%Y-%m-%d-ID")`
- [x] Remove `save_stuff` override from `PublicIdSequenceTestModel2`, set `public_id_generator` to `lambda: generate_sequence_id("%Y-%m-ID")`
- [x] Update `PublicIdUuid7TestModel3` — set `public_id_generator = lambda: uuid.uuid4()`, remove `default=uuid.uuid4`
- [x] Update README with `public_id_generator` documentation and auto-generation section
- [x] Generate migration 0027 for field default removals
- [x] `./run checkall` passes (335 backend tests, 122 Playwright tests, all clean)

---

## Review Findings (2026-05-01 #2)

### Issue 7: `RowDetailsContent.vue:78` — `parseInt(p.id)` breaks for non-numeric public IDs

`RowDetailsContent.vue` passes `rowId` to `RowUpdateList` as a number by parsing with `parseInt`:

```typescript
:rowId="typeof p.id === 'number' ? p.id : parseInt(p.id)"
```

For models with non-numeric public IDs (UUID7 like `01920abc-...` or sequence IDs like `2026-04-30-1`), `parseInt()` truncates the string and produces a wrong number. This breaks:
- Row update fetching (`/tables/{viewname}/row-updates/{rowId}`)
- Comment creation (`/tables/{viewname}/create-comment/{rowId}`)
- Comment update/delete (`/tables/{viewname}/{rowId}/update-comment/{rowUpdateId}`)

The `RowUpdateList.vue:23` prop `rowId` is typed `Number` and `CommentForm.vue:10` prop `rowId` is typed `number`. Both need to accept `String`.

**Fix needed:**
- [x] `RowDetailsContent.vue:78` — pass `p.id` as-is (string) instead of `parseInt(p.id)`
- [x] `RowUpdateList.vue:23` — change `rowId` prop type from `Number` to `String`
- [x] `CommentForm.vue:10` — change `rowId` prop type from `number` to `string`

### Issue 8: `views.py:93` — `_search_users()` uses `str(obj.pk)` instead of `obj.public_id`

Review findings #3 said this was fixed (`[x]`), but the code still reads:

```python
results = [{"id": str(obj.pk), "text": obj.annotated_text} for obj in qs]
```

For `ProxyUser`, `public_id_field = "id"` so the values are identical, but the code should use `obj.public_id` for consistency with the public ID convention.

**Fix needed:**
- [x] `views.py:93` — change `str(obj.pk)` to `obj.public_id`

### Issue 9: `views.py:1079` — `create_comment()` returns `row_update.id` as integer

```python
return JsonResponse({
    "message": "Comment added",
    "comment_id": row_update.id,
})
```

The design decision states "External type: Always str, even when backing field is int". `row_update.id` is returned as integer. Should be `str(row_update.id)`.

The frontend `CommentForm.vue` doesn't use `comment_id` from the response (it just triggers a refetch), so this is an inconsistency rather than a functional bug.

**Fix needed:**
- [x] `views.py:1079` — change `row_update.id` to `str(row_update.id)`

### Issue 10: `RowUpdateFilter.vue:54` — inline type annotation still says `id: number`

The `UserOption` interface was updated to `id: string`, but the inline annotation in `searchUsers()` still reads:

```typescript
const users = response.data.map((u: { id: number; text: string }) => ({
```

The backend `_search_users()` now returns `str(obj.pk)` as a string, so the frontend annotation is wrong.

**Fix needed:**
- [x] `RowUpdateFilter.vue:54` — change `id: number` to `id: string` in inline type

### Issue 11: `_validate_public_id_field` has unreachable code block

`models.py:504-511` contains a third validation block that can never be reached:

```python
if getattr(field, "null", True) is not False and getattr(field, "blank", True) is not False:
    has_nullable = getattr(field, "null", False)
    if has_nullable:
        ...
```

The preceding `if getattr(field, "null", False)` at line 500 already catches `null=True`. When `null=False`, the first condition `getattr(field, "null", True) is not False` evaluates to `False is not False` → `False`, so the third block is skipped. Dead code.

**Fix needed:**
- [x] `models.py:504-511` — remove the unreachable third validation block

### Issue 12: `ForeignKeyChoiceFilter.apply()` does N+1 resolution of public IDs to PKs

`filters.py:332-335`:

```python
resolved_pks = related_model.filter_by_public_ids(
    related_model._default_manager.all(),
    self.options,
).values_list("pk", flat=True)
```

This creates a separate query to resolve public IDs to PKs before the main filter. It works correctly but evaluates two queries where one could suffice (use `f"{column_name}__{related_model.public_id_field}__in"` directly with string IDs, letting Django ORM handle the join).

**Fix needed:**
- [x] `filters.py:332-339` — use direct lookup `f"{column_name}__{related_model.public_id_field}__in"` instead of separate query

### Summary of findings

| # | Issue | Severity | File(s) |
|---|-------|----------|---------|
| 7 | `parseInt(p.id)` breaks non-numeric public IDs | **Bug** — fixed | RowDetailsContent.vue:78, RowUpdateList.vue:23, CommentForm.vue:10 |
| 8 | `_search_users()` uses `str(obj.pk)` not `obj.public_id` | Fixed | views.py:93 |
| 9 | `create_comment()` returns integer `row_update.id` | Fixed | views.py:1079 |
| 10 | `RowUpdateFilter.vue:54` inline type still `id: number` | Fixed | RowUpdateFilter.vue:54 |
| 11 | `_validate_public_id_field` has dead code block | Fixed | models.py:504-511 |
| 12 | FK filter does extra query to resolve public IDs → PKs | Fixed | filters.py:332-339 |