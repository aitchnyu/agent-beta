# Proxy User Support Implementation Plan

## Overview

This document describes the implementation of proxy model support for Django's User model, allowing it to work with the table view system (BaseView).

## Problem Statement

Django proxy models cannot inherit from classes that have concrete fields. The existing `BaseModel` class has fields (`id`, `_maybe_title`, `created_at`), making it impossible for `ProxyUser` to inherit from it directly.

## Solution

Create a fieldless abstract base class `BaseBaseModel` that defines the interface for table views. Both `BaseModel` and `ProxyUser` can inherit from this class.

## Implementation Details

### 1. BaseBaseModel (models.py)

A new abstract Django model with NO fields, only class variables and method signatures:

```python
class BaseBaseModel(models.Model):
    """Abstract base model with no fields - allows proxy models to inherit."""
    
    class Meta:
        abstract = True
    
    # Class variables for configuration
    include_columns: ClassVar[tuple[str, ...]] = ()
    exclude_columns: ClassVar[tuple[str, ...]] = ()
    excluded_attrs: ClassVar[set[str]] = {"id"}
    
    # Abstract methods that subclasses must implement
    @classmethod
    def list_rows(cls, user: User | None) -> models.QuerySet[typing.Self]: ...
    
    @classmethod
    def resolve_columns_for_list(...) -> list[DjangoField]: ...
    
    @classmethod
    def can_create_row(cls, user: User | None) -> bool: ...
    
    @property
    def title(self) -> str: ...
```

### 2. BaseModel Updates (models.py)

`BaseModel` now inherits from `BaseBaseModel` and adds its fields:

```python
class BaseModel(BaseBaseModel):
    id = models.BigAutoField(primary_key=True)
    _maybe_title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Inherits all methods from BaseBaseModel
```

### 3. ProxyUser Implementation (models.py)

Uses multiple inheritance to combine User with BaseBaseModel:

```python
class ProxyUser(User, BaseBaseModel):
    """Proxy model for User that allows editing specific fields via table views."""
    
    class Meta:
        proxy = True
    
    # Only allow editing these fields via table views
    include_columns: ClassVar[tuple[str, ...]] = (
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    
    @classmethod
    def can_create_row(cls, user: User | None) -> bool:
        return False  # Users created via Django auth, not table views
```

### 4. View Updates (views.py)

- Updated `BaseView.model` type annotation from `type[BaseModel]` to `type[BaseBaseModel]`
- Updated `TableStuff.models_to_views` type to `dict[type[BaseBaseModel], str]`
- Added `EmailField` to field_handlers (EmailField is a CharField subclass)

### 5. Unit Tests (tests.py)

Added two new test classes:

#### ProxyUserTest
Tests for ProxyUser model functionality:
- `test_proxy_user_is_proxy_model` - Verifies proxy model setup
- `test_proxy_user_list_rows` - Tests listing users
- `test_proxy_user_get_row_for_user_and_operation` - Tests row retrieval
- `test_proxy_user_can_create_row` - Verifies create is disabled
- `test_proxy_user_resolve_columns` - Tests column resolution
- `test_proxy_user_title` - Tests title property

#### ProxyUserCrudTest
Tests for CRUD operations via UserStuffView:
- `test_user_list_rows` - Test listing users
- `test_user_row_details` - Test viewing user details
- `test_user_row_details_not_found` - Test 404 for non-existent user
- `test_user_create_row_get` - Test create returns 403 (disabled)
- `test_user_update_row_get` - Test update form
- `test_user_update_row_submit_success` - Test successful update
- `test_user_update_row_submit_partial` - Test partial update
- `test_user_update_row_submit_not_found` - Test 404 for non-existent
- `test_user_delete_row_success` - Test successful delete
- `test_user_delete_row_not_found` - Test 404 for non-existent

## Key Technical Considerations

### Type Annotations
Since `BaseBaseModel` doesn't define `objects`, type checkers need `type: ignore[attr-defined]`:
```python
cls.objects.all()  # type: ignore[attr-defined]
```

### Runtime Checks
For `BaseModel`-specific functionality, use `isinstance` checks:
```python
if isinstance(instance, BaseModel):
    # Access BaseModel-specific fields
```

### Field Handlers
The `EmailField` type was added to field_handlers because the lookup uses `field.__class__` directly (not inheritance-aware):
```python
EmailField: CharFieldHandler(self),  # EmailField is a CharField subclass
```

## Usage Example

```python
# In models.py
class ProxyUser(User, BaseBaseModel):
    class Meta:
        proxy = True
    
    include_columns = ("username", "email", "first_name", "last_name")

# In views.py
class UserStuffView(BaseView):
    model = ProxyUser
```

## Verification

Run the following commands to verify the implementation:
```bash
./run lintfix      # Lint and format
./run typecheck    # Type checking
./run test         # Run unit tests
./run checkall     # Full verification
```

## Status

✅ **COMPLETED** - All phases implemented and tested.

- [x] Phase 1: Create BaseBaseModel in models.py
- [x] Phase 2: Update BaseModel in models.py
- [x] Phase 3: Update ProxyUser in models.py
- [x] Phase 4: Update views.py
- [x] Phase 5: Write unit tests for ProxyUser
- [x] Phase 6: Verification - All tests pass
- [x] Phase 7: Implement refactoring - split feed_values loop
- [x] Phase 8: Update ProxyUser to allow editing is_superuser, first_name, last_name, is_staff, is_active
- [x] Phase 9: Add unit tests for create, list, details, update, delete views for user
