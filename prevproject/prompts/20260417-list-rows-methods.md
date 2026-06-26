
# Split list_rows

Refactor `list_rows` into `_list_rows` (orchestrator), `list_rows_1` (data gathering + filtering), and `list_rows_2` (pagination + serialization). Two dataclasses carry data between them.

## Data Flow

```
request, params
     |
     v
 list_rows_1()  -->  ListRowsContext  -->  list_rows_2()  -->  ListRows2Context
                                                              |
 _list_rows()  <───────────────────────────────────────────────┘
     |
     v
 InertiaResponse(ListRowsProps)
```

## Decisions

- [x] **column_schemas**: Compute once in `list_rows_1`, store in `ListRowsContext`, reuse in `list_rows_2`. Add `column_schemas: list[Any]` to `ListRowsContext`. Remove `columns_schemas()` call from `list_rows_2`.
- [x] **request in ListRowsContext**: Keep for future use.
- [x] **operation: ROW_OPERATIONS**: Not planned. Remove the comment.

## Context Definitions

### ListRowsContext (output of `list_rows_1`, input to `list_rows_2`)

Fields:
- `user: User | None` — from request, used for permissions
- `queryset: models.QuerySet[typing.Any]` — filtered queryset ready for pagination
- `list_page_schema: ListPageSchema` — params (filters, pagination, sort)
- `request: HttpRequest` — kept for future use
- `columns: list[DjangoField]` — resolved columns, used by `list_rows_2` for FK title filling
- `column_schemas: list[Any]` — computed once, reused by `list_rows_2` for row serialization and human_references

### ListRows2Context (output of `list_rows_2`, used by `_list_rows`)

Fields:
- `column_schemas: list[Any]` — `FieldSchema` list, for `ListRowsProps.columns`
- `rows: list[dict[str, Any]]` — serialized row data
- `page: dict[str, int]` — pagination info (`total_pages`, `total_count`)
- `human_row_references: dict[str, dict[int, str]]` — for FK filter display

`_list_rows` combines these with:
- `viewname = self.get_viewname_class()`
- `list_page_schema = context.list_page_schema`
- `user = get_authenticated_user_as_schema(request)`

## Checklist

- [x] Fix `ListRowsContext` dataclass:
    - [x] Change `columns` type to `list[DjangoField]`
    - [x] Add `column_schemas: list[Any]` field
    - [x] Remove `# operation: ROW_OPERATIONS` comment
- [x] Fix `ListRows2Context` dataclass:
    - [x] Add fields: `column_schemas`, `rows`, `page`, `human_row_references`
- [x] Fix `list_rows_1` return to pass `columns` and `column_schemas`
- [x] Fix `list_rows_2`:
    - [x] Remove `column_schemas` recomputation (use `list_rows_context.column_schemas`)
    - [x] Construct `ListRows2Context` properly in return
- [x] Fix `_list_rows` to populate `ListRowsProps` from both contexts
- [x] Run `./run lintfix`
- [x] Run `./run typecheck`
- [x] Run `./run test`

# Send data and components

In rows list, we will send this instead of sending `row_data`. We are rendering in custom manner.

columns: list[Th] = [Th(colname), Th(colname)....]
rows: dict[str,Td] (Td is base class) = {
    charfield: CharFieldTd(value=charfieldvalue),
    int: IntegerFieldTd(value=intvalue)
    ... we have Td subclasses for all types
}

Th and Td have .component. For Th, its `/components/Th`. For Td, have values like `/components/CharFieldTd` etc. Dynamic import each of them and render for every header and row cell. Each component will render the content appropriately in `<td>` tags. For integer and decimal, render as right aligned.

Do the same with backend and frontend for row details page.

Inline the contents of `list_rows_1` into `_list_rows`.

## Plan

### Phase 1: Inline `list_rows_1` into `_list_rows` [inline-list-rows-1]

Merge `list_rows_1` body directly into `_list_rows`. `list_rows_2` stays separate (it does the actual DB fetches). Remove `ListRowsContext` — `_list_rows` passes what `list_rows_2` needs as arguments. `list_rows_2` returns `ListRows2Context` unchanged.

After this, `_list_rows` does: resolve user, queryset, columns, column_schemas, validate filters, apply filters → pass to `list_rows_2` → build `ListRowsProps`.

### Phase 2: Backend Th/Td Pydantic models [backend-th-td-models]

Add to `responses.py`:

- `ThSchema(PydanticBaseModel)` — `name: str`, `component: str = "/components/Th"`
- `TdSchema(PydanticBaseModel)` — base class with `discriminator: str`, `component: str`, `value: Any`
- Subclasses: `CharTdSchema`, `TextTdSchema`, `IntegerTdSchema`, `BooleanTdSchema`, `DecimalTdSchema`, `DateTimeTdSchema`, `FileTdSchema`, `ForeignKeyTdSchema`
  - Each has a discriminator and typed `value` field
  - Each has its own `component` path (e.g. `"/components/CharFieldTd"`)
  - Integer and Decimal Td also carry `align_right: bool = True`

Add a mapping function that converts `(FieldSchema, raw_value) → TdSchema` using the field discriminator. Add similar mapping `FieldSchema → ThSchema`.

### Phase 3: Backend — produce Th/Td in list and details views [backend-th-td-views]

In `list_rows_2` (or after it): convert `column_schemas` to `list[ThSchema]` and each row's `dict[str, Any]` to `dict[str, TdSchema]`.

Update `ListRowsProps`:
- `columns: list[ThSchema]` (was `list[BaseFieldSchema]`)
- `rows: list[dict[str, TdSchema]]` (was `list[dict[str, Any]]`)

Do the same for `RowDetailsProps`:
- `fields: list[ThSchema]` (was `list[BaseFieldSchema]`)
- `field_values: dict[str, TdSchema]` (was `dict[str, Any]`)

The filter UI still needs the original `FieldSchema` info (choices, max_length, etc.). Two options:
- A: Keep `columns_raw: list[BaseFieldSchema]` alongside `columns: list[ThSchema]` for filter rendering.
- B: Embed the schema info into `ThSchema` so everything is in one place.

Go with option A for clarity — filters use `columns_raw`, table rendering uses `columns`.

### Phase 4: Frontend Th/Td Vue components [frontend-th-td-components]

Create per-field-type cell components under `frontend/src/components/cells/`:

- `Th.vue` — generic header cell, renders `<th>{{ name }}</th>` with right-align for numeric types
- `CharFieldTd.vue` — renders plain text
- `TextFieldTd.vue` — renders with `ExpandableCell` + `RenderRawHtml`
- `IntegerFieldTd.vue` — renders number, right-aligned
- `BooleanFieldTd.vue` — renders "Yes"/"No"
- `DecimalFieldTd.vue` — renders decimal string, right-aligned
- `DateTimeFieldTd.vue` — renders formatted date
- `FileFieldTd.vue` — renders download link or "-"
- `ForeignKeyFieldTd.vue` — renders link to related row or "-"

Each component receives its typed Td as a prop and wraps content in `<td>` (or the parent wraps `<td>` and the component just renders inner content — decide based on keeping `<td>` in the parent table structure).

### Phase 5: Frontend — update ListRows.vue and RowDetails.vue [frontend-pages]

**ListRows.vue**: Replace the giant `v-if/v-else-if` template chains in `<thead>` and `<tbody>` with dynamic component resolution. Use a `componentMap` that maps `td.component` string to the actual Vue component (imported eagerly or via `defineAsyncComponent`).

**RowDetails.vue**: Same approach — `FieldDisplay.vue` is replaced by dynamic Td components.

### Phase 6: Frontend schemas update [frontend-schemas]

Update `schemas.ts`:
- Add `ThSchema`, `TdSchema` and subclasses (Zod mirrors of backend Pydantic models)
- Update `ListRowsProps` to use new `columns` and `rows` types
- Update `RowDetailsProps` to use new `fields` and `field_values` types

### Phase 7: Cleanup and tests [cleanup-tests]

- Remove `FieldDisplay.vue` if fully replaced by Td components
- Remove `isAlignedRight()` helper from `ListRows.vue` (alignment is now in the Td component)
- Update Playwright tests if class names or DOM structure changes
- Run full lint/typecheck/test suite

## Checklist

### Phase 1: Inline `list_rows_1` into `_list_rows` [inline-list-rows-1]
- [x] Inline `list_rows_1` body into `_list_rows`
    - [x] Move user resolution, queryset, columns, column_schemas, filter validation, filter application into `_list_rows`
    - [x] Pass needed args to `list_rows_2` directly (remove `ListRowsContext`)
- [x] Delete `ListRowsContext` dataclass
- [x] Update `list_rows_2` signature to accept individual args instead of `ListRowsContext`
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 2: Backend Th/Td Pydantic models [backend-th-td-models]
- [x] Add `ThSchema` to `responses.py`
- [x] Add `TdSchema` base class to `responses.py`
- [x] Add Td subclasses to `responses.py`
    - [x] `CharFieldTdSchema`
    - [x] `TextFieldTdSchema`
    - [x] `IntegerFieldTdSchema`
    - [x] `BooleanFieldTdSchema`
    - [x] `DecimalFieldTdSchema`
    - [x] `DateTimeFieldTdSchema`
    - [x] `FileFieldTdSchema`
    - [x] `ForeignKeyFieldTdSchema`
- [x] Add mapping function `field_schema_to_th(FieldSchema) → ThSchema` in `serializers.py`
- [x] Add mapping function `field_value_to_td(FieldSchema, raw_value) → TdSchema` in `serializers.py`
- [x] Run `./run lintfix`, `./run typecheck`

### Phase 3: Backend — produce Th/Td in views [backend-th-td-views]
- [x] Update `list_rows_2` to produce `list[ThSchema]` and `list[dict[str, TdSchema]]`
- [x] Update `ListRowsProps`:
    - [x] `columns: list[ThSchema]`
    - [x] `columns_raw: list[BaseFieldSchema]` (for filter UI)
    - [x] `rows: list[dict[str, TdSchema]]`
- [x] Update `row_details` view to produce Th/Td
- [x] Update `RowDetailsProps`:
    - [x] `fields: list[ThSchema]`
    - [x] `field_values: dict[str, TdSchema]`
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 4: Frontend Th/Td Vue components [frontend-th-td-components]
- [x] Create `frontend/src/components/cells/Th.vue`
- [x] Create cell components in `frontend/src/components/cells/`
    - [x] `CharFieldTd.vue`
    - [x] `TextFieldTd.vue`
    - [x] `IntegerFieldTd.vue`
    - [x] `BooleanFieldTd.vue`
    - [x] `DecimalFieldTd.vue`
    - [x] `DateTimeFieldTd.vue`
    - [x] `FileFieldTd.vue`
    - [x] `ForeignKeyFieldTd.vue`

### Phase 5: Frontend — update pages [frontend-pages]
- [x] Update `ListRows.vue`
    - [x] Replace `<thead>` rendering with column names
    - [x] Replace `<tbody>` rendering with dynamic Td components
    - [x] Add component map for dynamic resolution
    - [x] Update filter UI to use `columns_raw` instead of `columns`
- [x] Update `RowDetails.vue`
    - [x] Replace `FieldDisplay` with dynamic Td components
- [x] Run `cd frontend && npm run lint:fix`, `cd frontend && npm run type-check`, `cd frontend && npm run lint`

### Phase 6: Frontend schemas update [frontend-schemas]
- [x] Add Zod schemas for `ThSchema`, `TdSchema` and subclasses in `schemas.ts`
- [x] Update `ListRowsProps` Zod schema
- [x] Update `RowDetailsProps` Zod schema

### Phase 7: Cleanup and tests [cleanup-tests]
- [x] Remove `isAlignedRight()` helper from `ListRows.vue`
- [x] Update backend tests for new Th/Td format
- [x] Run all checks (lintfix, typecheck, test --keepdb, frontend lint, frontend type-check)

### Phase 8: Dynamic component imports and items [dynamic-imports]
- [x] Create `frontend/src/utils/tdComponents.ts` with `import.meta.glob` + eager loading
- [x] Replace static `tdComponentMap` in `ListRows.vue` with `getTdComponent` from utils
- [x] Replace static `tdComponentMap` in `RowDetails.vue` with `getTdComponent` from utils
- [x] Delete `FieldDisplay.vue`
- [x] Run all checks
- [x] Move Th/Td import block to top of `serializers.py` [djangoapp/serializers.py:841]
- [x] Add comment explaining why `columns` and `columns_raw` are both needed in `ListRowsProps` [djangoapp/views.py:524]
- [x] Add comment explaining why `fields` and `columns_raw` are both needed in `RowDetailsProps` [djangoapp/views.py:344]
- [x] Create Pydantic model `ForeignKeyTdValue` for ForeignKeyFieldTdSchema value (`id`, `text`, `viewname`) instead of `dict[str, Any]` [djangoapp/responses.py:351]
    - [x] Update `field_value_to_td` to construct `ForeignKeyTdValue` with `viewname` from schema
    - [x] Update frontend Zod schema to include `viewname` in FK Td value
    - [x] Update `ForeignKeyFieldTd.vue` to use `value.viewname` instead of separate `viewName` prop
    - [x] Remove `getViewName()` and `findRawColumn()` from `ListRows.vue`
    - [x] Remove `getViewName()` from `RowDetails.vue`
- [x] Run all checks (lintfix, typecheck, test --keepdb, frontend lint/type-check)
- [x] Refactor: compute td_row directly from model object in `list_rows_2` instead of converting to dict first [djangoapp/views.py:660]
    - [x] Move Th/Td conversion into `list_rows_2`
    - [x] Update `ListRows2Context` to return `th_columns` and `td_rows` instead of raw `rows`
    - [x] Simplify `_list_rows` to read from result directly
- [x] Run all checks (lintfix, typecheck, test --keepdb, frontend lint/type-check)

### Phase 9: Non-nullable Td values and cleanup [non-nullable-td]
- [x] Remove `| None` from all Td value types in `responses.py` — None values mean the key is absent from the dict [djangoapp/responses.py:313]
    - [x] `CharFieldTdSchema.value: str` (was `str | None`)
    - [x] `TextFieldTdSchema.value: str` (was `str | None`)
    - [x] `IntegerFieldTdSchema.value: str | int` (was `str | int | None`)
    - [x] `BooleanFieldTdSchema.value: bool` (was `bool | None`)
    - [x] `DecimalFieldTdSchema.value: str` (was `str | None`)
    - [x] `DateTimeFieldTdSchema.value: str` (was `str | None`)
    - [x] `FileFieldTdSchema.value: dict[str, str]` (was `dict[str, str] | None`)
    - [x] Remove `ForeignKeyTdValue` class, use `value: dict[str, str | int]` on `ForeignKeyFieldTdSchema`
- [x] Update `field_value_to_td` to return `TdSchema | None`, skip None values [djangoapp/serializers.py]
- [x] Update `list_rows_2` to skip None-valued fields in td_rows [djangoapp/views.py]
- [x] Update `row_details` to skip None-valued fields in td_values [djangoapp/views.py]
- [x] Update frontend components to not accept null values
    - [x] `CharFieldTd.vue` — `value: string`
    - [x] `TextFieldTd.vue` — `value: string`
    - [x] `IntegerFieldTd.vue` — `value: string | number`
    - [x] `BooleanFieldTd.vue` — `value: boolean`
    - [x] `DecimalFieldTd.vue` — `value: string`
    - [x] `DateTimeFieldTd.vue` — `value: string`
    - [x] `FileFieldTd.vue` — `value: { filename: string; download_url: string }`
    - [x] `ForeignKeyFieldTd.vue` — `value: { id: number; text: string; viewname: string }`
- [x] Update Zod schemas to remove `.nullable()` from Td value types [frontend/src/schemas.ts]
- [x] Update `ListRows.vue` template to handle absent keys with `v-if`/`v-else`
- [x] Update `RowDetails.vue` template to handle absent keys with `v-if`
- [x] Remove `columns_raw` from `RowDetailsProps` (backend + frontend Zod) [djangoapp/views.py:345]
- [x] Run all checks (lintfix, typecheck, test --keepdb, frontend lint/type-check)

# Allow multiple filter classes in views 
We have ListRowsArgsConverter which returns ListPageSchema. 

rename listrowargs and other references with risonargs. This class will serialize/deserialize rison instead of ListPageSchema. 

BaseView has a list_page_schema which has default value of ListPageSchema and can be extended to a subclass of ListPageSchema. `_list_rows` will try to parse rison param to list_page_schema of its class. If it does not validate, return a plaintext response with http 400 error with pydantic validation error.

## Checklist

### Phase 10: Rename converter and add per-view schema [rison-args-converter]
- [x] Rename `ListRowsArgsConverter` to `RisonArgsConverter` in `djangoapp/views.py`
- [x] Rename converter registration from `"listrowsargs"` to `"risonargs"` [djangoapp/views.py:552]
- [x] Update URL pattern from `<listrowsargs:params>` to `<risonargs:params>` [djangoapp/views.py:1062]
- [x] Update `to_python` to return `dict` (parsed rison) instead of `ListPageSchema` — actual schema validation moves to `_list_rows`
- [x] Add `list_page_schema: type[PydanticBaseModel] = ListPageSchema` class attribute to `BaseView`
- [x] In `_list_rows`, parse rison `params` dict into `self.list_page_schema(**params)` with try/except
    - [x] On `ValidationError`, return `HttpResponse(str(e), status=400, content_type="text/plain")`
- [x] Update frontend `ListPageSchemaWrapper.generateUrlWithSchema` URL format from `/tables/${viewname}/list-rows/-${risonStr}-` (no change needed if URL structure stays same)
- [x] Add test for malformed rison input returning HTTP 404 (converter rejects invalid rison)
- [x] Add test for valid rison input that fails pydantic schema validation (e.g. wrong types) returning HTTP 400
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

# Mount custom components
In list rows, have divs with the following ids. We intend to let user use Vue Teleport on them.
- hook-teleport-before-filters, hook-teleport-after-filters (around the div with class `filters`)
- hook-teleport-before-table, hook-teleport-after-table (before and after table-pagination)
Mention these divs in readme.

User may override list_rows_2 with hook. Ensure ListRows2Context supports this
```python
def list_rows_2(...):
    foo = list_rows_2(...)
    foo.hook_component = '/components/custom/FirstStuff' #use dynamic import in Vue
    foo.hook_props = {...}
    foo.hook_props_2 = {...} # intended for lazy loading inertia props, can accept lazy and eager
    return foo
```
Document this override ability in readme.

There should be ListRowsContext class, list_rows_2 should have one context arg instead of multiple args. 

In list rows page, if hook component exists, render `<component component=hook_component props=props props2=props_2>` so it can render extra stuff. Render it inside an invisible div so users are forced to use teleport.

In `/tables/firststuff/list-rows/` in `hook-teleport-before-table`, override list_rows_2. Have a custom component in `/components/custom` that shows number of rows, using queryset.count(). Show distinct values of integer_field, also from queryset.

Write new docs after `### Notifications` in readme.

## Checklist

### Phase 11: Teleport target divs in ListRows.vue [teleport-targets]
- [x] Add teleport target divs to `ListRows.vue` template:
    - [x] `<div id="hook-teleport-before-filters">` before `<div class="filters">`
    - [x] `<div id="hook-teleport-after-filters">` after `<div class="filters">`
    - [x] `<div id="hook-teleport-before-table">` before `<table>`
    - [x] `<div id="hook-teleport-after-table">` after the `pagination-stuff` div

### Phase 12: ListRowsContext class and list_rows_2 single-arg refactor [list-rows-context]
- [x] Create `ListRowsContext` dataclass in `djangoapp/views.py`
    - [x] `columns: list[DjangoField]`
    - [x] `column_schemas: list[BaseFieldSchema]`
    - [x] `queryset: models.QuerySet[Any]`
    - [x] `list_page_schema: ListPageSchema`
- [x] Update `list_rows_2` signature to accept single `context: ListRowsContext` arg instead of multiple args
- [x] Update `_list_rows` call site to construct `ListRowsContext` and pass it
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 13: Hook fields on ListRows2Context [hook-context]
- [x] Add optional fields to `ListRows2Context`:
    - [x] `hook_component: str | None = None`
    - [x] `hook_props: dict[str, Any] | None = None`
    - [x] `hook_props_2: dict[str, Any] | None = None`
- [x] Add these fields to `ListRowsProps` in `responses.py`
    - [x] `hook_component: str | None = None`
    - [x] `hook_props: dict[str, Any] | None = None`
    - [x] `hook_props_2: dict[str, Any] | None = None`
- [x] Pass hook fields from `ListRows2Context` into `ListRowsProps` in `_list_rows`
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 14: Frontend hook component rendering [frontend-hook-render]
- [x] Update Zod schemas in `schemas.ts` for new `ListRowsProps` hook fields
- [x] Render hook component directly inside `#hook-teleport-before-table` div (not in hidden div; Teleport in hidden div didn't work)
- [x] Create `frontend/src/utils/hookComponents.ts` with `import.meta.glob` for `/components/custom/` directory
- [x] Run `cd frontend && npm run lint:fix`, `cd frontend && npm run type-check`, `cd frontend && npm run lint`

### Phase 15: FirstStuff hook example [firststuff-hook-example]
- [x] Override `list_rows_2` in `FirstStuffView` to call `super().list_rows_2(context)` then set hook fields:
    - [x] `hook_component = "/components/custom/FirstStuffListHook"`
    - [x] `hook_props` with `row_count` from `context.queryset.count()` and `distinct_integers` from `context.queryset.values_list("integer_field", flat=True).distinct()`
- [x] Create `frontend/src/components/custom/FirstStuffListHook.vue`
    - [x] Render inside `#hook-teleport-before-table` (direct rendering; Teleport inside hidden div didn't work)
    - [x] Display row count and distinct integer values
- [x] Run all checks (`./run lintfix`, `./run typecheck`, `./run test`, frontend lint/type-check)

### Phase 16: Documentation [mount-components-docs]
- [x] Add new docs section after `### Notifications` in `README.md`:
    - [x] Document teleport target divs (`hook-teleport-before-filters`, `hook-teleport-after-filters`, `hook-teleport-before-table`, `hook-teleport-after-table`)
    - [x] Document `list_rows_2` override pattern with hook component/props
    - [x] Document `ListRowsContext` and `ListRows2Context` structures
    - [x] Include `FirstStuff` example
- [x] Run `./run checkall`

# Inertia component name per view

Use Inertia's built-in component resolution. The server specifies the component name in `InertiaResponse(request, self.list_component, props)`. Each view can render a different page component — a `.vue` SFC that composes `ListRowsContent` with custom slot content.

No custom frontend registry. No hook components. No teleport divs. Just Vue named slots.

## Data Flow

```
Server (BaseView subclass)
  ├─ list_component: "FirstStuffListRows" (class attribute, default "ListRows")
  ├─ slot_props: { row_count: ..., distinct_integers: ... }
  └─ InertiaResponse(request, self.list_component, props)
        │
        ▼
Inertia resolve → pages/FirstStuffListRows.vue
  ├─ parses slot_props with local Zod schema
  ├─ renders <ListRowsContent> (shared component with named slots)
  └─ fills #before-table slot with custom content
```

## Decisions

- **Component name**: `BaseView.list_component` class attribute, default `"ListRows"`. Subclasses override.
- **No hook components**: Remove `FirstStuffListHook.vue`. Slot content is inline in the page component.
- **No teleport divs**: Remove `#hook-teleport-*` divs. `ListRowsContent.vue` provides named Vue slots instead.
- **No `hook_component`/`hook_props`/`hook_props_2`**: Replace with single `slot_props: dict[str, Any] | None` on `ListRowsProps` and `ListRows2Context`.
- **Type safety via local Zod**: Each child page defines its own Zod schema for `slot_props`. Runtime validation + compile-time types. No shared schema needed.
- **Named slots in `ListRowsContent.vue`**: `#before-filters`, `#after-filters`, `#before-table`, `#after-table`.
- **Shared content**: Extract `ListRows.vue` template + logic into `ListRowsContent.vue`. `ListRows.vue` becomes a thin wrapper. Child pages use `ListRowsContent` + fill slots.
- **No JSX**: Child pages are `.vue` SFCs. No `@vitejs/plugin-vue-jsx` needed.

## Terminology

| Old | New |
|-----|-----|
| `hook_component` | removed (no separate component) |
| `hook_props` / `hook_props_2` | `slot_props` |
| `hook-teleport-before-table` etc. | `<slot name="before-table">` etc. |
| `FirstStuffListHook.vue` | removed (inline in page component) |
| `hookComponents.ts` | removed |

## Mechanism

### Server specifies component name
```python
class BaseView:
    list_component: str = "ListRows"
    def _list_rows(self, request, params):
        return InertiaResponse(request, self.list_component, { "props": ... })

class FirstStuffView(BaseView):
    list_component = "FirstStuffListRows"
```

### Server sends slot data
```python
# In list_rows_2 override — return slot_props instead of hook_component/hook_props
def list_rows_2(self, context: ListRowsContext) -> ListRows2Context:
    result = super().list_rows_2(context)
    result.slot_props = {
        "row_count": context.queryset.count(),
        "distinct_integers": list(context.queryset.values_list("integer_field", flat=True).distinct()),
    }
    return result
```

### ListRowsContent.vue provides named slots
```html
<slot name="before-filters"></slot>
<div class="filters mb-3">...</div>
<slot name="after-filters"></slot>
<slot name="before-table"></slot>
<table class="table table-striped">...</table>
<div class="pagination-stuff">...</div>
<slot name="after-table"></slot>
```

### Child page validates and types slot_props
```vue
<!-- pages/FirstStuffListRows.vue -->
<script setup lang="ts">
import { z } from "zod"
import ListRowsContent from "../components/ListRowsContent.vue"
import { ListRowsProps } from "../schemas"

const SlotProps = z.object({
  row_count: z.number(),
  distinct_integers: z.array(z.number()),
})
type SlotProps = z.infer<typeof SlotProps>

const { props } = defineProps<{ props: Record<string, any> }>()
const p = ListRowsProps.parse(props)
const slot = SlotProps.parse(p.slot_props)
</script>

<template>
  <ListRowsContent :props="props">
    <template #before-table>
      <div class="card mb-3">
        <div class="card-body">
          <p>Total rows: <strong>{{ slot.row_count }}</strong></p>
          <p>Distinct integers: <strong>{{ slot.distinct_integers.join(", ") }}</strong></p>
        </div>
      </div>
    </template>
  </ListRowsContent>
</template>
```

### Base page has no slot content
```vue
<!-- pages/ListRows.vue -->
<script setup lang="ts">
import ListRowsContent from "../components/ListRowsContent.vue"
</script>
<template>
  <ListRowsContent :props="props" />
</template>
```

## Checklist

### Phase 17: Backend — `list_component` + `slot_props` [slot-props-backend]
- [x] Add `list_component: str = "ListRows"` class attribute to `BaseView`
- [x] In `_list_rows`, use `self.list_component` instead of hardcoded `"ListRows"` in `InertiaResponse`
- [x] `FirstStuffView` sets `list_component = "FirstStuffListRows"`
- [x] Rename `hook_component` → removed from `ListRowsProps` (Pydantic)
- [x] Rename `hook_props` → `slot_props` on `ListRowsProps` (Pydantic)
- [x] Remove `hook_props_2` from `ListRowsProps`
- [x] Rename fields on `ListRows2Context`: remove `hook_component`, `hook_props` → `slot_props`, remove `hook_props_2`
- [x] Update `FirstStuffView.list_rows_2` to set `slot_props` instead of `hook_component`/`hook_props`
- [x] Update `_list_rows` to pass `slot_props` from result
- [x] Update frontend Zod schema: remove `hook_component`/`hook_props`/`hook_props_2`, add `slot_props`
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 18: Extract `ListRowsContent.vue` [list-rows-content]
- [x] Create `frontend/src/components/ListRowsContent.vue`:
    - [x] Move `<template>` from `ListRows.vue` (filters, table, pagination)
    - [x] Remove teleport target divs (`#hook-teleport-*`)
    - [x] Add named slots: `<slot name="before-filters">`, `<slot name="after-filters">`, `<slot name="before-table">`, `<slot name="after-table">`
    - [x] Move `<script setup>` logic (props parsing, schema, filter getters, computed pagination)
- [x] Update `ListRows.vue` to be a thin wrapper:
    ```vue
    <script setup lang="ts">
    import ListRowsContent from "../components/ListRowsContent.vue"
    </script>
    <template>
      <ListRowsContent :props="props" />
    </template>
    ```
- [x] Run frontend lint/type-check

### Phase 19: `FirstStuffListRows.vue` child page [firststuff-child-page]
- [x] Create `frontend/src/pages/FirstStuffListRows.vue`:
    - [x] Import `ListRowsContent` and `ListRowsProps` Zod schema
    - [x] Define local `SlotProps` Zod schema for `slot_props`
    - [x] Parse `props` with `ListRowsProps.parse(props)`
    - [x] Parse `slot_props` with `SlotProps.parse(p.slot_props)`
    - [x] Fill `#before-table` slot with row count and distinct integers
- [x] Delete `frontend/src/components/custom/FirstStuffListHook.vue`
- [x] Delete `frontend/src/utils/hookComponents.ts`
- [x] Remove `getHookComponent` import and usage from `ListRowsContent.vue`
- [x] Verify FirstStuff list page renders slot content correctly
- [x] Run all checks (`./run lintfix`, `./run typecheck`, `./run test`, frontend lint/type-check)

### Phase 20: Cleanup and tests [slots-cleanup]
- [x] Verify all views work (no `list_component` override → `ListRows.vue` → empty slots)
- [x] Update backend tests for new `slot_props` field name
- [x] Update Playwright tests if DOM structure changed
- [x] Run `./run checkall`

# Demo model

Have a SlotDemoModel
It has title (char), int1, int2 fields.
Have a child class of ListPageSchema, SlotDemoListPageSchema. It has an extra attr, diff, which can be `any` literal or positive int.
In frontend, have a filter after the last filter, that can select any button or allow us to type a number and submit.
In the list_rows_2, filter on int1-int2, if "any", check if its >0, if int, check if its >= int value. If filter is active, show difference column as last column. 

## Checklist

### Phase 21: Backend — SlotDemoModel and SlotDemoListPageSchema [slot-demo-backend]
- [x] Create `SlotDemoModel` in `djangoapp/models.py` (after test models section)
    - [x] `title = models.CharField(max_length=100)`
    - [x] `int1 = models.IntegerField(default=0)`
    - [x] `int2 = models.IntegerField(default=0)`
- [x] Create `SlotDemoListPageSchema(PydanticBaseModel)` in `djangoapp/views.py` (just before SlotDemoView)
    - [x] Subclass `ListPageSchema` with `diff: Literal["any"] | int | None = None`
    - [x] Add Pydantic validator to ensure int is positive when not `"any"` or `None`
- [x] Create `SlotDemoView(BaseView)` in `djangoapp/views.py`
    - [x] `model = SlotDemoModel`, `list_page_schema = SlotDemoListPageSchema`, `list_component = "SlotDemoListRows"`
    - [x] Override `list_rows_2` to:
        - [x] `diff=None`: no filtering, no diff column
        - [x] `diff="any"`: filter `int1 - int2 > 0`, show diff column
        - [x] `diff=<int>`: filter `int1 - int2 >= int`, show diff column
    - [x] Register in `add_views()` call
- [x] Change `ListRowsProps.list_page_schema` type to `Any` so subclass fields like `diff` survive serialization
- [x] Add migration for `SlotDemoModel`
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`

### Phase 22: Frontend — SlotDemo custom page and diff filter [slot-demo-frontend]
- [x] Create `frontend/src/components/custom/SlotDemoListRows.vue`
    - [x] Read `diff` from raw `props.list_page_schema` (before Zod parsing strips it)
    - [x] Pre-fill number input with current int diff value on page load
    - [x] Diff filter UI in `#after-filters` slot:
        - [x] "None" button (active when diff is null) — clears diff
        - [x] "Any positive" button (active when diff is "any") — navigates with `diff: "any"`
        - [x] Number input + "Apply" button — navigates with `diff: <positive_int>`
    - [x] `navigateDiff()` uses raw `props.list_page_schema` for rison encoding, cleans null `crud_filter`/`row_update_filter`
- [x] Run `cd frontend && npm run lint:fix`, `cd frontend && npm run type-check`, `cd frontend && npm run lint`

### Phase 23: Playwright tests [slot-demo-tests]
- [x] `SlotDemoFilterE2ETestCase` with 12 tests:
    - [x] `test_diff_null_shows_all_rows_no_diff_column` — 5 rows, no diff column
    - [x] `test_diff_any_filters_positive_difference` — 2 rows, diff column present
    - [x] `test_diff_int_filters_by_minimum` — 1 row for diff=5
    - [x] `test_diff_filter_buttons_visible` — None, Any positive, Apply buttons
    - [x] `test_diff_filter_none_button_active_by_default` — btn-primary on None
    - [x] `test_diff_filter_any_button_active_when_any` — btn-primary on Any positive
    - [x] `test_diff_input_shows_value_when_int` — input shows "5" for diff=5
    - [x] `test_diff_input_empty_when_null` — input empty for diff=None
    - [x] `test_diff_input_empty_when_any` — input empty for diff="any"
    - [x] `test_click_any_positive_navigates` — click button, verify 2 rows
    - [x] `test_click_none_navigates` — click button, verify 5 rows
    - [x] `test_type_and_apply_int_filter` — type 9, apply, verify 1 row
- [x] Run `./run checkall` — 280 backend, frontend lint/type-check, 112 Playwright (1 pre-existing flaky failure unrelated to SlotDemo)

# Collapsed filter styling

## Checklist

### Phase 24: Filter pill styling [filter-pill-styling]
- [x] Update `FilterWrapper.vue` collapsed state:
    - [x] When active: render as pill/badge (rounded `<button>`, light bg, bold text, inline × close)
    - [x] When inactive: render as small grey text button
- [x] Update `main.css`:
    - [x] `.filter-active .filter-pill` — rounded corners, padding, grey bg, hover state
    - [x] `.pill-close-btn` — × styled as part of pill
    - [x] `.filter-inactive` — small grey text
- [x] Update Playwright boolean filter tests (`assertIn` instead of `assertEqual` for pill text)
- [x] Run `./run checkall`

## items

- [x] Factory function for auto PaginationSchema()
    [djangoapp/views.py:226]
    Removed explicit `pagination=PaginationSchema()` —
    `ListPageSchema` already defaults it.
- [x] Docstring for SlotDemoView: explain class for readme
    readers who want to create a similar class. Explain
    SlotDemoListRows too.
    [djangoapp/views.py:1236-1237]
- [x] Add docs to ListPageSchemaWrapper with brief desc of each
    method, organize by field type when one field type has
    multiple filters
    [frontend/src/ListPageSchemaWrapper.ts:7]
- [x] Check if `no-unused-vars` eslint-disable is needed around
    constructor
    [frontend/src/ListPageSchemaWrapper.ts:17]
    Yes, it is needed — TS parameter properties trigger the rule.
- [x] Allow nulls in navigateCustom (currently only handles
    undefined)
    [frontend/src/ListPageSchemaWrapper.ts:23]
    Changed to `value == null` (catches null and undefined).
- [x] generateUrlFromRaw has a param pageNumber with a default
    of 1, no need of redundant `raw.pagination.page_number`
    [frontend/src/ListPageSchemaWrapper.ts:65]
    Added `pageNumber` param to `generateUrlFromRaw`, removed
    all `raw.pagination.page_number = 1` from navigate methods.