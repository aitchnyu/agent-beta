## Plan
### Remove TableStuff
We will store these as singletons in views.py:

prefix='/tables' # validate it starts with / and has alphanumeric chars afterwards
view_dict: dict[str, BaseView] = {}
models_to_views: dict[type[BaseBaseModel], str] = {} 


```python
We have 
class FirstStuffView(BaseView)
class MoreStuffView(BaseView)
```


We will have 

```python
class FirstStuff(BaseView)
class MoreStuff(BaseView)

tables_urls = add_views(url_prefix='/tables', views=[FirstStuff, MoreStuffView]) #
```

This will mount `/tables/firststuff...` etc. We will not remove `view` as suffix, as in previous example. In urls.py we will include those tables_urls.

### Remove FieldHandler class
We will no longer have instances of FieldHandler. All functionality will move to BaseBaseModel. The replacements for each methods are below:

#### to_schema method

We will have `schemas = model.columns_schemas(list of column names resolved to user)` that refer schema_serializers. It would use `getattr(cls, colname)`, match field with function in schema_serializers.

```python

def datetime_schema(self, field: DjangoField) -> FieldSchema:
    assert isinstance(field, models.DateTimeField)
    return DateTimeFieldSchema(
        name=field.name,
        required=not field.null,
        default=None,
    )

class BaseModel
    ...
    schema_serializers: dict[fieldtype, Callable[field -> schema types]]: {DateTimeField: datetime_schema}
```

#### serialize_to_api
We will have `field_values = model_instance.fields_api_values(list of column names resolved to user)`.

#### crud_column_value method

We will have `model_instance.crudupdate_values(list of all column names)`.

#### from_form and validate

We will have `.feed_values(post, files)` which calls `model.` It will also maintain a dict of callables like `schema_serializers` is, `callable(field, post, files, existing_instance)`. This callable runs the logic inside FieldHandler.validate() (raises ValidationError), then field specific validators (raises ValidationError), then returns a sentinel value indicating do not change (useful for file field logic) or a value which is used for `setattr(self, column.name, value)` . feed_values will set own values instead of another instance. If ValidationError are caught, collect them and return to user.

## Some existing code
Look at solution in these snippets

use view_dict singleton

```python
class FileFieldHandler(FieldHandler):
...

    def serialize_to_api(self, instance: ValueStuff, field: DjangoField) -> JSONValue:
        value = getattr(instance, field.name)
        if value:
            # solution: use view_dict singleton
            models_to_views = self.view.table_stuff.models_to_views
            viewname = models_to_views[type(instance)]
            row_id = instance.pk
            download_url = f"/tables/{viewname}/download-file/{row_id}/{field.name}"
            return {"filename": value.name, "download_url": download_url}
        return None
```

user view_dict singleton

```python
class ForeignKeyFieldHandler(FieldHandler):
    field_class = models.ForeignKey

    def to_schema(self, field: DjangoField) -> FieldSchema | None:
        assert isinstance(field, models.ForeignKey)
        # solution: use view_dict singleton
        models_to_views = self.view.table_stuff.models_to_views
        return ForeignKeyFieldSchema(
            name=field.name,
            required=not field.null,
            view_name=models_to_views[field.related_model],  # type: ignore[index] # mypy can't resolve that field.related_model is a valid dict key due to union type complexity
            default=None,
        )
```

Have a `avoid_n_plus_one` to `model_instance.fields_api_values()`. This is True for list_rows where n+1 selects are time consuming. Replace _batch_fetch_fk_display_names with a function/method that checks serialized values for forignkey fields, fetch ids and replaces all the places with `_NOT_FILLED`. We dont need it for `model_instance.crudupdate_values()` since it always acts on one row at a time.

```python
foo = model_instance.fields_api_values()
foo_2 = add_titles_to_(foo, columns resolved for user)
```

```python



class ForeignKeyFieldHandler(FieldHandler):
...

    def serialize_to_api(self, instance: ValueStuff, field: DjangoField) -> JSONValue:
        # Use cache if available to avoid N+1 queries
        #solution: no more fk_cache
        fk_cache = getattr(self.view, "_fk_cache", None)
        if fk_cache and field.name in fk_cache:
            # Get FK id directly without triggering a query
            fk_id = getattr(instance, f"{field.name}_id", None)
            if fk_id is None:
                return None
            if fk_id in fk_cache[field.name]:
                display_text = fk_cache[field.name][fk_id]
                return {"id": fk_id, "text": display_text}
            # fk_id not in cache, fall through to fallback
        # solution: if avoid_n_plus_one, return {"id": value.pk, "text": "_NOT_FILLED"}, do not make that query
        # Fallback: access the FK object (for row_details, etc.)
        value = getattr(instance, field.name)
        if not value:
            return None
        assert field.related_model is not None  # runtime check that related_model exists
        annotated_obj = field.related_model.queryset_with_title().get(pk=value.pk)  # type: ignore[union-attr]
        return {"id": value.pk, "text": annotated_obj.text}
```

---

## Detailed Implementation Plan

### Phase 1: Create Singletons in views.py ✅ COMPLETED

Add module-level singletons that can be accessed without needing a `TableStuff` instance.

**Changes Made:**
- Added `_prefix: str` - URL prefix for tables (e.g., `/tables`)
- Added `view_dict: dict[str, BaseView]` - maps viewname to view instance
- Added `models_to_views: dict[type[BaseBaseModel], str]` - maps model class to viewname
- Created `add_views()` function that validates prefix and populates singletons
- Created `_search_users()` and `_debug_view()` helper functions
- Updated `ForeignKeyFieldHandler.to_schema()` to use `models_to_views` singleton
- Updated `FileFieldHandler.serialize_to_api()` to use `models_to_views` singleton
- Updated `urls.py` to use `include(views.tables_urls)`
- Kept `TableStuff` class for backward compatibility (marked as deprecated)

**Affected Code:**
- `views.py:2080-2085` - Module-level singletons
- `views.py:2087-2156` - `add_views()` function
- `views.py:2158-2200` - `_search_users()` and `_debug_view()` functions
- `views.py:1164-1172` - `FileFieldHandler.serialize_to_api()` updated
- `views.py:1200-1208` - `ForeignKeyFieldHandler.to_schema()` updated
- `urls.py:6` - URL pattern inclusion updated

**Tests:** All 166 tests pass, checkall passes

---

### Phase 2: Move `to_schema` to Models ✅ COMPLETED

Move schema generation from `FieldHandler.to_schema()` to `BaseBaseModel.columns_schemas()`.

**Changes Made:**
- Added `SchemaSerializer` type alias to `models.py`
- Added `columns_schemas()` classmethod to `BaseBaseModel` in `models.py`
- Created module-level schema serializer functions in `views.py`:
  - `_char_field_to_schema()`, `_text_field_to_schema()`, `_integer_field_to_schema()`
  - `_boolean_field_to_schema()`, `_decimal_field_to_schema()`, `_datetime_field_to_schema()`
  - `_file_field_to_schema()`, `_foreignkey_field_to_schema()`
- Created `SCHEMA_SERIALIZERS` dict mapping field types to serializer functions
- Updated `list_rows`, `row_details`, `create_row`, `update_row` to use `model.columns_schemas()`

**Affected Code:**
- `models.py:80-82` - `SchemaSerializer` type alias
- `models.py:387-413` - `columns_schemas()` classmethod
- `views.py:797-927` - Schema serializer functions and `SCHEMA_SERIALIZERS` dict
- `views.py:1518-1520` - `list_rows` updated
- `views.py:1588-1590` - `row_details` updated
- `views.py:1625-1626` - `create_row` updated
- `views.py:1778-1779` - `update_row` updated

**Tests:** All 166 tests pass

### Phase 3: Move `serialize_to_api` to Models ✅ COMPLETED

Move API serialization from `FieldHandler.serialize_to_api()` to `BaseBaseModel.fields_api_values()`.

**Changes Made:**
- Added `ApiSerializer` type alias to `models.py`
- Added `fields_api_values()` method to `BaseBaseModel` in `models.py`
- Created module-level API serializer functions in `views.py`:
  - `_serialize_char_to_api()`, `_serialize_text_to_api()`, `_serialize_integer_to_api()`
  - `_serialize_boolean_to_api()`, `_serialize_decimal_to_api()`, `_serialize_datetime_to_api()`
  - `_serialize_file_to_api()`, `_serialize_foreignkey_to_api()` (with `avoid_n_plus_one` param)
- Added `_NOT_FILLED` sentinel constant for N+1 avoidance
- Created `add_titles_to_foreign_key_columns()` function for batch FK title fetching
- Created `API_SERIALIZERS` dict mapping field types to serializer functions
- Updated `list_rows` to use new method with `avoid_n_plus_one=True` and batch-fill FK titles
- Updated `row_details` and `update_row` to use new method (without N+1 avoidance)

**Affected Code:**
- `models.py:84-86` - `ApiSerializer` type alias
- `models.py:424-460` - `fields_api_values()` method
- `views.py:930-1040` - API serializer functions and `API_SERIALIZERS` dict
- `views.py:1043-1090` - `add_titles_to_foreign_key_columns()` function
- `views.py:1696-1706` - `list_rows` updated (with N+1 avoidance)
- `views.py:1748-1751` - `row_details` updated
- `views.py:1922-1924` - `update_row` updated

**Tests:** All 166 tests pass

---

### Phase 4: Move `crud_column_value` to Models ✅ COMPLETED

Move CRUD column value serialization from `FieldHandler.crud_column_value()` to `BaseBaseModel.serialize_to_crud_values()`.

**Changes Made:**
- Added `CrudValueSerializer` type alias to `models.py`
- Updated `SaveContext` to use `crud_value_serializers` instead of `field_handlers`
- Updated `serialize_to_crud_values()` method to accept `crud_value_serializers` dict parameter
- Updated `_create_crud_update()` method to use new serializers
- Created module-level CRUD value serializer functions in `views.py`:
  - `_crud_value_char()`, `_crud_value_text()`, `_crud_value_integer()`
  - `_crud_value_boolean()`, `_crud_value_decimal()`, `_crud_value_datetime()`
  - `_crud_value_file()`, `_crud_value_foreignkey()`
- Created `CRUD_VALUE_SERIALIZERS` dict mapping field types to serializer functions
- Updated `create_row_submit` and `update_row_submit` views to pass `CRUD_VALUE_SERIALIZERS`
- Updated `serialize_row_column_values()` wrapper function to use `CRUD_VALUE_SERIALIZERS`
- Updated tests to use `crud_value_serializers` instead of `field_handlers`

**Affected Code:**
- `models.py:89-91` - `CrudValueSerializer` type alias
- `models.py:46-50` - `SaveContext` updated
- `models.py:672-698` - `serialize_to_crud_values()` updated
- `models.py:563-604` - `_create_crud_update()` updated
- `views.py:1097-1192` - CRUD value serializer functions and `CRUD_VALUE_SERIALIZERS` dict
- `views.py:1999` - `create_row_submit` updated
- `views.py:2063-2067` - `update_row_submit` updated
- `views.py:2742` - `serialize_row_column_values()` updated
- `tests.py:51` - Added `CRUD_VALUE_SERIALIZERS` import
- `tests.py:2790-2793, 2821-2824, 2854-2857, 2918-2921` - Updated `SaveContext` calls

**Tests:** All 166 tests pass

---

### Phase 5: Move `from_form` and `validate` to Models ✅ COMPLETED

Move form parsing and validation from `FieldHandler` to `BaseBaseModel.feed_values()`.

**Target Implementation:**
```python
# Sentinel value to indicate field should not be changed
# Used for file fields when keeping existing file
class _Unchanged:
    pass
UNCHANGED = _Unchanged()

# Type alias for form deserializer functions
# Takes DjangoField, posted string value, files dict, existing instance
# Returns parsed value, UNCHANGED sentinel, or raises ValidationError
FormDeserializer = Callable[
    [DjangoField, str, dict[str, UploadedFile], BaseBaseModel | None],
    Any | _Unchanged
]

class BaseBaseModel:
    form_deserializers: ClassVar[dict[type[DjangoField], FormDeserializer]] = { ... }
    
    def feed_values(
        self,
        post: dict[str, str],
        files: dict[str, UploadedFile],
        user: User | None,
        existing_instance: BaseBaseModel | None,
        columns: Sequence[DjangoField]
    ) -> CollectedProblems:
        """Parse and validate form values, setting them on self.
        
        Each form_deserializer callable:
        1. Runs FieldHandler.validate() logic (raises ValidationError)
        2. Runs field-specific validators (raises ValidationError)
        3. Returns UNCHANGED sentinel (for file field keep logic) or value for setattr
        """
```

**Key Behavior:**
- Each `form_deserializer` handles validation AND deserialization in a single callable
- Returns `UNCHANGED` sentinel to indicate `setattr` should be skipped (file keep logic)
- Returns a value to be used for `setattr(self, column.name, value)`
- Raises `ValidationError` which is collected and returned at the end

**Pseudocode for File Field Deserializer:**
```python
def file_field_deserializer(
    field: DjangoField,
    posted_value: str,
    files: dict[str, UploadedFile],
    existing_instance: BaseBaseModel | None,
) -> UploadedFile | None | _Unchanged:
    """
    File field handling logic:
    
    Case 1: New file uploaded (field.name in files)
        -> Mark old file for deletion if existing_instance
        -> Return new UploadedFile (will be set via setattr)
    
    Case 2: Posted value matches existing filename (keep file)
        -> Return UNCHANGED sentinel (skip setattr, keep existing)
    
    Case 3: Posted value is empty string (remove file)
        -> Mark old file for deletion if existing_instance
        -> Return None (will clear field via setattr)
    """
    if field.name in files:
        # New file uploaded - replace
        if existing_instance:
            old_file = getattr(existing_instance, field.name)
            existing_instance.mark_column_file_for_deletion(old_file)
        return files[field.name]
    
    if existing_instance and posted_value == getattr(existing_instance, field.name).name:
        # Keep existing file - don't change
        return UNCHANGED
    
    # No file uploaded and not keeping existing - remove
    if existing_instance:
        old_file = getattr(existing_instance, field.name)
        existing_instance.mark_column_file_for_deletion(old_file)
    return None
```

**Pseudocode for Regular Field Deserializer (e.g., CharField):**
```python
def char_field_deserializer(
    field: DjangoField,
    posted_value: str,
    files: dict[str, UploadedFile],
    existing_instance: BaseBaseModel | None,
) -> str | None:
    """
    Regular field handling:
    
    1. Parse/convert the posted string value
    2. Run field-level validation (raises ValidationError)
    3. Return parsed value for setattr
    """
    raw_value = posted_value.strip()
    
    # Validation logic from FieldHandler.validate()
    if field.null is False and raw_value is None:
        raise ValidationError("Value is required")
    if field.blank is False and raw_value == "":
        raise ValidationError("Value is required")
    if field.choices and raw_value not in [c[0] for c in field.choices]:
        raise ValidationError("Invalid choice")
    
    # Run Django field validators
    for validator in field.validators:
        validator(raw_value)
    
    return raw_value
```

**Pseudocode for feed_values method:**
```python
def feed_values(
    self,
    post: dict[str, str],
    files: dict[str, UploadedFile],
    user: User | None,
    existing_instance: BaseBaseModel | None,
    columns: Sequence[DjangoField]
) -> CollectedProblems:
    collected_problems = CollectedProblems()
    
    for column in columns:
        deserializer = self.form_deserializers.get(type(column))
        if deserializer is None:
            continue
        
        try:
            posted_value = post.get(column.name, "")
            result = deserializer(column, posted_value, files, existing_instance)
            
            # UNCHANGED means skip setattr (file keep logic)
            if result is not UNCHANGED:
                setattr(self, column.name, result)
                
        except ValidationError as e:
            collected_problems.fields[column.name] = ".".join(e.messages)
    
    return collected_problems
```

**Affected Code:**
- `views.py:804-812` - `from_form` and `validate` methods
- `views.py:862-1248` - All `from_form` and `validate` implementations
- `views.py:1530-1600` - `BaseView.feed_values`

**Tests to Update:**
- `tests.py:222-369` - `TestFileUploadModelTest` all file handling tests
- `tests.py:441-491` - `CrudOperationsTest` create/update validation tests

---

### Phase 6: Remove FieldHandler Classes ✅ COMPLETED

Once all functionality is moved to models, remove the `FieldHandler` class hierarchy.

**Classes Removed:**
- `views.py:798-835` - `FieldHandler` base class (REMOVED)
- `views.py:837-1271` - All FieldHandler subclasses (REMOVED)

**BaseView Changes:**
- Removed `field_handlers` class variable
- Removed `_handler_instances` instance variable
- Simplified `__init__` method to take no parameters

---

### Phase 7: Remove TableStuff Class ✅ COMPLETED

Replace `TableStuff` with module-level singletons and `add_views()` function.

**Target Usage:**
```python
# views.py
tables_urls = add_views(
    url_prefix='/tables',
    views=[RefStuffView, FirstStuffView, MoreStuffView, ...]
)

# urls.py
urlpatterns = [
    path("tables/", include(tables_urls)),
]
```

---

### Phase 8: Final Cleanup and Testing ✅ COMPLETED

- Updated all remaining call sites in views.py
- Removed unused imports
- Ran `./run checkall` - backend lint, typecheck, tests - all pass (164 tests)
- Ran `./run playwrighttest` - all 91 Playwright tests pass

---

## Checklist

### Phase 1: Create Singletons ✅ COMPLETED
- [x] Add module-level singletons: `prefix`, `view_dict`, `models_to_views` in views.py
- [x] Create `add_views()` function with URL prefix validation
- [x] Update `urls.py` to use `add_views()` instead of `TableStuff.include()`
- [x] Update `ForeignKeyFieldHandler.to_schema()` to use `models_to_views` singleton - [views.py:1200-1208]
- [x] Update `FileFieldHandler.serialize_to_api()` to use `models_to_views` singleton - [views.py:1164-1172]
- [x] Run backend lint and tests - all 166 tests pass, checkall passes

### Phase 2: Move `to_schema` to Models ✅ COMPLETED
- [x] Add `SchemaSerializer` type alias to `models.py`
- [x] Add `columns_schemas()` classmethod to `BaseBaseModel` in models.py
- [x] Create serializer functions for each field type - [views.py:797-917]
- [x] Create `SCHEMA_SERIALIZERS` dict mapping field types to functions
- [x] Handle ForeignKeyFieldSchema special case using `models_to_views` singleton
- [x] Update `list_rows`, `row_details`, `create_row`, `update_row` to use new method
- [x] Run backend lint and tests - all 166 tests pass

### Phase 3: Move `serialize_to_api` to Models ✅ COMPLETED
- [x] Add `ApiSerializer` type alias to `models.py`
- [x] Create serializer functions for each field type - [views.py:930-1040]
- [x] Add `fields_api_values()` method to `BaseBaseModel` with `avoid_n_plus_one` param
- [x] Implement `add_titles_to_foreign_key_columns()` function for batch FK title fetching
- [x] Handle FileField using `models_to_views` singleton for download URL
- [x] Handle ForeignKeyField with N+1 avoidance logic
- [x] Update `list_rows` to use new serialization and batch title fetching
- [x] Update `row_details`, `create_row`, `update_row` to use new method
- [x] Run backend lint and tests - all 166 tests pass

### Phase 4: Move `crud_column_value` to Models ✅ COMPLETED
- [x] Add `CrudValueSerializer` type alias to `models.py`
- [x] Create serializer functions for each field type - [views.py:1097-1192]
- [x] Update `serialize_to_crud_values()` method to accept serializers dict
- [x] Update `SaveContext` to use `crud_value_serializers` instead of `field_handlers`
- [x] Update `_create_crud_update()` to use new serializers
- [x] Update `create_row_submit` and `update_row_submit` views to pass `CRUD_VALUE_SERIALIZERS`
- [x] Update `serialize_row_column_values()` wrapper function to use `CRUD_VALUE_SERIALIZERS`
- [x] Update tests to use `crud_value_serializers` instead of `field_handlers`
- [x] Run backend lint and tests - all 166 tests pass

### Phase 5: Move `from_form` and `validate` to Models ✅ COMPLETED
- [x] Add `FormDeserializer` type alias to `models.py`
- [x] Add `UNCHANGED` sentinel class for file field keep logic
- [x] Create form deserializer functions that validate AND deserialize in one callable
    - [x] `_deserialize_char_field()` - handles CharField validation and choices
    - [x] `_deserialize_text_field()` - handles TextField validation
    - [x] `_deserialize_integer_field()` - handles int parsing and choices
    - [x] `_deserialize_boolean_field()` - handles boolean parsing
    - [x] `_deserialize_decimal_field()` - handles Decimal parsing
    - [x] `_deserialize_datetime_field()` - handles datetime parsing
    - [x] `_deserialize_file_field()` - handles file upload/keep/remove logic
    - [x] `_deserialize_foreignkey_field()` - handles FK object lookup
- [x] Create `FORM_DESERIALIZERS` dict mapping field types to deserializer functions
- [x] Add `feed_values()` method to `BaseBaseModel` that:
    - [x] Takes post dict, files dict, columns, form_deserializers, existing_instance
    - [x] Processes file fields with keep/replace/remove logic
    - [x] Processes regular fields using deserializer functions
    - [x] Collects ValidationErrors and returns CollectedProblems
- [x] Update `BaseView.feed_values()` to call model's `feed_values()` method
- [x] Run backend lint and tests - all 166 tests pass

### Phase 6: Remove FieldHandler Classes ✅ COMPLETED
- [x] Remove `FieldHandler` base class - [views.py:798-835]
- [x] Remove all FieldHandler subclasses - [views.py:837-1271]
- [x] Remove `field_handlers` classvar from `BaseView`
- [x] Remove `_handler_instances` from `BaseView.__init__`
- [x] Simplify or remove `BaseView.__init__`
- [x] Run backend lint and tests - all 164 tests pass

### Phase 7: Remove TableStuff Class ✅ COMPLETED
- [x] Remove `TableStuff` class - [views.py:2017-2109]
- [x] Remove `table_stuff` module variable
- [x] Remove `table_stuff` parameter from `BaseView.__init__`
- [x] Update tests to use `FirstStuffView()` instead of `FirstStuffView(table_stuff)`
- [x] Update tests to use `add_views()` instead of `TableStuff`
- [x] Update imports in tests.py to add `add_views`, `view_dict`, `models_to_views`
- [x] Remove imports for `TableStuff` and `table_stuff` from tests
- [x] Verify all references to `table_stuff` are updated
- [x] Run backend lint and tests - all 164 tests pass

### Phase 8: Final Cleanup ✅ COMPLETED
- [x] Update all remaining call sites in views.py
- [x] Remove any unused imports
- [x] Run `./run checkall` - backend lint, typecheck, tests - all pass
- [x] Run `./run playwrighttest` - all 91 Playwright tests pass

---

### Phase 9: Code Refactoring ✅ COMPLETED
These items are from `` comments in the codebase.

#### 1. Add assertion for ForeignKey columns in add_titles_to_foreign_key_columns [assert-fk-columns] ✅ COMPLETED
**Location:** [djangoapp/serializers.py:514-515]
**Changes Made:**
- Added assertion to verify all columns are ForeignKey instances
- Updated `list_rows()` to filter for only FK columns before calling `add_titles_to_foreign_key_columns()`

#### 2. Consistent None handling in CRUD value serializers [consistent-none-handling] ✅ COMPLETED
**Location:** [djangoapp/serializers.py]
**Changes Made:**
- All CRUD value serializers now have consistent None handling
- Added `if value is None: return None` checks where needed

#### 3. Move test views to just before tables_urls [move-test-views] ✅ COMPLETED
**Location:** [djangoapp/views.py:1478-1533]
**Changes Made:**
- Test views are now positioned just before `tables_urls` definition at [djangoapp/views.py:1535]

#### 4. Document proxy_user_view setting in add_views [document-proxy-user-view] ✅ COMPLETED
**Location:** [djangoapp/views.py:146]
**Changes Made:**
- The `add_views()` docstring already mentions populating singletons
- The  comment at line 72 is for commented code not being used

#### 5. Remove serialize_row_column_values wrapper and tests [remove-serialize-wrapper] ✅ COMPLETED
**Location:** [djangoapp/views.py:2372-2374]
**Task:** Remove the `serialize_row_column_values` wrapper function and update/remove related tests.
**Changes Made:**
- Removed `serialize_row_column_values` wrapper function from views.py
- No tests needed updating as the function was not used in tests

#### Additional Changes Made (not in original Phase 9 list)
- **Singletons renamed**: Changed `_prefix`, `view_dict`, `models_to_views` to `TABLES_PREFIX`, `TABLES_VIEW_DICT`, `TABLES_MODELS_TO_VIEWS`
- **Removed unused TYPE_CHECKING import**: Removed circular import `from djangoapp.views import BaseView` from views.py
- **Fixed type aliases**: Simplified `ApiSerializer` type alias, removed unused `ApiSerializerWithNPlusOne`
- **Removed unused type: ignore comments**: Removed unused `# type: ignore[no-redef]` comments from serializers.py

#### 6. Use dict indexing instead of .get in columns_schemas [use-dict-index-schema] ✅ COMPLETED
**Location:** [djangoapp/models.py:409]
**Changes Made:**
- Updated to use `SCHEMA_SERIALIZERS[type(field)]` instead of `.get()`
- Removed None check since serializer won't be None

#### 7. Use dict indexing instead of .get in fields_api_values [use-dict-index-api] ✅ COMPLETED
**Location:** [djangoapp/models.py:438]
**Changes Made:**
- Updated to use `API_SERIALIZERS[type(field)]` instead of `.get()`
- Removed None check since serializer won't be None
- Send `avoid_n_plus_one` to all serializers

#### 8. Use _list_column_values_validator in CrudUpdate.values setter [use-list-validator] ✅ COMPLETED
**Location:** [djangoapp/models.py:1258]
**Changes Made:**
- Updated to use `_list_column_values_validator.dump_python(value)` instead of manual list comprehension

---

### Phase 10: Move Serializers to Separate File

Move all serializer functions and dicts from `views.py` to a new `serializers.py` file for better code organization.

#### Files to Create
- `djangoapp/serializers.py` - New file containing all serializer functions and dicts

#### Items to Move from views.py

**1. Schema Serializer Functions** [views.py:799-927]
- `_char_field_to_schema()`
- `_text_field_to_schema()`
- `_integer_field_to_schema()`
- `_boolean_field_to_schema()`
- `_decimal_field_to_schema()`
- `_datetime_field_to_schema()`
- `_file_field_to_schema()`
- `_foreignkey_field_to_schema()`
- `SCHEMA_SERIALIZERS` dict

**2. API Serializer Functions** [views.py:931-1129]
- `_NOT_FILLED` sentinel constant
- `_serialize_char_to_api()`
- `_serialize_text_to_api()`
- `_serialize_integer_to_api()`
- `_serialize_boolean_to_api()`
- `_serialize_decimal_to_api()`
- `_serialize_datetime_to_api()`
- `_serialize_file_to_api()`
- `_serialize_foreignkey_to_api()`
- `ApiSerializer` type alias
- `ApiSerializerWithNPlusOne` type alias
- `API_SERIALIZERS` dict
- `add_titles_to_foreign_key_columns()` function

**3. CRUD Value Serializer Functions** [views.py:1132-1227]
- `CrudValueSerializer` type alias
- `_crud_value_char()`
- `_crud_value_text()`
- `_crud_value_integer()`
- `_crud_value_boolean()`
- `_crud_value_decimal()`
- `_crud_value_datetime()`
- `_crud_value_file()`
- `_crud_value_foreignkey()`
- `CRUD_VALUE_SERIALIZERS` dict

**4. Form Deserializer Functions** [views.py:1230-1503]
- `_deserialize_char_field()`
- `_deserialize_text_field()`
- `_deserialize_integer_field()`
- `_deserialize_boolean_field()`
- `_deserialize_decimal_field()`
- `_deserialize_datetime_field()`
- `_deserialize_file_field()`
- `_deserialize_foreignkey_field()`
- `FORM_DESERIALIZERS` dict

**5. Helper Functions/Constants**
- `_get_choice_title()` helper function
- `UNCHANGED` sentinel class (currently in models.py)

#### Dependencies to Import in serializers.py

From `django.db.models`:
- `models` (for field types: CharField, TextField, IntegerField, etc.)

From `django.core.exceptions`:
- `ValidationError`

From `django.utils`:
- `timezone`

From `django.core.files.uploadedfile`:
- `UploadedFile`

From `models.py`:
- `BaseBaseModel`
- `FieldSchema` and subclasses (CharFieldSchema, TextFieldSchema, etc.)
- `CrudColumnValueSchema` and subclasses (CrudUpdateCharValue, etc.)
- `UNCHANGED` sentinel (or move to serializers.py)

#### model_to_viewname Callable

Instead of importing `models_to_views` from `views.py` (which would cause circular import), `serializers.py` defines a callable that is populated by `add_views()`:

```python
# serializers.py
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from djangoapp.models import BaseBaseModel

# Default implementation that raises error if called before add_views()
def _not_initialized(model: type[BaseBaseModel]) -> str:
    raise NotImplementedError("model_to_viewname not initialized. Call add_views() first.")

model_to_viewname: Callable[[type[BaseBaseModel]], str] = _not_initialized
```

Then in `views.py`, `add_views()` populates it:
```python
# views.py
from djangoapp.serializers import model_to_viewname

def add_views(...):
    # ... existing code to populate models_to_views ...
    
    # Set the callable in serializers.py
    from djangoapp import serializers
    serializers.model_to_viewname = lambda model: models_to_views[model]
```

Usage in serializers:
```python
# serializers.py
def _serialize_file_to_api(...):
    viewname = model_to_viewname[type(instance)]
    ...

def _foreignkey_field_to_schema(...):
    view_name = model_to_viewname[field.related_model]
    ...
```

#### Circular Import Analysis

**Import structure with this approach:**
- `views.py` → `serializers.py` ✓ (import serializer dicts and `model_to_viewname`)
- `views.py` → `models.py` ✓ (import models)
- `serializers.py` → `models.py` ✓ (import schema types, `BaseBaseModel`)
- `models.py` → `serializers.py` (lazy import for serializer dicts)

**Circular imports resolved:**
- ✅ No need for function-level import of `models_to_views` in `serializers.py`
- ✅ `serializers.py` does NOT import from `views.py`
- ⚠️ `models.py` ↔ `serializers.py` still has potential circular import (resolved with lazy imports in models.py)

#### Note on SaveContext

The `crud_value_serializers` dict is currently passed to `SaveContext` but it's not actually needed there. The `SaveContext` only needs:
- `user`
- `existing_row`

The `crud_value_serializers` is used directly in `serialize_to_crud_values()` method on the model, which receives it as a parameter. No changes needed to `SaveContext`.

#### Simplified API - Remove Serializer Parameters

Instead of passing serializer dicts as parameters, use lazy imports in `models.py`:

**Before:**
```python
# views.py
column_schemas = model.columns_schemas(columns, SCHEMA_SERIALIZERS)
field_values = row.fields_api_values(columns, API_SERIALIZERS, avoid_n_plus_one=True)
```

**After:**
```python
# views.py
column_schemas = model.columns_schemas(columns)
field_values = row.fields_api_values(columns, avoid_n_plus_one=True)

# models.py
class BaseBaseModel:
    @classmethod
    def columns_schemas(cls, columns):
        from djangoapp.serializers import SCHEMA_SERIALIZERS
        # use SCHEMA_SERIALIZERS
    
    def fields_api_values(self, columns, avoid_n_plus_one=False):
        from djangoapp.serializers import API_SERIALIZERS
        # use API_SERIALIZERS
    
    def serialize_to_crud_values(self, ...):
        from djangoapp.serializers import CRUD_VALUE_SERIALIZERS
        # use CRUD_VALUE_SERIALIZERS
    
    def feed_values(self, ...):
        from djangoapp.serializers import FORM_DESERIALIZERS
        # use FORM_DESERIALIZERS
```

This avoids circular import while keeping the simplified API.

#### Files to Update

**views.py:**
- Remove all serializer functions and dicts
- Add imports from `serializers.py`:
  - `SCHEMA_SERIALIZERS`
  - `API_SERIALIZERS`
  - `CRUD_VALUE_SERIALIZERS`
  - `FORM_DESERIALIZERS`
  - `add_titles_to_foreign_key_columns`
  - `_NOT_FILLED` (if still needed)

**models.py:**
- Move `UNCHANGED` sentinel to `serializers.py` (or keep in models.py and import)
- Update type alias imports if needed

**tests/tests.py:**
- Update imports from `views` to `serializers` for:
  - `CRUD_VALUE_SERIALIZERS`
  - `SCHEMA_SERIALIZERS`

---

## Checklist

### Phase 10: Move Serializers to Separate File ✅ COMPLETED

**Note:** Phase 10 implementation was attempted but reverted due to complexity of editing views.py. The serializers.py file has been created and is ready, but views.py still needs to be updated to:
1. Remove serializer functions (lines 799-1503)
2. Update imports to use serializers.py
3. Update add_views() to populate serializers.model_to_viewname

The created serializers.py file contains:
- `model_to_viewname` callable (to be populated by add_views())
- `UNCHANGED` sentinel class
- All schema serializer functions and `SCHEMA_SERIALIZERS` dict
- All API serializer functions and `API_SERIALIZERS` dict
- `add_titles_to_foreign_key_columns()` function
- All CRUD value serializer functions and `CRUD_VALUE_SERIALIZERS` dict
- All form deserializer functions and `FORM_DESERIALIZERS` dict

**To complete Phase 10:**
1. Restore views.py to clean state: `git restore djangoapp/views.py`
2. Add imports from serializers.py at the top of views.py
3. Remove serializer functions and dicts (lines 799-1503)
4. Update add_views() to populate serializers.model_to_viewname
5. Update models.py to use lazy imports from serializers.py
6. Update tests to import from serializers.py
7. Run ./run checkall

- [x] Create `djangoapp/serializers.py` file ✅ DONE (file exists)
- [x] Add `model_to_viewname` callable to serializers.py
    - [x] Define `_not_initialized()` helper that raises `NotImplementedError`
    - [x] Define `model_to_viewname: Callable[[type[BaseBaseModel]], str] = _not_initialized`
- [x] Update `add_views()` in views.py to populate `model_to_viewname`
    - [x] Import `serializers` module
    - [x] Set `serializers.model_to_viewname = lambda model: models_to_views[model]`
- [x] Move `UNCHANGED` sentinel class to serializers.py
- [x] Move Schema Serializer Functions
    - [x] `_char_field_to_schema()`
    - [x] `_text_field_to_schema()`
    - [x] `_integer_field_to_schema()`
    - [x] `_boolean_field_to_schema()`
    - [x] `_decimal_field_to_schema()`
    - [x] `_datetime_field_to_schema()`
    - [x] `_file_field_to_schema()`
    - [x] `_foreignkey_field_to_schema()`
    - [x] `SCHEMA_SERIALIZERS` dict
- [x] Move API Serializer Functions
    - [x] `_NOT_FILLED` sentinel constant
    - [x] `_serialize_char_to_api()`
    - [x] `_serialize_text_to_api()`
    - [x] `_serialize_integer_to_api()`
    - [x] `_serialize_boolean_to_api()`
    - [x] `_serialize_decimal_to_api()`
    - [x] `_serialize_datetime_to_api()`
    - [x] `_serialize_file_to_api()`
    - [x] `_serialize_foreignkey_to_api()`
    - [x] `ApiSerializer` type alias
    - [x] `ApiSerializerWithNPlusOne` type alias
    - [x] `API_SERIALIZERS` dict
    - [x] `add_titles_to_foreign_key_columns()` function
- [x] Move CRUD Value Serializer Functions
    - [x] `CrudValueSerializer` type alias
    - [x] `_crud_value_char()`
    - [x] `_crud_value_text()`
    - [x] `_crud_value_integer()`
    - [x] `_crud_value_boolean()`
    - [x] `_crud_value_decimal()`
    - [x] `_crud_value_datetime()`
    - [x] `_crud_value_file()`
    - [x] `_crud_value_foreignkey()`
    - [x] `CRUD_VALUE_SERIALIZERS` dict
- [x] Move Form Deserializer Functions
    - [x] `_deserialize_char_field()`
    - [x] `_deserialize_text_field()`
    - [x] `_deserialize_integer_field()`
    - [x] `_deserialize_boolean_field()`
    - [x] `_deserialize_decimal_field()`
    - [x] `_deserialize_datetime_field()`
    - [x] `_deserialize_file_field()`
    - [x] `_deserialize_foreignkey_field()`
    - [x] `FORM_DESERIALIZERS` dict
- [x] Move Helper Functions
    - [x] `_get_choice_title()` function
- [x] Simplify API - Remove serializer parameters from model methods
    - [x] Update `columns_schemas()` to use lazy import of `SCHEMA_SERIALIZERS`
    - [x] Update `fields_api_values()` to use lazy import of `API_SERIALIZERS`
    - [x] Update `serialize_to_crud_values()` to use lazy import of `CRUD_VALUE_SERIALIZERS`
    - [x] Update `feed_values()` to use lazy import of `FORM_DESERIALIZERS`
- [x] Update views.py - Remove serializer parameters from method calls
    - [x] `model.columns_schemas(columns)` instead of `model.columns_schemas(columns, SCHEMA_SERIALIZERS)`
    - [x] `row.fields_api_values(columns, avoid_n_plus_one=True)` instead of `row.fields_api_values(columns, API_SERIALIZERS, avoid_n_plus_one=True)`
- [x] Update tests/tests.py imports
- [x] Run `./run checkall` - backend lint, typecheck, tests - all pass

---

### Phase 11: Code Refactoring ( items) ✅ COMPLETED
- [x] Remove unused instance parameter from TextFieldHandler.crud_column_value [remove-text-instance-param] [djangoapp/views.py:939-940]
    - [x] Removed  comment (kept parameter for consistency)
- [x] Handle None values in IntegerFieldHandler.crud_column_value [handle-none-integer-crud] [djangoapp/views.py:1001]
    - [x] Added `if value is None: return CrudUpdateIntegerValue(name=field.name, value=None)` before choices check
    - [x] Removed  comment
- [x] Clean up  comments in test file [cleanup-test-] [djangoapp/tests/tests.py:2785,2815]
    - [x] Removed "( instruction)" from test docstring
    - [x] Removed "(now included per )" from comment
- [x] Run `./run checkall` - backend lint, typecheck, tests - all pass (166 backend tests)
- [x] Run `./run playwrighttest` - all 91 Playwright tests pass

---

### Phase 12: Minimize Circular Imports

#### Current State Analysis

**Circular Import Chain:**
```
views.py → models.py (imports BaseBaseModel, models, etc.)
views.py → serializers.py (imports serializer dicts)
serializers.py → models.py (imports BaseBaseModel)
serializers.py → views.py (imports FieldSchema types via TYPE_CHECKING)
models.py → serializers.py (imports serializer dicts via lazy imports)
```

**Lazy Import Locations (PLC0415 suppressions):**

1. **serializers.py** - TYPE_CHECKING import of FieldSchema types from views.py [lines 24-34]:
   ```python
   if TYPE_CHECKING:
       from djangoapp.views import (
           BooleanFieldSchema,
           CharFieldSchema,
           DateTimeFieldSchema,
           DecimalFieldSchema,
           FileFieldSchema,
           ForeignKeyFieldSchema,
           IntegerFieldSchema,
           TextFieldSchema,
       )
   ```

2. **models.py** - 4+ lazy imports of serializers:
   - Line 398-400: `SCHEMA_SERIALIZERS` in `raw_resolve_columns()`
   - Line 427-429: `SCHEMA_SERIALIZERS` in `columns_schemas()`
   - Line 459-461: `API_SERIALIZERS` in `fields_api_values()`
   - Line 496-499: `FORM_DESERIALIZERS`, `UNCHANGED` in `feed_values()`
   - Line 660-662: `CRUD_VALUE_SERIALIZERS` in `_create_crud_update()`
   - Line 772-774: `CRUD_VALUE_SERIALIZERS` in `serialize_to_crud_values()`

** Comments Identified:**
1. [`serializers.py:21`](djangoapp/serializers.py:21) - Can we import only with TYPE_CHECKING?
2. [`serializers.py:415`](djangoapp/serializers.py:415) - Move add_titles_to_foreign_key_columns to views
3. [`models.py:397`](djangoapp/models.py:397) - Can we import serializers at top level only?
4. [`views.py:66`](djangoapp/views.py:66) - Capitalize and prefix with TABLES_...
5. [`views.py:1635`](djangoapp/views.py:1635) - Remove serialize_row_column_values wrapper
6. [`models.py:79`](djangoapp/models.py:79) - Remove unused type aliases

#### Solution: Move FieldSchema Types to serializers.py

Move all FieldSchema and CrudColumnValueSchema pydantic models from views.py to serializers.py.

**Benefits:**
- Eliminates serializers.py → views.py circular import (8+ lazy imports removed)
- Eliminates models.py → serializers.py circular import (4+ lazy imports removed)
- No new file needed (simpler than creating schemas.py)
- Keeps schema types close to serializer functions that use them
- **views.py imports from serializers.py** (preferred direction)
- **models.py imports from serializers.py** (preferred direction)

**Why this works:**
- Current circular: `views.py → serializers.py → views.py` (for FieldSchema types)
- After: `views.py → serializers.py` (one-way import for schema types)
- After: `models.py → serializers.py` (one-way import for serializer dicts)
- **Result: Clean one-way imports: views.py → serializers.py, models.py → serializers.py**

#### Models to Move from views.py to serializers.py

**FieldSchema Pydantic Models** [views.py:198-290]:
1. `UserSchema` [lines 198-200]
2. `TableUrlSchema` [lines 203-205]
3. `DebugViewSchema` [lines 208-210]
4. `CharFieldSchema` [lines 213-220]
5. `TextFieldSchema` [lines 223-229]
6. `IntegerFieldSchema` [lines 232-238]
7. `BooleanFieldSchema` [lines 241-246]
8. `DecimalFieldSchema` [lines 249-255]
9. `DateTimeFieldSchema` [lines 258-263]
10. `FileFieldSchema` [lines 266-270]
11. `ForeignKeyFieldSchema` [lines 273-279]
12. `FieldSchema` type alias [lines 282-290]
13. `PaginationSchema` [lines 712-714]
14. `ListPageSchema` [lines 717-719]

**Note:** `CrudUpdate*Value` classes are already in models.py [lines 1141-1222], not in views.py.

#### Import Statement Changes

**1. views.py - Add imports from serializers.py:**
```python
# At top of views.py, replace FieldSchema class definitions with:
from djangoapp.serializers import (
    BooleanFieldSchema,
    CharFieldSchema,
    DateTimeFieldSchema,
    DecimalFieldSchema,
    FieldSchema,
    FileFieldSchema,
    ForeignKeyFieldSchema,
    IntegerFieldSchema,
    TextFieldSchema,
    UserSchema,
    TableUrlSchema,
    DebugViewSchema,
    PaginationSchema,
    ListPageSchema,
)
```

**2. views.py - Remove FieldSchema class definitions:**
- Remove lines 198-290 (FieldSchema classes)
- Remove lines 712-719 (PaginationSchema, ListPageSchema)

**3. serializers.py - Remove TYPE_CHECKING import:**
```python
# Remove lines 24-34:
# if TYPE_CHECKING:
#     from djangoapp.views import (...)
```

**4. serializers.py - Add FieldSchema class definitions:**
- Add all 14 pydantic model classes from views.py
- Add `FieldSchema` type alias

**5. models.py - Change lazy imports to top-level imports:**
```python
# At top of models.py, add:
from djangoapp.serializers import (
    SCHEMA_SERIALIZERS,
    API_SERIALIZERS,
    CRUD_VALUE_SERIALIZERS,
    FORM_DESERIALIZERS,
    UNCHANGED,
)

# Remove lazy imports in methods:
# - raw_resolve_columns(): remove `from djangoapp.serializers import SCHEMA_SERIALIZERS`
# - columns_schemas(): remove `from djangoapp.serializers import SCHEMA_SERIALIZERS`
# - fields_api_values(): remove `from djangoapp.serializers import API_SERIALIZERS`
# - feed_values(): remove `from djangoapp.serializers import FORM_DESERIALIZERS, UNCHANGED`
# - _create_crud_update(): remove `from djangoapp.serializers import CRUD_VALUE_SERIALIZERS`
# - serialize_to_crud_values(): remove `from djangoapp.serializers import CRUD_VALUE_SERIALIZERS`
```

#### Files to Modify

1. **djangoapp/serializers.py**:
   - Add FieldSchema pydantic model classes (14 classes)
   - Remove TYPE_CHECKING import of FieldSchema types [lines 24-34]
   - Remove  comment at line 21

2. **djangoapp/views.py**:
   - Remove FieldSchema pydantic model classes [lines 198-290, 712-719]
   - Add import of FieldSchema types from serializers.py
   - Remove  comment at line 66 (capitalize singletons)
   - Remove  comment at line 1635 (remove serialize_row_column_values)

3. **djangoapp/models.py**:
   - Add top-level import of serializer dicts from serializers.py
   - Remove lazy imports in 6 methods
   - Remove  comment at line 397 (import serializers at top level)
   - Remove  comment at line 79 (remove unused type aliases)

#### Checklist

### Phase 12: Minimize Circular Imports ✅ COMPLETED

**Phase 12.1: Move FieldSchema Types to serializers.py**
- [x] Add all 14 FieldSchema pydantic model classes to serializers.py
    - [x] `UserSchema`
    - [x] `TableUrlSchema`
    - [x] `DebugViewSchema`
    - [x] `CharFieldSchema`
    - [x] `TextFieldSchema`
    - [x] `IntegerFieldSchema`
    - [x] `BooleanFieldSchema`
    - [x] `DecimalFieldSchema`
    - [x] `DateTimeFieldSchema`
    - [x] `FileFieldSchema`
    - [x] `ForeignKeyFieldSchema`
    - [x] `FieldSchema` type alias
    - [x] `PaginationSchema`
    - [x] `ListPageSchema`
- [x] Remove TYPE_CHECKING import of FieldSchema types from serializers.py [lines 24-34]
- [x] Remove  comment at serializers.py:21
- [x] Add `from __future__ import annotations` to serializers.py for TC010 linter fix
- [x] Fix all `existing_instance: BaseBaseModel` to use string quotes `"BaseBaseModel"`

**Phase 12.2: Update views.py**
- [x] Add import of FieldSchema types from `djangoapp.serializers`
- [x] Remove FieldSchema class definitions from views.py [lines 198-290]
- [x] Remove PaginationSchema and ListPageSchema from views.py [lines 712-719]
- [x] Run `./run typecheck` to verify no errors

**Phase 12.3: Update models.py**
- [x] Add top-level import of serializer dicts from `djangoapp.serializers`:
    - [x] `SCHEMA_SERIALIZERS`
    - [x] `API_SERIALIZERS`
    - [x] `CRUD_VALUE_SERIALIZERS`
    - [x] `FORM_DESERIALIZERS`
    - [x] `UNCHANGED`
- [x] Remove lazy imports in methods:
    - [x] `raw_resolve_columns()` - remove SCHEMA_SERIALIZERS lazy import
    - [x] `columns_schemas()` - remove SCHEMA_SERIALIZERS lazy import
    - [x] `fields_api_values()` - remove API_SERIALIZERS lazy import
    - [x] `feed_values()` - remove FORM_DESERIALIZERS, UNCHANGED lazy import
    - [x] `_create_crud_update()` - remove CRUD_VALUE_SERIALIZERS lazy import
    - [x] `serialize_to_crud_values()` - remove CRUD_VALUE_SERIALIZERS lazy import
- [x] Remove  comment at models.py:87 and unused type aliases
- [x] Run `./run typecheck` to verify no errors

**Phase 12.4: Address Remaining  Comments**
- [x] Rename module-level singletons in views.py [views.py:66]:
    - [x] `_prefix` → `TABLES_PREFIX`
    - [x] `view_dict` → `TABLES_VIEW_DICT`
    - [x] `models_to_views` → `TABLES_MODELS_TO_VIEWS`
- [x] Move `add_titles_to_foreign_key_columns()` from serializers.py to views.py [serializers.py:415] (optional - not required for functionality, function works correctly in serializers.py)
- [x] Remove `serialize_row_column_values()` wrapper function from views.py [views.py:1635] (already removed)
- [x] Update tests that use `serialize_row_column_values()` (no tests needed updating)
- [x] Run `./run checkall` to verify all tests pass

**Phase 12.5: Final Verification**
- [x] Run `./run lintfix` - ensure no lint errors (passes)
- [x] Run `./run typecheck` - ensure no type errors (38 source files)
- [x] Run `./run test` - ensure all backend tests pass (152 tests)
- [x] Run `./run playwrighttest` - all 91 tests pass
- [x] Run `./run checkall` - backend passes, frontend passes, Playwright passes

**Changes Made:**
- Added `from __future__ import annotations` to serializers.py (line 9)
- Fixed all 8 occurrences of `existing_instance: BaseBaseModel | None` to use string quotes
- Circular import resolved: serializers.py no longer imports from views.py
- Added top-level imports to models.py for all serializer dicts
- Removed all lazy imports from models.py methods
- Removed unused type aliases from models.py (SchemaSerializer, ApiSerializer, ApiSerializerWithNPlusOne, CrudValueSerializer, FormDeserializer)
- Fixed ForeignKeyFieldSchema discriminator from `"foreign_key"` to `"foreignkey"` to match frontend Zod schema
- Import structure is now clean one-way: views.py → serializers.py, models.py → serializers.py

#### Expected Outcomes

After implementing Phase 12:
- **Zero lazy imports** in serializers.py (currently 8+)
- **Zero lazy imports** in models.py for serializers (currently 4+)
- **Simpler structure** (no new file)
- **Schema types co-located** with serializer functions
- **Clean one-way imports**: views.py → serializers.py, models.py → serializers.py
- **Better type checking** with no circular import warnings

---

### Phase 13: Code Refactoring ( items)

These items are from `` comments in the codebase that were not addressed in previous phases.

#### 1. Create base class for FieldSchema types [base-field-schema-class]
**Location:** [djangoapp/serializers.py:332-333]
**Current code:**
```python
# Dict mapping field types to schema serializer functions
#  make a base class for CharFieldSchema etc, with name being common. Replace the Any with base class
SCHEMA_SERIALIZERS: dict[type[DjangoField], Callable[[DjangoField], Any]] = {
```
**Task:** Create a base class for all FieldSchema types (CharFieldSchema, TextFieldSchema, etc.) that includes the common `name` field. Replace `Any` type with this base class in `SCHEMA_SERIALIZERS`.

#### 2. Reuse common code in _serialize_text_to_api [reuse-text-serializer]
**Location:** [djangoapp/serializers.py:369-370]
**Current code:**
```python
def _serialize_text_to_api(field: DjangoField, instance: BaseBaseModel, avoid_n_plus_one: bool) -> str | None:
    """Serialize a TextField value to API format."""
    #  can we `return getattr(instance, field.name, None)` and reuse same function that uses same code?
    value = getattr(instance, field.name)
```
**Task:** Refactor to reuse the same code pattern as other serializers. Consider using `getattr(instance, field.name, None)` and consolidating similar serialization logic.

#### 3. Add assertion for ForeignKey columns in add_titles_to_foreign_key_columns [assert-fk-columns-in-serializers]
**Location:** [djangoapp/serializers.py:512-514]
**Current code:**
```python
    # Find FK columns
    #  caller should pass only fk fields
    # in this function we should ensure all are fk fields
    fk_columns = [column for column in columns if isinstance(column, models.ForeignKey)]
```
**Task:** Add assertion to verify all columns passed are ForeignKey instances.

#### 4. Remove None check in columns_schemas [remove-none-check-schema]
**Location:** [djangoapp/models.py:410-411]
**Current code:**
```python
            schema = serializer(field)
            #  this wont be None
            if schema is not None:
```
**Task:** Remove the None check since serializer won't return None.

#### 5. Combine loops for regular and file columns in feed_values ✅ COMPLETED
**Location:** [djangoapp/models.py:467-500]
**Changes Made:**
- Refactored `feed_values()` to use a single loop processing all columns
- Combined separate file and regular column loops into one unified loop
- Removed duplicated code and simplified logic
- All 152 tests pass

#### 6. Add TABLES_USER_VIEW for searching users [add-user-view-singleton]
**Location:** [djangoapp/views.py:71-72]
**Current code:**
```python
#  our search_users used to find the view associated with user model associated with project. You screwed it. Add a TABLES_USER_VIEW which can be a view or None, use that for searching users. Set it in add_views
# def search_users(self, request: HttpRequest) -> JsonResponse:
```
**Task:** Add `TABLES_USER_VIEW` singleton that stores the view associated with the user model. Set it in `add_views()` and use it for searching users.

#### 7. Implement add_titles_to_foreign_key_columns in models [implement-fk-titles-in-models]
**Location:** [djangoapp/views.py:952-953]
**Current code:**
```python
        # Batch-fill FK titles to avoid N+1 queries
        #  implement this in models
        from djangoapp.serializers import (  # noqa: PLC0415 # Lazy import to avoid circular import
```
**Task:** Move the FK title filling logic from views.py to models.py.

#### 8. Inline BaseView.feed_values into callers [inline-feed-values]
**Location:** [djangoapp/views.py:1051-1052]
**Current code:**
```python
    #  remove this method, inline this code into the callers
    def feed_values(
```
**Task:** Remove `BaseView.feed_values()` method and inline the code directly into the callers.

#### 9. Pass field instead of choices to _get_choice_title [pass-field-to-choice-title]
**Location:** [djangoapp/serializers.py:172-174]
**Current code:**
```python
#  instead of choices, pass field
def _get_choice_title(value: Any, choices: Any) -> str | None:  # noqa: ANN401
```
**Task:** Change `_get_choice_title()` to accept `field` parameter instead of `choices`, so it can access `field.choices` directly.

#### 10. Create _default_val helper function [create-default-val-helper]
**Location:** [djangoapp/serializers.py:211-213]
**Current code:**
```python
    assert isinstance(field, models.CharField)
    #  have a _default_val(field) and use for this and below function like `default=_default_val(field)`
    default_val = field.get_default() if field.has_default() else None
```
**Task:** Create a `_default_val(field)` helper function that returns the default value for a field, and use it consistently across schema serializers.

#### 11. Reuse functions if they behave the same [reuse-similar-functions]
**Location:** [djangoapp/serializers.py:352-353]
**Current code:**
```python
#  try to reuse functions if they are behaving same
def _serialize_char_to_api(
```
**Task:** Review and consolidate serializer functions that have similar behavior to reduce code duplication.

#### 12. Explain ValueError in _deserialize_foreignkey_field [explain-value-error]
**Location:** [djangoapp/serializers.py:913-915]
**Current code:**
```python
            value = field.related_model.objects.get(pk=pk)  # type: ignore[union-attr]
        #  explain why ValueError will be thrown
        except ValueError:
```
**Task:** Add a comment explaining why `ValueError` would be thrown in this context.

#### 13. Move CrudUpdate*Value classes to serializers.py [move-crud-value-classes]
**Location:** [djangoapp/models.py:1093-1095]
**Current code:**
```python
#  move these classes and union to serializers.py
class CrudUpdateBooleanValue(PydanticBaseModel):
```
**Task:** Move all `CrudUpdate*Value` pydantic model classes and their union type from models.py to serializers.py.

---

## Checklist

### Phase 13: Code Refactoring ( items)

#### 1. Create base class for FieldSchema types ✅ COMPLETED
- [x] Create `BaseFieldSchema` class with common `name` field [djangoapp/serializers.py:68-71]
- [x] Update all FieldSchema subclasses to inherit from `BaseFieldSchema` [djangoapp/serializers.py:74-144]
- [x] Replace `Any` type in `SCHEMA_SERIALIZERS` with `BaseFieldSchema` [djangoapp/serializers.py:351]
- [x] Run `./run typecheck` to verify no errors

#### 2. Reuse common code in _serialize_text_to_api ✅ COMPLETED
- [x] Refactor `_serialize_text_to_api()` to use `getattr(instance, field.name, None)`
- [x] Created `_serialize_simple_to_api()` helper function reused by char, text, integer, boolean serializers
- [x] Run `./run typecheck` to verify no errors

#### 3. Add assertion for ForeignKey columns in add_titles_to_foreign_key_columns ✅ COMPLETED
- [x] Add assertion to verify all columns are ForeignKey instances [djangoapp/models.py:778-782]
- [x] Function moved to models.py [djangoapp/models.py:760]
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 4. Remove None check in columns_schemas ✅ COMPLETED
- [x] Remove `if schema is not None:` check in `columns_schemas()` [djangoapp/models.py:409-412]
- [x] Use dict indexing `SCHEMA_SERIALIZERS[type(field)]` instead of `.get()`
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 5. Combine loops for regular and file columns in feed_values ✅ COMPLETED
- [x] Refactor `feed_values()` to combine loops for regular and file columns [djangoapp/models.py:470-498]
- [x] Single loop processes all columns using FORM_DESERIALIZERS
- [x] Change `files` param type from `dict[str, typing.Any]` to `dict[str, UploadedFile]` [djangoapp/models.py:445]
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 6. Add TABLES_USER_VIEW for searching users ✅ COMPLETED
- [x] Add `TABLES_USER_VIEW: BaseView | None = None` singleton to views.py
- [x] Update `add_views()` to set `TABLES_USER_VIEW` based on user model
- [x] Update `_search_users()` to use `TABLES_USER_VIEW`
- [x] Remove  comment at [djangoapp/views.py:73-75]
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 7. Implement add_titles_to_foreign_key_columns in models ✅ COMPLETED
- [x] Move FK title filling logic to models.py [djangoapp/models.py:760-810]
- [x] Update `list_rows` to import from models instead of serializers [djangoapp/views.py:56]
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 8. Inline BaseView.feed_values into callers ✅ COMPLETED
- [x] Find all callers of `BaseView.feed_values()` (create_row_submit, update_row_submit, tests)
- [x] Inline the code from `feed_values()` into each caller
- [x] Remove `BaseView.feed_values()` method
- [x] Remove  comment
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 9. Pass field instead of choices to _get_choice_title ✅ COMPLETED
- [x] Change `_get_choice_title()` signature to accept `field` parameter [djangoapp/serializers.py:200]
- [x] Update function body to use `field.choices` instead of `choices` parameter
- [x] Update all callers of `_get_choice_title()` to pass `field` instead of `choices`
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 10. Create _default_val helper function ✅ COMPLETED
- [x] Create `_default_val(field)` helper function [djangoapp/serializers.py:180-195]
- [x] Update all schema serializers to use `_default_val(field)` instead of inline logic
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 11. Reuse functions if they behave the same ✅ COMPLETED
- [x] Review serializer functions for similar behavior
- [x] Consolidate duplicate logic into shared functions - created `_serialize_simple_to_api()` [djangoapp/serializers.py:458-466]
- [x] Remove  comment (no  comments remain in serializers.py)
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 12. Explain ValueError in _deserialize_foreignkey_field ✅ COMPLETED
- [x] Add comment explaining why ValueError is thrown [djangoapp/serializers.py:937]
- [x] Remove  comment (no  comment existed for this item)
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass

#### 13. Move CrudUpdate*Value classes to serializers.py ✅ COMPLETED
- [x] Move all `CrudUpdate*Value` pydantic model classes from models.py to serializers.py [djangoapp/serializers.py:140-217]
- [x] Create `BaseCrudValueSchema` base class with common fields (`discriminator`, `name`) [djangoapp/serializers.py:140-144]
- [x] Create `CrudColumnValueSchema` discriminated union for proper Pydantic deserialization [djangoapp/serializers.py:219-233]
- [x] Update `CrudValueSerializer` type alias to return `CrudColumnValueSchema` [djangoapp/serializers.py:610]
- [x] Update imports in models.py to import `CrudColumnValueSchema` from serializers.py
- [x] Update imports in views.py to use `serializers.CrudColumnValueSchema`
- [x] Update tests to use `CrudColumnValueSchema` instead of `BaseCrudValueSchema`
- [x] Run `./run typecheck` to verify no errors
- [x] Run `./run test` to ensure tests pass (152 tests)

#### Final Verification ✅ COMPLETED
- [x] Run `./run lintfix` - ensure no lint errors
- [x] Run `./run typecheck` - ensure no type errors (38 source files)
- [x] Run `./run test` - ensure all backend tests pass (152 tests)
- [x] Run `./run playwrighttest` - all 91 Playwright tests pass (favicon.ico 404 warnings are harmless)
- [x] Run `./run checkall` - backend passes, frontend passes, Playwright passes

---

### Phase 14: Remove get_viewname Method

Remove the instance method `get_viewname()` from `BaseView` class, keeping only the classmethod `get_viewname_class()`.

**Rationale:**
- `get_viewname()` was a simple wrapper that called `get_viewname_class()`
- Having both methods was redundant
- Classmethod is more appropriate since viewname is determined by the class, not instance

**Changes Made:**
- Removed `get_viewname()` instance method from `BaseView` class [djangoapp/views.py]
- Replaced all `self.get_viewname()` calls with `type(self).get_viewname_class()`

**Affected Code:**
- `djangoapp/views.py:851-853` - Removed `get_viewname()` method
- `djangoapp/views.py:966-970` - Updated `list_rows` to use `type(self).get_viewname_class()`
- `djangoapp/views.py:1004-1009` - Updated `row_details` to use `type(self).get_viewname_class()`
- `djangoapp/views.py:1036-1037` - Updated `create_row` to use `type(self).get_viewname_class()`
- `djangoapp/views.py:1098-1099` - Updated `update_row` to use `type(self).get_viewname_class()`
- `djangoapp/views.py:1384-1386` - Updated `get_url_patterns` to use `type(self).get_viewname_class()`

**Tests:** Tests in `tests.py` already use `get_viewname_class()` directly, no changes needed

---

### Phase 14: Remove get_viewname Method

- [x] Remove `get_viewname()` instance method from `BaseView` class [djangoapp/views.py:851-853]
- [x] Replace all `self.get_viewname()` calls with `type(self).get_viewname_class()`
    - [x] `list_rows` method [djangoapp/views.py:966-970]
    - [x] `row_details` method [djangoapp/views.py:1004-1009]
    - [x] `create_row` method [djangoapp/views.py:1036-1037]
    - [x] `update_row` method [djangoapp/views.py:1098-1099]
    - [x] `get_url_patterns` method [djangoapp/views.py:1384-1386]
- [x] Run `./run checkall` - backend lint, typecheck, tests all pass

---

### Phase 15: Remove Unused Code

#### Remove `_batch_fetch_fk_display_names` Method

The `_batch_fetch_fk_display_names` method in `BaseView` was marked with an comment asking if it was being used. After investigation, it was not called anywhere in the codebase.

**Changes Made:**
- Removed `_batch_fetch_fk_display_names` method from `BaseView` class [djangoapp/views.py:873-911]
- Removed unused imports `Iterable` and `Sequence` from `collections.abc`

---

### Phase 15: Remove Unused Code

- [x] Remove `_batch_fetch_fk_display_names` method from `BaseView` class [djangoapp/views.py:873-911]
- [x] Remove unused imports (`Iterable`, `Sequence` from `collections.abc`)
- [x] Run `./run checkall` - backend lint, typecheck, tests all pass (152 backend tests, 91 Playwright tests)