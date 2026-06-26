# BaseView Logic Move - Implementation Plan

## Status: COMPLETED ✓

All phases implemented and verified with `./run checkall` (95 backend tests + 73 Playwright tests passing).

---

## Summary of Changes

### Phase 1: URL Pattern Changes (COMPLETED)
Changed from tablename-based to viewname-based URL patterns:
- **Old**: `/tables/list-rows/FirstStuff/...`
- **New**: `/tables/firststuff/list-rows/...`

### Phase 2: Move CRUD Methods from TableStuff to BaseView (COMPLETED)

#### Architecture Changes:
1. **`field_handlers`** - Moved from TableStuff instance to `BaseView.field_handlers` class-level attribute
2. **`supported_handlers()`** - Moved from TableStuff instance method to `BaseView.supported_handlers()` classmethod
3. **`models_to_views`** - Added as `BaseView.models_to_views` class-level dict, populated by TableStuff during initialization
4. **CRUD methods** - All moved from TableStuff to BaseView as classmethods:
   - `list_rows()`, `row_details()`, `create_row()`, `create_row_submit()`
   - `update_row()`, `update_row_submit()`, `delete_row()`
   - `search_rows()`, `download_file()`, `feed_values()`
5. **URL registration** - Each BaseView now has `get_url_patterns()` classmethod that returns its URL patterns

#### Key Design Decisions:
- Methods are classmethods on BaseView, using `cls.model` instead of `viewname` parameter
- `ForeignKeyFieldHandler` and `FileFieldHandler` use `BaseView.models_to_views` for lookups
- TableStuff still manages view registration and provides `debug_view`
- URL patterns are generated per-view via `get_url_patterns()`

### Files Modified:
1. **[`djangoapp/views.py`](djangoapp/views.py)** - Main refactoring
   - Added `field_handlers`, `models_to_views` as ClassVar on BaseView
   - Moved all CRUD methods from TableStuff to BaseView as classmethods
   - Added `get_url_patterns()` classmethod to BaseView
   - Updated `ForeignKeyFieldHandler.to_schema()` to use `BaseView.models_to_views`
   - Updated `FileFieldHandler.serialize_to_api()` to use `BaseView.models_to_views`

2. **[`frontend/src/pages/ListRows.vue`](frontend/src/pages/ListRows.vue)** - Fixed FK link URL format
3. **[`frontend/src/components/FieldDisplay.vue`](frontend/src/components/FieldDisplay.vue)** - Fixed FK link URL format
4. **[`djangoapp/tests/tests.py`](djangoapp/tests/tests.py)** - Updated to use `BaseView.supported_handlers()`, `BaseView.field_handlers`, `BaseView.feed_values()`
5. **[`djangoapp/tests/test_playwright.py`](djangoapp/tests/test_playwright.py)** - Added `test_row_details_fk_link_url()` test

---

## Original Requirements

We have TableStuff and BaseView.

We have
view_name = view.__name__

Actually, use model name lower case to generate url. Baseview may also have a viewname_override which is str | None which takes priority. Test this override.

TableStuff will have view_dict and models_to_views. But BaseView will do all the crud processing. Move field_handlers, supported_handlers, include etc to BaseView. 

When we do TableStuff([BaseView1, BaseView2]) the BaseView classes will store the TableStuff instance. This is useful to foreign key columns to link to details view for other models.

Each view will register urls with django, but with a different pattern.

```python
# currently
path(
    "list-rows/<str:tablename>/-<listrowsargs:params>-",
    self.list_rows,
    name="list-rows",
),
path(
    "row-details/<str:tablename>/<int:row_id>",
    self.row_details,
    name="row-details",
),
path("create-row/<str:tablename>", self.create_row, name="create-row"),

# update to 
path(
    "viewname/list-rows/-<listrowsargs:params>-",
    self.list_rows,
    name="list-rows-viewname",
),
path(
    "viewname/row-details/<int:row_id>",
    self.row_details,
    name="row-details-viewname",
),
path("viewname/create-row", self.create_row, name="create-row-viewname"),
```

Instead of tablename terminology, call it viewname.

Keep _debug endpoint. It will use TableStuff to look up urls.
