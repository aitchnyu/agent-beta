# custom rendering in row details page

Details page - add widgets.  
have a _row_details similar to _list_rows. It will call row_details. Users may override the behavior so they can render custom stuff. Have a RowDetailsContext with th_columns, td_rows, etc, and slot_props. Similar to list_component, have a details_component with default. Have slots `before-row` and `after-row`.

SlotDemoView will have overridden details_component and row_details. Its after-row will have `prev: <title and link of prev row>` and `next: <title and link of next row>`, as applicable.
Update the docstrings to that class and README with new info. Info should be similar and consistent to _list_rows.

## Data Flow

```
request, row_id
     |
     v
 _row_details()  -->  resolve user, row, columns, column_schemas, title
     |
     v
 row_details(context)  -->  populate th_columns, td_rows on context  -->  RowDetailsContext
     |
     v
 _row_details()  -->  InertiaResponse(self.details_component, RowDetailsProps)
```

## Decisions

- **Single context**: `RowDetailsContext` holds both input (row, user, columns, column_schemas) and output (th_columns, td_rows, slot_props). Simpler than the ListRowsContext/ListRows2Context split because row details is a simpler operation.
- **Prev/next ordering**: PK ascending, scoped to visible rows only (via `model.list_rows(user)`).
- **row_updates/can_comment**: Stay in `_row_details`. Not part of `RowDetailsContext` since they aren't about field rendering.

## RowDetailsContext

```python
@dataclass
class RowDetailsContext:
    row: BaseModel           # the model instance
    user: User | None        # for permission-aware queries in overrides
    columns: list[DjangoField]
    column_schemas: list[BaseFieldSchema]
    th_columns: list[ThSchema]                      # populated by row_details
    td_rows: dict[str, Any]                          # populated by row_details (field_name -> TdSchema)
    slot_props: dict[str, Any] | None = None
```

## Plan

### Phase 1: Backend — `_row_details` / `row_details` split [row-details-split]

Rename the current `row_details` URL handler to `_row_details`. Extract the field-serialization logic into a new overridable `row_details(self, context: RowDetailsContext) -> RowDetailsContext`. Add `details_component: str = "RowDetails"` class attribute to `BaseView`. Add `slot_props` to `RowDetailsProps`. Update URL patterns to point to `_row_details`.

### Phase 2: Frontend — `RowDetailsContent.vue` and slots [row-details-content]

Extract `RowDetails.vue` template/logic into `RowDetailsContent.vue` with named slots `before-row` and `after-row`. `RowDetails.vue` becomes a thin wrapper. Update Zod schemas.

### Phase 3: SlotDemoView — prev/next navigation [slot-demo-prev-next]

Override `row_details` in `SlotDemoView` to compute prev/next row info (visible rows, PK ordering). Set `details_component = "SlotDemoRowDetails"`. Create `SlotDemoRowDetails.vue` page component with `#after-row` slot showing prev/next links.

### Phase 4: Documentation [row-details-docs]

Update SlotDemoView docstring and README to document the `row_details` override pattern, `details_component`, and `RowDetailsContext`. Mirror the `list_rows` documentation structure.

## Checklist

### Phase 1: Backend — `_row_details` / `row_details` split [row-details-split]
- [x] Add `RowDetailsContext` dataclass in `djangoapp/views.py` (after `ListRows2Context`)
    - [x] `row: BaseModel`
    - [x] `user: User | None`
    - [x] `columns: list[DjangoField]`
    - [x] `column_schemas: list[BaseFieldSchema]`
    - [x] `th_columns: list[ThSchema]`
    - [x] `td_rows: dict[str, Any]`
    - [x] `slot_props: dict[str, Any] | None = None`
- [x] Add `details_component: str = "RowDetails"` class attribute to `BaseView` [djangoapp/views.py:620]
- [x] Add `slot_props: dict[str, Any] | None = None` to `RowDetailsProps` [djangoapp/views.py:343]
- [x] Rename current `row_details` method to `_row_details` on `BaseView`
    - [x] Change signature to `_row_details(self, request: HttpRequest, row_id: int) -> HttpResponse`
    - [x] Keep row resolution, 404 check, title computation, and InertiaResponse building
    - [x] Build `RowDetailsContext` and call `self.row_details(context)` instead of inline field serialization
    - [x] Use `self.details_component` instead of hardcoded `"RowDetails"` in InertiaResponse
    - [x] Pass `slot_props=context.slot_props` to `RowDetailsProps`
- [x] Add new overridable `row_details(self, context: RowDetailsContext) -> RowDetailsContext` on `BaseView`
    - [x] Compute `th_columns` from `column_schemas` (same as current inline logic)
    - [x] Compute `td_rows` from row field values (same as current inline logic)
    - [x] Return `context`
- [x] Update URL pattern to point to `self._row_details` instead of `self.row_details` [djangoapp/views.py:1103]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 2: Frontend — `RowDetailsContent.vue` and slots [row-details-content]
- [x] Create `frontend/src/components/RowDetailsContent.vue`
    - [x] Move template from `RowDetails.vue` (Layout wrapper, title, fields, RowUpdateList, edit/delete buttons)
    - [x] Add named slots: `<slot name="before-row">`, `<slot name="after-row">`
    - [x] Move `<script setup>` logic (props parsing, schema, delete handler)
- [x] Update `RowDetails.vue` to be a thin wrapper
- [x] Update Zod schema `RowDetailsProps` in `schemas.ts`:
    - [x] Add `slot_props: z.record(z.string(), z.any()).nullable().optional()`
- [x] Run `cd frontend && npm run lint:fix`, `cd frontend && npm run type-check`, `cd frontend && npm run lint`

### Phase 3: SlotDemoView — prev/next navigation [slot-demo-prev-next]
- [x] Override `row_details` in `SlotDemoView` [djangoapp/views.py:1244]
    - [x] Call `super().row_details(context)`
    - [x] Query visible rows via `SlotDemoModel.list_rows(user=context.user)`
    - [x] Find prev row: `qs.filter(pk__lt=context.row.pk).order_by("-pk").first()`
    - [x] Find next row: `qs.filter(pk__gt=context.row.pk).order_by("pk").first()`
    - [x] Use `model.queryset_with_title()` to annotate titles for prev/next
    - [x] Set `context.slot_props` with `{"prev": {"title": ..., "id": ...}, "next": {"title": ..., "id": ...}}` (omit prev/next keys when absent)
- [x] Set `details_component = "SlotDemoRowDetails"` on `SlotDemoView`
- [ ] Create `frontend/src/components/custom/SlotDemoRowDetails.vue`
    - [x] Define local Zod schema for `slot_props` (prev/next with title and id)
    - [x] Parse `props` with `RowDetailsProps`
    - [x] Fill `#after-row` slot with prev/next links:
        - [x] `< Link :href="/tables/${viewname}/row-details/${prev.id}"> prev: {{ prev.title }} </Link>`
        - [x] `< Link :href="/tables/${viewname}/row-details/${next.id}"> next: {{ next.title }} </Link>`
        - [x] Conditionally render (v-if) when prev/next exist
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`
- [x] Run `cd frontend && npm run lint:fix`, `cd frontend && npm run type-check`, `cd frontend && npm run lint`

### Phase 4: Documentation [row-details-docs]
- [x] Update `SlotDemoView` docstring to document `row_details` override and `details_component` [djangoapp/views.py:1244]
- [x] Add new section in `README.md` after "Custom Content in List Rows" (or as subsection):
    - [x] Document `row_details` override pattern (mirrors `list_rows` section)
    - [x] Document `RowDetailsContext` fields table
    - [x] Document `details_component` class attribute
    - [x] Document `RowDetailsContent.vue` named slots table (`before-row`, `after-row`)
    - [x] Include SlotDemoView prev/next example
- [x] Run `./run checkall`

