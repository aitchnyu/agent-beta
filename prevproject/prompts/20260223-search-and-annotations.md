# Search and Annotations Implementation Plan

## Overview
We are changing `/search-rows` endpoint and displaying FK names in row list and details.

## Breaking Changes / Deletions

### Models to Remove (`djangoapp/models.py`)
- [x] Remove `SelectContext` dataclass, `BaseFilter`, `RefFilter`, `UserFilter`, `CategoryFilter` classes
- [x] Remove `select_filters` ClassVar from `BaseBaseModel`, `FirstStuff`, `ForeignKeyModel`
- [x] Remove `_maybe_title` field, `has_title`, `minimum_title_length`, `title` property/setter from `BaseModel`/`BaseBaseModel`
- [x] Remove `has_title = True` from `Ref`, `FirstStuff`
- [x] Remove `_maybe_title` from `excluded_attrs` in `BaseModel`

### Views to Remove/Modify (`djangoapp/views.py`)
- [x] Remove `SelectContext` import (replaced with `SearchContext`)
- [x] Rewrite `search_rows` method (line 1400-1419)
- [x] Simplify `ForeignKeyFieldHandler.serialize_to_api` to use `title_annotation`
- [x] Update `human_row_references` and `_generate_references` to use `title_annotation`
- [x] Remove title handling from `create_row_submit` / `feed_values`

### Migrations Required
- [x] Create migration to remove `_maybe_title` field from `BaseModel` (data loss is acceptable)
  - Created: `djangoapp/migrations/0004_remove_maybe_title_field.py`

### Frontend Changes
- [x] None needed - API response format stays the same (`{id, title}` for search, `{id, text}` for FK values)

---

## New Implementation

### Step 1: Add `SearchContext` dataclass ✅ DONE

**File:** `djangoapp/models.py`

```python
@dataclass
class SearchContext:
    user: User | None
    queryset: models.QuerySet[Any]  # The queryset to refine (already annotated with text)
    text: str  # The search text string
```

---

### Step 2: Add `title_annotation` class variable to `BaseBaseModel` ✅ DONE

**File:** `djangoapp/models.py`

```python
class BaseBaseModel(models.Model):
    # ... existing code ...
    
    # Defines how to compute display title. Defaults to ID.
    # Override in subclasses for custom display (e.g., Concat("first_name", Value(" "), "last_name"))
    title_annotation: ClassVar[models.F | models.Value | models.functions.Concat] = F("id")
```

For specific models:
- `ProxyUser`: `Concat("first_name", Value(" "), "last_name")` ✅ DONE
- `Ref`: `F("char_field")` ✅ DONE
- `CategoryModel`: `F("name")` ✅ DONE
- `FirstStuff`: Uses default `F("id")` (no override needed) ✅ DONE

---

### Step 3: Add `search_text` classmethod to `BaseBaseModel` ✅ DONE

**File:** `djangoapp/models.py`

**IMPORTANT:** `search_text()` should NOT generate queries inside. It just returns an annotated queryset.
Filtering is done by the `@search` decorator using `SearchContext`.

```python
@classmethod
def search_text(cls, text: str) -> models.QuerySet[typing.Self]:  # noqa: ARG003
    """Return annotated queryset for search.
    
    Default implementation: return all rows with text annotation.
    Subclasses can override for custom behavior, but should NOT filter here.
    Use @search decorator for filtering based on SearchContext.
    """
    return cls.objects.all().annotate(text=cls.title_annotation)
```

---

### Step 4: Add `SearchProxy`, `@search` decorator, and `get_search_method` to `BaseBaseModel` ✅ DONE

**File:** `djangoapp/models.py`

```python
class SearchProxy:
    """Wrapper that makes a search method behave like a classmethod."""
    def __init__(
        self,
        func: Callable[[type, SearchContext], models.QuerySet[Any]],
        column_name: str,
    ) -> None:
        self.func = func
        self.column_name = column_name
        self.__name__ = func.__name__
    
    def __call__(self, model_class: type, context: SearchContext) -> models.QuerySet[Any]:
        """Allow calling the proxy directly with model class and context."""
        return self.func(model_class, context)
    
    def __get__(self, obj: Any, objtype: type | None = None) -> Callable[[SearchContext], models.QuerySet[Any]]:
        def wrapper(context: SearchContext) -> models.QuerySet[Any]:
            return self.func(objtype, context)
        return wrapper


def search(column_name: str):
    """
    Decorator to define a search method for a FK column.
    
    Usage:
        @search("fk_column_name")
        @classmethod
        def any_method_name(cls, context: SearchContext) -> QuerySet:
            # context.queryset is the base queryset from search_text (already annotated)
            # context.text is the search string
            # context.user is the current user
            return context.queryset.filter(some_condition)
    """
    def decorator(func: Callable[[type, SearchContext], models.QuerySet[Any]]) -> SearchProxy:
        return SearchProxy(func, column_name)
    return decorator
```

Add `get_search_method` as a classmethod on `BaseBaseModel`:

```python
class BaseBaseModel(models.Model):
    # ... existing code ...
    
    @classmethod
    def get_search_method(cls, column_name: str) -> SearchProxy | None:
        """Get the search method for a column name by iterating class attributes."""
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if isinstance(attr, SearchProxy) and attr.column_name == column_name:
                return attr
        return None
```

---

### Step 5: Rewrite `/search-rows` endpoint ✅ DONE

**File:** `djangoapp/views.py`

**IMPORTANT:** The `@search` decorator goes on the model that HAS the FK column, not the related model.
The `search_rows` endpoint calls `model.get_search_method(columnname)` (the source model with the FK).

```python
from djangoapp.models import SearchContext

@classmethod
def search_rows(cls, request: HttpRequest, columnname: str) -> JsonResponse:
    model = cls.model
    field = model._meta.get_field(columnname)  # noqa: SLF001
    related_model = field.related_model
    text = request.GET.get("query", "").strip()
    
    # Start with base search_text results (already annotated with text)
    queryset = related_model.search_text(text)
    
    # Check for @search decorated method on the model that HAS the FK column
    search_method = model.get_search_method(columnname)
    if search_method:
        context = SearchContext(
            user=get_authenticated_user(request),
            queryset=queryset,
            text=text,
        )
        queryset = search_method(context)
    
    rows = queryset[:20]
    data = {
        "rows": [
            {"id": row.pk, "title": getattr(row, "text", str(row.pk))}
            for row in rows
        ]
    }
    return JsonResponse(data)
```

---

### Step 6: Add batch FK display helper to `BaseView` ✅ DONE

**File:** `djangoapp/views.py`

```python
@classmethod
def _batch_fetch_fk_display_names(
    cls,
    rows: Iterable[Any],
    fk_fields: Sequence[DjangoField],
) -> dict[str, dict[int, str]]:
    """Batch fetch display names for FK fields to avoid N+1 queries.

    Args:
        rows: The rows to fetch FK display names for
        fk_fields: List of ForeignKey fields

    Returns:
        Dict mapping field_name -> {fk_id -> display_text}

    """
    result: dict[str, dict[int, str]] = {}

    for field in fk_fields:
        assert isinstance(field, models.ForeignKey)
        assert field.related_model is not None

        # Collect all non-null FK ids for this field (using _id to avoid triggering queries)
        fk_ids: set[int] = set()
        for row in rows:
            fk_id = getattr(row, f"{field.name}_id", None)
            if fk_id is not None:
                fk_ids.add(fk_id)

        if not fk_ids:
            result[field.name] = {}
            continue

        # Batch fetch display names using title_annotation
        title_annotation = field.related_model.title_annotation
        annotated_qs = field.related_model.objects.filter(pk__in=fk_ids).annotate(
            text=title_annotation
        )
        result[field.name] = {obj.pk: getattr(obj, "text", str(obj.pk)) for obj in annotated_qs}

    return result
```

---

### Step 7: Update `list_rows` to use batch FK fetch ✅ DONE

**File:** `djangoapp/views.py`

The `list_rows` method now:
1. Collects FK fields from column_names
2. Calls `_batch_fetch_fk_display_names` before the row loop
3. Passes `fk_cache` to `serialize_to_api`

```python
# Collect FK fields for batch fetching
fk_fields = [f for f in column_names if isinstance(f, models.ForeignKey)]

# Batch fetch FK display names (one query per unique FK model type)
fk_cache = cls._batch_fetch_fk_display_names(page.object_list, fk_fields)

# Rows
row_data: list[dict[str, Any]] = []
for row in page.object_list:
    row_dict = {"id": row.pk, "title": str(row)}
    for field in column_names:
        fhandler = cls.field_handlers[field.__class__]
        row_dict[field.name] = fhandler.serialize_to_api(row, field, fk_cache)
    row_data.append(row_dict)
```

Also updated `ForeignKeyFieldHandler.serialize_to_api` to use `fk_cache`:

```python
def serialize_to_api(
    self,
    instance: ValueStuff,
    field: DjangoField,
    fk_cache: dict[str, dict[int, str]] | None = None,
) -> JSONValue:
    # Use cache if available to avoid N+1 queries
    if fk_cache and field.name in fk_cache:
        # Get FK id directly without triggering a query
        fk_id = getattr(instance, f"{field.name}_id", None)
        if fk_id is None:
            return None
        display_text = fk_cache[field.name].get(fk_id, str(fk_id))
        return {"id": fk_id, "text": display_text}

    # Fallback: access the FK object (for row_details, etc.)
    value = getattr(instance, field.name)
    if not value:
        return None
    assert field.related_model is not None
    title_annotation = field.related_model.title_annotation
    annotated_obj = field.related_model.objects.annotate(text=title_annotation).get(
        pk=value.pk
    )
    return {"id": value.pk, "text": annotated_obj.text}
```

---

### Step 8: DO NOT change `row_details` ✅ DONE

Per feedback, row_details should remain unchanged. The N+1 fix is only for `list_rows`.

---

### Step 9: Simplify `ForeignKeyFieldHandler.serialize_to_api` ✅ DONE

**File:** `djangoapp/views.py`

```python
def serialize_to_api(self, instance: ValueStuff, field: DjangoField) -> JSONValue:
    value = getattr(instance, field.name)
    if not value:
        return None
    # Get display text using title_annotation from the related model
    assert field.related_model is not None
    title_annotation = field.related_model.title_annotation
    annotated_obj = field.related_model.objects.annotate(text=title_annotation).get(
        pk=value.pk
    )
    return {"id": value.pk, "text": annotated_obj.text}
```

---

### Step 10: Update `_generate_references` to use `title_annotation` ✅ DONE

**File:** `djangoapp/views.py`

```python
def _generate_references(
    self, related_model: type[models.Model], ids: list[int]
) -> dict[int, str]:
    """Generate human-readable references from related model records."""
    title_annotation = related_model.title_annotation
    annotated = related_model.objects.filter(pk__in=ids).annotate(text=title_annotation)
    return {obj.pk: getattr(obj, "text", str(obj.pk)) for obj in annotated}
```

---

### Step 11: Update specific models with `title_annotation` and `@search` ✅ DONE

**File:** `djangoapp/models.py`

**IMPORTANT:** The `@search("column_name")` decorator goes on the model that HAS the FK column.
The method filters the **related model's** queryset (available via `context.queryset`).

```python
class ProxyUser(User, BaseBaseModel):
    """Target of FirstStuff.user_fk FK column."""
    title_annotation = Concat("first_name", Value(" "), "last_name")
    # No @search here - search methods go on the model with the FK column

class FirstStuff(BaseModel):
    """Model with user_fk FK column - @search goes HERE."""
    user_fk = models.ForeignKey("ProxyUser", null=True, on_delete=models.RESTRICT)
    
    @search("user_fk")
    @classmethod
    def search_user_fk(cls, context: SearchContext) -> models.QuerySet[Any]:
        """Filter ProxyUser by ID, username, first_name, or last_name.
        
        context.queryset is a ProxyUser queryset (from search_text).
        """
        text = context.text
        if not text:
            return context.queryset.none()
        if text.isnumeric():
            return context.queryset.filter(id=int(text))
        return context.queryset.filter(
            models.Q(username__icontains=text)
            | models.Q(first_name__icontains=text)
            | models.Q(last_name__icontains=text)
        )

class Ref(BaseModel):
    title_annotation = F("char_field")
    char_field = models.CharField(max_length=10)

class CategoryModel(BaseModel):
    title_annotation = F("name")
```

---

### Step 12: Unit Tests ✅ DONE

**File:** `djangoapp/tests/tests.py`

Existing tests have been updated to:
- [x] Remove `_maybe_title` assertions
- [x] Work without `select_filters`

New tests added:
- [x] Query count test for list_rows - `QueryCountTest.test_list_rows_query_count`
  - Verifies that `list_rows` uses batch FK fetching to avoid N+1 queries
  - Uses `assertNumQueries(3)` for: count, main query, and one batch FK query

---

## Implementation Order

1. [x] Add `SearchContext` dataclass with `user`, `queryset`, `text`
2. [x] Add `title_annotation` to `BaseBaseModel` (default `F("id")`)
3. [x] Add `search_text` classmethod to `BaseBaseModel` (just returns annotated queryset, no filtering)
4. [x] Add `SearchProxy` with `__call__`, `@search` decorator
5. [x] Add `get_search_method` classmethod to `BaseBaseModel`
6. [x] Update `ProxyUser`, `Ref`, `CategoryModel` with `title_annotation`
7. [x] Add `@search("user_fk")` decorator to `FirstStuff` (model with FK column) for filtering users
8. [x] Rewrite `/search-rows` endpoint (calls `model.get_search_method`, not `related_model.get_search_method`)
9. [x] Add `_batch_fetch_fk_display_names` helper to `BaseView`
10. [x] Update `list_rows` with batch FK fetch (uses `fk_cache` parameter)
11. [x] Simplify `ForeignKeyFieldHandler.serialize_to_api`
12. [x] Update `_generate_references` to use `title_annotation`
13. [x] Remove old code (`select_filters`, filter classes, `_maybe_title`, etc.)
14. [x] Create migration to remove `_maybe_title` field
15. [x] Update tests (remove old `_maybe_title` assertions)
16. [x] Run `./run checkall` to verify all linting passes

---

## Summary of Key Decisions

| Decision | Choice |
|----------|--------|
| `_maybe_title` data migration | Acceptable to lose data |
| Default `title_annotation` | `F("id")` |
| `search_text()` behavior | Returns annotated queryset only (no filtering) |
| Filtering logic | Use `@search` decorator with `SearchContext` |
| `SearchContext.queryset` | Already annotated with `text` |
| `SearchProxy.__call__` | Handles classmethods by detecting `classmethod` descriptor |
| `get_search_method` | Classmethod on `BaseBaseModel` |
| `@search` method discovery | Iterate class attributes (no registry) |
| **`@search` placement** | On model with FK column, not related model |
| `row_details` changes | None - keep as is |
| FK caching | Batch fetch in `list_rows` using `fk_cache` dict |
| Query count target | 1 count + 1 main + 1 batch FK query (3 total) |

---

## Refactoring TODOs

### Code Organization
- [x] Move `SearchContext` dataclass close to `SearchProxy` class (they are related)
- [x] Rename `SearchContext.text` to `SearchContext.search_text` for clarity

### BaseBaseModel.search_text
- [x] Return `.none()` if text is not numeric (default implementation should only match numeric IDs)

### SearchProxy and get_search_method
- [x] `_get_search_proxies` is now used in `get_search_method`

### FirstStuff.search_user_fk cleanup
- [x] Remove the redundant `ProxyUser.search_text(context.text)` call since `context.queryset` is already the result of `search_text()`
- [x] The method now just filters `context.queryset` directly

### SearchContext type parameter
- [x] Add generic type parameter to SearchContext for the queryset model type:
  ```python
  @dataclass
  class SearchContext(Generic[T]):
      user: User | None
      queryset: models.QuerySet[T]
      search_text: str
  ```
- [x] Update method signatures:
  ```python
  # Old
  def search_user_fk(cls, context: SearchContext) -> models.QuerySet["ProxyUser"]
  # New
  def search_user_fk(cls, context: SearchContext["ProxyUser"]) -> models.QuerySet["ProxyUser"]
  ```

### Model method to combine search logic
- [x] Create a model method that combines `search_text` and `@search` method lookup:
  ```python
  # In BaseBaseModel
  @classmethod
  def search_for_fk_column(
      cls, 
      column_name: str, 
      user: User | None, 
      search_text: str
  ) -> models.QuerySet[Any]:
      field = cls._meta.get_field(column_name)
      related_model = field.related_model
      queryset = related_model.search_text(search_text)
      search_method = cls.get_search_method(column_name)
      if search_method:
          context = SearchContext(user=user, queryset=queryset, search_text=search_text)
          queryset = search_method(context)
      return queryset
  ```

### ForeignKeyFieldHandler.serialize_to_api
- [x] ~~Use `self.fk_lookup` instance variable instead of passing `fk_lookup` as parameter~~
  - **NOT APPLICABLE**: FieldHandler instances are singletons shared across all views (see `BaseView.field_handlers` classvar).
  - Using `self.fk_lookup` would cause race conditions in multi-threaded environments.
  - The current design (passing `fk_lookup` as parameter) is correct.

---

## Future TODOs - COMPLETED

### Test Organization
- [x] Move `TableStuffSmokeTestsTest.test_table_stuff_crashes_on_bad_model` to above `SmokeTestsTest` class
  - Location: `djangoapp/tests/tests.py:2250`

### Test Improvements
- [x] Remove `test_non_numeric_search_has_text_annotation` test
- [x] Add test when a user has first name equal to `str(self.user.pk)` and verify both ID match and text match appear in results
  - Location: `djangoapp/tests/tests.py:2411`
  - New test: `test_numeric_search_returns_both_id_and_text_matches`

---

## Bugs / Issues Found

### search-rows returns empty title for users with no first/last name ✅ FIXED
- **Issue**: `/tables/firststuff/search-rows/user_fk` returns `{"id": 1, "title": " "}` for users with empty first_name and last_name
- **Root cause**: `ProxyUser.title_annotation = Concat("first_name", Value(" "), "last_name")` produces `" "` when both are empty
- **Fix**: Updated `ProxyUser.title_annotation` to use `Coalesce(NullIf(Trim(Concat(...)), Value("")), "username")` to fall back to username when first_name and last_name are empty
- **Tests**:
  - [x] Added test case `test_user_with_empty_names_has_fallback_title` in `SearchUserFkTest`

---

## Refactoring TODOs - Phase 2

### Test Improvements
- [x] Use `result_pks = [r.pk for r in result]` and match for exact items with `set()` or alphabetical id sorting
- [x] In `test_list_rows_query_count`, refactor to use normal request-response instead of RequestFactory

### Architecture Improvements
- [x] `TableStuff.__init__` should initialize BaseView instances with `.table_stuff` reference
  - Already done: `view.table_stuff = self` in TableStuff.__init__
- [x] Remove `BaseView.models_to_views = original_models_to_views` pattern - no longer needed with proper architecture
  - Each TableStuff instance has its own `models_to_views`, so the class-level `BaseView.models_to_views` is no longer needed

### Row Details Page
- [x] Supply `title_annotation` for page title in `row_details` instead of using `str(row)`

### fk_cache parameter
- [x] Remove `fk_cache` parameter from `serialize_to_api`
  - **COMPLETED**: FieldHandler instances are now per-BaseView instance (not singletons).
  - Handlers access `self.view._fk_cache` for batch FK lookups (set by `list_rows` method).
  - `BaseView.__init__` initializes `self._fk_cache = None`.
  - `ForeignKeyFieldHandler.serialize_to_api` checks `self.view._fk_cache` and falls back to query if not available.

### List Page - Remove title column
- [x] Remove `title` field from `list_rows` row data in backend (`djangoapp/views.py`)
- [x] Update frontend `ListRows.vue` to show ID column instead of Title column
- [x] Update frontend `schemas.ts` to remove `title` from `ListRowsSchema.rows`
- [x] `SearchRowsResponseSchema` still needs `title` (used for FK search dropdown)

---

## Refactoring TODOs - Phase 3: Instance-based FieldHandler architecture

### Goal
Refactor FieldHandler to be per-BaseView instance, with each handler having a reference to its view via `__init__(self, view: BaseView)`. This eliminates the need for `table_stuff` parameters in method signatures.

### Changes Completed

#### 1. FieldHandler base class
- [x] Add `__init__(self, view: "BaseView") -> None` method
- [x] Store `self.view = view` for handler access to `table_stuff`

#### 2. Update all FieldHandler implementations
- [x] CharFieldHandler - no changes needed (doesn't use table_stuff)
- [x] TextFieldHandler - no changes needed (doesn't use table_stuff)
- [x] IntegerFieldHandler - no changes needed (doesn't use table_stuff)
- [x] BooleanFieldHandler - no changes needed (doesn't use table_stuff)
- [x] DecimalFieldHandler - no changes needed (doesn't use table_stuff)
- [x] DateTimeFieldHandler - no changes needed (doesn't use table_stuff)
- [x] FileFieldHandler - use `self.view.table_stuff.models_to_views` instead of parameter
- [x] ForeignKeyFieldHandler - use `self.view.table_stuff.models_to_views` instead of parameter

#### 3. Update BaseView class
- [x] Change `field_handlers` ClassVar to store handler **types**: `dict[type[DjangoField], type[FieldHandler]]`
- [x] In `__init__`, create instance dict: `self._handler_instances[field_cls] = handler_cls(self)`
- [x] Update all callers to use `self._handler_instances[field.__class__]` instead of `self.field_handlers[field.__class__]`

#### 4. Remove table_stuff and fk_cache parameters from method signatures
- [x] `to_schema(self, field)` - no extra parameters
- [x] `serialize_to_api(self, instance, field)` - no extra parameters (fk_cache accessed via `self.view._fk_cache`)

#### 5. Update tests
- [x] Add `from unittest.mock import MagicMock` import
- [x] Update tests to create handler instances with mock view: `handler_class(mock_view)`
- [x] Update all `BaseView` methods to use `self` instead of `cls`
- [x] Update tests to work with instance-based views
