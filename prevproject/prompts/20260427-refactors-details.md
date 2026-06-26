# Refactors and bug fixes

## `_search-users` returns empty [search-users-bug]

Two bugs in `RowUpdateFilter.vue` cause user search to always return empty.
The frontend was written to match the `search_rows` endpoint convention
but `_search_users` uses different param name and response shape.

### Endpoint comparison

| Endpoint | URL | Param | Response shape |
|---|---|---|---|
| `search_rows` (FK) | `firststuff/search-rows/user_fk` | `?query=jes` | `{"rows": [{id, title}]}` |
| `_search_users` | `_search-users` | `?q=jes` | `[{id, text}]` |

Frontend `RowUpdateFilter.vue` sends `?query` and expects
`response.data.users` — matches neither endpoint.

### Bug 1: Param name mismatch
Frontend sends `params: { query }` → URL becomes `?query=alice`.
Backend reads `request.GET.get("q", "")` → always gets empty string.
[frontend/src/components/filters/RowUpdateFilter.vue:49]
[djangoapp/views.py:86]

### Bug 2: Response shape mismatch
Frontend expects `response.data.users.map(...)`.
Backend returns a plain JSON array via `JsonResponse(results, safe=False)`.
So `response.data` is `[{id: 1, text: "Alice"}]` — no `.users` property.
Accessing `.users` returns `undefined`, `.map()` throws, catch block
sets `userOptions.value = []`.
[frontend/src/components/filters/RowUpdateFilter.vue:51]
[djangoapp/views.py:90]

### No tests catch this
- `TablesUserViewTest` uses `?q=ali` (correct param) and checks array
  directly — passes fine.
- `RowUpdatePlaywrightTests` only checks filter visibility/expanding.
  Never types into user search multiselect.
- No integration test exercises frontend→backend round-trip for user
  search.

### Playwright test added
`test_row_update_user_search_returns_results` in
`RowUpdatePlaywrightTests` [test_playwright.py:3639]
Creates user "Alice Smith", opens RowUpdateFilter, types "alice" in
multiselect, asserts option containing "Alice" appears.
Currently **fails** — confirms the bug. Will pass once both fixes are
applied.

## Checklist

- [x] Fix param name: change `params: { query }` to
      `params: { q: query }`
    [frontend/src/components/filters/RowUpdateFilter.vue:49]
- [x] Fix response shape: change `response.data.users.map(...)` to
      `response.data.map(...)`
    [frontend/src/components/filters/RowUpdateFilter.vue:51]
- [x] Add Playwright test: type in user search multiselect, verify
      results appear
    [test_playwright.py:3639]
- [x] Run `./run checkall`
    280 backend tests, frontend lint/type-check, 115 Playwright
    (1 pre-existing flaky failure unrelated to this fix).

## Row update filter not persisting [row-update-filter-name-mismatch]

Backend `ListPageSchema` has field `crud_filter`.
Frontend Zod schema + ListPageSchemaWrapper use `row_update_filter`.
When user applies a row update filter, frontend sends
`row_update_filter` in rison URL. Backend's Pydantic model doesn't
recognize that field (expects `crud_filter`), silently drops it.
Response's `list_page_schema` has `crud_filter: null` and no
`row_update_filter`, so frontend sees no active filter.

Symptom: after applying a row update filter with user_ids and actions,
the filter widget appears blank — users field empty, checkboxes
unchecked.

### Fix
Rename backend `crud_filter` to `row_update_filter` everywhere.

### Checklist
- [x] `djangoapp/views.py` — `ListPageSchema.crud_filter` →
      `row_update_filter`, all references
- [x] `djangoapp/tests/` — test references
- [x] Add Playwright test: apply row update filter, reload, verify
      filter state persists in UI
    [test_playwright.py:3669]
    `test_row_update_filter_persists_on_reload` — creates user,
    navigates with `row_update_filter.user_ids`, checks multiselect
    tag shows "Bob Jones".
- [x] Run `./run checkall`
    280 backend, frontend lint/type-check, 116 Playwright.

## Row update filter shows "User 1" instead of username [row-update-user-names]

When loading a page with `row_update_filter.user_ids`, the frontend
showed `User {id}` instead of the actual username.

`RowUpdateFilter.vue:89-95` mapped user_ids to
`{id, title: "User {id}"}`. The backend didn't resolve user names for
row_update_filter user_ids — there was a TODO at [views.py:735]:
`# TODO do this for crud update filter too`

### Fix
`ListPageSchema.human_row_references` now resolves
`row_update_filter.user_ids` to usernames via `TABLES_USER_VIEW.model`,
storing them in `references["__users__"]`.

Frontend `RowUpdateFilter.vue` receives `humanRowReferences` prop and
uses `humanRowReferences["__users__"][id]` for display names.

### Checklist
- [x] In `ListPageSchema.human_row_references`, resolve
      `row_update_filter.user_ids` to usernames via
      `TABLES_USER_VIEW.model`
    [djangoapp/views.py:487-497]
- [x] Include user references in the response as
      `human_row_references["__users__"]`
- [x] Frontend `RowUpdateFilter.vue` watch on `currentFilter`:
      use resolved names instead of `User {id}`
    [frontend/src/components/filters/RowUpdateFilter.vue:91-97]
- [x] Pass `humanRowReferences` prop from `ListRowsContent.vue`
    [frontend/src/components/ListRowsContent.vue:222]
- [x] Update Playwright test to assert "Bob Jones" in multiselect tag
    [test_playwright.py:3691]
- [x] Run `./run checkall`

## `actions` type mismatch: single Literal vs array [actions-type-mismatch]

Backend `RowUpdateFilter.actions` was
`Literal["created_row", "updated_row", "commented"] | None` — a single
string value.
[djangoapp/filters.py:362]

Frontend sends and receives an array:
`actions: z.array(z.enum([...])).nullable()`
[frontend/src/schemas.ts:433-434]

When backend serialized `actions: "created_row"`, frontend got a string.
`selectedActions.value = newFilter.actions || []` iterated the string as
characters.

### Checklist
- [x] Change backend `actions` to
      `list[Literal["created_row", "updated_row", "commented"]] | None`
    [djangoapp/filters.py:362]
- [x] Update `filter_user_and_actions` to accept `actions` list,
      use `action__in=actions`
    [djangoapp/models.py:1130-1155]
- [x] Fix test references `actions="created_row"` →
      `actions=["created_row"]`
    [djangoapp/tests/test_filters.py:1524,1597]
- [x] Run `./run checkall`

## items

- [x] Use `queryset_with_title` instead of manual
      `.annotate(text=user_model.title_annotation)`
    [djangoapp/views.py:495]
- [x] Send user references using actual user viewname (e.g.
      `userstuff`) as the key, and include the user viewname in the
      client response so frontend can look up users generically.
      Remove `__users__` hardcoded key.
    [djangoapp/views.py:494,498]
    [djangoapp/views.py:549 — `user_viewname` field in `ListRowsProps`]
    [frontend/src/schemas.ts:505 — `user_viewname` in Zod schema]
    [frontend/src/components/filters/RowUpdateFilter.vue:92 —
    `humanRowReferences[props.userViewname]`]
- [x] Run `./run checkall`

## CSS Refactor Plan [css-refactor]

### Problem

`frontend/src/main.css` is 1546 lines with massive duplication:
- RowUpdateFilter styles: **duplicated 4 times** (lines 132, 432, 732, 1032)
- RowUpdateList styles: **duplicated 4 times** (lines 191, 491, 791, 1091)
- CommentForm styles: **duplicated 4 times** (lines 353, 653, 953, 1253)
- Colors like `#3b82f6`, `#d1d5db`, `#e5e7eb` repeated dozens of times
- No variables, no nesting

### Solution: SCSS with Vite

Vite has built-in SCSS support — `npm install -D sass`. SCSS is
compiled at build time into a single `main.css` (no config changes).

### File structure

```
frontend/src/
  styles/
    _variables.scss        — colors, spacing, font sizes, radii
    _base.scss             — .field-item, misc global
    filters.scss           — filter widget, pill, box, header
    row-update-filter.scss — RowUpdateFilter section styles
    row-update-list.scss   — RowUpdateList, timeline, comments
    comment-form.scss      — form, textarea, char counter
    text-cell.scss         — text cell toggle/overflow
    rich-text.scss         — rich text display
    notifications.scss     — notification list, sidebar
  main.scss                — @use's all partials, replaces main.css
```

### `_variables.scss` — shared design tokens

```scss
$gray-50: #f9fafb;
$gray-100: #f3f4f6;
$gray-200: #e5e7eb;
$gray-300: #d1d5db;
$gray-400: #9ca3af;
$gray-500: #6b7280;
$gray-600: #4b5563;
$gray-700: #374151;
$gray-800: #1f2937;

$blue-500: #3b82f6;
$blue-600: #2563eb;
$green-500: #10b981;
$amber-500: #f59e0b;
$red-500: #ef4444;
$red-50: #fef2f2;

$radius-sm: 0.25rem;
$radius-md: 0.375rem;
$radius-lg: 0.5rem;
$radius-full: 9999px;

$border-default: 1px solid $gray-300;
$border-light: 1px solid $gray-200;
```

### Example: filters.scss with variables + nesting

```scss
@use 'variables' as *;

.filter-collapsed {
  display: inline;
  cursor: pointer;
  margin-right: 0.5rem;
  white-space: nowrap;

  button {
    border: none;
    background: none;
    padding: 0;
  }
}

.filter-active .filter-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.5rem;
  border-radius: $radius-full;
  border: none;
  background-color: $gray-200;
  font-weight: 600;
  color: $gray-800;
  cursor: pointer;

  &:hover { background-color: $gray-300; }
}

.filter-inactive {
  color: $gray-400;
  font-size: 0.8rem;
}
```

### `main.scss` — entry point

```scss
@import 'bootstrap/dist/css/bootstrap.min.css';
@use 'styles/base';
@use 'styles/filters';
@use 'styles/row-update-filter';
@use 'styles/row-update-list';
@use 'styles/comment-form';
@use 'styles/text-cell';
@use 'styles/rich-text';
@use 'styles/notifications';
```

### Checklist

- [x] `npm install -D sass` in frontend/
- [x] Create `frontend/src/styles/_variables.scss`
- [x] Create `frontend/src/styles/_base.scss` — move `.field-item`
- [x] Create `frontend/src/styles/filters.scss` — filter
      widget/pill/box (deduplicate to 1 copy)
- [x] Create `frontend/src/styles/row-update-filter.scss`
      (deduplicate, keep 1 copy)
- [x] Create `frontend/src/styles/row-update-list.scss`
      (deduplicate, keep 1 copy)
- [x] Create `frontend/src/styles/comment-form.scss`
      (deduplicate, keep 1 copy)
- [x] Create `frontend/src/styles/text-cell.scss`
- [x] Create `frontend/src/styles/rich-text.scss`
- [x] Create `frontend/src/styles/notifications.scss`
- [x] Create `frontend/src/main.scss` — @use all partials
- [x] Update `frontend/src/main.ts` —
      `import './main.css'` → `import './main.scss'`
- [x] Delete `frontend/src/main.css`
- [x] Replace hardcoded colors with SCSS variables in all files
- [x] Run `./run checkall`

### Expected result

~1546 lines → ~400 lines across 9 files. No duplication.
Build output: still single `main.css` (Vite compiles SCSS → CSS).

# More refactoring

## Compact list rows table [compact-table]

Headers should be much smaller font. Borders for each column. Fixed min-width per column type. Table should be scrollable to the right.

### Checklist

- [x] Add `.list-rows-table` class and `overflow-x: auto` wrapper in
      `ListRowsContent.vue`
    [frontend/src/components/ListRowsContent.vue:248]
- [x] Style table headers smaller (e.g. `font-size: 0.75rem`,
      `font-weight: 600`, `text-transform: uppercase`, `color: $gray-500`)
    [frontend/src/styles/table.scss]
- [x] Add column borders (`td, th { border-right: $border-light }`)
    [frontend/src/styles/table.scss]
- [x] Set `min-width` per column type in `_variables.scss` (e.g. boolean
      4rem, integer 6rem, char 10rem, text 15rem, datetime 12rem, fk 10rem,
      decimal 8rem, file 10rem)
    [frontend/src/styles/_variables.scss:26-34]
- [x] Apply min-width via column discriminator class (`colClass()`)
    [frontend/src/components/ListRowsContent.vue:152-158]
- [x] Run `./run checkall`

## Show count of objects in pagination [pagination-count]

`total_count` is already sent from backend
[djangoapp/views.py:747 — `"total_count": paginator.count`]
and available in frontend as `p.page.total_count`
[frontend/src/schemas.ts:500 — `page: z.object({ total_pages, total_count })`]
but the pagination UI only shows page numbers, not the total object count.

### Checklist

- [x] Display total count in pagination area, e.g.
      `"Showing 26-50 of 120"`
    [frontend/src/components/ListRowsContent.vue:295-298]
- [x] Compute start/end from `page_number`, `per_page`, `total_count`
    [frontend/src/components/ListRowsContent.vue:58-64]
- [x] Run `./run checkall`

## Restrict create/edit to logged-in users [auth-create-edit]

`create_row` and `update_row` both use `maybe_user(request)` which returns
`None` for anonymous users — no 404 is raised.
[djangoapp/views.py:799-803 — `create_row` uses `maybe_user`]
[djangoapp/views.py:864-868 — `update_row` uses `maybe_user`]
`create_row_submit` and `update_row_submit` also use `maybe_user`.
[djangoapp/views.py:829-832]
[djangoapp/views.py:892-896]
`create_comment` already uses `user_or_404(request)` — correct pattern.
[djangoapp/views.py:1008]

### Checklist

- [x] `create_row`: replace `maybe_user(request)` with `user_or_404(request)`
    [djangoapp/views.py:802]
- [x] `create_row_submit`: replace `maybe_user(request)` with
      `user_or_404(request)`
    [djangoapp/views.py:832]
- [x] `update_row`: replace `maybe_user(request)` with `user_or_404(request)`
    [djangoapp/views.py:867]
- [x] `update_row_submit`: replace `maybe_user(request)` with
      `user_or_404(request)`
    [djangoapp/views.py:895]
- [x] Add test: unauthenticated GET to `create-row` returns 404
    [djangoapp/tests/test_views.py — `UnauthenticatedCreateEditTest`]
- [x] Add test: unauthenticated POST to `create-row-submit` returns 404
- [x] Add test: unauthenticated GET to `update-row` returns 404
- [x] Add test: unauthenticated POST to `update-row-submit` returns 404
- [x] Run `./run checkall`

## `any of` filters: remove empty and duplicate values [filter-dedupe]

When `ForeignKeyFilter.submitChoices` sends an empty `options` array, the
backend stores `{discriminator: "fk", mode: "any", options: []}` — a filter
with no effect. Duplicate values also accumulate.
[frontend/src/components/filters/ForeignKeyFilter.vue:185-188 — `submitChoices`]
[frontend/src/ListPageSchemaWrapper.ts:229-232 — `navigateForeignKeyChoices`]

### Checklist

- [x] In `ForeignKeyFilter.submitChoices`, filter out empty `values`:
      if empty, call `navigateUnsetFilter` instead
    [frontend/src/components/filters/ForeignKeyFilter.vue:185-192]
- [x] Deduplicate `values` before navigating:
      `[...new Set(values)]`
    [frontend/src/components/filters/ForeignKeyFilter.vue:186]
- [x] Run `./run checkall`

## Store URL in FK crud updates [fk-url-storage]

`ForeignKeyWrapper` stores `{id, title}` but the frontend computes the
row-details URL each time it renders a FK link.
Add `url` field so frontend can use it directly.
[djangoapp/responses.py:179-183 — `ForeignKeyWrapper`]
[djangoapp/serializers.py:561-573 — `to_fk_wrapper` builds wrapper without
url]
[frontend/src/schemas.ts:216-219 — `ForeignKeyWrapperSchema` has no url]

### Checklist

- [x] Add `url: str | None = None` to `ForeignKeyWrapper`
    [djangoapp/responses.py:179-184]
- [x] In `to_fk_wrapper`, compute URL from the related model's viewname:
      `f"/tables/{viewname}/row-details/{val.pk}"`
    [djangoapp/serializers.py:569-570]
- [x] Update `ForeignKeyWrapperSchema` to include `url: z.string().nullable().optional()`
    [frontend/src/schemas.ts:216-220]
- [x] Update test for `RowUpdateForeignKeyValue` to assert `url` field
    [djangoapp/tests/test_models.py:903-911]
    [djangoapp/tests/test_serializers.py:573-574]
- [x] Run `./run checkall`

# More problems
Examine each of these classes. Check if any context allows null. If nulls dont make sense, make it not nullable. Identify them and their zod counterparts for fixing.

These look like it cant be null:
```python
class ForeignKeyWrapper(PydanticBaseModel):
    """Wrapper for foreign key values with id, title, and url."""

    id: int | None
    title: str | None = None
    url: str | None = None

class RowUpdateBooleanValue(BaseRowValueSchema):
    """Boolean column value for row updates."""

    discriminator: typing.Literal["boolean"] = "boolean"
    old_value: bool | None = None
    new_value: bool | None = None
```

char field filter in list rows - cant delete option by clicking, duplicate option can be selected. Write a playwright test to confirm our desired behavior and debug the issue.

Write a management command to delete all notifications.

### Checklist

- [x] Write management command `deletenotifications` that deletes all
      `Notification` objects
    [djangoapp/management/commands/deletenotifications.py]
- [x] Add test for the management command
    [djangoapp/tests/test_deletenotifications.py]
- [x] Run `./run checkall`
    286 backend (1 pre-existing failure), 119 Playwright pass.

## Char field filter: can't delete option, allows duplicates [char-filter-delete-dupe]

In list rows, the char field filter has two bugs:
1. Clicking a selected option doesn't remove/deselect it
2. The same option can be selected multiple times

### Checklist

- [x] Write Playwright test: add a char filter option, try to remove it by
      clicking, assert it's removed
    [test_playwright.py:2285 — test_char_choice_remove_selected_by_click]
- [x] Write Playwright test: add the same char filter option twice, assert
      only one instance remains
    [test_playwright.py:2307 — test_char_choice_no_duplicate_options]
- [x] Fix delete-on-click behavior in char field filter component
    Added `track-by="value"` to `CharChoiceFilter.vue` and
    `IntegerChoiceFilter.vue` multiselects so `removeElement` can identify
    options by value instead of reference.
    Used computed `multiselectOptions` for stable option objects.
    [frontend/src/components/filters/CharChoiceFilter.vue:128]
    [frontend/src/components/filters/IntegerChoiceFilter.vue:131]
- [x] Fix duplicate prevention in char field filter component
    Same `track-by` fix — vue-multiselect's `select()` checks `isSelected`
    before adding, preventing duplicates.
- [x] Update `fill_char_choice_multiselect` and
      `fill_integer_choice_multiselect` Playwright helpers to use
      `focus()`+`fill()` instead of `.multiselect` click, which was
      hitting tag elements and triggering `removeElement`.
    [test_playwright.py:2134]
    [test_playwright.py:126]
- [x] Run `./run checkall`

## Nullable audit: identify fields that shouldn't be nullable [nullable-audit]

Examine Pydantic/backend response models and their Zod counterparts.
If `None` doesn't make semantic sense for a field, make it required.

### Audit findings

**`ForeignKeyWrapper`** [djangoapp/responses.py:179-184]
Every construction site passes all three fields:
[djangoapp/serializers.py:571], [djangoapp/tests/test_models.py:906-907,912,916].
The nullability is on the *containing* field
(`RowUpdateForeignKeyValue.old_value: ForeignKeyWrapper | None`)
meaning "no FK was set". Inside the wrapper, all fields are always
populated. All three can be non-nullable.

**`RowUpdateBooleanValue`** [djangoapp/responses.py:194-199]
No `BooleanField(null=True)` exists anywhere in the codebase.
Boolean values are always `True` or `False`. `old_value` and
`new_value` can be `bool` (non-nullable).
[djangoapp/serializers.py:508 — passes raw values, never None]

**`IntegerChoiceWrapper`** [djangoapp/responses.py:165-169]
Constructed at [djangoapp/serializers.py:492,495] and
[djangoapp/tests/test_models.py:864-865,868-869].
Always passes `value` and `value_title` together. The `| None` on the
containing field (`RowUpdateIntegerChoiceValue.old_value:
IntegerChoiceWrapper | None`) handles "no value". Inside the wrapper,
both fields always populated → can be non-nullable.

**`CharChoiceWrapper`** [djangoapp/responses.py:172-176]
Constructed at [djangoapp/serializers.py:462,465] and
[djangoapp/tests/test_models.py:882-883,886-887].
Same pattern as IntegerChoiceWrapper. Both fields always populated.
Can be non-nullable.

**`ForeignKeyTdValue`** [djangoapp/responses.py:343-346]
Already non-nullable. No changes needed.

### Per-class checklist

- [x] `UserSchema` [djangoapp/responses.py:25-29] — no nullable fields, no change
- [x] `RowUpdateResponse` [djangoapp/responses.py:32-43]
    - [x] `created_by: UserSchema | None` — legitimately nullable (system actions)
    - [x] `column_values: list[Any] | None` — legitimately nullable (comments have no columns)
    - [x] `comment_content: str | None` — legitimately nullable (row updates have no comment)
    - [x] `comment_deleted_at`, `comment_deleted_by`, `comment_edited_at` — legitimately nullable
- [x] `RowUpdateListResponse` [djangoapp/responses.py:46-52]
    - [x] `edit_comment_timeout: int | None` — legitimately nullable (not configured)
    - [x] `delete_comment_timeout: int | None` — legitimately nullable (not configured)
- [x] `IntegerChoiceWrapper` [djangoapp/responses.py:165-169]
    - [x] `value: int | None` → `value: int`
    - [x] `value_title: str | None` → `value_title: str`
- [x] `CharChoiceWrapper` [djangoapp/responses.py:172-176]
    - [x] `value: str | None` → `value: str`
    - [x] `value_title: str | None` → `value_title: str`
- [x] `ForeignKeyWrapper` [djangoapp/responses.py:179-184]
    - [x] `id: int | None` → `id: int`
    - [x] `title: str | None` → `title: str`
    - [x] `url: str | None` → `url: str`
- [x] `RowUpdateBooleanValue` [djangoapp/responses.py:194-199]
    - [x] `old_value: bool | None` → `bool`
    - [x] `new_value: bool | None` → `bool`
- [x] `RowUpdateIntegerValue` [djangoapp/responses.py:202-207]
    - [x] `old_value: int | None` — legitimately nullable (IntegerField can have null=True)
    - [x] `new_value: int | None` — legitimately nullable
- [x] `RowUpdateIntegerChoiceValue` [djangoapp/responses.py:210-215]
    - [x] `old_value: IntegerChoiceWrapper | None` — legitimately nullable
    - [x] `new_value: IntegerChoiceWrapper | None` — legitimately nullable
- [x] `RowUpdateCharValue` [djangoapp/responses.py:218-223]
    - [x] `old_value: str | None` — legitimately nullable (blank char fields)
    - [x] `new_value: str | None` — legitimately nullable
- [x] `RowUpdateCharChoiceValue` [djangoapp/responses.py:226-231]
    - [x] `old_value: CharChoiceWrapper | None` — legitimately nullable
    - [x] `new_value: CharChoiceWrapper | None` — legitimately nullable
- [x] `RowUpdateTextValue` [djangoapp/responses.py:234-239]
    - [x] `old_value: str | None` — legitimately nullable
    - [x] `new_value: str | None` — legitimately nullable
- [x] `RowUpdateDecimalValue` [djangoapp/responses.py:242-247]
    - [x] `old_value: str | None` — legitimately nullable
    - [x] `new_value: str | None` — legitimately nullable
- [x] `RowUpdateForeignKeyValue` [djangoapp/responses.py:250-255]
    - [x] `old_value: ForeignKeyWrapper | None` — legitimately nullable
    - [x] `new_value: ForeignKeyWrapper | None` — legitimately nullable
- [x] `RowUpdateDatetimeValue` [djangoapp/responses.py:258-263]
    - [x] `old_value: str | None` — legitimately nullable
    - [x] `new_value: str | None` — legitimately nullable
- [x] `RowUpdateFileValue` [djangoapp/responses.py:266-271]
    - [x] `old_value: str | None` — legitimately nullable
    - [x] `new_value: str | None` — legitimately nullable
- [x] `BooleanFieldSchema` [djangoapp/responses.py:111-115]
    - [x] `default: bool | None` — legitimately nullable (Django BooleanField can have no default)
- [x] `CharFieldSchema` [djangoapp/responses.py:86-92]
    - [x] `choices: list[dict[str, str]] | None` — legitimately nullable
    - [x] `default: str | None` — legitimately nullable
- [x] `TextFieldSchema` [djangoapp/responses.py:95-100]
    - [x] `default: str | None` — legitimately nullable
- [x] `IntegerFieldSchema` [djangoapp/responses.py:103-108]
    - [x] `choices: list[dict[str, str]] | None` — legitimately nullable
    - [x] `default: int | None` — legitimately nullable
- [x] `DecimalFieldSchema` [djangoapp/responses.py:118-123]
    - [x] `default: str | None` — legitimately nullable
- [x] `DateTimeFieldSchema` [djangoapp/responses.py:126-130]
    - [x] `default: str | None` — legitimately nullable
- [x] `FileFieldSchema` [djangoapp/responses.py:133-136]
    - [x] `default: str | None` — legitimately nullable
- [x] `ForeignKeyFieldSchema` [djangoapp/responses.py:139-144]
    - [x] `default: dict[str, Any] | None` — legitimately nullable
- [x] Update Zod counterparts for tightened types
    - [x] `IntegerChoiceWrapperSchema.value` remove `.nullable()`
          [frontend/src/schemas.ts]
    - [x] `IntegerChoiceWrapperSchema.value_title` remove `.nullable()`
          [frontend/src/schemas.ts]
    - [x] `CharChoiceWrapperSchema.value` remove `.nullable()`
          [frontend/src/schemas.ts]
    - [x] `CharChoiceWrapperSchema.value_title` remove `.nullable()`
          [frontend/src/schemas.ts]
    - [x] `ForeignKeyWrapperSchema.id` remove `.nullable()`
          [frontend/src/schemas.ts:217]
    - [x] `ForeignKeyWrapperSchema.title` remove `.nullable().optional()`
          [frontend/src/schemas.ts:218]
    - [x] `ForeignKeyWrapperSchema.url` remove `.nullable().optional()`
          [frontend/src/schemas.ts:219]
    - [x] `RowBooleanColumnValueSchema.old_value` remove `.nullable()`
          [frontend/src/schemas.ts:226]
    - [x] `RowBooleanColumnValueSchema.new_value` remove `.nullable()`
          [frontend/src/schemas.ts:227]
- [x] Update test references if any construct with None values
- [x] Run `./run checkall`
    284 backend tests, frontend lint/type-check, 117 Playwright. All pass.

# More 
Nullable int field is not getting set as null. Add unit tests that set nullable values. 1 or 2 playwright tests - nothing extensive.

### Checklist

- [x] Investigate: nullable int field not being set as null on create/update
    `IntegerFieldDeserializer` returned `UNCHANGED` for empty string on
    nullable fields with defaults, preventing explicit null assignment.
    Fixed: check `field.null` first — if True, return `None` for empty.
    [djangoapp/serializers.py:723-725]
- [x] Add unit test: create row with nullable int field set to null
    [djangoapp/tests/test_views.py — test_create_row_nullable_integer_empty_set_to_null]
- [x] Add unit test: update row setting nullable int field to null
    [djangoapp/tests/test_views.py — test_update_row_nullable_integer_cleared_to_null]
- [x] Add deserializer unit tests for nullable int empty→null
    [djangoapp/tests/test_serializers.py — test_deserialize_nullable_integer_empty_returns_null_on_create/update]
- [x] Add Playwright test: clear nullable int field to null via UI
    [test_playwright.py — test_update_row_clear_nullable_integer_to_null]
- [x] Run `./run checkall`
    290 backend (1 pre-existing failure), 120 Playwright. All pass.

## Clear all button styling [clear-all-red]

Clear all button should be red like delete button

### Checklist

- [x] Find the "clear all" button component and its current styling
    [frontend/src/pages/Notifications.vue:166] — used `btn-outline-warning`
- [x] Change `btn-outline-warning` to `btn-outline-danger` to match delete
      button style
    [frontend/src/pages/Notifications.vue:166]
- [x] Run `./run checkall`

# more
Rename list_rows_2 to list_rows. list_rows is what a user must override. Update whole codebase with new references.

`#### Custom Page Component` in readme - do this examle without zod. Then show original example with zod, recommending zod for type safety.

## Rename `list_rows_2` to `list_rows` [rename-list-rows]

### Checklist

- [x] Rename `BaseView.list_rows_2` → `BaseView.list_rows` in
      `djangoapp/views.py`
- [x] Update all subclasses that override `list_rows_2` → `list_rows`
    - [x] `FirstStuffView.list_rows_2` → `FirstStuffView.list_rows`
          [djangoapp/views.py:1175]
    - [x] `SlotDemoView.list_rows_2` → `SlotDemoView.list_rows`
          [djangoapp/views.py:1272]
    - [x] `SlotDemoView` docstring reference [djangoapp/views.py:1258]
- [x] Update all call sites that reference `list_rows_2`
    - [x] `self.list_rows_2(ctx)` → `self.list_rows(ctx)`
          [djangoapp/views.py:685]
    - [x] `super().list_rows_2(context)` in FirstStuffView and SlotDemoView
- [x] Update test references `list_rows_2` → `list_rows`
    - [x] SlotDemoFilterE2ETestCase docstring [test_playwright.py:3865]
- [x] Update README references `list_rows_2` → `list_rows`
    - [x] Section heading and code examples [README.md:499]
    - [x] ListRowsContext table heading [README.md:516]
    - [x] ListRows2Context table heading [README.md:525]
- [x] Update model docstring `list_rows_2` → `list_rows`
    - [x] `SlotDemoModel` docstring [djangoapp/models.py:1743]
- [x] Run `./run checkall`
    288 backend, frontend lint/type-check, 120 Playwright. All pass.

## README: show Custom Page Component without Zod, then with [readme-zod-examples]

### Checklist

- [x] Rewrite `#### Custom Page Component` example without Zod
      (plain props, no `.parse()`, type assertion)
    [README.md:536]
- [x] Show the original example with Zod below it, recommending Zod
      for type safety
    [README.md:562]
- [x] Run `./run checkall`