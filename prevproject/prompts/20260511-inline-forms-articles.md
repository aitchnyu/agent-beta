## Articles

Have an abstract article table in models/base.py. It has title, content is text field with 50000 characters, editor which is user.

Have Article1 and Article2 models in app.py and corresponding views. Article2 has score, an int field.

Base class behavior for the views:
Create - show title, content and other fields
List - show title and other fields, no content
Details - Dont show title, show content and other fields
Update - allow title and other fields
Delete - allow it for all

---

## Checklist

### Backend models [§Models]

- [x] Create abstract `BaseArticle(BaseModel)` in `models/base.py`
    - [x] `title_annotation = F("title")` [§M-title-ann]
    - [x] `title = models.CharField(max_length=255)` [§M-title]
    - [x] `content = models.TextField(max_length=50000)` [§M-content]
    - [x] `editor = models.ForeignKey("djangoapp.ProxyUser", on_delete=models.CASCADE)` [§M-editor]
    - [x] Override `resolve_columns()` for column visibility per operation [§M-resolve]
        - [x] `"create"`: return all columns [§M-resolve]
        - [x] `"list"`: exclude `content` [§M-resolve]
        - [x] `"details"`: exclude `title` [§M-resolve]
        - [x] `"update"`: exclude `content` [§M-resolve]
        - [x] `"delete"`: return all columns [§M-resolve]
    - [x] `class Meta: abstract = True`
    - [x] Override `save_stuff()` to auto-set `editor` from `context.user` via lazy-imported `ProxyUser.objects.get(pk=...)` [§M-editor-auto]
- [x] Create `Article1(BaseArticle)` in `models/app.py` — no extra fields [§M-A1]
- [x] Create `Article2(BaseArticle)` in `models/app.py` [§M-A2]
    - [x] `score = models.IntegerField(default=0)`
- [x] Register all three in `models/__init__.py` re-exports and `__all__`

### Views [§Views]

- [x] Create `BaseArticleView(BaseView)` in `views/base.py` — shared view base for article models [§V-base]
- [x] Create `Article1View(BaseArticleView)` in `views/app.py` [§V-A1]
- [x] Create `Article2View(BaseArticleView)` in `views/app.py` [§V-A2]
- [x] Register both views in `add_views()` call in `views/app.py` [§V-reg]
- [x] Import both models in `views/app.py` imports

### Tests [§Tests]

- [x] Unit tests for `resolve_columns` on `Article1`
    - [x] create returns `(title, content, editor)`
    - [x] list returns `(title, editor)` — no content
    - [x] details returns `(content, editor)` — no title
    - [x] update returns `(title, editor)` — no content
    - [x] delete returns all columns
- [x] Unit tests for `resolve_columns` on `Article2`
    - [x] create returns `(title, content, editor, score)`
    - [x] list returns `(title, editor, score)` — no content
    - [x] details returns `(content, editor, score)` — no title
    - [x] update returns `(title, editor, score)` — no content
    - [x] delete returns all columns
- [x] Inertia endpoint CRUD tests for both models
    - [x] list view columns match expectations
    - [x] details view columns match expectations
    - [x] create form fields match expectations
    - [x] update form fields match expectations
    - [x] create sets editor from logged-in user

### Migrations [§Migrations]

- [x] Generate migrations for new models (0028, 0029)
- [x] Run `./run test` to verify migrations apply cleanly

### Lint/Typecheck [§Lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (353 tests)
- [x] `./run playwrighttest` passes (123 tests)

## Save from details page
Implement row edit in details page. When we double click a field, fetch the stuff again since display columns and editable columns may differ, and show edit form within the page. When we save it, page is refreshed. Focus the field which was double clicked. Still have edit button which focuses for first field.

No need of `/update-row/<id>` page.

Have functions and components to reduce code duplication and huge modules.

Double click a cell from list page, including fk fields which are links, and it will open details page in edit mode and focus on field.

Playwright tests for row details should have test for double clicking multiple fields.

---

## Checklist

### Backend [§Backend]

- [x] Add method `BaseView.get_update_form_data(user, row_id)` returning `(fields: list[FieldSchema], field_values: dict)` [§BE-method]
    - [x] Uses `model.fields_or_404(user, "update", row)` to get editable columns [§BE-method]
    - [x] Returns `None` if user lacks update access [§BE-method]
    - [x] DRY — called by `_row_details` (when editField param present) and the removed update page [§BE-method]
- [x] Extend `RowDetailsProps` with optional `edit_fields: list[FieldSchema] | None` and `edit_field_values: dict[str, Any] | None` [§BE-props]
- [x] Update `_row_details` to accept optional query param `editField` [§BE-details]
    - [x] When `editField` present and user has update access, call `get_update_form_data` and include in props [§BE-details]
    - [x] Include `edit_field_name: str | None` in props for focus target [§BE-details]
- [x] Remove `update_row` (GET) page endpoint and its URL pattern [§BE-remove]
- [x] Keep `update_row_submit` (POST) endpoint unchanged [§BE-keep]

### Frontend — Details page inline edit [§FE-details]

- [x] `RowDetailsContent.vue` reads `p.edit_fields` / `p.edit_field_values` from props [§FE-state]
    - [x] If present, renders in edit mode with `focusedField = p.edit_field_name` [§FE-state]
    - [x] If absent, renders in display mode [§FE-state]
- [x] Add `@dblclick` handler on each field display `<div>` in `RowDetailsContent.vue` [§FE-dblclick]
    - [x] Navigates to same details URL with `?editField={field.name}` via `router.visit` [§FE-dblclick]
    - [x] Backend includes edit data in the response — no extra roundtrip [§FE-dblclick]
- [x] Conditionally render `RowForm` in place of field display when edit data is present [§FE-form]
    - [x] On save success, calls `router.visit(detailsUrl)` (without editField) to return to display mode [§FE-form]
    - [x] Cancel button navigates back to details URL without editField [§FE-form]
- [x] Edit button navigates to `?editField={first_field_name}` [§FE-editbtn]
    - [x] Falls back to first display field when no edit data loaded yet [§FE-editbtn]
- [x] Update `RowForm.vue` submit: on update success, redirect to `row-details/{id}` instead of always going there [§FE-redirect]

### Frontend — List page dblclick to details [§FE-list]

- [x] Add `@dblclick` handler on list page `<td>` cells [§FE-list-dbl]
    - [x] Regular cells: dblclick navigates to `row-details/{row.id}?editField={column.name}` [§FE-list-dbl]
- [x] FK link cells: `ForeignKeyFieldTd.vue` contains a `<Link>` inside `<td>` [§FE-list-fk]
    - [x] Single click on `<Link>` follows FK to related row's details (existing behavior) [§FE-list-fk]
    - [x] Add `@dblclick.stop.prevent` on the `<Link>` to prevent single-click navigation from firing mid-dblclick [§FE-list-fk]
    - [x] On dblclick, emit event to parent `<td>` which navigates to current row's details with `editField` [§FE-list-fk]
    - [x] Implementation: add `@dblclick` on the `<td>` wrapper in `ListRowsContent.vue` template; FK `<Link>` dblclick uses `@dblclick.stop.prevent` to cancel link navigation, then calls same navigation [§FE-list-fk]

### Frontend — Details page reads editField [§FE-query]

- [x] Handled by backend — when `editField` query param present, `_row_details` includes edit data in props [§FE-query]
- [x] Frontend reads `edit_fields` from props and enters edit mode [§FE-query]

### Frontend — Remove UpdateRow page [§FE-remove]

- [x] Delete `frontend/src/pages/UpdateRow.vue` [§FE-del]
- [x] Remove `update-row/<str:row_id>` URL pattern from `BaseView.get_url_patterns()` [§FE-del]

### Frontend — Code organization [§FE-org]

- [x] Extract edit-mode logic into composable `useRowEdit.ts` [§FE-composable]
    - [x] Accepts initial `editFields`, `editValues`, `focusedField` from props [§FE-composable]
    - [x] Exposes `editing`, `editFields`, `editValues`, `focusedField`, `errors`, `startEdit(fieldName)`, `cancelEdit()` [§FE-composable]

### Tests [§Tests]

- [x] Backend — `_row_details` with `editField` param [§T-details-edit]
    - [x] Without `editField`: `edit_fields` is `None` in props [§T-details-edit]
    - [x] With `editField=title`: `edit_fields` present, `edit_field_values` has title value, `edit_field_name == "title"` [§T-details-edit]
    - [x] Article2 variant with score field [§T-details-edit]
- [x] Playwright: inline edit on details page [§T-pw-dbl]
    - [x] Double-click field div → form appears with field input focused [§T-pw-dbl]
    - [x] Change field, submit → page refreshes with new value in display mode [§T-pw-dbl]
    - [x] Cancel edit → returns to display mode without changes [§T-pw-dbl]
- [x] Playwright: list page double-click navigates to details in edit mode [§T-pw-list]
    - [x] Double-click cell in list → navigates to details with `?editField=`, edit form shown [§T-pw-list]
- [x] Playwright: Edit button on details page [§T-pw-editbtn]
    - [x] Click Edit button → enters edit mode [§T-pw-editbtn]

## More details page stuff
Details page will show stuff as form only. Have a save and delete button. If some fields are not editable, show them as disabled. If its not editable, save button and fields are disabled.

When serving details page, serve the details for editable fields. Assert that editable fields is a subset or equal to displayable fields and is same order as displayable fields. Have tests for this in views.

Rename editField param as focusField.

When using inputs for fields, values may be hard to see. For fk fields, render the options such that after title, there is a clickable link that opens in a new tab. For file field, show a download link below field. Have playwright tests for these.

---

## Checklist

### Backend — Always-serve edit data on details page [§BE-always]

- [x] `_row_details` always includes `edit` prop (remove conditional on `editField`/`focusField`) [§BE-always-serve]
    - [x] If user is authenticated and has update access, include `edit` with fields/values [§BE-always-serve]
    - [x] If no update access, include `edit` with empty fields or handle gracefully on frontend [§BE-always-serve]
- [x] `focusField` query param (renamed from `editField`) — only controls `edit.field_name` for focus [§BE-focusfield]
    - [x] Rename in `_row_details`, URL patterns, tests [§BE-focusfield]
- [x] Add assertion: editable columns ⊆ displayable columns, same order [§BE-assert]
    - [x] In `_row_details`, after computing `details_columns` and `update_columns`, assert `set(update) ⊆ set(details)` and order preserved [§BE-assert]
    - [x] Test: `BaseArticle` details shows `(title, content, editor)`, update shows `(title, editor)` — subset holds [§BE-assert]
    - [x] Test: `Article2` details shows `(title, content, editor, score)`, update shows `(title, editor, score)` — subset holds [§BE-assert]
- [x] `BaseArticle.resolve_columns("details")` must include `title` so editable ⊆ displayable holds [§BE-details-cols]
    - [x] Change from `exclude title` to `return all columns` [§BE-details-cols]
    - [x] Update existing resolve_columns tests [§BE-details-cols]

### Backend — Unauthenticated details page [§BE-anon]

- [x] Unauthenticated users can still view details page (read-only, all fields disabled) [§BE-anon-view]
- [x] `edit` prop is `None` when user is unauthenticated [§BE-anon-view]

### Frontend — Details page always-form [§FE-form]

- [x] `RowDetailsContent.vue` always renders `RowForm` (remove `v-if/v-else` display/edit branching) [§FE-always-form]
    - [x] Remove display-mode template (`v-for` field divs) [§FE-always-form]
    - [x] Remove `editing` computed — always editing [§FE-always-form]
    - [x] Remove Edit/Delete buttons from display mode; move Save/Delete into/after the form [§FE-always-form]
- [x] `RowForm.vue` receives both displayable fields and editable fields [§FE-disabled]
    - [x] Non-editable fields rendered as disabled inputs [§FE-disabled]
    - [x] If no fields are editable, Save button is disabled [§FE-disabled]
- [x] Double-click on list page cells navigates to details with `?focusField=` (renamed from `editField`) [§FE-list-rename]
- [x] Remove `?editField` from all navigation calls, replace with `?focusField` [§FE-rename]

### Frontend — FK field link [§FE-fk-link]

- [x] In `RowForm` FK multiselect, show clickable link after title that opens related row in new tab [§FE-fk-link]
    - [x] Link target: `/tables/{related_viewname}/row-details/{related_id}` [§FE-fk-link]
    - [x] Opens in new tab (`target="_blank"`) [§FE-fk-link]
- [x] Requires viewname for related model — uses `field.view_name` from `ForeignKeyFieldSchema` passed as `fkViewName` prop [§FE-fk-viewname]

### Frontend — File field download link [§FE-file-link]

- [x] In `RowForm` file field, show download link below the file input when file exists [§FE-file-link]
    - [x] Link text: filename, opens download URL [§FE-file-link]

### Tests [§T-more]

- [x] Backend: assert editable ⊆ displayable in `_row_details` for FirstStuff [§T-subset]
- [x] Backend: assert editable ⊆ displayable in `_row_details` for Article1, Article2 [§T-subset]
- [x] Backend: `focusField` param sets `edit.field_name` correctly [§T-focusfield]
- [x] Backend: unauthenticated details page has `edit = None` [§T-anon]
- [x] Playwright: FK field in details form has clickable link opening in new tab [§T-pw-fk]
- [x] Playwright: File field in details form has download link [§T-pw-file]
- [x] Playwright: non-editable fields are disabled [§T-pw-disabled]
- [x] Playwright: Save button disabled when all fields are non-editable [§T-pw-disabled]
- [x] Update existing tests: rename `editField` → `focusField` everywhere [§T-rename]

### Lint/Typecheck [§Lint2]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes
- [x] `./run playwrighttest` passes

## Components
Title-content edit component. Add endpoint to view. Override after-row. All semantics done!

Have an endpoint called /update-content for base article view. It will take title and content and update them. Check permission to update. Have a component like SlotDemoRowDetails, but not in /custom dir as its a builtin, that allows you to edit title and content. Dont allow to edit otherwise.

---

## Checklist

### Backend — `/update-content` endpoint [§BE-uc]

- [x] Add `update_content(self, request, row_id)` method to `BaseArticleView` [§BE-uc-method]
    - [x] POST only; reads `title` and `content` from request data [§BE-uc-method]
    - [x] Checks update permission via `model.get_row_for_user_and_operation` — returns 404 if denied [§BE-uc-perm]
    - [x] Updates only `title` and `content` fields on the row [§BE-uc-method]
    - [x] Returns `RowFormResponse` (success with row id, or validation error) [§BE-uc-resp]
- [x] Register the endpoint in `get_router()` as `POST /{vn}/update-content/{row_id}` [§BE-uc-route]
- [x] Unit tests for `update_content` [§BE-uc-test]
    - [x] Authenticated user with update permission can update title+content [§BE-uc-test]
    - [x] Unauthenticated user gets 404 [§BE-uc-test]
    - [x] Validation: title required, content required [§BE-uc-test]
    - [x] Article2 variant preserves score [§BE-uc-test]

### Backend — `BaseArticleView` details component [§BE-detail-comp]

- [x] Set `details_component = "ArticleRowDetails"` on `BaseArticleView` [§BE-comp]
- [x] Verify `Article1View` and `Article2View` inherit it correctly [§BE-comp]

### Frontend — `ArticleRowDetails.vue` page component [§FE-ard]

- [x] Create `frontend/src/pages/ArticleRowDetails.vue` (not in `/custom`) [§FE-ard-file]
    - [x] Uses `RowDetailsContent` with `before-row` slot for title+content editor [§FE-ard-slot]
    - [x] Reads `p.slot_props` for current `title` and `content` values [§FE-ard-props]
- [x] Title+content editor in the `before-row` slot [§FE-ard-editor]
    - [x] Shows `title` as a text input [§FE-ard-editor]
    - [x] Shows `content` as a `RichTextEditor` [§FE-ard-editor]
    - [x] Save button posts to `/tables/api/{viewname}/update-content/{row_id}` [§FE-ard-save]
    - [x] On success, Inertia reloads props via `router.reload` [§FE-ard-save]
    - [x] Inputs are disabled if `can_update_content` is false [§FE-ard-disabled]
    - [x] Save button disabled until values are modified (dirty tracking) [§FE-ard-dirty]

### Backend — `row_details` provides title+content in slot_props [§BE-slot]

- [x] Override `row_details` in `BaseArticleView` to set `context.slot_props` with `title` and `content` from the row [§BE-slot-props]
    - [x] `slot_props = {"title": row.title, "content": row.content, "can_update_content": bool}` [§BE-slot-props]
- [x] `can_update_content` based on whether user has update permission [§BE-slot-perm]

### Tests [§T-uc]

- [x] Backend unit test: `update_content` endpoint on `Article1View` / `Article2View` [§T-uc-unit]
- [x] Backend unit test: `slot_props` includes title, content, can_update_content [§T-uc-slot]
- [x] Playwright: navigate to article details, see content editor in before-row slot [§T-uc-pw]
- [x] Playwright: edit title via content editor, save, verify updated [§T-uc-pw]
- [x] Playwright: unauthenticated user sees disabled title input and no save button [§T-uc-pw-anon]

## Remove articles
We have been adding prerequisites to articles. We will remove BaseArticle, BaseArticleView, ArticleRowDetails and their dependents. We will add them back later.

---

## Checklist

### Models

- [x] Remove `BaseArticle` class from `models/base.py`
- [x] Remove `Article1`, `Article2` classes from `models/app.py`
    - [x] Remove `BaseArticle` import from `models/app.py`
- [x] Remove `BaseArticle`, `Article1`, `Article2` from `models/__init__.py` imports and `__all__`

### Views

- [x] Remove `BaseArticleView` class from `views/base.py`
    - [x] Includes `details_component`, `row_details` override, `update_content` method, `get_router` override
- [x] Remove `Article1View`, `Article2View` classes from `views/app.py`
    - [x] Remove `BaseArticleView` import
    - [x] Remove `Article1`, `Article2` imports
    - [x] Remove from `add_views()` registration list

### Frontend

- [x] Delete `frontend/src/pages/ArticleRowDetails.vue`

### Migrations

- [x] Delete `djangoapp/migrations/0028_article1_article2.py`
- [x] Delete `djangoapp/migrations/0029_alter_article1_editor_alter_article2_editor.py`

### Tests

- [x] Delete `djangoapp/tests/test_articles.py`
- [x] Remove `ArticleContentEditorE2eTestCase` from `djangoapp/tests/playwright/test_playwright.py`
    - [x] Keep `test_create_row_required_fk_empty_returns_error` in `CrudOperationsTest` (uses `ForeignKeyModel`, not articles)

### Cleanup

- [x] Remove any orphaned imports referencing article models/views
- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (336 tests)
- [x] `./run playwrighttest` passes (129 tests)

## Fixes and widgets for fields
We have to upgrade this code.

td_rows name is wrong, you are sending values.

```
    def _row_details(self, request: HttpRequest, row_id: str) -> HttpResponse:
...
            th_columns=[],
            # aihere imply its values
            td_rows={},
        )
```

We introduced TdSchema for list rows, we have components for each td value.
For create/details/edit we will have components for each input type and we will send this info from client-side. Render the components. Research TdSchema and its commit to make similar thing. Update readme.

Revert the "always form" details page back to "Save from details page" pattern:
display mode shows TdSchema cell values (like list view), double-click opens edit form using InputSchema components. No disabled fields concept needed. Editable fields need not be a subset of displayable fields.

In ProxyUser, prevent changing username — exclude from update columns. Have a test for that.

---

## Checklist

### Backend — Rename `td_rows` → `cell_values` [§BR-rename]

- [x] Rename `td_rows` → `cell_values` in `ListRows2Context` dataclass (`views/base.py:638`) [§BR-rename-list]
    - [x] Update all usages: `result.td_rows` in `list_rows()`, `views/app.py` override
- [x] Rename `td_rows` → `cell_values` in `RowDetailsContext` dataclass (`views/base.py:651`) [§BR-rename-ctx]
- [x] Rename in `row_details()` base method — `context.td_rows[cs.name]` → `context.cell_values[cs.name]` (`views/base.py:818`) [§BR-rename-method]
- [x] Rename in `_row_details()` — `td_rows={}` → `cell_values={}` (`views/base.py:840`) [§BR-rename-details]
- [x] Rename in `_row_details()` — `field_values=context.td_rows` → `cell_values=context.cell_values` (`views/base.py:875`) [§BR-rename-inertia]
- [x] Rename `field_values` → `cell_values` in `RowDetailsProps` Pydantic model (`views/base.py:362`) [§BR-rename-props]
- [x] Rename in `views/app.py` override — `result.td_rows` → `result.cell_values` (`views/app.py:201`) [§BR-rename-override]
- [x] Remove both `aihere` comments in `_row_details`:
    - [x] `# aihere imply its values` at line 839
    - [x] `# aihere explain this code below, and maybe some way to simplify` at line 847

### Backend — Revert "always form" in `_row_details` [§BR-revert]

- [x] Revert `_row_details` to only include edit data when `focusField` param is present (`views/base.py:847-864`) [§BR-revert-edit]
    - [x] Currently: always calls `get_update_form_data()` and sets `edit_data`
    - [x] Revert to: only call `get_update_form_data()` when `focus_field_name is not None`
    - [x] When `focusField` absent: `edit_data = None` (display mode)
    - [x] When `focusField` present and user has update access: compute and include edit data
- [x] Remove the subset assertion — editable columns need NOT be subset of displayable (`views/base.py:852-859`) [§BR-revert-assert]
    - [x] Delete `assert update_col_set <= details_col_set` block
    - [x] This allows `resolve_columns("update")` to return columns not in `resolve_columns("details")`

### Backend — InputSchema classes [§BR-input]

Parallel to TdSchema: a discriminated union of field-type schemas, each carrying a `component` path for frontend resolution. No `disabled` field.

- [x] Create `BaseInputSchema` in `responses.py` (after FieldSchema section) [§BR-input-base]
    - [x] Fields: `discriminator: str`, `component: str`, `name: str`, `required: bool`
- [x] Create `CharFieldInputSchema(BaseInputSchema)` [§BR-input-char]
    - [x] `discriminator: Literal["char"] = "char"`, `component: str = "/components/inputs/CharFieldInput"`
    - [x] `max_length: int | None = None`, `choices: list[dict[str, str]] | None = None`, `default: str | None = None`
- [x] Create `TextFieldInputSchema(BaseInputSchema)` [§BR-input-text]
    - [x] `component: str = "/components/inputs/TextFieldInput"`, `length: int`, `default: str | None = None`
- [x] Create `IntegerFieldInputSchema(BaseInputSchema)` [§BR-input-int]
    - [x] `component: str = "/components/inputs/IntegerFieldInput"`, `choices`, `default`
- [x] Create `BooleanFieldInputSchema(BaseInputSchema)` [§BR-input-bool]
    - [x] `component: str = "/components/inputs/BooleanFieldInput"`, `default: bool | None = None`
- [x] Create `DecimalFieldInputSchema(BaseInputSchema)` [§BR-input-dec]
    - [x] `component: str = "/components/inputs/DecimalFieldInput"`, `decimal_places: int`, `default`
- [x] Create `DateTimeFieldInputSchema(BaseInputSchema)` [§BR-input-dt]
    - [x] `component: str = "/components/inputs/DateTimeFieldInput"`, `default`
- [x] Create `FileFieldInputSchema(BaseInputSchema)` [§BR-input-file]
    - [x] `component: str = "/components/inputs/FileFieldInput"`, `default`
- [x] Create `ForeignKeyFieldInputSchema(BaseInputSchema)` [§BR-input-fk]
    - [x] `component: str = "/components/inputs/ForeignKeyFieldInput"`, `view_name: str`, `default`
- [x] Define `InputSchema` union type (all 8 variants) [§BR-input-union]
- [x] Add `field_schema_to_input(schema: BaseFieldSchema) -> InputSchema` in `serializers.py` [§BR-input-convert]
    - [x] Dispatch on `schema.discriminator` like `field_value_to_td` does
    - [x] Copy relevant fields from FieldSchema to InputSchema variant
- [x] Update `responses.py` `__all__` or re-exports if needed

### Backend — Use InputSchema in form responses [§BR-use]

- [x] Change `EditDetailsProps.fields` type from `list[FieldSchema]` to `list[InputSchema]` (`views/base.py:352`) [§BR-use-edit]
- [x] Change `CreateRowProps.fields` type from `list[FieldSchema]` to `list[InputSchema]` [§BR-use-create]
- [x] Update `create_row()` — convert FieldSchema to InputSchema before sending [§BR-use-create-method]
    - [x] `schemas = model.columns_schemas(columns)` → then `input_schemas = [serializers.field_schema_to_input(s) for s in schemas]`
- [x] Update `get_update_form_data()` — convert FieldSchema to InputSchema [§BR-use-update-method]
    - [x] `fields = model.columns_schemas(columns)` → then `input_fields = [serializers.field_schema_to_input(s) for s in fields]`
- [x] Keep `columns_raw` in `ListRowsProps` as `FieldSchema` (filters don't need component paths) [§BR-use-list]

### Frontend — InputSchema Zod schemas [§FE-schema]

- [x] Create `CharFieldInputBase`, `TextFieldInputBase`, etc. Zod objects in `schemas.ts` [§FE-schema-bases]
    - [x] Mirror backend InputSchema fields: `discriminator`, `component`, `name`, `required`, plus type-specific fields
- [x] Create `CharFieldInputSchema = CharFieldInputBase.extend({ discriminator: z.literal("char") })` etc. [§FE-schema-ext]
- [x] Define `InputSchema = z.discriminatedUnion("discriminator", [...])` [§FE-schema-union]
- [x] Export type aliases: `type CharFieldInput = z.infer<typeof CharFieldInputSchema>`, etc. [§FE-schema-types]
- [x] Add `type InputField = z.infer<typeof InputSchema>`; keep `type Field = z.infer<typeof FieldSchema>` for list filters [§FE-schema-type]
- [x] Update `EditDetailsProps` to use `z.array(InputSchema)` instead of `z.array(FieldSchema)` [§FE-schema-edit]
- [x] Update `CreateRowProps` to use `z.array(InputSchema)` instead of `z.array(FieldSchema)` [§FE-schema-create]
- [x] Rename `field_values` → `cell_values` in `RowDetailsProps` Zod schema (the TdSchema display dict) [§FE-schema-rename]
- [x] Keep `EditDetailsProps.field_values` as-is (raw editing values, not TdSchema) [§FE-schema-edit-keep]

### Frontend — Input components [§FE-comp]

Split `FieldInput.vue` monolith into individual components under `components/inputs/`, mirroring `components/cells/` pattern.

- [x] Create `inputComponents.ts` in `utils/` (parallel to `tdComponents.ts`) [§FE-comp-resolver]
    - [x] Uses `import.meta.glob<{ default: Component }>(["../components/inputs/*.vue"], { eager: true })`
    - [x] Exports `getInputComponent(input: InputSchemaType): Component`
- [x] Create `components/inputs/CharFieldInput.vue` [§FE-comp-char]
    - [x] Props: `field: CharFieldInput`, `modelValue`, `error?: string`
    - [x] Renders `<select>` if `field.choices`, else `<input type="text">` with maxlength
- [x] Create `components/inputs/TextFieldInput.vue` [§FE-comp-text]
    - [x] Uses `RichTextEditor` component
- [x] Create `components/inputs/IntegerFieldInput.vue` [§FE-comp-int]
    - [x] Renders `<select>` if `field.choices`, else `<input type="number">`
- [x] Create `components/inputs/BooleanFieldInput.vue` [§FE-comp-bool]
    - [x] Renders `<input type="checkbox">` with label
- [x] Create `components/inputs/DecimalFieldInput.vue` [§FE-comp-dec]
    - [x] Renders `<input type="number">` with step based on `decimal_places`
- [x] Create `components/inputs/DateTimeFieldInput.vue` [§FE-comp-dt]
    - [x] Renders `<input type="datetime-local">`
- [x] Create `components/inputs/ForeignKeyFieldInput.vue` [§FE-comp-fk]
    - [x] Uses `ForeignKeyMultiselect` component
- [x] Create `components/inputs/FileFieldInput.vue` [§FE-comp-file]
    - [x] Uses `FileUploadWidget` component
- [x] Each component wraps in `<div :class="['mb-3', 'column-input-' + field.name]">` with label and error feedback [§FE-comp-wrap]
- [x] Delete `components/FieldInput.vue` after all input components are created [§FE-comp-delete]

### Frontend — Update RowForm.vue to use dynamic components [§FE-form]

- [x] Replace `<FieldInput v-for="field in fields">` with `<component :is="getInputComponent(field)" ...>` [§FE-form-dynamic]
    - [x] Import `getInputComponent` from `inputComponents.ts`
    - [x] Pass `field`, `modelValue`, `error`, `viewname` as props
    - [x] Remove `disabled` prop from RowForm — no per-field disabled concept
- [x] Remove import of `FieldInput` from `RowForm.vue` [§FE-form-import]
- [x] Update `submitForm()` — `field.discriminator` still works since InputSchema has same discriminator [§FE-form-submit]

### Frontend — Revert `RowDetailsContent.vue` to display + edit toggle [§FE-revert]

- [x] Display mode: render TdSchema cell values using dynamic cell components (like list view) [§FE-revert-display]
    - [x] For each field in `p.fields`, get `p.cell_values[field.name]` (TdSchema)
    - [x] Render `<component :is="getTdComponent(td)" :value="td.value" />` using `tdComponents.ts`
    - [x] Each field has a label, double-click handler, and delete button
- [x] Add `@dblclick` handler on each display field div → `router.visit(detailsUrl + '?focusField=' + field.name)` [§FE-revert-dblclick]
- [x] Edit mode: when `p.edit` is present (focusField param set), render `RowForm` [§FE-revert-edit]
    - [x] Show `RowForm` with `p.edit.fields` (InputSchema), `p.edit.field_values`, `p.edit.field_name`
    - [x] On save success: `router.visit(detailsUrl)` (without focusField) — returns to display mode
    - [x] Cancel button: `router.visit(detailsUrl)` without focusField
- [x] Edit button on display mode: navigates to `?focusField={first_field_name}` [§FE-revert-editbtn]
- [x] Remove `hasEditableFields` computed — no longer needed (no always-form) [§FE-revert-cleanup]
- [x] Import `getTdComponent` from `tdComponents.ts` for display rendering [§FE-revert-import]

### Frontend — Rename field_values → cell_values [§FE-rename]

- [x] Update `RowDetailsContent.vue` — `p.field_values` → `p.cell_values` (the TdSchema display values) [§FE-rename-details]
- [x] Keep `p.edit.field_values` as-is (raw editing values, not TdSchema) [§FE-rename-edit]

### Backend — ProxyUser username not editable [§BR-proxy]

- [x] Update `ProxyUser.resolve_columns()` in `models/app.py` to exclude `"username"` for `"update"` operation [§BR-proxy-cols]
    - [x] `if context.operation == "update": return [c for c in columns if c != "username"]`
    - [x] `"details"` still includes username (so it appears on details page display)
    - [x] `"update"` excludes username (so it can't be edited via update_row_submit)

### Tests [§Tests]

- [x] Unit test: `field_schema_to_input()` converts each FieldSchema variant correctly [§T-convert]
    - [x] `CharFieldSchema` → `CharFieldInputSchema` with `component="/components/inputs/CharFieldInput"`
    - [x] `TextFieldSchema` → `TextFieldInputSchema`
    - [x] `IntegerFieldSchema` → `IntegerFieldInputSchema`
    - [x] `BooleanFieldSchema` → `BooleanFieldInputSchema`
    - [x] `DecimalFieldSchema` → `DecimalFieldInputSchema`
    - [x] `DateTimeFieldSchema` → `DateTimeFieldInputSchema`
    - [x] `FileFieldSchema` → `FileFieldInputSchema`
    - [x] `ForeignKeyFieldSchema` → `ForeignKeyFieldInputSchema`
- [x] Backend test: `create_row` response includes InputSchema (with `component` field) instead of FieldSchema [§T-create-input]
- [x] Backend test: `_row_details` without `focusField` — `edit` is `None` [§T-revert-none]
- [x] Backend test: `_row_details` with `focusField` — `edit` present with InputSchema fields [§T-revert-edit]
- [x] Backend test: `td_rows` renamed to `cell_values` in all response props [§T-rename]
- [x] Backend test: ProxyUser `resolve_columns("update")` excludes `"username"` [§T-proxy-cols]
- [x] Backend test: ProxyUser `resolve_columns("details")` still includes `"username"` [§T-proxy-details]
- [x] Backend inertia test: update ProxyUser without username field — username unchanged [§T-proxy-update]
- [x] Remove/update tests for the removed subset assertion [§T-assert-remove]
- [x] Playwright: details page display mode shows cell values (double-click to edit) [§T-pw-display]
- [x] Playwright: ProxyUser details page — username shown in display mode, not in edit form [§T-pw-proxy]
- [x] Update existing tests that reference `td_rows` → `cell_values` [§T-existing]
- [x] Update existing tests that reference `field_values` → `cell_values` in RowDetailsProps assertions [§T-existing-props]

### README [§Docs]

- [x] Update `RowDetailsContext` table: `td_rows` → `cell_values` with updated description [§D-ctx]
- [x] Update `ListRows2Context` table: `td_rows` → `cell_values` with updated description [§D-list-ctx]
- [x] Add section documenting InputSchema pattern (parallel to TdSchema) [§D-input]
    - [x] Table of InputSchema variants with component paths
    - [x] Note that `field_schema_to_input()` converts FieldSchema → InputSchema
    - [x] Frontend uses `inputComponents.ts` for dynamic resolution (parallel to `tdComponents.ts`)
- [x] Update "Custom Content in Row Details" — details page has display mode (TdSchema cells) + edit mode (InputSchema form on double-click) [§D-details]

### Lint/Typecheck [§Lint3]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes
- [x] `./run playwrighttest` passes

---

## Review Findings

### Checklist inaccuracy — [§BR-revert]

The checklist at line 380-389 says to revert `_row_details` to only include edit data when `focusField` param is present. The actual code (`views/base.py:847-855`) always serves edit data. The frontend toggles client-side via `isEditing` ref. The checklist description does not match the implementation.

### Extra queries / performance

- [x] Move `get_update_form_data` call inside the `if user is not None` block in `_row_details` — no longer applicable; `_row_details` no longer calls `get_update_form_data` (edit moved to update page)
- [ ] `can_delete` in `_row_details` (line 871-876) makes a separate `get_row_for_user_and_operation(row_id, user, "delete")` call — extra query just for button visibility

### Replace `start-edit` event with global push/pop

Replace the fragile `window.dispatchEvent("start-edit")` + event listener pattern with a module-level global:

- [x] Create `frontend/src/utils/startEdit.ts` with:
    - [x] module-level `let _pendingField: string | null = null`
    - [x] `pushStartEdit(colName: string)` — sets `_pendingField`
    - [x] `popStartEdit(): string | null` — reads and clears `_pendingField`
- [x] `ListRowsContent.vue`: replace `window.dispatchEvent(new CustomEvent("start-edit", ...))` with `pushStartEdit(colName)` (call before `router.visit`, no `onSuccess` needed)
- [x] `RowDetailsContent.vue`:
    - [x] Remove `window.addEventListener("start-edit", ...)` and `window.removeEventListener("start-edit", ...)`
    - [x] Remove `handleStartEdit` function
    - [x] In `onMounted`, call `popStartEdit()` — if non-null, set `focusedField` and `isEditing = true`
- [x] Playwright test for list-to-details double-click should still pass unchanged

## Update page is back
Now we have create_row. Now have endpoint connected to `_create_row` which calls `create_row`. The `create_row` returns `CreateRowProps`. We can override `create_row`. Similar to `_list_rows` and `list_rows`.

Bring back row update page which was gone in last commit. Have `_update_row` and `update_row`.

Reason: I want forms in create_row and update_row easier to override.

---

## Checklist

### Backend — `_create_row` / `create_row` split [§BE-create-split]

- [x] Rename current `create_row` → `create_row` (overridable, returns `CreateRowProps`) [§BE-create-method]
    - [x] Extract body into `create_row(self, request: HttpRequest) -> CreateRowProps` — same logic, but returns `CreateRowProps` instead of `InertiaResponse` [§BE-create-method]
    - [x] Current code at `views/base.py:885-911` becomes the overridable method
    - [x] Add docstring: overridable; return `CreateRowProps` to customize fields (e.g. change `component` to swap input widgets)
- [x] Create `_create_row(self, request: HttpRequest) -> HttpResponse` as endpoint handler [§BE-create-endpoint]
    - [x] Calls `self.create_row(request)`, wraps result in `InertiaResponse(request, "CreateRow", {"props": ...})` [§BE-create-endpoint]
    - [x] Same pattern as `_list_rows` / `list_rows` and `_row_details` / `row_details` [§BE-create-endpoint]
- [x] Update `get_url_patterns()` — change `self.create_row` → `self._create_row` in the `create-row` path (`views/base.py:1191`) [§BE-create-url]

### Backend — `_update_row` / `update_row` and update page endpoint [§BE-update-split]

- [x] Create `update_row(self, request: HttpRequest, row_id: str) -> UpdateRowProps` (overridable) [§BE-update-method]
    - [x] Uses `get_update_form_data(user, row)` to get fields and field_values [§BE-update-method]
    - [x] Returns `UpdateRowProps(viewname=..., fields=..., field_values=..., user=..., row_id=row_id)` [§BE-update-method]
    - [x] Returns 404 if user lacks update access (via `get_update_form_data` returning `None`) [§BE-update-method]
    - [x] Add docstring: overridable; return `UpdateRowProps` to customize fields (e.g. change `component` to swap input widgets)
- [x] Create `_update_row(self, request: HttpRequest, row_id: str) -> HttpResponse` as endpoint handler [§BE-update-endpoint]
    - [x] Calls `self.update_row(request, row_id)`, wraps result in `InertiaResponse(request, "UpdateRow", {"props": ...})` [§BE-update-endpoint]
- [x] Add URL pattern for update page in `get_url_patterns()` [§BE-update-url]
    - [x] `path(f"{viewname}/update-row/<str:row_id>", self._update_row, name=f"update-row-{viewname}")` [§BE-update-url]

### Frontend — `UpdateRow.vue` page [§FE-update-page]

- [x] Create `frontend/src/pages/UpdateRow.vue` [§FE-update-file]
    - [x] Uses `Layout`, `RowForm` components [§FE-update-file]
    - [x] Parses `UpdateRowProps` from props [§FE-update-file]
    - [x] Calls `popStartEdit()` synchronously in setup — if non-null, passes as `focusedField` to `RowForm`; falls back to first field if null [§FE-update-file]
    - [x] Renders `RowForm` with `mode="update"`, `row_id`, `fields`, `initialFieldValues`, `viewname`, `focusedField` [§FE-update-file]

### Frontend — List page dblclick navigates to update page [§FE-list-nav]

- [x] Change `navigateToEdit` in `ListRowsContent.vue` to navigate to `/tables/${viewname}/update-row/${rowId}` [§FE-list-url]
    - [x] Keep `pushStartEdit(columnName)` call before `router.visit` — UpdateRow consumes it via `popStartEdit` [§FE-list-url]
- [x] FK cell dblclick in `ForeignKeyFieldTd.vue` — same update, navigates to update page [§FE-list-fk]

### Frontend — Details page dblclick navigates to update page [§FE-details-nav]

- [x] Change `startEdit` in `RowDetailsContent.vue` to navigate to `/tables/${viewname}/update-row/${rowId}` [§FE-details-url]
    - [x] Call `pushStartEdit(fieldName)` before `router.visit` [§FE-details-url]
    - [x] Replace inline edit toggle (`isEditing = true`) with navigation to update page [§FE-details-url]
- [x] Edit button navigates to update page with first field focused [§FE-details-editbtn]
    - [x] Call `pushStartEdit(firstFieldName)` then `router.visit(updatePageUrl)` [§FE-details-editbtn]
- [x] Remove inline edit mode from details page (`isEditing`, `focusedField`, `cancelEdit`, inline `RowForm`) [§FE-details-cleanup]
    - [x] Details page becomes display-only (TdSchema cells + delete button) [§FE-details-cleanup]
    - [x] Replace `popStartEdit` import with `pushStartEdit` import — details page pushes, update page pops [§FE-details-cleanup]

### Frontend — `RowForm.vue` on update success redirects to details page [§FE-form-redirect]

- [x] Verify `RowForm.vue` update success already redirects to `row-details/{id}` — keep as-is [§FE-form-keep]
- [x] Add Cancel button on update page that navigates back to `row-details/{id}` [§FE-form-cancel]

### Tests [§T-update-page]

- [x] Backend inertia test: `GET /{vn}/update-row/{row_id}` returns 200 with `UpdateRowProps` fields [§T-update-get]
    - [x] Verify response has `fields`, `field_values`, `row_id`, `viewname` [§T-update-get]
    - [x] Verify unauthenticated user gets 404 [§T-update-get]
- [x] Backend inertia test: existing `create_row` endpoint still works after refactor [§T-create-still]
- [x] Playwright: double-click cell on list page → navigates to update page, field focused via `pushStartEdit`/`popStartEdit` [§T-pw-list-dbl]
- [x] Playwright: double-click field on details page → navigates to update page, field focused via `pushStartEdit`/`popStartEdit` [§T-pw-details-dbl]
- [x] Playwright: Edit button on details page → navigates to update page with first field focused [§T-pw-details-edit]
- [x] Playwright: update page — edit field, submit, redirects to details page with updated value [§T-pw-update-submit]
- [x] Playwright: update page Cancel button → returns to details page without changes [§T-pw-update-cancel]

## Article model and views
Bring back article models and views mentioned here. User should be able to edit title and content.
Content should be a new Quill component. Use BaseInputSchema and override create and edit row pages to render new component for title.
Give it a light blue background just for our convenience 
When creating - have a warning at bottom that we cant add images
When editing - show image button in toolbar

ArticleImage model
    uuid7 public id
    article - Article fk
    image - file field

ArticleView has `/upload-article-image/<row_id>`. Image button calls this and gets a `/download-article-image/<row_id>/<image_uuid>` which also served from view. This checks read permission for user, else 404.

When we save article, check the image links, match the ones for row id. If there are ArticleImages in disk which are not present in article content, delete those images. Implement this in Article model save_stuff.

Deleting article and deleting image will mark images for delete.

---

## Checklist

### Backend — Article model [§A-model]

- [x] Create `Article(BaseModel)` in `models/app.py` [§A-model-class]
    - [x] `title_annotation = F("title")`
    - [x] `title = models.CharField(max_length=255)`
    - [x] `content = models.TextField(max_length=50000)`
    - [x] `editor = models.ForeignKey("djangoapp.ProxyUser", on_delete=models.CASCADE)`
    - [x] Override `save_stuff()` to clean orphaned images (editor is mandatory, no auto-set)
    - [x] Register in `models/__init__.py` re-exports and `__all__`

### Backend — ArticleImage model [§A-image-model]

- [x] Create `ArticleImage(BaseModel)` in `models/app.py` [§A-image-class]
    - [x] `public_id` using uuid7 generator (like `PublicIdUuid7TestModel`)
    - [x] `article = models.ForeignKey("djangoapp.Article", on_delete=models.CASCADE)`
    - [x] `image = models.FileField(upload_to="article_images/")` (FileField since Pillow not installed)
    - [x] Register in `models/__init__.py` re-exports and `__all__`

### Backend — Article image cleanup on save [§A-cleanup]

- [x] Override `save_stuff()` on `Article` to clean orphaned images [§A-cleanup-save]
    - [x] After `super().save_stuff()`, parse `self.content` for image URLs matching `/download-article-image/{row_id}/{uuid}`
    - [x] Find `ArticleImage` objects for `self` whose `public_id` is not in the parsed set
    - [x] Mark those images for deletion via `mark_image_for_deletion`, then delete the `ArticleImage` records
- [x] Override `delete()` on `Article` to mark all related `ArticleImage.image` files for deletion before deleting [§A-cleanup-delete]
- [x] Override `delete()` on `ArticleImage` to mark its `image` file for deletion before deleting [§A-cleanup-image-delete]

### Backend — ArticleView [§A-view]

- [x] Create `ArticleView(BaseView)` in `views/app.py` [§A-view-class]
    - [x] Override `create_row()` — replace `content` field's InputSchema `component` with custom article content component
    - [x] Override `update_row()` — same component swap for content field
    - [x] Override `get_router()` to add upload/download endpoints (call `super().get_router()` first)
    - [x] Register in `add_views()` call

### Backend — Upload/download article image endpoints [§A-endpoints]

- [x] Add `upload_article_image(self, request, row_id)` to `ArticleView` [§A-upload]
    - [x] POST only; reads image file from `request.FILES`
    - [x] Checks update permission via `get_row_for_user_and_operation` — 404 if denied
    - [x] Creates `ArticleImage(article=row, image=file)`
    - [x] Returns JSON with `url` field pointing to `/download-article-image/{row_id}/{image.public_id}`
- [x] Add `download_article_image(self, request, row_id, image_id)` to `ArticleView` [§A-download]
    - [x] GET only; checks read permission via `get_row_for_user_and_operation` — 404 if denied
    - [x] Looks up `ArticleImage` by `uuid_id` and `article_id` — 404 if not found
    - [x] Returns `FileResponse` with the image
- [x] Register both in `get_router()` override [§A-routes]
    - [x] `POST /{vn}/upload-article-image/{row_id}`
    - [x] `GET /{vn}/download-article-image/{row_id}/{image_id}`

### Frontend — Article content input component [§A-fe-component]

- [x] Create `components/inputs/ArticleContentInput.vue` [§A-fe-comp]
    - [x] Props: `field`, `modelValue`, `error?`, `viewname?`, `rowId?`
    - [x] Renders Quill editor with custom toolbar config (not RichTextEditor wrapper)
    - [x] Light blue background (`.article-content-input` class in `rich-text.scss`)
- [x] Create mode: no image button in toolbar, show warning below editor [§A-fe-create]
    - [x] Warning text conveys "Only saved articles can save images. Save this article first, then edit to add images."
    - [x] Detect create vs update via `rowId` prop (null = create)
- [x] Update mode: add image button to Quill toolbar [§A-fe-update]
    - [x] Custom Quill image handler registered via `modules.toolbar.handlers.image` in Quill config
    - [x] On click: call `POST /tables/api/{viewname}/upload-article-image/{rowId}` with selected file
    - [x] On success: insert `<img src="...">` into Quill editor at cursor position

### Frontend — Article content InputSchema [§A-fe-schema]

- [x] Add `ArticleContentInputSchema` Zod schema in `schemas.ts` [§A-fe-zod]
    - [x] Same shape as `TextFieldInputSchema` but with different `component` path
- [x] Ensure `inputComponents.ts` resolves the custom component path

### Tests [§A-tests]

- [x] Backend: `Article.save_stuff()` removes orphaned `ArticleImage` records not referenced in content [§A-t-cleanup]
    - [x] Verify `FileMarkedForDeletion` record created for orphaned image file
- [x] Backend: `Article.save_stuff()` keeps `ArticleImage` records that are referenced in content [§A-t-keep]
- [x] Backend: `Article.delete()` marks all related images for file deletion [§A-t-delete]
- [x] Backend: `upload_article_image` returns image URL, creates `ArticleImage` [§A-t-upload]
    - [x] Verify image file exists on disk after upload
- [x] Backend: `upload_article_image` returns 404 without update permission [§A-t-upload-perm]
- [x] Backend: `download_article_image` returns image file with read permission [§A-t-download]
    - [x] Verify response contains actual file content
- [x] Backend: `download_article_image` returns 404 without read permission (now checks via `get_row_for_user_and_operation`)
- [x] Backend: after save, HTML content matches download URLs for referenced images (end-to-end: upload → insert into content → save → verify content has correct URLs)
- [x] Backend: `upload_article_image` checks update permission via `get_row_for_user_and_operation`
- [x] Backend: `download_article_image` checks read permission via `get_row_for_user_and_operation`
- [x] Playwright: create article page shows warning about images, no image button in toolbar [§A-t-pw-create]
    - [x] Verify warning text conveys "Only saved articles can save images"
- [x] Playwright: update article page shows image button in toolbar [§A-t-pw-update]
- [x] Playwright: upload image on update page, image appears in editor [§A-t-pw-upload]
    - [x] After upload, submit form, verify saved article content has download URL in HTML
    - [x] Verify image file exists on disk via `ArticleImage.image.storage.exists`
- [x] Playwright: upload image, save, remove image from content, save again — verify orphaned image cleaned up
- [x] Playwright: upload image, save, delete article — verify all related images deleted
- [x] Playwright: verify Quill image handler uses custom upload (no URL prompt dialog appears)

### Migrations [§A-migrations]

- [x] Generate migrations for `Article` and `ArticleImage` models
- [x] `./run test --keepdb` to verify migrations apply cleanly

### Lint/Typecheck [§A-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes
- [x] `./run playwrighttest` passes

### Refactoring [§A-refactor]

- [x] Move `ArticleView` to `views/base.py` as generic `ArticleContentView` base class
    - [x] Abstract image model config via class vars (`image_model`, `image_model_article_field`, etc.)
    - [x] Generic `upload_article_image`/`download_article_image` using configured models
    - [x] Generic `get_router` with `_as_handler` wrapper
- [x] Subclass `ArticleView(ArticleContentView)` in `views/app.py` with `model = Article`, `image_model = ArticleImage`

### Bug fixes found during testing [§A-bugfix]

- [x] Fix `RowForm.vue` not passing `:row-id` to input components — `ArticleContentInput` always in create mode
- [x] Fix `ArticleModelTest.test_delete_article_marks_images` — use `article_id=pk` instead of `article=instance` after delete
- [x] Fix `CategoryModel` missing import in `test_views.py` (pre-existing)
- [x] Remove redundant local `ArticleImage` imports in `test_views.py` (pre-existing)

### Review findings — implementation gaps [§A-review]

These items were checked off in the original checklist but the implementation was incomplete or incorrect. All have been fixed:

- [x] Backend: `upload_article_image` now checks update permission via `get_row_for_user_and_operation(row_id, user, "update")`
- [x] Backend: `download_article_image` now checks read permission via `get_row_for_user_and_operation(row_id, user, "read")`
- [x] Frontend: Quill image handler registered via `modules.toolbar.handlers.image` in Quill config — no more `addEventListener` race
- [x] Frontend: warning text updated to "Only saved articles can save images. Save this article first, then edit to add images."
- [x] Backend: `sanitize_html` (`utils.py`) now allows `img` tag with `src` attribute — was stripping embedded images on save
- [x] Backend: `_cleanup_orphaned_images` no longer double-marks images (`delete()` already calls `mark_image_for_deletion`)

### Review — additional tests [§A-review-tests]

- [x] Backend: verify `FileMarkedForDeletion` created for orphaned images after `save_stuff`
- [x] Backend: verify image file exists on disk after `upload_article_image`
- [x] Backend: verify `download_article_image` response body contains actual file content
- [x] Backend: end-to-end test — upload image → insert URL into content → save → verify content HTML has correct download URL
- [x] Playwright: upload image, submit update form, verify saved content has download URL in HTML
- [x] Playwright: verify image file exists on disk via `ArticleImage.image.storage.exists`
- [x] Playwright: upload image, save, remove img from content, save again — verify `ArticleImage` record deleted
- [x] Playwright: upload image, save, delete article — verify all related images and `FileMarkedForDeletion` records
- [x] Playwright: verify no Quill URL prompt dialog appears on image button click
- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (369 tests, 1 pre-existing failure in `test_create_rows`)
- [x] `./run playwrighttest` passes (142 tests)

## Changes
Change all upload_to in file fields and prefix with /uploads. Migrate if you need to.

Have two url prefixes `/article/...` and `/article2/...` using two different models Article and Article2, inheriting Article. Article2 has int field named score and has public id field, using `yyyy-mm-dd-id` format. Test both urls work fine. Have test to create Article2 with score.

We have `hasattr(existing_instance, "mark_column_file_for_deletion")`. Can it be ever false? Else use `existing_instance.mark_column_file_for_deletion()` without that check.

Article images are not rendered in content in details view. Fix that and add playwright tests to verify. Add only specific relaxations for html filtering.

---

## Checklist

### upload_to prefix [§C-upload]

- [x] Change `ArticleImage.image` `upload_to` from `"article_images/"` to `"uploads/article_images/"` in `models/app.py`
    - [x] Existing `upload_to="uploads/"` fields on `TestFileUploadModel`, `SerializerTestModel`, `CharFieldModel` already have the prefix — no change needed
    - [x] `FileMarkedForDeletion.file` has no `upload_to` — no change needed
- [x] Generate migration

### Article2 model [§C-article2-model]

- [x] Create `Article2(Article)` in `models/app.py` — multi-table inheritance
    - [x] `public_id_field: ClassVar[str] = "seq_id"`
    - [x] `public_id_generator` using `generate_sequence_id("%Y-%m-%d-ID")`
    - [x] `seq_id = models.CharField(max_length=100, unique=True, editable=False)`
    - [x] `score = models.IntegerField(default=0)`
    - [x] `include_columns: ClassVar[tuple[str, ...]] = ("title", "content", "editor", "score")`
    - [x] Inherits `save_stuff`, `_cleanup_orphaned_images`, `delete` from `Article` — ArticleImage FK to `Article` works with MTI (same pk)
- [x] Register `Article2` in `models/__init__.py` re-exports and `__all__`

### Article2View [§C-article2-view]

- [x] Create `Article2View(ArticleContentView)` in `views/app.py`
    - [x] `model = Article2`
    - [x] `image_model = ArticleImage` — shared with Article (MTI means Article2 pk == Article pk)
    - [x] Viewname auto-resolves to `"article2"` — URL prefix `/tables/article2/...`
- [x] Import `Article2` in `views/app.py`
- [x] Register `Article2View` in `add_views()` call

### Remove hasattr check [§C-hasattr]

- [x] Remove `hasattr(existing_instance, "mark_column_file_for_deletion")` from `feed_values` in `models/base.py:639`
    - [x] `mark_column_file_for_deletion` is defined on `_BaseModelMixin`, `existing_instance` is already checked with `isinstance(existing_instance, _BaseModelMixin)` — always true

### Fix article images in details view [§C-img-render]

- [x] Add `"img"` to `ALLOWED_TAGS` in `frontend/src/utils/html.ts` — frontend sanitizer strips `<img>` from content in details view
- [x] Add `img: ["src"]` to `ALLOWED_ATTRIBUTES` in `frontend/src/utils/html.ts`
    - [x] Backend `utils.py` already has `img`/`src` (added in previous review), but frontend `html.ts` was missed

### Migrations [§C-migrations]

- [x] Generate migrations for Article2 model and ArticleImage upload_to change
- [x] `./run test --noinput` to verify

### Tests — Backend [§C-tests]

- [x] Add `Article2InertiaTest` class in `test_views.py`
    - [x] `test_article2_create_row` — POST creates Article2 with score, verifies title and score
    - [x] `test_article2_list_rows` — GET /article2/ list includes score column
    - [x] `test_article2_details` — GET details shows score in cell_values
    - [x] `test_article2_update_row` — POST update changes score
    - [x] `test_article2_public_id` — created Article2 has `yyyy-mm-dd-id` format seq_id

### Tests — Playwright [§C-pw]

- [x] Add test: article details page renders `<img>` tags from content (upload image, save, visit details, verify img visible)
- [x] Add test: Article2 create via update page shows score field

### Lint/Typecheck [§C-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes
- [x] `./run playwrighttest` passes

## More checks
git mv test_views to tests/views/views and spin off tests/views/articles 

And there is only one image model

new aihere too

Dry `def _as_handler` by defining OurRouter `router.add_api_operation_method` which wraps `router.add_api_operation`

- [x] `git mv djangoapp/tests/test_views.py djangoapp/tests/views/test_views.py` — move test file into new `views/` package
- [x] Create `djangoapp/tests/views/__init__.py`
- [x] Spin off article-related test classes into `djangoapp/tests/views/test_articles.py`
    - [x] `ArticleViewTest` — article upload/download/component tests
    - [x] `Article2InertiaTest` — Article2 CRUD tests
    - [x] `FileMissingFromDiskTest` — FileNotFoundError 404 tests for download_file and download_article_image
- [x] Update imports in the new file
- [x] Remove article test classes from `tests/views/test_views.py` (keep only non-article tests)
- [x] Verify only one `ArticleImage` model exists (no duplicate image model introduced)
- [x] Address aihere at `models/base.py:621` — `# aihere if any comments were removed by last commit` — verify no comments were lost; remove aihere comment
- [x] Address aihere at `views/base.py:1064` — `# aihere just return Response, not FileResponse` — change `FileResponse(b"...", status=404, ...)` to `HttpResponse(b"...", status=404, ...)`; remove aihere comment
- [x] Dry `def _as_handler` — defined identically in `BaseView.get_router` (line 1152) and `ArticleContentView.get_router` (line 1345)
    - [x] Extract to module-level `_as_handler` + `_add_route` helper that wraps `router.add_api_operation` + `_as_handler`
    - [x] `ArticleContentView.get_router` calls `super().get_router()` then adds routes — reuses shared `_add_route` instead of redefining `_as_handler`
- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes

## aihere: Refactoring [§AI]

### Models — Move Article and ArticleImage to base.py [§AI-move]

- [x] Move `Article` class from `models/app.py` to `models/base.py` [AI-move-article]
    - [x] Keep `Article2` in `models/app.py` — do not move [models/app.py:626]
- [x] Move `ArticleImage` class from `models/app.py` to `models/base.py` [AI-move-image]
- [x] Update imports in `models/__init__.py`, `views/app.py`, `views/base.py`, test files

### Models — Use Django's `get_user_model()` [§AI-user]

- [x] Kept `models.ForeignKey("djangoapp.ProxyUser", ...)` — ProxyUser is a proxy model, can't be AUTH_USER_MODEL; get_user_model() returns auth.User which lacks _BaseModelMixin methods [models/app.py:575]

### Models — Use XML parser for img src extraction [§AI-xml]

- [x] Replace regex `re.findall(pattern, self.content)` with `html.parser.HTMLParser` subclass [models/app.py:591]
    - [x] `_ImgSrcExtractor` class uses `handle_starttag` to extract `<img src="...">` URLs from content

### Views — Remove unnecessary constants in ArticleContentView [§AI-constants]

- [x] Remove overridable class variables that will never be overridden [views/base.py:1243]
    - [x] `content_field_name`, `content_component`, `image_model_article_field`, `image_model_public_id_field`, `image_model_file_field` — hardcoded in methods
    - [x] `image_model` also hardcoded — ArticleImage used directly

### Views — Define schema model with component built-in [§AI-schema]

- [x] Created `ArticleContentInputSchema` in `responses.py` with `component = "/components/inputs/ArticleContentInput"` [views/base.py:1254]
    - [x] `_swap_content_component` creates `ArticleContentInputSchema` instances instead of model_copy
    - [x] Added to `InputSchema` union in `responses.py`

### Views — Move imports to top of file [§AI-imports]

- [x] `ArticleContentTdSchema` moved to top-level imports in `views/base.py` [views/base.py:1269]

### Views — Add assertion for content_td [§AI-assert]

- [x] Added `assert content_td is not None` in `row_details()` [views/base.py:1274]

### Views — Create OurRouter child class [§AI-router]

- [x] Created `OurRouter(Router)` with `add_method(path, methods, bound_method)` convenience method [views/base.py:1340]
    - [x] Wraps bound method in plain function for Ninja compatibility
    - [x] Replaced all `_add_route()` calls with `router.add_method()`
    - [x] Removed module-level `_add_route` and `_as_handler` helpers

### Views — image_model is constant [§AI-img-model]

- [x] `image_model` hardcoded as `ArticleImage` in `ArticleContentView` — subclasses no longer set it [views/app.py:233]

### Lint/Typecheck [§AI-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (375/376, 1 pre-existing failure)
- [x] `./run playwrighttest` passes (144/144)

## aihere: Round 2 [§AI2]

### Models — `Article.editor` FK [§AI2-editor]

- [x] `models/base.py:1517` — Change `on_delete=models.CASCADE` to `on_delete=models.RESTRICT`; remove `use get_user_model` from aihere comment (decided against in §AI-user — ProxyUser is a proxy model, `get_user_model()` returns `auth.User` which lacks `_BaseModelMixin` methods) [AI2-restrict]

### Models — `ArticleImage` parent class [§AI2-parent]

- [x] `models/base.py:1552` — Change `ArticleImage` parent from `BaseModel` to `models.Model` [AI2-model-parent]
    - [x] Move any needed fields/methods from `BaseModel` directly onto `ArticleImage`
    - [x] Update imports

### Models — `delete_safely` method [§AI2-delete-safely]

- [x] `models/base.py:1554` — Implement `delete_safely()` on `_BaseModelMixin` [AI2-delete-base]
    - [x] For `_BaseModelMixin.delete_safely`: iterate all file columns, add each to `FileMarkedForDeletion`, then call `.delete()`
    - [x] For `ArticleImage.delete_safely`: ensure `image` file is added to `FileMarkedForDeletion`, then call `.delete()`
    - [x] Replace `.delete()` calls with `.delete_safely()` in `delete_row` view and `Article._cleanup_orphaned_images`
    - [x] Remove `delete()` overrides on both `Article` and `ArticleImage` — logic moves into `delete_safely`
    - [x] Remove `skip_mark` parameter from `ArticleImage.delete()`

### Views — `OurRouter.add_method` docstring [§AI2-router-doc]

- [x] `views/base.py:656` — Add docstring to `OurRouter.add_method` explaining why bound methods need wrapping for Ninja [AI2-router-docstring]

### Views — Move imports to top [§AI2-imports]

- [x] `views/base.py:1265` — Move `from ninja.errors import HttpError` from inside `upload_article_image` to top-level imports [AI2-imports-top]

### Views — `download_article_image` docstring [§AI2-download-doc]

- [x] `views/base.py:1283` — Add docstring to `download_article_image` explaining why it's needed (serves uploaded images with permission check, not a static file) [AI2-download-docstring]

### Frontend — RowForm row-id comment [§AI2-rowid]

- [x] `RowForm.vue:147` — Replace `<!-- aihere why is row-id needed? -->` with explanatory comment: row-id is needed by `ArticleContentInput` to distinguish create vs update mode and to build upload URL [AI2-rowid-comment]

### Tests — Backend test cleanup [§AI2-test-cleanup]

- [x] `tests/views/test_articles.py:15-16` — Remove both aihere comments; tests already assert on `FileMarkedForDeletion` (verify and remove comments) [AI2-test-comments]
- [x] `tests/views/test_articles.py:135` — Remove `test_article_create_row_uses_custom_component` — covered by schema conversion tests [AI2-test-remove]
- [x] `tests/views/test_articles.py:144` — Remove `test_article_update_row_uses_custom_component` — covered by schema conversion tests [AI2-test-remove]

### Tests — Playwright test cleanup [§AI2-pw-cleanup]

- [x] `tests/playwright/test_articles.py:213` — Review `test_remove_image_orphan_cleanup` and `test_delete_article_orphan_cleanup` — kept as they test browser flow, not model logic [AI2-pw-dupes]
- [x] `tests/playwright/test_articles.py:333` — Update docstrings in `ArticleE2eTestCase` to mention Article2 is a custom class (MTI with score field), verifying article features work with custom classes [AI2-pw-docstrings]