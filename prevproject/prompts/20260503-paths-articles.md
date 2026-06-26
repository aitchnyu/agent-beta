# Prerequisites and refactors

## Django Ninja

Now we have .get_url_patterns() returning both json and http endpoints. It should return a tuple[tuple[api endpoints], tuple[http endpoints]]. Mount json endpoints under `/tables/api/firstuff` and the http under `/tables/firstuff`. For example `/tables/firststuff/row-details/4` will remain the same. Mount the `/api` before the user can mount a view called `api`, get pattern priority. For json endpoints, use Django Ninja. 

For example, in create_comment we are manually parsing body and returning requests. We will define input pydantic schemas and output schemas and define based on that. If 404 or 400 is raised, return appropriate json response. Ninja will handle the serialization and deserialization. sanitize_html will be in input schema.

Minimize json payload by avoiding null responses

## Modules
I've been meaning to separate stuff into framework code and application code.

Models should be a module. Have a base.py and app.py. Latter file should contain the stuff after: `# ------------------ Our test models, must be last part of this model ---------------------` 

Move public_ids into this module.

Views should be a module. Have a base.py and app.py. Latter file should contain the stuff after: `# ---------------- Our test views -------------------`

## More
List view has id header. The link text is id. Instead, link text should be title annotation. That column will have no header text. It will have a magifying glass icon. Click it, it will autofocus to a select field and allow us to search and navigate to rows by searching them. Have a playwright test for that.

For proxyuser, remove first_name and last_name from list view, since title annotation contains that.

In row updates, updates for fk should have clickable links.

No need to show `ID: 3` in details page

---

## Checklist

### Django Ninja [§Django Ninja]

- [x] Refactor `.get_url_patterns()` to return `tuple[tuple[api_endpoints], tuple[http_endpoints]]`
    - [x] Mount json endpoints under `/tables/api/firstuff` [§DJ-1]
    - [x] Mount http endpoints under `/tables/firstuff` (existing paths unchanged, e.g. `/tables/firststuff/row-details/4`) [§DJ-1]
    - [x] Ensure `/api` pattern has priority over user-mounted `api` view [§DJ-1]
- [x] Integrate Django Ninja for json endpoints
    - [x] Add `django-ninja` to dependencies, create `ninja_api = NinjaAPI()` in `ninja_api.py` [§DJ-2]
    - [x] Replace `urls.py` manual `path()` for api_patterns with `ninja_api.urls` mounted under `tables/api/` [§DJ-2]
        - [x] Remove in `urls.py:5` after this refactor
    - [x] Define input/output schemas per endpoint [§DJ-2]
    - [x] Move `sanitize_html` into input schema [§DJ-2]
    - [x] Replace manual body parsing and response construction with Ninja serialization/deserialization [§DJ-2]
    - [x] Return appropriate json response for 404 and 400 errors [§DJ-2]
    - [x] Convert endpoints to Ninja (one at a time, in this order):
        - [x] `search_rows` — GET `/{viewname}/search-rows/{columnname}` [§DJ-SR]
            - Input: query param `query: str`
            - Output: `SearchRowsResponse` (rows: list of `{id, title}`)
            - Currently: `request.GET.get("query")` + manual dict construction
        - [x] `row_updates` — GET `/{viewname}/row-updates/{row_id}` [§DJ-RU]
            - Input: path `row_id: str`
            - Output: `RowUpdateListResponse`
            - Currently: `JsonResponse(response.model_dump(exclude_none=True))`
            - Note: returns 404 as `HttpResponse("Not found")` — change to Ninja 404
        - [x] `create_comment` — POST `/{viewname}/create-comment/{row_id}` [§DJ-CC]
            - Input: `CommentRequest` (already pydantic with `sanitize_html` validator)
            - Output: `CommentResponse`
            - Currently: `json.loads(request.body)` + `CommentRequest(**body)` — Ninja handles this
        - [x] `update_comment` — POST `/{viewname}/{row_id}/update-comment/{row_update_id}` [§DJ-UC]
            - Input: `CommentRequest`
            - Output: `CommentResponse`
            - Currently: same manual parsing as create_comment
        - [x] `delete_comment` — POST `/{viewname}/{row_id}/delete-comment/{row_update_id}` [§DJ-DC]
            - Input: path `row_id: str`, `row_update_id: int`
            - Output: `DeleteRowResponse`
            - Currently: no body, just path params
        - [x] `create_row_submit` — POST `/{viewname}/create-row-submit` [§DJ-CRS]
            - Input: `request.POST` + `request.FILES` (form data, not JSON)
            - Output: `RowFormResponse` (discriminated union: `SuccessResponse | ValidationErrorResponse`)
            - Note: This uses multipart form data, may need special Ninja handling
        - [x] `update_row_submit` — POST `/{viewname}/update-row-submit/{row_id}` [§DJ-URS]
            - Input: same as create_row_submit + path `row_id`
            - Output: `RowFormResponse`
        - [x] `_notifications_delete` — POST `notifications/delete` [§DJ-ND]
            - Input: `{"notification_ids": list[int]}`
            - Output: `DeleteNotificationsResponse`
            - Currently: `json.loads(request.body)` + `body.get("notification_ids")`
        - [x] `_notifications_clear` — POST `notifications/clear` [§DJ-NC]
            - Input: `{"viewname": str | None}`
            - Output: `DeleteNotificationsResponse`
            - Currently: `json.loads(request.body)` + `body.get("viewname")`
- [x] Minimize json payload by avoiding null responses [§DJ-3]
    - [x] Add `exclude_none=True` to all JSON `model_dump()` calls [§DJ-3]
        - [x] `_notifications_delete`
        - [x] `_notifications_clear`
        - [x] `row_updates`
        - [x] `create_row_submit`
        - [x] `update_row_submit`
        - [x] `_validation_error_response`
- [x] Add tests for Ninja endpoints
    - [x] Test input validation (pydantic schemas)
    - [x] Test output serialization
    - [x] Test 400/404 error responses

### More [§More]

- [x] List view: replace id header column
    - [x] Link text should be title annotation instead of id [§M-1]
    - [x] Column header should have no text [§M-1]
    - [x] Column header should have a magnifying glass icon [§M-1]
    - [x] Clicking icon auto-focuses a select field to search and navigate to rows [§M-1]
    - [x] Add playwright test for search-and-navigate functionality [§M-1]
- [x] ProxyUser list view: remove `first_name` and `last_name` columns (title annotation covers them) [§M-2]
- [x] Row updates: FK updates should have clickable links [§M-3]
- [x] Details page: remove `ID: 3` display [§M-4]
- [x] Fix Playwright test `test_row_details_fk_link_url` to use public_id instead of .pk [§M-5]
- [x] Add `UserWithPublicId` type alias (`= User`) and annotate user parameters in models.py, views.py [§M-6]


### Frontend alignment [§Frontend]

- [x] Add `nullableOptional` helper to `schemas.ts` — wraps a Zod schema as `.nullable().optional()` [§FE-1]
    - Backend uses `exclude_none=True` via Ninja Router, so `None` keys are absent from JSON
    - Frontend needs `.optional()` (missing key) not just `.nullable()` (explicit null)
- [x] Replace all `.nullable().optional()` chains in `schemas.ts` with `nullableOptional()` [§FE-1]
    - `RowUpdateResponseSchema`: `column_values`, `comment_content`, `comment_deleted_at`, `edited_by`, `edited_at`
    - `RowColumnValueSchema` variants: `old_value`, `new_value`, `value_title`, `url`
    - `RowDetailsProps`, `ListRowsProps`: `slot_props`, `user_viewname`
- [x] Ensure no console error messages in Playwright tests [§FE-2]
    - [x] Move console error listener from `SearchNavigateE2ETestCase` into `BasePlaywrightTestCase` — all 16 test classes should inherit it [§FE-2]
        - Add `self.console_errors: list[str] = []` in `BasePlaywrightTestCase.setUp()`
        - Add `self.page.on("console", self._handle_console)` when page is created
        - Add `_handle_console` and `tearDown` with `self.fail()` from `SearchNavigateE2ETestCase`
        - Remove duplicate `setUp`/`_handle_console`/`tearDown` from `SearchNavigateE2ETestCase`
    - [x] Allowlist known benign console errors (e.g. `Content-Security-Policy` is already filtered) — add others if tests reveal them [§FE-2]

### items

- [x] `test_filters.py:1491` — rename any `filt` to `filter` in this file [§AH-3]
- [x] `models.py:1781` — keep first and last name, dont show for list, show for create and edit [§AH-2]
    - Added `first_name`, `last_name` to `include_columns`
    - Override `resolve_columns` to exclude them from `"list"` operation only
    - Updated `test_user_row_details` to assert first_name/last_name ARE present in details
- [x] `ListRowsContent.vue:277` — create a `th` component which contains the search feature [§AH-1]

---

## Review of commit `0e33d26` — "Ninja for managing apis"

### Bugs

- [x] `RowDetailsContent.vue:30` accesses `response.data.type` but `DeleteRowResponse` has no `type` field — only `message` [§R-1]
    - Hardcoded `"success"` instead
- [x] `created_by` in `RowUpdateResponseSchema` uses `UserSchema.nullable()` but not `.optional()` [§R-2]
    - Changed to `nullableOptional(UserSchema)`
- [x] `comment_deleted_by` field missing from frontend `RowUpdateResponseSchema` [§R-3]
    - Added `comment_deleted_by: nullableOptional(UserSchema)` to frontend schema
- [x] `edit_comment_timeout` and `delete_comment_timeout` in `RowUpdateListResponseSchema` use `.nullable()` without `.optional()` [§R-4]
    - Changed to `nullableOptional(z.number())`

### Dead code

- [x] Remove old `_search_users`, `_notifications_delete`, `_notifications_clear` functions (views.py:137-254) [§R-5]

### Schema quality

- [x] `SearchRowsResponse.rows` uses `list[dict[str, str]]` instead of a typed Pydantic model (responses.py:83-84) [§R-6]
    - Defined `SearchRowItem(PydanticBaseModel)` with `id: str` and `title: str`

### Stale docs

- [x] `add_views` docstring says "Returns: A tuple (list of URLPatterns, app_name)" but now returns `list[URLPattern]` (views.py:320-322) [§R-7]

### Fragility

- [ ] Ninja API reset in `add_views` manipulates private attributes (views.py:387-400) [§R-8]
    - `_router_registrations`, `_routers`, `_bound_routers_cache`, `_frozen` — all private API
    - No public Ninja API to reset routers; could break on django-ninja upgrades
    - Consider alternative: instantiate a fresh `NinjaAPI()` per `add_views` call, or track which routers were added and remove only those
- [x] `getFkData()` called up to 3× per template block in `RowColumnValues.vue` [§R-9]
    - Replaced with `resolvedRows` computed that resolves `fkOld`/`fkNew` once per row

## models and views modules
Models and views should be modules. I'm intending to split framework-like code from application-level code. Move models.py to models/base.py and views.py to views/base.py. Update import statements. Use git rename and commit.

Move the application-level code to own files.  
From models, move `# ------------------ Our test models, must be last part of this model ---------------------` to models/app.py.  
From views, move `# ---------------- Our test views -------------------` to views/app.py.
Move `public_ids` into the `models/` package

### Checklist

- [x] `git mv djangoapp/models.py djangoapp/models/base.py` [§MOD-1]
- [x] `git mv djangoapp/views.py djangoapp/views/base.py` [§MOD-1]
- [x] `git mv djangoapp/public_ids.py djangoapp/models/public_ids.py` [§MOD-1]
    - [x] Create compat shim at `djangoapp/public_ids.py` re-exporting from `djangoapp.models.public_ids` (for migrations)
- [x] Extract test models (after marker comment) to `models/app.py` [§MOD-2]
    - [x] Add imports for `BaseModel`, `_BaseModelMixin`, `SaveContext`, `SearchContext`, `search`, etc.
    - [x] Late-import `ProxyUser` in `base.py` methods to avoid circular import (`_build_row_update_response`, `filter_user_and_actions`)
- [x] Extract test views (after marker comment) to `views/app.py` [§MOD-3]
    - [x] Add imports for model classes from `djangoapp.models.app`, view base classes from `djangoapp.views.base`
    - [x] Remove app model imports from `views/base.py` that are only needed in `views/app.py`
- [x] Create `models/__init__.py` and `views/__init__.py` re-exporting from both submodules [§MOD-4]
    - [x] Explicitly re-export `_BaseModelMixin`, `_default_integer_callable` (underscore names excluded from `import *`)
    - [x] Add `__all__` list for mypy `attr-defined` checks
- [x] Update `views/base.py` `public_ids` import to relative (`.public_ids`) [§MOD-5]
- [x] Run lint, typecheck, tests [§MOD-6]
    - [x] Backend: ruff, mypy, 335 tests (5 pre-existing date-dependent failures)
    - [x] Frontend: eslint, vue-tsc — all pass