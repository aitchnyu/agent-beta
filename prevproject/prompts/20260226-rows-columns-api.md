## Initial

### Include
We will remove cls.exclude_columns [remove-exclude-columns-1]. We will keep only cls.include_columns [keep-include-columns]. When we have include_columns defined, column resolution will use those columns only and it will use that order of columns in list and details pages [include-columns-order]. Test it shows up in same order [test-include-order]. Test that order is different with/without include_columns on same model [test-include-order-diff]. Test that entering invalid/duplicate values in include_columns will trigger smoke_tests [test-include-validation]. Also refactor smoke_tests to separate private methods for each check [refactor-smoke-tests].

### Row resolution
We currently have cls.modify_query (which we will remove) [replace-modify-query].
We will replace with
def resolve_rows(cls, context:ResolveRowsContext) -> Queryset:
    return context.query # base class behavior, we can filter from this for list/details/update/delete

We use output query to check to fetch for list [resolve-rows-list]. If id is present in query, details, update and delete succeeds, else 404 [resolve-rows-404].

class ResolveRowsContext [create-resolve-rows-context]
    user
    query
    operation: union of list/details/update/delete

### Column resolution
We have this method which we intend for user: resolve_column_permission_for_user_and_operation (which we will remove) [replace-resolve-column-permission]
We will replace it with this:

def resolve_columns(cls, context:ResolveColumnsContext) -> tuple[str]|None:
    return context.columns # base class behavior, we can return different columns

class ResolveColumnsContext[cls] [update-resolve-columns-context]
    columns: tuple[str], comes from include_columns
    user
    operation: union of create/list/details/update/delete
    maybe_row: row|None, provided for details/update/delete ()

If we return None from this function, user will get a 404 error [resolve-columns-none-404]. If user passes missing id, he will get 404 before resolve_columns is called [missing-id-404-before].

Yes, read is split into list/details. Have distinct tests with different columns [test-list-details-different-columns].

We used resolve_column_permission_for_user_and_operation from other methods. Now we will use resolve_columns for create/list/details/update/delete views [use-resolve-columns-all-views]. Test each of them. have test where list/details have different columns [test-list-details-different-columns].

Dont use FirstStuff class for any more tests [no-firststuff-tests]. Minimal models for all operations. Check which tests have to be adapted [adapt-existing-tests].

Add tests where edit and delete are prevented since row matching id had column call prevent_edit and prevent_delete set to true [test-prevent-edit-delete].

No more can_create_row [remove-can-create-row], since we can return None from resolve_columns.

### Saving
Now we have:
before_change - raise errors, context: user, row, saved_row (which we will remove) [replace-before-change]

Replace with:
model.save_stuff(user, context: SaveContext) - catch errors

Views call .save_stuff [views-call-save-stuff]. User can override like:

```python
...
if self.char_field == "11":
    raise ValidationError({"char_field": "value is 11", "_top": "Oops, something is 11"})
super().save_stuff(user, saved_row)
```

The ValidationError will render in frontend [validation-error-frontend].

class SaveContext[cls] [create-save-context]
    user:
    saved_row: fetch the row from db

### CRUD Operations
For each operation, these operations are called in this order [crud-operation-order].
 - create - resolve_columns, save_stuff
 - list - resolve_rows, resolve_columns
 - details - resolve_rows, resolve_columns
 - update - resolve_rows, resolve_columns, save_stuff
 - delete - resolve_rows, resolve_columns


### Brief description
Create a md file describing resolve_rows, resolve_columns, save_stuff [create-docs-md]. Audience is third party developer using these methods. Examples to prevent deletes/updates using both resolve_rows and resolve_columns and all crud operations [docs-prevent-examples]. Examples How to have validation errors for field and _top [docs-validation-examples].

## Plan
This place was filled in by agent.

### Checklist

#### Phase 1: Include columns cleanup
- [x] Remove `exclude_columns` class variable from BaseBaseModel [remove-exclude-columns-1]
- [x] Remove `ExcludeFirst` model class (uses exclude_columns) [remove-exclude-columns-1]
- [x] Remove `BothIncludeExclude` model class (tests both include/exclude) [remove-exclude-columns-1]
- [x] Update `raw_resolve_columns` to only use `include_columns`, remove exclude_columns logic [remove-exclude-columns-1]
- [x] Remove test `test_exclude_first_column` in BaseModelTest [remove-exclude-columns-1]
- [x] Remove test `test_both_include_exclude_raises_error` in BaseModelTest [remove-exclude-columns-1]
- [x] Update `include_columns` to preserve order when returning columns [include-columns-order]
- [x] Add test that columns appear in same order as defined in `include_columns` [test-include-order]
- [x] Add test that order is different with/without include_columns on same model [test-include-order-diff]
- [x] Add smoke_test validation for invalid column names in `include_columns` [test-include-validation]
- [x] Add smoke_test validation for duplicate column names in `include_columns` [test-include-validation]
- [x] Refactor `smoke_tests` to separate private methods for each check (`_validate_search_proxies`, `_validate_include_columns`) [refactor-smoke-tests]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 2: Row resolution - ResolveRowsContext and resolve_rows
- [x] Create `ResolveRowsContext` dataclass with user, query, operation fields [create-resolve-rows-context]
- [x] Add `resolve_rows` classmethod to BaseBaseModel returning `context.query` by default (will replace `modify_query`) [replace-modify-query]
- [x] Update `list_rows` to use `resolve_rows` instead of `modify_query` [resolve-rows-list]
- [x] Update `get_row_for_user_and_operation` to use `resolve_rows` instead of `modify_query` [resolve-rows-404]
- [x] Ensure 404 is returned when row id not found in resolved query [resolve-rows-404]
- [x] Remove `ModifyQueryContext` dataclass (replaced by ResolveRowsContext) [replace-modify-query]
- [x] Remove `modify_query` method from BaseBaseModel [replace-modify-query]
- [x] Update views to use `resolve_rows` for list/details/update/delete operations [resolve-rows-list] [resolve-rows-404]
- [x] Create minimal test model for prevent tests with boolean field `prevent_edit` and `prevent_delete` [test-prevent-edit-delete]
- [x] Add test where edit is prevented via resolve_rows filtering out the row [test-prevent-edit-delete]
- [x] Add test where delete is prevented via resolve_rows filtering out the row [test-prevent-edit-delete]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 3: Column resolution - ResolveColumnsContext and resolve_columns
- [x] Update `ResolveColumnsContext` dataclass to add `columns` field (tuple[str]) [update-resolve-columns-context]
- [x] Update `ResolveColumnsContext` dataclass to add `maybe_row` field (row|None) [update-resolve-columns-context]
- [x] Update operation type to include list/details separately (not just read) [update-resolve-columns-context]
- [x] Create `resolve_columns` classmethod returning `context.columns` by default, or None for 404 (will replace `resolve_column_permission_for_user_and_operation`) [replace-resolve-column-permission]
- [x] Remove `resolve_column_permission_for_user_and_operation` method [replace-resolve-column-permission]
- [x] Remove `resolve_columns_for_list`, `resolve_columns_for_create`, `resolve_columns_for_update` methods [use-resolve-columns-all-views]
- [x] Update create view to use `resolve_columns` with operation="create" [use-resolve-columns-all-views]
- [x] Update list view to use `resolve_columns` with operation="list" [use-resolve-columns-all-views]
- [x] Update details view to use `resolve_columns` with operation="details" [use-resolve-columns-all-views]
- [x] Update update view to use `resolve_columns` with operation="update" [use-resolve-columns-all-views]
- [x] Update delete view to use `resolve_columns` with operation="delete" [use-resolve-columns-all-views]
- [x] Return 404 when `resolve_columns` returns None [resolve-columns-none-404]
- [x] Ensure 404 for missing id happens before `resolve_columns` is called [missing-id-404-before]
- [x] Create minimal test model for list/details tests with different columns [test-list-details-different-columns]
- [x] Add test where list and details return different columns [test-list-details-different-columns]
- [x] Add test where edit is prevented via resolve_columns returning None [test-prevent-edit-delete]
- [x] Add test where delete is prevented via resolve_columns returning None [test-prevent-edit-delete]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 4: Remove can_create_row
- [x] Remove `can_create_row` classmethod from BaseBaseModel [remove-can-create-row]
- [x] Remove can_create_row check from `create_row` view (use resolve_columns returning None instead) [remove-can-create-row]
- [x] Remove can_create_row check from `create_row_submit` view [remove-can-create-row]
- [x] Remove `can_create_row` override from ProxyUser model [remove-can-create-row]
- [x] Update test `test_user_create_row_get_fails` to use resolve_columns returning None [remove-can-create-row]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 5: Saving - SaveContext and save_stuff
- [x] Create `SaveContext` dataclass with user and saved_row fields [create-save-context]
- [x] Create `save_stuff` method on BaseBaseModel that takes user and SaveContext (will replace `before_change`) [replace-before-change]
- [x] Move `before_change` logic to `save_stuff` in base class [replace-before-change]
- [x] Remove `BeforeSaveContext` dataclass (replaced by SaveContext) [replace-before-change]
- [x] Remove `before_change` method from BaseBaseModel [replace-before-change]
- [x] Update `feed_values` in views to call `save_stuff` instead of `before_change` [views-call-save-stuff]
- [x] Update `create_row_submit` view to call `save_stuff` [views-call-save-stuff]
- [x] Update `update_row_submit` view to call `save_stuff` [views-call-save-stuff]
- [x] Ensure ValidationError from `save_stuff` renders in frontend [validation-error-frontend]
- [x] Update `Ref.before_change` to `Ref.save_stuff` [replace-before-change]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 6: CRUD Operations order verification
- [x] Verify create calls: resolve_columns, save_stuff [crud-operation-order]
- [x] Verify list calls: resolve_rows, resolve_columns [crud-operation-order]
- [x] Verify details calls: resolve_rows, resolve_columns [crud-operation-order]
- [x] Verify update calls: resolve_rows, resolve_columns, save_stuff [crud-operation-order]
- [x] Verify delete calls: resolve_rows, resolve_columns [crud-operation-order]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 7: Test adaptations
- [x] Identify and adapt existing tests using FirstStuff [adapt-existing-tests]
- [x] Replace FirstStuff usage with minimal models where appropriate [no-firststuff-tests]
- [x] Run `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall` - fix any issues

#### Phase 8: Documentation
- [x] Create `docs/rows-columns-api.md` documentation file [create-docs-md]
- [x] Document `resolve_rows` method with examples [create-docs-md]
- [x] Document `resolve_columns` method with examples [create-docs-md]
- [x] Document `save_stuff` method with examples [create-docs-md]
- [x] Add example: prevent create using resolve_rows + resolve_columns together [docs-prevent-examples]
- [x] Add example: prevent list using resolve_rows + resolve_columns together [docs-prevent-examples]
- [x] Add example: prevent details using resolve_rows + resolve_columns together [docs-prevent-examples]
- [x] Add example: prevent update using resolve_rows + resolve_columns together [docs-prevent-examples]
- [x] Add example: prevent delete using resolve_rows + resolve_columns together [docs-prevent-examples]
- [x] Add example: field-level validation error in save_stuff [docs-validation-examples]
- [x] Add example: _top level validation error in save_stuff [docs-validation-examples]

#### Phase 9: Follow-up items
- [x] Make a method on model with (user, operation, maybe_row) that generates column names and calls resolve_columns with ResolveColumnsContext [column_nameviews-helper]
- [x] Raise 404 when resolved_columns is None in feed_values [column_namefeed-values-404]
- [x] Use class method for resolving raw fields in `_validate_include_columns` [column_namevalidate-fields]
- [x] Move descriptions to docstring of respective methods in `smoke_tests` [column_namesmoke-tests-docstring]
- [x] Accept any iterable in `resolve_columns` return type annotation [column_nameresolve-columns-iterable]
- [x] Throw error if empty iterable is returned from `resolve_columns`, add test [column_nameempty-columns-error]
- [x] Explain `_top` in `save_stuff` docstring [column_nameexplain-top]
- [x] Ensure ValidationError with `_top` is documented in docstring and md file [column_nametop-documentation]
- [x] In docstring and md file, mention operation is "read" for `resolve_rows`, whereas for columns we have distinct list and details [column_nameoperation-read-docs]
- [x] Consider renaming `get_row_for_user_and_operation` to `get_row_or_404` and raising 404 there [column_namerename-get-row]
- [x] Merge assertion of `test_include_columns_preserves_order` with `test_include_columns_different_from_default` [column_namemerge-tests]
- [x] Have docstrings for why, not just what in `ResolveRowsTest` [column_nametest-docstrings]
- [x] Use class defaults in `ResolveRowsTest.setUp`, and call params only when it's True [column_nametest-defaults]
- [x] Rename `resolve_columns_to_fields` to `fields_or_404` and raise Http404 instead of returning None [column_namefields-or-404]
- [x] Rename `column_names` variable to `columns` in views since `fields_or_404` returns `list[DjangoField]`, not `list[str]` [column_namecolumn-names]
- [x] Remove `if column_names is None` checks in views since `fields_or_404` raises Http404 instead of returning None [column_nameremove-none-checks]
- [x] Update docs/rows-columns-api.md example to just use/return context.query [column_namedocs-resolve-rows]
- [x] Fix docs/rows-columns-api.md error handling section - create now returns 404 not 403 [column_namedocs-error-handling]
- [x] Update docs/rows-columns-api.md to describe _top in ValidationError handling [column_namedocs-validation]