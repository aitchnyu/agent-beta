# Tables stuff

## Functionality

Proxy classes, BaseModel - can allow other models to work. For example, User from another app.

### CRUD API

This document describes the API for controlling row and column resolution in the tables application.

#### Overview

The tables application provides three main extension points for controlling data access and visibility:

1. **`resolve_rows`** - Control which rows a user can access for each operation
2. **`resolve_columns`** - Control which columns are visible for each operation
3. **`save_stuff`** - Control validation and saving of rows

#### Row Resolution

The `resolve_rows` classmethod controls which rows a user can access for list, details, update, and delete operations.

##### Method Signature

```python
@classmethod
def resolve_rows(cls, context: ResolveRowsContext) -> models.QuerySet[typing.Self]:
    ...
```

##### ResolveRowsContext

| Field | Type | Description |
|-------|------|-------------|
| `user` | `User \| None` | The authenticated user, or None for anonymous |
| `query` | `QuerySet` | The default queryset for this model |
| `operation` | `Literal["list", "details", "update", "delete"]` | The operation being performed |

##### Base Behavior

The base implementation returns `context.query` unchanged. Override to filter rows based on user or operation.

##### Example: Filter rows by user

```python
@classmethod
def resolve_rows(cls, context: ResolveRowsContext) -> models.QuerySet[typing.Self]:
    qs = super().resolve_rows(context)
    if context.user and not context.user.is_superuser:
        # Regular users can only see their own rows
        qs = qs.filter(owner=context.user)
    return qs
```

##### Example: Prevent updates and deletes

```python
@classmethod
def resolve_rows(cls, context: ResolveRowsContext) -> models.QuerySet[typing.Self]:
    # Base implementation just returns context.query unchanged
    # Override to filter rows based on operation
    if context.operation in ("update", "delete"):
        # Prevent all updates and deletes by returning empty queryset
        return context.query.none()
    return context.query
```

#### Column Resolution

The `resolve_columns` classmethod controls which columns are visible for each operation. Return `None` to deny access entirely.

##### Method Signature

```python
@classmethod
def resolve_columns(cls, context: ResolveColumnsContext) -> tuple[str, ...] | None:
    ...
```

##### ResolveColumnsContext

| Field | Type | Description |
|-------|------|-------------|
| `user` | `User \| None` | The authenticated user, or None for anonymous |
| `columns` | `tuple[str, ...]` | The default columns from `include_columns` |
| `operation` | `Literal["create", "list", "details", "update", "delete"]` | The operation being performed |
| `maybe_row` | `BaseModel \| None` | The row for details/update/delete operations |

##### Base Behavior

The base implementation returns `context.columns` unchanged. Return `None` to deny access (results in 404 for the user).

##### Example: Different columns for list vs details

```python
@classmethod
def resolve_columns(cls, context: ResolveColumnsContext) -> tuple[str, ...] | None:
    if context.operation == "list":
        # Show only summary columns in list view
        return ("id", "name", "status")
    # Show all columns in details view
    return context.columns
```

##### Example: Prevent creation

```python
@classmethod
def resolve_columns(cls, context: ResolveColumnsContext) -> tuple[str, ...] | None:
    if context.operation == "create":
        # Return None to prevent creation
        return None
    return super().resolve_columns(context)
```


#### Saving

The `save_stuff` method handles validation and saving of rows. Override to add custom validation logic.

##### Method Signature

```python
def save_stuff(self, context: SaveContext[typing.Self]) -> None:
    ...
```

##### SaveContext

| Field | Type | Description |
|-------|------|-------------|
| `user` | `User \| None` | The authenticated user, or None for anonymous |
| `existing_row` | `BaseModel \| None` | The existing row for updates, None for creates |

##### Base Behavior

The base implementation calls `self.save()`. Override to add validation before saving.

##### Example: Field validation

```python
def save_stuff(self, context: SaveContext[typing.Self]) -> None:
    if self.char_field == "11":
        raise ValidationError({
            "char_field": "value is 11",
            "_top": "Oops, something is 11"
        })
    super().save_stuff(context)
```

##### Example: Top-level error

```python
def save_stuff(self, context: SaveContext[typing.Self]) -> None:
    if self.start_date > self.end_date:
        raise ValidationError({
            "_top": "Start date must be before end date"
        })
    super().save_stuff(context)
```

##### Example: Conditional validation

```python
def save_stuff(self, context: SaveContext[typing.Self]) -> None:
    # Only validate on create
    if context.existing_row is None:
        if self.status == "published":
            raise ValidationError({
                "status": "Cannot create rows with published status"
            })
    super().save_stuff(context)
```

##### Example: Changing values

```python
def save_stuff(self, context: SaveContext[typing.Self]) -> None:
    self.combined = self.cost_1 + self.cost_2
    super().save_stuff(context)
```

#### CRUD Operation Order

For each CRUD operation, the methods are called in this order:

| Operation | Method Order |
|-----------|--------------|
| **create** | `resolve_columns` → `save_stuff` |
| **list** | `resolve_rows` → `resolve_columns` |
| **details** | `resolve_rows` → `resolve_columns` |
| **update** | `resolve_rows` → `resolve_columns` → `save_stuff` |
| **delete** | `resolve_rows` → `resolve_columns` |

#### Error Handling

- If `resolve_rows` returns an empty queryset for details/update/delete operations, the user gets a 404 error. For list operations, an empty page is shown.
- If `resolve_columns` returns `None`, the user gets a 404 error (for all operations including create)
- If `save_stuff` raises `ValidationError`, the errors are displayed in the frontend:
  - Field-specific errors: `{"field_name": "error message"}` - shown next to the field
  - Form-level errors: `{"_top": "overall form error"}` - shown at the top of the form
  - Both can be combined: `{"field_name": "error", "_top": "overall error"}`

#### include_columns

The `include_columns` class attribute defines the default set of columns and their order:

```python
class MyModel(BaseModel):
    include_columns = ("id", "name", "status", "created_at")
    
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    internal_field = models.CharField(max_length=50)  # Not included
```

Columns not in `include_columns` are hidden from all operations by default.


### Filtering
| Filter Type                        | Operators                                                      | Example                                                                                                                                                                                                     |
|------------------------------------|----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Boolean** (`bv`)                 | `true`, `false`                                                | `?f[is_active]=(d:bv,value:true)`                                                                                                                                                      |
| **Integer Comparison** (`icomp`)   | `eq`, `gt`, `gte`, `lt`, `lte`, `ne`, `inc`, `ex`              | `?f[age]=(d:icomp,op:gt,number_1:25)` (range: `?f[age]=(d:icomp,op:inc,number_1:18,number_2:30)`)                                                     |
| **Integer Choice** (`ich`)         | `any`, `none`                                                  | `?f[status]=(d:ich,op:any,options:[1,2,3])`                                                                                                                                      |
| **Integer Null** (`null`)          | `true`, `false`                                                | `?f[optional_field]=(d:null,value:true)`                                                                                                                                               |
| **Char Choice** (`cc`)             | `any`, `none`                                                  | `?f[category]=(d:cc,op:any,options:[red,blue])`                                                                                                                                  |
| **Char Text** (`ct`)               | Contains text                                                  | `?f[name]=(d:ct,text:john)`                                                                                                                                                            |
| **Char Blank** (`cb`)              | `true`, `false`                                                | `?f[description]=(d:cb,value:true)`                                                                                                                                                    |
| **Decimal Comparison** (`dcomp`)   | `eq`, `gt`, `gte`, `lt`, `lte`, `ne`, `inc`, `ex`              | `?f[price]=(d:dcomp,op:gt,number_1:100.50)` (range: `?f[price]=(d:dcomp,op:inc,number_1:50,number_2:200)`)                                            |
| **Decimal Null** (`dnull`)         | `true`, `false`                                                | `?f[discount]=(d:dnull,value:false)`                                                                                                                                                   |
| **Datetime Comparison** (`dtcomp`) | `eq`, `gt`, `gte`, `lt`, `lte`, `ne`, `inc`, `ex`              | `?f[created_at]=(d:dtcomp,op:gt,datetime_1:2023-01-01T00:00)` (range: `?f[created_at]=(d:dtcomp,op:inc,datetime_1:2023-01-01,datetime_2:2023-12-31)`) |
| **Datetime Null** (`dtnull`)       | `true`, `false`                                                | `?f[updated_at]=(d:dtnull,value:true)`                                                                                                                                                 |
| **Datetime Relative** (`dtrel`)    | `past`, `next` with units (`hours`, `days`, `months`, `years`) | `?f[created_at]=(direction:past,d:dtrel,quantity:1,unit:days)`                                                                                                                         |
| **Foreign Key** (`fk`)             | `any`, `none`                                                  | `?f[user_fk]=(d:fk,op:any,options:[1,2,3])`                                                                                                                                      |
| **Foreign Key Null** (`fknull`)    | `true`, `false`                                                | `?f[user_fk]=(d:fknull,value:true)`                                                                                                                                                    |
#### List Page Filter

The `RowUpdateFilter` allows filtering rows on the list page based on their row update history:

- **Users** - Filter by which users made changes
- **Actions** - Filter by action type (created, updated, commented)
- **Date Range** - Filter by when changes occurred
- **Mode** - "any of" (default) or "none of"

Example URL: `?f[__row_update__]=(d:row_update,mode:any,user_ids:[1,2],actions:[created_row,updated_row])`

### Row Update Logs

The `RowUpdate` model provides an audit trail for all create, update, and comment actions on rows.

#### Overview

Every time a row is created or updated, a `RowUpdate` entry is automatically created to track the change. Users can also add comments to rows. These updates are displayed in the row details page as a timeline.

#### RowUpdate Model

| Field | Type | Description |
|-------|------|-------------|
| `action` | `CharField` | One of: `created_row`, `updated_row`, `commented` |
| `created_at` | `DateTimeField` | When the action occurred |
| `created_by` | `ForeignKey(User)` | The user who performed the action |
| `modelname` | `CharField` | The model's app_label.model_name |
| `row_pk` | `IntegerField` | The primary key of the affected row |
| `_values` | `JSONField` | Serialized column values (for create/update) |
| `comment_content` | `TextField` | The comment text (for comments) |
| `comment_deleted_at` | `DateTimeField` | When the comment was soft-deleted |
| `comment_deleted_by` | `ForeignKey(User)` | The user who deleted the comment |
| `edited_at` | `DateTimeField` | When the comment was last edited |
#### Permission System

Access to row updates is controlled by the `row_update_access_timeout` method on BaseModel. This is an **instance method** that returns a timeout in seconds. Return `0` or negative to deny access.

##### Method Signature

```python
def row_update_access_timeout(self, context: CommentPermissionContext) -> int:
    ...
```

##### Return Value

- `int > 0`: The timeout in seconds. Comments can be edited/deleted within this window.
- `int <= 0`: Access denied for the operation.

##### Context Class

There is one context class used for all comment operations:

| Field | Type | Description |
|-------|------|-------------|
| `user` | `User \| None` | The authenticated user making the request |
| `operation` | `Literal["create_comment", "update_comment", "delete_comment"]` | The operation being performed |
| `row` | `BM \| None` | The model instance (for update/delete operations) |


##### Default Implementation

```python
def row_update_access_timeout(self, context: CommentPermissionContext) -> int:
    """Return timeout in seconds for the given comment operation.

    Default implementation returns 86400 (24 hours) for all operations.
    Override this method to customize permission logic.

    For create_comment operation: Any positive integer allows comment creation.
    For update_comment operation: User must be comment author within timeout.
    For delete_comment operation: Any user can delete within timeout (no author check).

    Args:
        context: CommentPermissionContext containing user and operation info.

    Returns:
        int: Timeout in seconds (operation allowed within this window)
             0 or negative: Operation not allowed

    """
    return 86400  # 24 hours
```


#### Example: Only allow staff to comment

```python
def row_update_access_timeout(self, context: CommentPermissionContext) -> int:
    if context.operation == "create_comment":
        if context.user is None or not context.user.is_staff:
            return 0
        return 86400  # 24 hours
    return super().row_update_access_timeout(context)
```

#### Example: Extended edit window for admins

```python
def row_update_access_timeout(self, context: CommentPermissionContext) -> int:
    if context.operation == "update_comment":
        # Admins can edit any comment within 7 days
        if context.user and context.user.is_superuser:
            return 7 * 86400  # 7 days
    # Use default 24-hour window for others
    return super().row_update_access_timeout(context)
```

### Row Update Redaction

The `redact_row_updates` method controls which columns are visible in row updates.

#### Method Signature

```python
@classmethod
def redact_row_updates(
    cls,
    context: RowUpdateRedactContext,
) -> dict[int, list[str] | Literal["datetime_only", "datetime_user"]]:
    ...
```

#### RowUpdateRedactContext

| Field | Type | Description |
|-------|------|-------------|
| `user` | `User \| None` | The authenticated user making the request |
| `row_updates` | `Sequence[RowUpdate]` | The row updates to potentially redact |
| `row` | `BaseModel` | The row being viewed |

#### Return Value

A dictionary mapping row update IDs to visibility:
- `list[str]`: Column names that are visible (full access)
- `"datetime_only"`: Only show timestamp, hide creator and all column values
- `"datetime_user"`: Show timestamp and creator username, hide all column values

#### Default Behavior

Returns all recorded columns for all row updates:

```python
@classmethod
def redact_row_updates(cls, context: RowUpdateRedactContext) -> dict[int, list[str] | Literal["datetime_only", "datetime_user"]]:
    return {ru.id: ru.recorded_columns() for ru in context.row_updates}
```

#### Example: Redact sensitive columns for non-staff

```python
class SensitiveModel(BaseModel):
    salary = models.DecimalField(...)
    notes = models.TextField()

    @classmethod
    def redact_row_updates(cls, context: RowUpdateRedactContext) -> dict[int, list[str] | Literal["datetime_only", "datetime_user"]]:
        if context.user and context.user.is_staff:
            # Staff can see all columns
            return {ru.id: ru.recorded_columns() for ru in context.row_updates}
        # Non-staff see datetime and user only
        return {ru.id: "datetime_user" for ru in context.row_updates}
```

#### Example: Conditional redaction based on column content

Redact only when sensitive columns like "salary" are part of the row update:

```python
class EmployeeModel(BaseModel):
    salary = models.DecimalField(...)
    department = models.CharField(...)

    @classmethod
    def redact_row_updates(cls, context: RowUpdateRedactContext) -> dict[int, list[str] | Literal["datetime_only", "datetime_user"]]:
        if context.user and context.user.is_staff:
            # Staff can see all columns
            return {ru.id: ru.recorded_columns() for ru in context.row_updates}
        
        # Check each row update for sensitive columns
        result = {}
        for ru in context.row_updates:
            if "salary" in ru.recorded_columns():
                # Non-staff see only datetime and user when salary is involved
                result[ru.id] = "datetime_user"
            else:
                # Show all columns for non-sensitive updates
                result[ru.id] = ru.recorded_columns()
        return result
```


### Public IDs

Models can designate a field other than `id` as the public identifier exposed to web clients. The internal `.pk`/`.id` is never sent to the client.

#### Configuration

Set `public_id_field` on your model:

```python
class Article(BaseModel):
    public_id_field: ClassVar[str] = "slug"
    slug = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
```

By default, `public_id_field = "id"`, so most models need no configuration.

#### Auto-generation

When a model has a custom `public_id_field`, `BaseModel.save()` automatically
generates a value on creation if the field is still empty. The generator is only
called during `save()` — not on every model instantiation — which minimizes gaps
in sequential IDs. The default `public_id_generator` produces a UUID v7 string:

```python
class Article(BaseModel):
    public_id_field: ClassVar[str] = "slug"
    slug = models.CharField(max_length=100, unique=True)
    # public_id_generator is inherited — returns UUID v7 by default
```

Override `public_id_generator` for different strategies:

```python
from djangoapp.public_ids import generate_sequence_id

class Invoice(BaseModel):
    public_id_field: ClassVar[str] = "seq_id"
    public_id_generator: ClassVar[Callable[[], Any]] = lambda: generate_sequence_id("%Y-%m-%d-ID")
    seq_id = models.CharField(max_length=100, unique=True, editable=False)
```

For cases where you need more control (e.g. validation on update), you can still
set the public ID manually in `save_stuff()` instead of relying on auto-generation:

```python
def save_stuff(self, context):
    if context.existing_row is not None:
        validate_public_id_format(self.slug)
    super().save_stuff(context)
```

#### Properties and Methods

| Method | Description |
|--------|-------------|
| `row.public_id` | Returns `str(getattr(row, row.public_id_field))` |
| `Model.has_custom_public_id()` | Returns `True` if `public_id_field != "id"` |
| `Model.get_by_public_id(queryset, public_id)` | Filters queryset by the public_id field |
| `Model.get_by_public_id_or_404(queryset, public_id)` | Same, raises `Http404` if not found |

#### ID Generator Functions

`djangoapp/public_ids.py` provides generator functions you can use with `public_id_generator`:

- `BaseModel.generate_uuid7_id() -> str` — generates a UUID v7 string using Python 3.14's `uuid.uuid7()`. This is the default `public_id_generator`.

- `generate_sequence_id(format_str, start=1, now=None) -> str` — generates date-based sequential IDs using Postgres sequences. The format string must contain exactly one `ID` placeholder:

```python
public_id_generator: ClassVar[Callable[[], Any]] = lambda: generate_sequence_id("%Y-%m-%d-ID")
# e.g. "2026-04-30-1"
```

#### Validation

Public ID values must match `[a-zA-Z0-9_-]+`. Use `public_id_django_validator` on editable fields:

```python
slug = models.CharField(max_length=100, unique=True, validators=[public_id_django_validator])
```

For programmatic validation, use `validate_public_id_format(value)` which raises `ValueError`, or `public_id_django_validator(value)` which raises Django's `ValidationError`.

#### Smoke Tests

When `has_custom_public_id()` is `True`, smoke tests validate:
- The `public_id_field` exists on the model
- It is a model field (not a property or annotation)
- It has `unique=True`
- It is not nullable (`null=False`)
- `"id"` is NOT in `include_columns`


### Notifications

Models can notify users when rows are created, updated, or commented on.

#### notify_users Method

Override `notify_users` on your model to specify which users should receive notifications for a given action.

##### Method Signature

```python
def notify_users(self, context: NotifyContext) -> Sequence[User]:
    ...
```

##### NotifyContext Types

| Context Type | `type` field | When triggered |
|---|---|---|
| `CreateRowNotifyContext` | `"create_row"` | After a row is created via `save_stuff` |
| `UpdateRowNotifyContext` | `"update_row"` | After a row is updated via `save_stuff` |
| `CreateCommentNotifyContext` | `"create_comment"` | After a comment is created |
| `UpdateCommentNotifyContext` | `"update_comment"` | After a comment is edited |

Each context has a `user` field (the actor) and a `type` field.

##### Default Behavior

Returns an empty list — no notifications are sent by default.

##### Actor Exclusion Rule

Users are never notified about their own actions. Even if `notify_users` returns the actor, the notification system filters them out automatically.

##### Example: Notify all staff when a row is created

```python
def notify_users(self, context: NotifyContext) -> Sequence[User]:
    if context.type == "create_row":
        return list(User.objects.filter(is_staff=True))
    return []
```

##### Example: Notify row owner on update or comment

```python
def notify_users(self, context: NotifyContext) -> Sequence[User]:
    if context.type in ("update_row", "create_comment"):
        return [self.owner] if self.owner else []
    return []
```

#### RowUpdateUserNotification Model

| Field | Type | Description |
|---|---|---|
| `row_update` | `ForeignKey(RowUpdate)` | The row update that triggered the notification |
| `user` | `ForeignKey(User)` | The user to notify |

A `UniqueConstraint(fields=["row_update", "user"])` prevents duplicate notifications. Upserts use `bulk_create(ignore_conflicts=True)`.

#### Notifications Page

Authenticated users can view their notifications at `/tables/notifications/page`. The page shows a sidebar with per-model counts, filtering, select-all/delete, and a "Clear all" button. Pagination is 50 per page.

### Custom Content in List Rows

Refer SlotDemoListRows for an example.

#### Overriding `list_rows`

Override `list_rows` on your view to pass custom data to the page. The method receives a `ListRowsContext` and returns a `ListRows2Context`. Set `slot_props` on the result to pass typed data to the page component:

```python
class MyModelView(BaseView):
    model = MyModel
    list_component = "MyModelListRows"

    def list_rows(self, context: ListRowsContext) -> ListRows2Context:
        result = super().list_rows(context)
        result.slot_props = {
            "row_count": context.queryset.count(),
        }
        return result
```

##### ListRowsContext (input to `list_rows`)

| Field | Type | Description |
|-------|------|-------------|
| `columns` | `list[DjangoField]` | Resolved columns |
| `column_schemas` | `list[BaseFieldSchema]` | Schema metadata for each column |
| `queryset` | `QuerySet` | Filtered queryset ready for pagination |
| `list_page_schema` | `ListPageSchema` | Pagination and filter params |

##### ListRows2Context (output of `list_rows`)

| Field | Type | Description |
|-------|------|-------------|
| `column_schemas` | `list[BaseFieldSchema]` | Column schemas |
| `th_columns` | `list[ThSchema]` | Table header schemas |
| `cell_values` | `list[dict[str, TdSchema]]` | Serialized row data |
| `page` | `dict[str, int]` | Pagination info |
| `human_row_references` | `dict[str, dict[int, str]]` | FK display names |
| `slot_props` | `dict[str, Any] \| None` | Custom data passed to the page component's slots |

#### Custom Page Component

Set `list_component` on your view to specify a different Inertia page component. The page component uses `ListRowsContent` with named slots.

Without Zod (simple, no validation):

```vue
<!-- pages/MyModelListRows.vue -->
<script setup lang="ts">
import ListRowsContent from "../components/ListRowsContent.vue"

const { props } = defineProps<{ props: Record<string, any> }>()
const number = (props.slot_props as { row_count: number }).row_count
</script>

<template>
  <ListRowsContent :props="props">
    <template #before-table>
      <div class="card mb-3">
        <div class="card-body">
          <p>Total rows: <strong>{{ number }}</strong></p>
        </div>
      </div>
    </template>
  </ListRowsContent>
</template>
```

With Zod (recommended for type safety):

```vue
<!-- pages/MyModelListRows.vue -->
<script setup lang="ts">
import { z } from "zod"
import ListRowsContent from "../components/ListRowsContent.vue"
import { ListRowsProps } from "../schemas"

const SlotProps = z.object({
  row_count: z.number(),
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
        </div>
      </div>
    </template>
  </ListRowsContent>
</template>
```

The base `ListRows.vue` page renders `ListRowsContent` with no slot content. Views without a `list_component` override use it by default.

The list rows page provides Vue named slots for injecting custom content:

| Slot name | Location |
|-----------|----------|
| `before-filters` | Before the filter bar |
| `after-filters` | After the filter bar |
| `before-table` | Before the data table |
| `after-table` | After pagination |

### Schema Types

The backend sends two parallel schema systems to the frontend: **TdSchema** for displaying cell values and **InputSchema** for rendering form inputs.

#### TdSchema (display)

TdSchema variants are used for rendering cell values in list rows and details display mode. Each variant carries a `component` path for frontend dynamic resolution.

| Variant | Component | Value Type |
|---------|-----------|------------|
| `CharFieldTdSchema` | `/components/cells/CharFieldTd` | `str` |
| `TextFieldTdSchema` | `/components/cells/TextFieldTd` | `str` |
| `IntegerFieldTdSchema` | `/components/cells/IntegerFieldTd` | `str \| int` |
| `BooleanFieldTdSchema` | `/components/cells/BooleanFieldTd` | `bool` |
| `DecimalFieldTdSchema` | `/components/cells/DecimalFieldTd` | `str` |
| `DateTimeFieldTdSchema` | `/components/cells/DateTimeFieldTd` | `str` |
| `FileFieldTdSchema` | `/components/cells/FileFieldTd` | `dict[str, str]` |
| `ForeignKeyFieldTdSchema` | `/components/cells/ForeignKeyFieldTd` | `ForeignKeyTdValue` |

Frontend resolution uses `tdComponents.ts` via `getTdComponent(td)`.

#### InputSchema (form inputs)

InputSchema variants are used for rendering form inputs on create and edit pages. Each variant carries a `component` path for frontend dynamic resolution. They parallel TdSchema but include form-specific metadata (max_length, choices, decimal_places, etc.).

| Variant | Component | Key Fields |
|---------|-----------|------------|
| `CharFieldInputSchema` | `/components/inputs/CharFieldInput` | `max_length`, `choices`, `default` |
| `TextFieldInputSchema` | `/components/inputs/TextFieldInput` | `length`, `default` |
| `IntegerFieldInputSchema` | `/components/inputs/IntegerFieldInput` | `choices`, `default` |
| `BooleanFieldInputSchema` | `/components/inputs/BooleanFieldInput` | `default` |
| `DecimalFieldInputSchema` | `/components/inputs/DecimalFieldInput` | `decimal_places`, `default` |
| `DateTimeFieldInputSchema` | `/components/inputs/DateTimeFieldInput` | `default` |
| `FileFieldInputSchema` | `/components/inputs/FileFieldInput` | `default` |
| `ForeignKeyFieldInputSchema` | `/components/inputs/ForeignKeyFieldInput` | `view_name`, `default` |

Frontend resolution uses `inputComponents.ts` via `getInputComponent(input)`.

The conversion from `FieldSchema` (Django field metadata) to `InputSchema` is done by `field_schema_to_input()` in `serializers.py`.

### Custom Content in Row Details

Refer SlotDemoRowDetails for an example.

#### Details Page Behavior

The details page has two modes:

- **Display mode** (default): Shows field values as TdSchema cells using dynamic cell components (same as list view). Double-clicking a field opens edit mode with that field focused. An Edit button opens edit mode focused on the first field.
- **Edit mode**: Renders an inline form using InputSchema components. Save returns to display mode; Cancel also returns to display mode.

The backend always includes edit data (InputSchema fields and values) in the response props. The frontend manages display/edit state client-side — toggling between modes does not require a server round-trip. Double-clicking a cell in list view navigates to the details page and opens edit mode via a custom DOM event.

#### Overriding `row_details`

Override `row_details` on your view to pass custom data to the page. The method receives a `RowDetailsContext` and returns it. Set `slot_props` on the context to pass typed data to the page component:

```python
class MyModelView(BaseView):
    model = MyModel
    details_component = "MyModelRowDetails"

    def row_details(self, context: RowDetailsContext) -> RowDetailsContext:
        context = super().row_details(context)
        context.slot_props = {
            "extra_info": "some value",
        }
        return context
```

##### RowDetailsContext (input and output of `row_details`)

| Field | Type | Description |
|-------|------|-------------|
| `row` | `BaseModel` | The model instance |
| `user` | `User \| None` | Current user |
| `columns` | `list[DjangoField]` | Resolved columns |
| `column_schemas` | `list[BaseFieldSchema]` | Schema metadata for each column |
| `th_columns` | `list[ThSchema]` | Table header schemas (populated by `row_details`) |
| `cell_values` | `dict[str, TdSchema]` | Serialized field data (populated by `row_details`) |
| `slot_props` | `dict[str, Any] \| None` | Custom data passed to the page component's slots |

#### Custom Details Page Component

Set `details_component` on your view to specify a different Inertia page component. The page component uses `RowDetailsContent` with named slots.

Without Zod (simple, no validation):

```vue
<!-- components/custom/MyModelRowDetails.vue -->
<script setup lang="ts">
import RowDetailsContent from "../RowDetailsContent.vue"

const { props } = defineProps<{ props: Record<string, any> }>()
const extra = (props.slot_props as { extra_info: string }).extra_info
</script>

<template>
  <RowDetailsContent :props="props">
    <template #after-row>
      <p>{{ extra }}</p>
    </template>
  </RowDetailsContent>
</template>
```

With Zod (recommended for type safety):

```vue
<!-- components/custom/MyModelRowDetails.vue -->
<script setup lang="ts">
import { z } from "zod"
import RowDetailsContent from "../RowDetailsContent.vue"
import { RowDetailsProps } from "../../schemas"

const SlotProps = z.object({
  extra_info: z.string(),
})
type SlotProps = z.infer<typeof SlotProps>

const { props } = defineProps<{ props: Record<string, any> }>()
const p = RowDetailsProps.parse(props)
const slot = SlotProps.parse(p.slot_props)
</script>

<template>
  <RowDetailsContent :props="props">
    <template #after-row>
      <p>{{ slot.extra_info }}</p>
    </template>
  </RowDetailsContent>
</template>
```

The base `RowDetails.vue` page renders `RowDetailsContent` with no slot content. Views without a `details_component` override use it by default.

The row details page provides Vue named slots for injecting custom content:

| Slot name | Location |
|-----------|----------|
| `before-row` | Before the field list |
| `after-row` | After the field list |

### Articles

The articles system provides a blog-like feature with WYSIWYG editing, image uploads, tags, and author support. It is mounted under `/articles`. The app customizes permissions by registering two resolvers — **editors** and **participants** — via decorators.

#### Editors and participants

There are two roles (plus anonymous). Which users count as each is decided by the app, not the framework:

```python
# djangoapp/views/app.py
from django.db.models import QuerySet
from djangoapp.models.base import User
from djangoapp.views.articles import article_editors, article_participants


@article_editors
def _article_editors() -> QuerySet[User]:
    return User.objects.filter(is_superuser=True)


@article_participants
def _article_participants() -> QuerySet[User]:
    return User.objects.all()
```

`@article_editors` and `@article_participants` register a zero-arg callable that returns the `QuerySet[User]` of editors / participants. The article views and models test membership via these querysets (`Article.is_editor(user)`, `Article.is_participant(user)`). If a resolver is not registered, you will encounter `NotImplementedError`.

> **Invariant: editors ⊆ participants.** The app's resolvers must return an editors set that is a subset of the participants set (the default does — editors are superusers, participants are all users).

#### Permissions (articles)

| Operation | editor | participant | anonymous |
|-----------|--------|--------------|-----------|
| **list** | published + own drafts; `?unpublished=true` shows **every** article (all drafts) | published + own drafts | published only |
| **details** | any article | published + own drafts | published only |
| **create** | yes; may assign any participant as the article's `author` | no (404) | no (404) |
| **update** | any article | only articles where they are the `author` | no (404) |
| **delete** | any article | only articles where they are the `author` | no (404) |
| **tags (view/create/update/delete)** | yes | no (404) | no (404) |
| **upload image** | any article | only their own articles | no (404) |
| **download image** | any article | published articles + their own drafts | published only |
| **subscribe / unsubscribe** | published articles | published articles | no (404) |

#### Permissions (comments)

Comments live on published articles (and editors'/authors' drafts for reading). Creating a comment additionally requires the article's `is_commenting_enabled` flag (per-article toggle; 404 when off). Comment edits are allowed within a short timeout after posting.

| Operation | editor | participant | anonymous |
|-----------|--------|--------------|-----------|
| **list (read)** | on any article they can view | on published + their own-draft articles | on published only |
| **create** | on published articles | on published articles | no (404) |
| **update** | own comment, within the edit timeout | own comment, within the edit timeout | no (404) |
| **delete (soft)** | any comment | own comment, or any comment on an article they author | no (404) |

Drafts (articles with no `published_at`) are readable only by editors and the article's author; commenting and subscribing are disabled on drafts entirely (they return 404). The first time a user comments on a published article they are automatically added as a subscriber.

### Users

The users system provides a custom `User` model with public profile pages and a superuser-only admin (list, edit, history). `AUTH_USER_MODEL` is set to the project `User` (`AbstractUser` + `BaseModel`).

It is implemented as plain Django Ninja `Router` functions in `djangoapp/views/users.py`, exposed as a ready-made `users_api` instance mounted under `/users` (see the Articles mounting snippet above).

#### Pages & endpoints

All `/users` management routes are superuser-only (404 otherwise). `/users/id/{public_id}` is public.

| Route | Method | Access | Description |
|-------|--------|--------|-------------|
| `/users/list` | GET | Superuser | Paginated table (25/page, orphans 5) of all users: Full name, Username, Email, Public, Staff, Superuser. Inactive rows render fainter. A single-select username search above the table jumps to a profile. |
| `/users/id/{public_id}` | GET | Public (anonymous allowed) | First and last name always shown; `username` and `description` only when the profile's `has_public_profile=True` (the owner is gated by the same flag). Superuser viewers additionally see the target's email, public/staff/superuser/active flags and a history count. |
| `/users/edit/{public_id}` | GET | Superuser | Edit form. `username` is shown read-only. |
| `/users/edit/{public_id}` | POST | Superuser | Applies the edit (see editable fields below), sanitizes `description`, records a `UserHistory` "edited" entry, and returns the public id. |
| `/users/history/{public_id}` | GET | Superuser | History timeline with per-field diffs (the `description` diff renders as sanitized HTML). |
| `/users/api/search?q=` | GET | Superuser | Username search feeding the list page's jump-to-profile widget. Returns `{users: [{public_id, username, title}]}` — no pk leak. |

#### Editable fields

The edit form updates these fields; **`username` is never editable**:

`first_name`, `last_name`, `email`, `description` (rich text, sanitized via `nh3`), `has_public_profile`, `is_active`, `is_staff`, `is_superuser`.

A superuser cannot clear their own `is_superuser` or `is_active` flag (returns 400), preventing accidental self-lockout. A no-op submit (no field changed) is not recorded as history.

#### Permissions

| Operation | Superuser | Other authenticated | Anonymous |
|-----------|-----------|---------------------|-----------|
| **List** (`/users/list`) | All users | 404 | 404 |
| **Edit / History / Search** | Yes | 404 | 404 |
| **Profile** (`/users/id/{public_id}`) | Full attributes + history count | Name only; description/username gated by `has_public_profile` | Same as other authenticated |
| **Self-demotion** | Blocked (400) | n/a | n/a |


## Tools used
- Backend
  - UV
  - Inertia Django https://inertiajs.github.io/inertia-django/guide/client-side-setup and Inertia
  - Python rison for url https://github.com/betodealmeida/python-rison/tree/master
- Frontend
  - Inertia+Vue as Frontend framework https://inertiajs.com/docs/v2/getting-started/index
  - Vue3 + Vite
  - Zod for validation https://zod.dev/v4
  - Vue Multiselect for selects https://vue-multiselect.js.org/
  - SweetAlert for toasts and dialogs https://sweetalert2.github.io/
  - Quill for WYSIWYG

## Structure
- djangoproject - django project
- djangoapp - django app
  - views
  - tests - unit and E2E
- frontend - supposed to compile to main.js and main.css for djangoapp
- run - we use `./run <cmd>` to perform various activities
- AI agents should refer AGENTS.md

## Project Setup

### Prerequisites
- Python 3.14+
- PostgreSQL
- Node 25+
- uv >= 0.11 (for relative `exclude-newer` durations)

### Local Setup
1. Clone the repository
2. Install dependencies:
   ```bash
   ./run init
   ```
3. Run migrations:
   ```bash
   ./run runserver

### commands
```
./run checkall
./run lintfix
./run coverage
cd frontend && npm run dev
cd frontend && npm run lint
cd frontend && npm run lintfix
```
