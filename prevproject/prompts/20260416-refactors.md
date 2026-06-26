# Set 1
Have a common Sweetalert module and import from there only. Try to have DRY function with message params.

Dont send username to frontend at all - only id and title. Check all places.

Implement package age for uv and npm https://news.ycombinator.com/item?id=47513932

Update mypy to latest

Allow long comments and docstring
[tool.ruff.lint.pycodestyle]
max-doc-length = 200
ignore-overlong-task-comments = true

This is to avoid the E501 exemptions
`djangoapp/models.py:1507: error: Couldn't resolve related manager 'rowupdate_set' for relation 'djangoapp.models.RowUpdate.created_by'.  [django-manager-missing]  # noqa: E501, W505 let comments exceed line width`

In tests, have a playwright dir. Copy test_playwright there twice. One should be test_playwright, other is test_notifications. Latter file should retain notification tests.

Text with html, and changes too. Overflow if too long.

Text field renders in table cell, details, updates in row details and notification. For cell, have an expand button if overflow. For others, have a max height and scroll bar.

---

## Detailed Plan

### Phase 1: Common SweetAlert Module [sweetalert-module]

Three components duplicate `Swal.mixin()` and `Swal.fire()` patterns:
- `frontend/src/pages/Notifications.vue:6,41,105` — imports Swal, creates `Toast` mixin, uses `Swal.fire()` for confirm
- `frontend/src/components/RowUpdateList.vue:5,32,70` — same pattern
- `frontend/src/pages/RowDetails.vue:4,18,27` — same pattern

#### 1.1 Create `frontend/src/utils/sweetalert.ts`
- Export a `showToast(type, title)` function wrapping `Swal.mixin({ toast, position, ... }).fire()`
- Export a `showConfirm(options: { title, text?, icon? })` function wrapping `Swal.fire()` and returning `result.isConfirmed`
- Remove direct `Swal` imports from all three components
- Import and use the shared functions instead

#### 1.2 Update components
- `Notifications.vue` — replace Swal import and Toast with `showToast`/`showConfirm`
- `RowUpdateList.vue` — same
- `RowDetails.vue` — same

---

### Phase 2: Replace `username` with `title` in UserSchema [username-to-title]

Backend `UserSchema` (in `responses.py` and `serializers.py`) currently sends `{id, username}`. The `title` is computed via `ProxyUser.title_annotation` (first_name + last_name, falling back to username). Change to send `{id, title}` instead.

#### 2.1 Backend — Update `UserSchema` in `djangoapp/responses.py:13-17`
- Rename field `username` → `title`
- `UserSchema` becomes: `id: int`, `title: str`

#### 2.2 Backend — Update `UserSchema` in `djangoapp/serializers.py:55-57`
- Same change: `username` → `title`

#### 2.3 Backend — Update `user_schema_from_id` in `djangoapp/models.py:935-938`
- `UserSchema(id=user_id, username=user_map[user_id])` → `UserSchema(id=user_id, title=user_map[user_id])`
- The `user_map` already uses `title_annotation`, so the value is correct

#### 2.4 Backend — Update `get_authenticated_user_as_schema` in `djangoapp/views.py:568-571`
- `UserSchema(id=request.user.id, username=request.user.username)` → use `title_annotation` or compute title inline
- Need to compute the title the same way `ProxyUser.title_annotation` does: `Coalesce(Trim(first_name + " " + last_name), username)`

#### 2.5 Frontend — Update `UserSchema` in `frontend/src/schemas.ts:18-19`
- Change `username: z.string()` → `id: z.number(), title: z.string()`
- Update `User` interface at line 27-29: `{ id: number; title: string }`

#### 2.6 Frontend — Update all `.username` references
- `Layout.vue:34` — `user.username` → `user.title`
- `RowDetails.vue:84` — `p.user?.username` → `p.user?.title`
- `RowUpdateList.vue:183` — `update.created_by.username` → `update.created_by.title`
- `RowUpdateComment.vue:120` — `update.edited_by.username` → `update.edited_by.title`
- `Notifications.vue:23,210` — `username` → `title`
- `RowUpdateFilter.vue:12,54,96,110,207,208` — `username` → `title`

#### 2.7 Backend — Update tests
- `test_views.py` — update assertions that check `username` field in responses (e.g., lines 367, 441-443, 452, 708)
- `test_models.py` — update assertions checking `created_by.username` (e.g., lines 1152, 1482, 1495, 1564)
- `test_playwright.py` — update assertions checking username display (e.g., lines 3098-3109)

---

### Phase 3: Upgrade Django 6.0, django-stubs 6.0, mypy 1.20 [django-mypy-upgrade]

Current versions → target versions:
- `django>=5.2.6` → `django>=6.0`
- `django-stubs[compatible-mypy]>=5.2.7` → `django-stubs[compatible-mypy]>=6.0.2`
- `mypy>=1.18` → `mypy>=1.20`

Version compatibility matrix (from django-stubs README):
- django-stubs 6.0.2 supports mypy 1.13–1.20, Django 6.0 (partial: 5.2, 5.1, 5.0), Python 3.10–3.14
- Our project uses Python 3.13, so all versions are compatible

#### 3.1 Update `pyproject.toml` dependency versions
- `django>=5.2.6` → `django>=6.0`
- `django-stubs[compatible-mypy]>=5.2.7` → `django-stubs[compatible-mypy]>=6.0.2`
- `mypy>=1.18` → `mypy>=1.20`

#### 3.2 Django 6.0 breaking changes to audit

From the Django 6.0 release notes, the following may affect this project:

- **`DEFAULT_AUTO_FIELD` now defaults to `BigAutoField`**: Our `settings.py` does NOT set this. Django 6.0 changes the default from `AutoField` to `BigAutoField`. If our migrations were created without this setting, existing auto-generated PKs are already `AutoField`. We should add `DEFAULT_AUTO_FIELD = "django.db.models.AutoField"` to settings to preserve existing behavior, OR accept the new default and note that only new models without explicit PK will use `BigAutoField`.

- **Custom ORM expressions must return params as tuple**: The `as_sql()` method should return `tuple[str, tuple]` not `tuple[str, list]`. Grep for `as_sql` in our codebase — if we have custom lookups/expressions, update them.

- **`Field.pre_save()` may be called multiple times**: Our custom `pre_save` implementations (if any) must be idempotent.

- **`Model.NotUpdated` exception**: `Model.save()` now raises `Model.NotUpdated` (a subclass of `DatabaseError`) instead of generic `DatabaseError` when a forced update affects no rows. If we catch `DatabaseError` anywhere for this purpose, update to catch `NotUpdated`.

- **`GeneratedField` fields refreshed after `save()`**: On PostgreSQL, generated fields are now refreshed via `RETURNING` after `save()`. Our `_create_row_update` captures old values before save — verify this still works correctly.

- **JSON serializer writes trailing newline**: Should not affect us.

- **`load_dotenv(verbose=True)` deprecation**: Our `settings.py:15` uses `load_dotenv(verbose=True)`. The `verbose` parameter was deprecated in python-dotenv 1.0+. Remove `verbose=True` or update to new API.

- **Settings doc URLs**: `settings.py` comments reference Django 5.2 docs — update to 6.0.

#### 3.3 Features removed in Django 6.0 to check
- **Support for positional arguments to `Model.save()` removed**: Ensure we don't call `instance.save(True)` or similar positional args. All our saves use keyword args already.
- **`CheckConstraint` `check` keyword argument removed**: Was renamed to `condition` in Django 5.0. Verify no usage.
- **`get_cache_name()` removed from `FieldCacheMixin`**: Internal API, unlikely to affect us.

#### 3.4 Resolve mypy comments in codebase

Existing mypy-related comments to address:

- `djangoapp/models.py:160` — `# TODO in a later mypy version, ensure its classmethod`
  - With mypy 1.20, test if `@classmethod` decorator on `from_db` is now properly inferred. Remove the TODO if resolved.

- `djangoapp/models.py:1194-1195` — `# noqa: E501, W505 let comments exceed line width` on `django-manager-missing` errors
  - These are django-stubs mypy plugin errors about unresolved related managers. After upgrading to django-stubs 6.0.2, check if these are resolved. If still present, these are known limitations of the stubs plugin for reverse relations on proxy/unconventional models.

- `djangoapp/models.py:1225` — `# type: ignore[assignment]` on `RowUpdateManager.from_queryset()` call
  - Check if django-stubs 6.0 has better typing for `Manager.from_queryset()`. If resolved, remove the ignore.

- `djangoapp/models.py:238,267,268,710` — `# type: ignore[attr-defined, no-any-return]` for Django manager on abstract/proxy model
  - These are inherent limitations: `objects` is not defined on abstract base models at the type level. Likely still needed with django-stubs 6.0, but verify.

- `djangoapp/middleware.py:4` — `# type: ignore[attr-defined]` on `from inertia import share`
  - Check if `inertia-django` has improved type stubs. If not, keep the ignore.

#### 3.5 Run `uv lock` and test
- Run `uv lock` to update the lockfile
- Run `./run typecheck` and fix any new errors
- Run `./run test` and verify no regressions

---

### Phase 4: Allow long comments and docstrings [ruff-long-comments]

#### 4.1 Add `ignore-overlong-task-comments` to `pyproject.toml`
- Under `[tool.ruff.lint.pycodestyle]`, add `ignore-overlong-task-comments = true`
- This allows long comments (including `# noqa:` and type ignore comments) to exceed line length
- Remove existing `# noqa: E501` exemptions that were only needed because of long comments

#### 4.2 Clean up existing E501 exemptions
- `djangoapp/models.py:1194-1195` — `# noqa: E501, W505 let comments exceed line width` on the `django-manager-missing` comments
- After adding `ignore-overlong-task-comments = true`, these `# noqa: E501, W505` can be removed (the W505 may still be needed if `max-doc-length` is exceeded — verify)
- Search for any other `# noqa: E501` in codebase and remove where no longer needed

---

### Phase 5: Playwright test directory [playwright-dir]

#### 5.1 Create `djangoapp/tests/playwright/` directory

#### 5.2 Split `djangoapp/tests/test_playwright.py` into two files
- `djangoapp/tests/playwright/test_playwright.py` — all tests except `NotificationE2eTestCase`
- `djangoapp/tests/playwright/test_notifications.py` — the `NotificationE2eTestCase` class (line 3634+)
- Add `__init__.py` to the new directory
- Ensure both files import `BasePlaywrightTestCase` correctly
- Update the test runner config if needed (check `pyproject.toml` or `run` script for test discovery paths)

#### 5.3 Remove old `djangoapp/tests/test_playwright.py`

---

### Phase 6: Text field overflow handling [text-overflow]

Text fields render HTML via `RenderRawHtml` in four contexts:
1. **Table cell** (ListRows) — currently plain text via `htmlToPlaintext()` at `ListRows.vue:299`
2. **Row details** (FieldDisplay) — `RenderRawHtml` at `FieldDisplay.vue:52-55`
3. **Row updates** (RowColumnValues) — `RenderRawHtml` at `RowColumnValues.vue:37-39,63-65,74-76`
4. **Notifications** (Notifications) — `RenderRawHtml` at `Notifications.vue:220-222`

Also `RowUpdateComment.vue:112-114` for comment content.

#### 6.1 Table cell — expand button for overflow
- In `ListRows.vue:298-300`, the text column currently shows `htmlToPlaintext(row[column.name])`
- Wrap in a container with CSS `max-height` and `overflow: hidden` when collapsed
- Add an expand/collapse toggle button that shows when text overflows
- Use a CSS class like `.text-cell-collapsed` (max-height ~3rem) and `.text-cell-expanded` (no max-height)
- Detect overflow via `scrollHeight > clientHeight` check in a small directive or computed

#### 6.2 Row details, row updates, notifications, comments — max-height with scrollbar
- Add CSS to `.rich-text-display` in `main.css`: `max-height: 300px; overflow-y: auto;`
- This applies to all `RenderRawHtml` instances that use `className="rich-text-display"`
- Alternatively, create a separate class like `.rich-text-display-scrollable` for contexts that need it

#### 6.3 CSS additions in `frontend/src/main.css`
- `.text-cell-collapsed` — `max-height: 3rem; overflow: hidden; position: relative;`
- `.text-cell-expanded` — `max-height: none;`
- `.text-cell-toggle` — small button styled as "Show more" / "Show less"
- `.rich-text-display` — add `max-height` and `overflow-y: auto` (or new variant class)

---

### Phase 7: Package age for uv and npm [package-age]

Reference: https://news.ycombinator.com/item?id=47513932

The HN thread explains that uv, npm, bun, and pnpm now support a minimum release age config. This protects against installing compromised packages that were just published (giving the community time to detect attacks).

This is a **config setting**, not code. Both uv and npm use global config files.

#### 7.1 Configure uv package age

Add to `~/.config/uv/uv.toml` (global user config):
```toml
exclude-newer = "7 days"
```

This prevents uv from resolving to packages published less than 7 days ago. Override per-package with `--exclude-newer "0 days"` on the CLI when needed (e.g., for security patches).

#### 7.2 Configure npm package age

Add to `~/.npmrc` (global user config):
```
min-release-age=7
```

This sets minimum release age to 7 days. Override per-install with `--min-release-age 0`.

#### 7.3 Document in project README or AGENTS.md
- Add a note about these config settings so other developers are aware
- The settings are per-developer (global config), not project-level

---

## Django 6.0 / mypy / django-stubs Upgrade Findings

### Version Compatibility
| Package | Current | Target | Latest |
|---------|---------|--------|--------|
| Django | >=5.2.6 | >=6.0 | 6.0.1 |
| django-stubs | >=5.2.7 | >=6.0.2 | 6.0.2 |
| mypy | >=1.18 | >=1.20 | 1.20.1 |

django-stubs 6.0.2 supports mypy 1.13–1.20 and Django 5.0–6.0. Python 3.13 is supported.

### Django 6.0 Breaking Changes Audit

| Change | Impact | Action |
|--------|--------|--------|
| `DEFAULT_AUTO_FIELD` defaults to `BigAutoField` | We don't set this in settings.py | Add `DEFAULT_AUTO_FIELD = "django.db.models.AutoField"` to preserve existing PK types, or accept new default |
| Custom ORM `as_sql()` must return tuple params | Low — grep for `as_sql` in codebase | Check, likely not affected |
| `Model.NotUpdated` exception | Low — check if we catch `DatabaseError` for forced update failures | Search and update if found |
| `Field.pre_save()` called multiple times | Low — check custom `pre_save` | Verify idempotency |
| `GeneratedField` refreshed after `save()` | Low — verify `_create_row_update` old-value capture still works | Test |
| `load_dotenv(verbose=True)` deprecated | `settings.py:15` uses this | Remove `verbose=True` |
| Settings doc URLs reference 5.2 | `settings.py:4,7,22` | Update comments to reference 6.0 |
| Positional args to `Model.save()` removed | Low — we use keyword args | Verify |

### Mypy Comments to Resolve

| File:Line | Comment | Resolution with mypy 1.20 + django-stubs 6.0.2 |
|-----------|---------|------------------------------------------------|
| `models.py:160` | `# TODO in a later mypy version, ensure its classmethod` | Test if resolved; remove TODO if so |
| `models.py:1194-1195` | `django-manager-missing` noqa E501 comments | Check if django-stubs 6.0 resolves; if not, `ignore-overlong-task-comments` handles the noqa |
| `models.py:1225` | `# type: ignore[assignment]` on `from_queryset()` | Check if better typed in django-stubs 6.0 |
| `models.py:238,267,268` | `# type: ignore[attr-defined, no-any-return]` on abstract model | Inherent limitation, likely still needed |
| `middleware.py:4` | `# type: ignore[attr-defined]` on inertia import | Depends on inertia-django stubs, likely still needed |

### Package Age Config

From the HN thread: npm, bun, pnpm, and uv all support minimum release age natively via config files. The recommended setting is 7 days:

- **uv**: `~/.config/uv/uv.toml` → `exclude-newer = "7 days"`
- **npm**: `~/.npmrc` → `min-release-age=7`
- Override per-install: `uv add <pkg> --exclude-newer "0 days"`, `npm install <pkg> --min-release-age 0`

This is a global developer config, not project-level.

---

## Checklist

### Phase 1: Common SweetAlert Module
- [x] Create `frontend/src/utils/sweetalert.ts` with
    - [x] `showToast(type, title)` function
    - [x] `showConfirm(options)` function
- [x] Update `frontend/src/pages/Notifications.vue`
    - [x] Remove `import Swal from "sweetalert2"`
    - [x] Remove `Toast` mixin definition
    - [x] Replace `Toast.fire(...)` with `showToast(...)`
    - [x] Replace `Swal.fire(...)` with `showConfirm(...)`
- [x] Update `frontend/src/components/RowUpdateList.vue`
    - [x] Remove `import Swal from "sweetalert2"`
    - [x] Remove `Toast` mixin definition
    - [x] Replace `Toast.fire(...)` with `showToast(...)`
    - [x] Replace `Swal.fire(...)` with `showConfirm(...)`
- [x] Update `frontend/src/pages/RowDetails.vue`
    - [x] Remove `import Swal from "sweetalert2"`
    - [x] Remove `Toast` mixin definition
    - [x] Replace `Swal.fire(...)` with `showConfirm(...)`

### Phase 2: Replace `username` with `title`
- [x] Backend — Update `UserSchema` in `djangoapp/responses.py`
    - [x] Rename `username` → `title`
- [x] Backend — Update `UserSchema` in `djangoapp/serializers.py`
    - [x] Rename `username` → `title`
- [x] Backend — Update `user_schema_from_id` in `djangoapp/models.py:938`
    - [x] Change to `UserSchema(id=user_id, title=user_map[user_id])`
- [x] Backend — Update `get_authenticated_user_as_schema` in `djangoapp/views.py:570`
    - [x] Compute title using same logic as `ProxyUser.title_annotation`
- [x] Frontend — Update `UserSchema` and `User` in `frontend/src/schemas.ts:18-29`
    - [x] Add `id: z.number()` to UserSchema
    - [x] Rename `username` → `title`
- [x] Frontend — Update all `.username` → `.title` references in
    - [x] `Layout.vue:34`
    - [x] `RowDetails.vue:84`
    - [x] `RowUpdateList.vue:183`
    - [x] `RowUpdateComment.vue:120`
    - [x] `Notifications.vue:23,210`
    - [x] `RowUpdateFilter.vue:12,54,96,110,207,208`
- [x] Backend — Update test assertions
    - [x] `test_views.py` — `username` → `title` in expected dicts
    - [x] `test_models.py` — `created_by.username` → `created_by.title`
    - [x] `test_playwright.py` — username display assertions
- [x] Add test verifying `UserSchema` returns `id` and `title` (not `username`)

### Phase 3: Upgrade Django 6.0, django-stubs 6.0.2, mypy 1.20
- [x] Update versions in `pyproject.toml`
    - [x] `django>=5.2.6` → `django>=6.0`
    - [x] `django-stubs[compatible-mypy]>=5.2.7` → `django-stubs[compatible-mypy]>=6.0.2`
    - [x] `mypy>=1.18` → `mypy>=1.20`
- [x] Django 6.0 breaking changes
    - [x] Add `DEFAULT_AUTO_FIELD = "django.db.models.AutoField"` to `settings.py` (or accept `BigAutoField` default)
    - [x] Remove `verbose=True` from `load_dotenv()` in `settings.py:15`
    - [x] Update settings.py doc URLs from 5.2 → 6.0
    - [x] Grep for `as_sql` — verify params returned as tuple
    - [x] Grep for `DatabaseError` catch blocks — update to `Model.NotUpdated` if relevant
    - [x] Verify `_create_row_update` old-value capture works with `GeneratedField` refresh
- [x] Resolve mypy comments
    - [x] `models.py:160` — test if classmethod TODO is resolved with mypy 1.20
    - [x] `models.py:1194-1195` — check if `django-manager-missing` errors resolved with django-stubs 6.0.2
    - [x] `models.py:1225` — check if `from_queryset()` typing improved
- [x] Run `uv lock` to update lockfile
- [x] Run `./run typecheck` and fix new errors
- [x] Run `./run test` and verify no regressions

### Phase 4: Allow long comments and docstrings
- [x] Add `ignore-overlong-task-comments = true` under `[tool.ruff.lint.pycodestyle]` in `pyproject.toml`
- [x] Search and remove `# noqa: E501` exemptions that are no longer needed
    - [x] `djangoapp/models.py:1194-1195` — `# noqa: E501, W505` on django-manager-missing comments
    - [x] Other files with E501 noqa for comments

### Phase 5: Playwright test directory
- [x] Create `djangoapp/tests/playwright/__init__.py`
- [x] Create `djangoapp/tests/playwright/test_playwright.py`
    - [x] Copy all test classes from `djangoapp/tests/test_playwright.py` except `NotificationE2eTestCase`
    - [x] Ensure imports are correct
- [x] Create `djangoapp/tests/playwright/test_notifications.py`
    - [x] Copy `NotificationE2eTestCase` class
    - [x] Ensure imports are correct
- [x] Remove `djangoapp/tests/test_playwright.py`
- [x] Update test runner config if needed
- [x] Verify `./run test` and `./run playwrighttest` still discover tests

### Phase 6: Text field overflow handling
- [x] Table cell (ListRows) — expand button for overflow
    - [x] Update text column template in `ListRows.vue` to use collapsible container
    - [x] Add expand/collapse toggle logic
    - [x] Style `.text-cell-collapsed` and `.text-cell-expanded` in `main.css`
- [x] Row details, row updates, notifications, comments — max-height with scrollbar
    - [x] Add `max-height` and `overflow-y: auto` to `.rich-text-display` or new variant class in `main.css`
    - [x] Ensure `FieldDisplay.vue`, `RowColumnValues.vue`, `Notifications.vue`, `RowUpdateComment.vue` use the scrollable class where needed
- [x] Add CSS for text cell toggle button in `main.css`

### Phase 7: Package age
- [x] Add `exclude-newer` (7 days) to `[tool.uv]` in `pyproject.toml`
- [x] Add `min-release-age=7` to `frontend/.npmrc`

### Final
- [x] `./run checkall` passes

---

## Pydantic Class Audit [pydantic-audit]

All `PydanticBaseModel` subclasses across the codebase, by file:

### `responses.py` (15 classes) — Response schemas for API endpoints + field schemas
| Class | Fields | Used by |
|-------|--------|---------|
| `UserSchema` | id, title | models.py, views.py |
| `RowUpdateResponse` | id, action, created_at, created_by, column_values, comment_* | models.py, views.py |
| `RowUpdateListResponse` | can_create_comment, edit/delete_comment_timeout, updates | views.py |
| `NotificationItem` | id, viewname, row_pk, row_update | views.py |
| `NotificationListResponse` | notifications, viewname_counts, total_count, current_page, total_pages | views.py |
| `DeleteNotificationsResponse` | deleted_count | views.py |
| `BaseFieldSchema` | name, required, discriminator | serializers.py, views.py |
| `CharFieldSchema` | name, required, max_length, choices, default | serializers.py |
| `TextFieldSchema` | name, required, length, default | serializers.py |
| `IntegerFieldSchema` | name, required, choices, default | serializers.py |
| `BooleanFieldSchema` | name, required, default | serializers.py |
| `DecimalFieldSchema` | name, required, decimal_places, default | serializers.py |
| `DateTimeFieldSchema` | name, required, default | serializers.py |
| `FileFieldSchema` | name, required, default | serializers.py |
| `ForeignKeyFieldSchema` | name, required, view_name, default | serializers.py |
| `FieldSchema` (union) | — | serializers.py, views.py |

### `serializers.py` (0 Pydantic classes) — Serializer functions only
All Pydantic schema classes have been moved to `responses.py`. `serializers.py` contains only:
- Serializer functions (`_char_field_to_schema`, `_serialize_char_to_api`, `_rowupdate_value_char`, etc.)
- Deserializer classes (`BaseDeserializer`, `CharFieldDeserializer`, etc.)
- Lookup dicts (`SCHEMA_SERIALIZERS`, `JSON_VALUE_SERIALIZERS`, `ROW_VALUE_SERIALIZERS`, `FORM_DESERIALIZERS`)
- Sentinel and helper utilities (`UNCHANGED`, `_NOT_FILLED`, `model_to_viewname`)

### `views.py` (11 classes) — View props and API schemas
| Class | Dependencies | Can move to responses.py? |
|-------|-------------|--------------------------|
| `TableUrlSchema` | None | **YES** — no external deps, currently only in views.py |
| `DebugViewSchema` | `TableUrlSchema`, `UserSchema` | **YES** — no external deps beyond responses.py |
| `RowDetailsprops` | `FieldSchema`, `UserSchema`, `RowUpdateResponse` | **NO** — references `FieldSchema` from responses.py (already there) |
| `CreateRowProps` | `FieldSchema`, `UserSchema` | **NO** — references `FieldSchema` from responses.py |
| `UpdateRowProps` | extends `CreateRowProps` | **NO** — same reason |
| `SuccessResponse` | None | **YES** — no external type deps |
| `ValidationErrorResponse` | None | **YES** — no external type deps |
| `CommentRequest` | None | **YES** — no external type deps |
| `PaginationSchema` | None | **YES** — no external type deps |
| `ListPageSchema` | `UnionFilter`, `RowUpdateFilter` (from filters.py) | **NO** — would create cycle: responses.py → filters.py → models.py → responses.py |
| `ListRowsProps` | `FieldSchema`, `UserSchema`, `ListPageSchema` | No — references `FieldSchema` and `ListPageSchema` |

### `filters.py` (16 classes) — Filter schemas with `apply()` behavior
All filter classes (`FilterABC`, `BooleanValueFilter`, `IntegerComparisonFilter`, etc.) have `apply()` methods and are cohesive with filter logic. **Should stay in filters.py.**

### Recommendations

#### Move `*FieldSchema` classes to `responses.py` [pydantic-audit-move-fieldschema]
Moved all FieldSchema classes from `serializers.py` to `responses.py` for consistency:
- [x] `BaseFieldSchema` + 8 field schema variants (`CharFieldSchema`, `TextFieldSchema`, `IntegerFieldSchema`, `BooleanFieldSchema`, `DecimalFieldSchema`, `DateTimeFieldSchema`, `FileFieldSchema`, `ForeignKeyFieldSchema`)
- [x] `FieldSchema` union type
- [x] Added Django field type imports to `responses.py` (`CharField`, `IntegerField`, `BooleanField`, `DecimalField`, `DateTimeField`, `ForeignKey`)
- [x] Updated `serializers.py` to import `FieldSchema` classes from `responses.py`
- [x] Removed duplicate `UserSchema`, `TableUrlSchema`, `DebugViewSchema` from `serializers.py`
- [x] Updated `views.py` to import `BaseFieldSchema`, `FieldSchema` from `responses.py`
- [x] Updated test imports: `test_serializers.py`, `test_filters.py`, `test_models.py`
- [x] Ran linting and tests — all passed

#### Move wrapper and RowValueSchema classes to `responses.py` [pydantic-audit-move-rowvalueschema]
- [x] `IntegerChoiceWrapper`, `CharChoiceWrapper`, `ForeignKeyWrapper`
- [x] `BaseRowValueSchema` + 10 variants (`RowUpdateBooleanValue`, `RowUpdateIntegerValue`, `RowUpdateIntegerChoiceValue`, `RowUpdateCharValue`, `RowUpdateCharChoiceValue`, `RowUpdateTextValue`, `RowUpdateDecimalValue`, `RowUpdateForeignKeyValue`, `RowUpdateDatetimeValue`, `RowUpdateFileValue`)
- [x] `RowColumnValueSchema` union type
- [x] Updated `serializers.py` imports
- [x] Updated `models.py` to import `RowColumnValueSchema` from `responses.py`
- [x] Updated test imports: `test_serializers.py`, `test_models.py`, `test_views.py`
- [x] Ran linting and tests — all passed

#### Eliminate duplicates
- [x] `UserSchema` in `serializers.py` — removed, import from `responses.py` instead
- [x] `TableUrlSchema` in `serializers.py` — removed, only exists in views.py now
- [x] `DebugViewSchema` in `serializers.py` — removed, only exists in views.py now
- [ ] Move `TableUrlSchema` from `views.py` to `responses.py`
- [ ] Move `DebugViewSchema` from `views.py` to `responses.py`

#### Move to `responses.py` (no circular import risk)
- [ ] `SuccessResponse` from `views.py:362-364`
- [ ] `ValidationErrorResponse` from `views.py:367-370`
- [ ] `CommentRequest` from `views.py:376-377`
- [ ] `PaginationSchema` from `views.py:380-382`

#### Cannot move to `responses.py` (circular import risk)
- `RowDetailsprops`, `CreateRowProps`, `UpdateRowProps` — depend on `FieldSchema` (now from `responses.py`, no issue)
- `ListPageSchema` — depends on `UnionFilter`, `RowUpdateFilter` from `filters.py`; moving would create cycle: `responses.py` → `filters.py` → `models.py` → `responses.py`
- `ListRowsProps` — depends on `FieldSchema`, `ListPageSchema`

#### Keep in current location (cohesive with behavior)
- All filter classes in `filters.py` — cohesive with filter `apply()` behavior

---

## Frontend-Backend Schema Name Mismatches [schema-name-mismatches]

`schemas.ts` line 6 says: "Each of them has a corresponding Pydantic schema with the same name." This is no longer true for several schemas.

### ~~Mismatches~~ Resolved — chose Pydantic names (Option B)

- [x] Renamed frontend `ListRowsSchema` → `ListRowsProps`
- [x] Renamed frontend `RowDetailsSchema` → `RowDetailsProps`
- [x] Renamed frontend `CreateRowSchema` → `CreateRowProps`
- [x] Renamed frontend `UpdateRowSchema` → `UpdateRowProps`
- [x] Fixed backend `RowDetailsprops` → `RowDetailsProps` (casing fix)
- [x] Updated imports in `RowDetails.vue`, `ListRows.vue`, `CreateRow.vue`, `UpdateRow.vue`
- [x] Removed redundant `type` imports where value and type share the same name
- [x] Ran lint, typecheck, tests — all passed