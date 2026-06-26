# Initial Requirements

Add `{viewname}/<int:row_id>/search-users`
Take param similar to  _search_users - use it only for filter - return every user

It returns id, text and is_visible
For is_visible, run resolve_rows in a loop and check if that user can return that row.
Api returns upto 10 results so loop runs 10 times.

Add quill-mention to quill based components. Results formatting so that is_visible with false value will show a warning in yellow "invisible". Ensure no xss attacks.

https://github.com/quill-mention/quill-mention

Store span tag in html with special class - update the css so content is styled in both editor and viewing components. Ensure html tag is properly stored when saved, ie escaping doesnt affect it.

---

## Detailed Plan

### Phase 1: Backend - Search Users API Endpoint

#### 1.1 Add `search_users_for_row` method to `BaseView` [djangoapp/views.py]
- Add new method `search_users_for_row(self, request, row_id)` on `BaseView`
- URL pattern: `f"{viewname}/<int:row_id>/search-users"` (as noted in  at `views.py:957`)
- Takes `q` query param to filter users (same param as `_search_users`)
- Logic:
  - Get the row via `model.get_row_for_user_and_operation(row_id, user, "read")` - return 404 if not found
  - Get search query from `request.GET.get("q", "")`
  - Use `TABLES_USER_VIEW.model.search_text(query)` to get annotated queryset (reuses existing `ProxyUser.search_text`)
  - Slice to 10 results (`[:10]`)
  - For each user, check visibility by running `model.resolve_rows(ResolveRowsContext(user=u, query=model.default_query(), operation="read"))` and checking if row_id is in the result
  - Return `JsonResponse` with list of `{"id": obj.pk, "text": obj.text, "is_visible": bool}`
- Register URL in `get_url_patterns()` (replace  comment)

#### 1.2 Add tests for search_users_for_row endpoint [djangoapp/tests/]
- Test returns 404 when row not found
- Test returns users with correct `is_visible` values
- Test respects `q` filter parameter
- Test returns at most 10 results
- Test works with models that override `resolve_rows`

---

### Phase 2: Backend - Allow Mention Span Tags in HTML Sanitization

#### 2.1 Update `ALLOWED_TAGS` in `djangoapp/utils.py`
- Add `span` to the allowed tags set

#### 2.2 Update `ALLOWED_ATTRIBUTES` in `djangoapp/utils.py`
- Add `"span": {"class", "data-id", "data-denotation-char"}` to allowed attributes
- The `quill-mention` module outputs spans with `class="mention"`, `data-id`, `data-denotation-char`, and `data-value`

#### 2.3 Add tests for span tag sanitization [djangoapp/tests/]
- Test that mention spans are preserved with correct attributes
- Test that malicious span attributes (onclick, etc.) are stripped
- Test that `class="mention"` is preserved

---

### Phase 3: Frontend - Install and Configure quill-mention

#### 3.1 Install quill-mention package
- Run `npm install quill-mention` in frontend directory
- Check if `@types/quill-mention` exists; if not, add type declarations

#### 3.2 Create type declarations if needed [frontend/src/]
- Add type declarations for `quill-mention` module if no @types package exists

---

### Phase 4: Frontend - Update RichTextEditor Component

#### 4.1 Integrate quill-mention into RichTextEditor [frontend/src/components/RichTextEditor.vue]
- Import `quill-mention` and register with Quill
- Add `mention` module to Quill config
- The `source(searchTerm, renderList)` function should:
  - Call `GET /tables/{viewname}/{rowId}/search-users?q={searchTerm}`
  - Map response to quill-mention item format `{id, value, is_visible}`
  - Call `renderList(items)` to display dropdown
- Add `viewname` and `rowId` as new props to the component (required when mentions are enabled)
- Add optional `enableMentions` prop (default false) to control whether mention module is loaded
- Configure `renderItem(item)` to show yellow "invisible" badge when `is_visible === false`

#### 4.2 Update CommentForm to pass mention props [frontend/src/components/CommentForm.vue]
- Pass `viewname` and `rowId` props to `RichTextEditor`
- Pass `enableMentions: true`

#### 4.3 Update RowUpdateComment to pass mention props [frontend/src/components/RowUpdateComment.vue]
- Need to receive `viewname` and `rowId` props
- Pass to `RichTextEditor` when editing

---

### Phase 5: Frontend - Update HTML Sanitization for Mention Spans

#### 5.1 Update `sanitizeHtml` in `frontend/src/utils/html.ts`
- Add `span` to `ALLOWED_TAGS`
- Add `class`, `data-id`, `data-denotation-char`, `data-value` to `ALLOWED_ATTR`
- These attributes are needed for quill-mention to re-render mentions in the editor

---

### Phase 6: Frontend - CSS Styling for Mentions

#### 6.1 Add mention styles to `frontend/src/main.css`
- Style `.ql-editor .mention` for Quill editor (snow theme)
- Style `.rich-text-display .mention` for read-only display
- Mention chip style: inline-block with background color, rounded, slightly padded
- Yellow warning badge for "invisible" mentions (`.mention.invisible` or similar)

---

### Phase 7: Verify HTML Storage Integrity

#### 7.1 Ensure mention HTML is stored and retrieved correctly
- Verify that `TextFieldDeserializer` in `djangoapp/serializers.py` preserves span tags (already handled by `sanitize_html` update)
- Verify that `sanitize_html` in `djangoapp/views.py` for comment content preserves span tags
- Verify that `RenderRawHtml.vue` displays mention spans correctly (already handled by frontend sanitization update)
- Verify that loading saved HTML back into Quill editor re-renders mentions as editable blots

---

### Phase 8: Propagation and E2E

#### 8.1 Update RowUpdateList/RowDetails for mention propagation
- `RowUpdateList.vue` already uses `RenderRawHtml` for text values - mentions will render automatically once CSS and sanitization are updated
- `RowDetails.vue` needs to pass `viewname` and `rowId` down to `CommentForm` (already does this)

#### 8.2 Playwright tests
- Test that @mention dropdown appears when typing `@` in comment editor
- Test that selecting a user inserts a mention span
- Test that mention spans are rendered in comment display
- Test that "invisible" warning shows for non-visible users
- Test that mention HTML survives save/reload cycle

---

## Checklist

### Backend - Search Users API

- [x] Add `search_users_for_row` method to `BaseView` in [djangoapp/views.py] ~~~ [x] URL pattern: `f"{viewname}/<int:row_id>/search-users"` (as noted in  at `views.py:957`)
- [x] Takes `q` query param to filter - use it only for filter - return every user
- [x] It returns id, text and is_visible
- [x] For is_visible, run resolve_rows in a loop and check if that user can return that row.
- [x] Api returns upto 10 results so loop runs 10 times.

- [x] Add tests for search_users_for_row endpoint [djangoapp/tests/]
    - [x] Test returns users with correct `is_visible` values
    - [x] Test returns 404 when row not found
    - [x] Test respects `q` filter parameter
    - [x] Test returns at most 10 results
    - [x] Test works with models that override `resolve_rows`
    - [x] Test `is_visible` is `false` when `resolve_rows` excludes that user

### Backend - Allow Mention Span Tags in HTML Sanitization

#### 2.1 Add `span` to `ALLOWED_TAGS` in [djangoapp/utils.py]
- [x] Add `class`, `data-id`, `data-denotation-char`, `data-value` to `ALLOWED_ATTRIBUTES`

#### 2.2 Update `ALLOWED_ATTRIBUTES` in [djangoapp/utils.py`
- [x] Add `"span": {"class", "data-id", "data-denotation-char", "data-value"}` to allowed attributes

#### 2.3 Add tests for span tag sanitization [djangoapp/tests/]
- [x] Test mention spans with valid attributes are preserved
- [x] Test that malicious span attributes (onclick, etc.) are stripped
- [x] Test `class="mention"` is specifically preserved

### Phase 3: Frontend - Install and Configure quill-mention

#### 3.1 Install quill-mention package
- [x] Run `npm install quill-mention` in frontend directory
- [x] Check if `@types/quill-mention` exists; if not, add type declarations

#### 3.2 Create type declarations if needed [frontend/src/]

#### Phase 4: Frontend - Update RichTextEditor Component

#### 4.1 Integrate quill-mention into RichTextEditor [frontend/src/components/RichTextEditor.vue]
- [x] Import `quill-mention` and register with Quill
- [x] Add `mention` module to Quill config
- [x] The `source(searchTerm, renderList)` function should:
  - [x] Call `GET /tables/{viewname}/{rowId}/search-users?q={searchTerm}`
  - [x] Map response to quill-mention item format `{id, value, is_visible}`
- [x] Call `renderList(items)` to display dropdown
- [x] Add `viewname` and `rowId` as new props to the component (required when mentions are enabled)
- [x] Add optional `enableMentions` prop (default false) to control whether mention module is loaded
- [x] Configure `renderItem(item)` to show yellow "invisible" badge when `is_visible === false`

#### 4.2 Update CommentForm to pass mention props [frontend/src/components/CommentForm.vue]
- [x] Pass `viewname` and `rowId` props to `RichTextEditor`
- [x] Pass `enableMentions: true`

#### 4.3 Update RowUpdateComment for mentions [frontend/src/components/RowUpdateComment.vue]
- [x] Need to receive `viewname` and `rowId` props
- [x] Pass `enableMentions`, `viewname`, `rowId` props to `RichTextEditor` in edit mode

#### 4.4 Update RowUpdateList and RowDetails for mention propagation
- [x] `RowUpdateList.vue` already uses `RenderRawHtml` for text values - mentions will render automatically once CSS and sanitization are updated
- [x] `RowDetails.vue` needs to pass `viewname` and `rowId` down to `CommentForm` (already does this)

### Phase 5: Frontend - Update HTML Sanitization for Spans

#### 5.1 Update `sanitizeHtml` in `frontend/src/utils/html.ts`
- [x] Add `span` to `ALLOWED_TAGS`
- [x] Add `class`, `data-id`, `data-denotation-char`, `data-value` to `ALLOWED_ATTR`

#### Phase 6: Frontend - CSS Styling for Mentions

#### 6.1 Add mention styles to `frontend/src/main.css`
- [x] Style `.ql-editor .mention` for Quill editor (snow theme)
- [x] Style `.rich-text-display .mention` for read-only display
- [x] Mention chip style: inline-block with background color, rounded, slightly padded
- [x] Yellow warning badge for "invisible" mentions (`.mention.invisible` or similar)

### Phase 7: Verify HTML Storage Integrity

#### 7.1 Ensure mention HTML is stored and retrieved correctly
- [x] Verify that `TextFieldDeserializer` in `djangoapp/serializers.py` preserves span tags (already handled by `sanitize_html` update)
- [x] Verify that `sanitize_html` in `djangoapp/views.py` for comment content preserves span tags
- [x] Verify that `RenderRawHtml.vue` displays mention spans correctly (already handled by frontend sanitization update)
- [x] Verify that loading saved HTML back into Quill editor re-renders mentions as editable blots

### Phase 8: Propagation and E2E

#### 8.1 Update RowUpdateList/RowDetails for mention propagation
- [x] `RowUpdateList.vue` already uses `RenderRawHtml` for text values - mentions will render automatically once CSS and sanitization are updated
- [x] `RowDetails.vue` needs to pass `viewname` and `rowId` down to `CommentForm` (already does this)

### Testing

#### 9.1 Playwright tests
- [x] Test that @mention dropdown appears when typing `@` in comment editor
- [x] Test that selecting a user inserts a mention span
- [x] Test that mention spans are rendered in comment display
- [x] Test that "invisible" warning shows for non-visible users
- [x] Test that mention HTML survives save/reload cycle


---

## Checklist

### Backend - Search Users API
- [x] Add `search_users_for_row` method to `BaseView` in [djangoapp/views.py] ~~~ [x] URL pattern `f"{viewname}/<int:row_id>/search-users"` (as noted in  at `views.py:957`)
- [x] Takes `q` query param to filter - use it only for filter - return every user
- [x] It returns id, text and is_visible
- [x] For is_visible, run resolve_rows in a loop and check if that user can return that row.
- [x] Api returns upto 10 results so loop runs 10 times.
- [x] Add tests for search_users_for_row endpoint in [djangoapp/tests/]
    - [x] Test returns users with correct `is_visible` values
    - [x] Test returns 404 when row not found
    - [x] Test respects `q` filter parameter
    - [x] Test returns at most 10 results
    - [x] Test works with models that override `resolve_rows`
    - [x] Test `is_visible` is `false` when `resolve_rows` excludes that user

### Backend - HTML Sanitization
- [x] Add `span` to `ALLOWED_TAGS` in [djangoapp/utils.py]
- [x] Add `class`, `data-id`, `data-denotation-char`, `data-value` to `ALLOWED_ATTRIBUTES`
- [x] Add tests for span tag sanitization in [djangoapp/tests/]
    - [x] Test mention spans with valid attributes are preserved
    - [x] Test that malicious span attributes (onclick, etc.) are stripped
    - [x] Test `class="mention"` is specifically preserved

### Frontend - quill-mention Integration
- [x] Install `quill-mention` package via `npm install quill-mention` in frontend directory
- [x] Add type declarations for `quill-mention` if no `@types` package exists
- [x] Update `RichTextEditor.vue` in [frontend/src/components/RichTextEditor.vue]
    - [x] Add props: `viewname?: string`, `rowId?: number`, `enableMentions?: boolean`
    - [x] Import `quill-mention` and register with Quill
    - [x] Configure `mention` module in Quill options when `enableMentions` is true
    - [x] Implement `source` function to call `/tables/{viewname}/{rowId}/search-users?q={searchTerm}`
    - [x] Map response to quill-mention item format `{id, value, is_visible}`
    - [x] Call `renderList(items)` to display dropdown
    - [x] Add `renderItem(item)` to show yellow "invisible" badge when `is_visible === false`
- [x] Update `CommentForm.vue` in [frontend/src/components/CommentForm.vue]
    - [x] Pass `viewname`, `rowId` and `enableMentions` to `RichTextEditor`
- [x] Update `RowUpdateComment.vue` in [frontend/src/components/RowUpdateComment.vue]
    - [x] Accept `viewname` and `rowId` props to enable mention mode
    - [x] Pass `viewname`, `rowId` and `enableMentions` to `RichTextEditor` when editing
    - [x] Update `RowUpdateList.vue` in [frontend/src/components/RowUpdateList.vue]
    - [x] Pass `viewname` and `rowId` to `RowUpdateComment.vue` to enable mentions in edit mode
    - [x] Update `RowDetails.vue` in [frontend/src/pages/RowDetails.vue]
    - [x] Pass `viewname` and `rowId` to `CommentForm` (already does this)

### Frontend - HTML Sanitization for Spans
- [x] Update `sanitizeHtml` in `frontend/src/utils/html.ts`
- [x] Add `span` to `ALLOWED_TAGS`
- [x] Add `"span": {"class", "data-id", "data-denotation-char", "data-value"}` to `ALLOWED_ATTR`

### Frontend - CSS Styling for Mentions
- [x] Add mention styles to `frontend/src/main.css`
- [x] Style `.ql-editor .mention` for Quill editor (snow theme)
- [x] Style `.rich-text-display .mention` for read-only display
- [x] Mention chip style: inline-block with background color, rounded, slightly padded
- [x] Yellow warning badge for "invisible" mentions (`.mention.invisible` or similar)

### Verification
- [x] Verify mention HTML is stored and retrieved correctly
- [x] Verify that `TextFieldDeserializer` in `djangoapp/serializers.py` preserves span tags (already handled by `sanitize_html` update)
- [x] Verify that `sanitize_html` in `djangoapp/views.py` for comment content preserves span tags
- [x] Verify that `RenderRawHtml.vue` displays mention spans correctly (already handled by frontend sanitization update)
- [x] Verify that loading saved HTML back into Quill editor re-renders mentions as editable blots

### Testing
- [x] Playwright tests for @mention functionality
    - [x] Test that @mention dropdown appears on `@` key
    - [x] Test that selecting a user inserts a mention span
    - [x] Test that mention spans are rendered in comment display
    - [x] Test that "invisible" warning shows for non-visible users
    - [x] Test that mention HTML survives save/reload cycle

# Next corrections

Remove `{viewname}/<int:row_id>/search-users`. Use `_search_users` instead. No `is_visible` either - it's meaningless when creating a row (the user may not have a row context yet).

###  items found

| File | Line | Comment |
|------|------|---------|
| `djangoapp/utils.py` | 47 | `_MentionCleaner` class uses regex/string manipulation. Rewrite with HTML/XML parser |
| `djangoapp/tests/test_utils.py` | 100 | No need to keep `data-denotation-char` in test expectations |
| `frontend/src/components/RichTextEditor.vue` | 4 | Use explicit plugin registration, not autoregister |
| `frontend/src/components/RichTextEditor.vue` | 12 | `enableMentions` should be true by default. Add comments for each prop |
| `frontend/src/components/RichTextEditor.vue` | 70 | Make an explicit type for the renderList callback |
| `frontend/src/components/RichTextEditor.vue` | 79 | Let error bubble up, don't check response.ok or have catch block |
| `frontend/src/components/RichTextEditor.vue` | 104 | Ensure no XSS in renderItem, explain why it's safe |
| `frontend/src/components/CommentForm.vue` | 68 | No need of placeholder feature |

---

## Detailed Plan - Corrections

### Phase C1: Backend - Remove `search_users_for_row` endpoint

#### C1.1 Remove `search_users_for_row` method from `BaseView` [djangoapp/views.py:890-931]
- Delete the `search_users_for_row` method entirely
- Remove the URL pattern `f"{viewname}/<int:row_id>/search-users"` from `get_url_patterns()` at line 1002-1004

#### C1.2 Remove `search_users_for_row` tests [djangoapp/tests/test_views.py:1019-1102]
- Delete the `SearchUsersForRowTests` test class (lines 1019-1102)

#### C1.3 Remove `is_visible` from frontend - RichTextEditor [frontend/src/components/RichTextEditor.vue]
- Change the `source` function to call `_search-users` endpoint (no row context needed): `GET /tables/_search-users?q={searchTerm}`
- Remove `viewname` and `rowId` props from `RichTextEditor` (no longer needed for mention source)
- Remove `is_visible` from the response mapping
- Remove the `renderItem` logic that shows "invisible" badge
- Keep `enableMentions` prop but make it default true ()

#### C1.4 Remove `is_visible` from frontend - CommentForm [frontend/src/components/CommentForm.vue]
- Remove `viewname` and `rowId` props (no longer needed for mention passthrough)
- Remove `enable-mentions`, `viewname`, `row-id` bindings from `RichTextEditor`
- Remove placeholder ()

#### C1.5 Remove `is_visible` from frontend - RowUpdateComment [frontend/src/components/RowUpdateComment.vue]
- Remove `viewname` and `rowId` props
- Remove `enable-mentions`, `viewname`, `row-id` bindings from `RichTextEditor` in edit mode

#### C1.6 Remove `is_visible` from frontend - RowUpdateList [frontend/src/components/RowUpdateList.vue]
- Remove `viewname` and `rowId` props
- Remove `viewname` and `row-id` bindings from `RowUpdateComment`

#### C1.7 Remove `is_visible` from frontend - RowDetails [frontend/src/pages/RowDetails.vue]
- Check if `viewname`/`rowId` are passed to `CommentForm` or `RowUpdateList` - remove if only used for mentions

#### C1.8 Remove invisible badge CSS [frontend/src/main.css]
- Remove `.mention-invisible-badge` styles (no longer needed without `is_visible`)

### Phase C2: Backend - Rewrite `_MentionCleaner` with HTML/XML parser [djangoapp/utils.py:47]

#### C2.1 Rewrite `_MentionCleaner` class
- Replace the current regex/string-based `_MentionCleaner` with a proper HTML/XML parser implementation
- Keep the same behavior: preserve mention spans, strip BOM, unwrap plain spans
- Use `html.parser.HTMLParser` (already imported) or `xml.etree.ElementTree`
- Remove `data-denotation-char` from allowed attributes ( at test_utils.py:100)

#### C2.2 Update `ALLOWED_ATTRIBUTES` for span
- Remove `data-denotation-char` from allowed span attributes in both backend and frontend
- Keep: `class`, `data-id`, `data-value`

#### C2.3 Update tests [djangoapp/tests/test_utils.py]
- Remove `data-denotation-char` from test expectations
- Update `test_sanitize_html_preserves_mention_span` to not expect `data-denotation-char`

### Phase C3: Frontend - quill-mention explicit registration [frontend/src/components/RichTextEditor.vue]

#### C3.1 Replace autoregister with explicit registration
- Replace `import "quill-mention/autoregister"` with explicit `Quill.register()` call
- Import the mention module directly

#### C3.2 Make `enableMentions` default true, add prop comments
- Change `enableMentions?: boolean` to default `true`
- Add comments explaining each prop

#### C3.3 Create explicit type for renderList callback
- Define a named type/interface for the mention item and renderList callback
- Replace inline type annotations

#### C3.4 Remove response.ok check and catch block
- Remove `if (!response.ok)` check - let errors bubble up
- Remove `catch` block

#### C3.5 Document XSS safety in renderItem
- Add comment explaining why `renderItem` is XSS-safe (using DOM `createElement` and `textContent`-style escaping, not raw HTML with user input)

### Phase C4: Frontend - Remove placeholder from CommentForm [frontend/src/components/CommentForm.vue]

#### C4.1 Remove placeholder prop passthrough
- Remove `placeholder` attribute from `RichTextEditor` usage

### Phase C5: Update Playwright tests [djangoapp/tests/test_playwright.py]

#### C5.1 Remove/update invisible warning test
- Remove `test_invisible_warning_shows_for_non_visible_users` (no longer relevant)
- Update other tests to use `_search-users` endpoint instead of row-specific one

### Phase C6: Prop cleanup - remove viewname/rowId passthrough

#### C6.1 Trace and remove viewname/rowId from all intermediate components
- `RowDetails.vue` -> `CommentForm.vue` -> `RichTextEditor.vue`
- `RowDetails.vue` -> `RowUpdateList.vue` -> `RowUpdateComment.vue` -> `RichTextEditor.vue`
- Remove these props if they are only used for mention source URL construction

---

## Checklist - Corrections

### Backend - Remove search_users_for_row
- [x] Delete `search_users_for_row` method from `BaseView` in [djangoapp/views.py]
- [x] Remove URL pattern `{viewname}/<int:row_id>/search-users` from `get_url_patterns()` in [djangoapp/views.py]
- [x] Delete `SearchUsersForRowTests` class in [djangoapp/tests/test_views.py]
    - [x] `test_search_users_for_row_returns_users_with_visibility`
    - [x] `test_search_users_for_row_returns_404_when_row_not_found`
    - [x] `test_search_users_for_row_respects_q_filter`
    - [x] `test_search_users_for_row_returns_at_most_10_results`
    - [x] `test_search_users_for_row_is_visible_false_when_resolve_rows_excludes`

### Backend - Rewrite _MentionCleaner with HTML/XML parser
- [x] Rewrite `_MentionCleaner` in [djangoapp/utils.py] using ElementTree XML parser (no regex/string manipulation)
- [x] Remove `data-denotation-char` from `_MENTION_ATTRS` and `ALLOWED_ATTRIBUTES` in [djangoapp/utils.py]
    - [x] Update test `test_sanitize_html_preserves_mention_span` in [djangoapp/tests/test_utils.py]

### Frontend - RichTextEditor corrections [frontend/src/components/RichTextEditor.vue]
- [x] Replace `import "quill-mention/autoregister"` with explicit `Quill.register()` call
- [x] Make `enableMentions` default to `true`
- [x] Add comments explaining each prop
- [x] Create explicit type for mention item and renderList callback (`MentionItem`, `MentionModuleOptions`)
- [x] Change `source` to call `_search-users` endpoint instead of row-specific endpoint
- [x] Remove `viewname` and `rowId` props
- [x] Remove `is_visible` from response mapping
- [x] Remove invisible badge logic from `renderItem`
- [x] Remove `response.ok` check and `catch` block
- [x] Add XSS safety comment in `renderItem`

### Frontend - CommentForm cleanup [frontend/src/components/CommentForm.vue]
- [x] `viewname` and `rowId` props retained — used by CommentForm's own API call for comment submission, not just mentions
- [x] Remove `enable-mentions`, `viewname`, `row-id` bindings from `RichTextEditor`
- [x] Remove `placeholder` from `RichTextEditor` usage

### Frontend - RowUpdateComment cleanup [frontend/src/components/RowUpdateComment.vue]
- [x] Remove `viewname` and `rowId` props
- [x] Remove `enable-mentions`, `viewname`, `row-id` bindings from `RichTextEditor`

### Frontend - RowUpdateList cleanup [frontend/src/components/RowUpdateList.vue]
- [x] Remove `viewname` and `rowId` props
- [x] Remove `viewname` and `row-id` bindings from `RowUpdateComment`

### Frontend - RowDetails cleanup [frontend/src/pages/RowDetails.vue]
- [x] `viewname`/`rowId` passed to `CommentForm` — needed for comment submission API, not just mentions
- [x] Remove `viewname`/`rowId` passthrough to `RowUpdateList`

### Frontend - CSS cleanup [frontend/src/main.css]
- [x] Remove `.mention-invisible-badge` styles (no longer needed)

### Frontend - HTML sanitization [frontend/src/utils/html.ts]
- [x] Remove `data-denotation-char` from `ALLOWED_ATTR`

### Playwright tests [djangoapp/tests/test_playwright.py]
- [x] Remove `test_invisible_warning_shows_for_non_visible_users` (no longer relevant)
- [x] Verify other mention tests still pass with `_search-users` endpoint

---

##  items

| # | File | Line | Comment |
|---|------|------|---------|
| 1 | `frontend/src/components/RichTextEditor.vue` | 36 | Explain `isInternalChange` var and `setHTML` workflow in comments |
| 2 | `frontend/src/components/RichTextEditor.vue` | 77 | Mentions are enabled at all times, dont make a prop for it |
| 3 | `frontend/src/components/RichTextEditor.vue` | 83 | Use axios since endpoint uses sessions, use query param instead of string manipulation |
| 4 | `frontend/src/components/RichTextEditor.vue` | 88 | Make a zod type and parse, we have it elsewhere in codebase |
| 5 | `frontend/src/components/RichTextEditor.vue` | 113 | Did you destroy quill instance? |
| 6 | `frontend/src/components/FieldDisplay.vue` | 52 | If this component allows null/undefined, pass it as-is; if `rich-text-display` is used in all cases, dont make it a prop |
| 7 | `djangoapp/utils.py` | 42 | Explain `_BOM` constant |
| 8 | `djangoapp/utils.py` | 234 | No more `_clean_mention_spans`, clean BOM characters in this function only |
| 9 | `frontend/src/pages/RowDetails.vue` | 176 | Move `CommentForm` and its logic to `RowUpdateList` |
| 10 | `frontend/src/components/RowUpdateList.vue` | 69 | Make `formatValue` exhaustive, seeing mistakes like `char_choice_field [object Object]` and `ref_fk [object Object]` |
| 11 | `frontend/src/components/RowUpdateList.vue` | 188 | Explain what `v-else` means in this context |
| 12 | `frontend/src/components/FieldInput.vue` | 20 | Are we using `rowId`? |
| 13 | `frontend/src/components/FieldInput.vue` | 84 | Enable mentions always. No placeholder, no rowId, no viewname |
| 14 | `djangoapp/tests/test_playwright.py` | 526 | Class should be defined `quill-editor` instead of `ql-editor` — change in component template, CSS, and test selectors |
| 15 | `djangoapp/tests/test_playwright.py` | 3645 | Dont use `ProxyUser`, use `User` instead |
| 16 | `djangoapp/tests/test_playwright.py` | 3685 | Dont just count mentions, be more specific about tag and content |
| 17 | `djangoapp/tests/test_utils.py` | 13 | Make a single test for legal tags, try to make test and returned strings multiline strings |
| 18 | `djangoapp/tests/test_utils.py` | 75 | Have single test for illegal tags, try to make test and returned strings multiline strings |
| 19 | `djangoapp/views.py` | 458 | Just make `_viewname` a local var in whichever method is using it |
| 20 | `frontend/src/utils/html.ts` | 38 | Associate allowed attrs with matching tags |

---

## Detailed Plan -  Items

### Phase A1: RichTextEditor cleanup [frontend/src/components/RichTextEditor.vue]

#### A1.1 Add comments explaining `isInternalChange` and `setHTML` workflow
- Add a block comment above `isInternalChange` explaining:
  - `isInternalChange` is a guard flag to prevent re-emit of `update:modelValue` when we programmatically set HTML
  - `setHTML` sets innerHTML directly and uses this flag so the `text-change` handler ignores the programmatic change
  - Without this guard, setting `modelValue` from parent would cause an infinite loop (parent sets → editor fires text-change → emits back to parent → repeat)

#### A1.2 Remove `enableMentions` prop, always enable mentions
- Remove `enableMentions` prop from `Props` interface
- Remove the `if (props.enableMentions)` conditional — always include the mention module config
- Update `CommentForm.vue` and `FieldInput.vue` to remove `:enable-mentions` bindings

#### A1.3 Replace `fetch` with `axios`, use query param
- Replace `fetch` call with axios (already used in the project)
- Ensure session cookies are sent (axios defaults to sending credentials)
- Keep `encodeURIComponent` for the query param

#### A1.4 Add zod schema for search-users response
- Define a zod schema for the `_search-users` response: `z.array(z.object({ id: z.number(), text: z.string() }))`
- Parse the response with the schema before mapping

#### A1.5 Destroy quill instance on unmount
- Check if Quill provides a `destroy()` or equivalent cleanup method
- If so, call it in `onUnmounted`
- At minimum, ensure event listeners are removed (currently done via `.off`)

### Phase A2: FieldDisplay null/undefined handling [frontend/src/components/FieldDisplay.vue]

#### A2.1 Decide on null handling for text field in FieldDisplay
- If `FieldDisplay` allows null/undefined values, pass them as-is to `RenderRawHtml`
- If `rich-text-display` is always used, remove the prop and handle null internally
- Currently wraps with `String(value ?? '')` — decide if this is the right approach or if raw null should flow through

### Phase A3: Backend utils cleanup [djangoapp/utils.py]

#### A3.1 Add comment explaining `_BOM` constant
- Add a comment explaining that `\ufeff` is the BOM (Byte Order Mark) character
- Quill inserts BOM characters for cursor positioning — these must be stripped from stored HTML

#### A3.2 Inline BOM cleaning into `sanitize_html`, remove `_clean_mention_spans`
- Move the BOM stripping logic directly into `sanitize_html`
- Remove the separate `_clean_mention_spans` function if its only remaining job is BOM stripping
- Keep mention span cleaning if it does more than BOM removal

### Phase A4: Move CommentForm into RowUpdateList [frontend/src/pages/RowDetails.vue]

#### A4.1 Move CommentForm and its logic to RowUpdateList
- Move the `<CommentForm>` component from `RowDetails.vue` into `RowUpdateList.vue`
- Move associated state/logic (e.g., `refreshRowUpdates`, `canCreateComment`) accordingly
- Pass necessary props (`viewname`, `rowId`) through `RowUpdateList`

### Phase A5: Make formatValue exhaustive [frontend/src/components/RowUpdateList.vue]

#### A5.1 Handle all `ColumnValue` types in `formatValue`
- Current issues: `char_choice_field` shows `[object Object]`, `ref_fk` shows `[object Object]`
- Add proper handling for choice fields (extract `value`/`label`) and FK fields (extract display text)
- Make the switch exhaustive over all field discriminators

#### A5.2 Add comment explaining v-else context
- Add a comment at line 188 explaining what `v-else` captures (the fallback case for row updates that have both old and new values)

### Phase A6: FieldInput mention and prop cleanup [frontend/src/components/FieldInput.vue]

#### A6.1 Check if `rowId` is used, remove if not
- `rowId` is in the `Props` interface — check all usages
- If only used for conditional mention enabling, remove it

#### A6.2 Enable mentions always, remove placeholder/viewname/rowId from RichTextEditor
- Remove `:placeholder` binding
- Remove `:enable-mentions` binding (always enabled after A1.2)
- Remove `:viewname` and `:row-id` bindings
- Remove `viewname` and `rowId` from FieldInput props if no longer needed

### Phase A7: Playwright test improvements [djangoapp/tests/test_playwright.py]

#### A7.1 Define `quill-editor` class on the editor wrapper, update CSS and tests
- In `RichTextEditor.vue`, the `<div ref="editorRef" class="rich-text-editor">` becomes the Quill root — add `quill-editor` class to it (or to the wrapper)
- Quill's snow theme adds `.ql-editor` to the inner div automatically — the  asks to use a custom `quill-editor` class instead
- Update any CSS in `main.css` that targets `.ql-editor` to target `.quill-editor` (or the wrapper class)
- Update Playwright test selectors from `.ql-editor` to `.quill-editor`

#### A7.2 Use `User` instead of `ProxyUser` in mention tests
- Replace `ProxyUser.objects.create(...)` with `User.objects.create(...)` at line 3646

#### A7.3 Be more specific about mention assertions
- Instead of just `mention.count() > 0`, assert on the specific tag and content
- e.g., check `data-id` attribute value and inner text content

### Phase A8: TestUtils consolidation [djangoapp/tests/test_utils.py]

#### A8.1 Consolidate legal tag tests into a single test
- Combine `test_sanitize_html_basic_text`, `test_sanitize_html_bold_italic`, `test_sanitize_html_headings`, `test_sanitize_html_lists`, `test_sanitize_html_links`, `test_sanitize_html_tables`, `test_sanitize_html_hr_br` into one test
- Use multiline strings for input and expected output

#### A8.2 Consolidate illegal tag tests into a single test
- Combine `test_sanitize_html_removes_script`, `test_sanitize_html_removes_onclick`, `test_sanitize_html_removes_style`, `test_sanitize_html_removes_iframe` into one test
- Use multiline strings for input and expected output

### Phase A9: BaseView `_viewname` to local var [djangoapp/views.py]

#### A9.1 Convert `self._viewname` instance variable to local variable
- Find all methods that reference `self._viewname`
- Replace with a local variable `viewname = self.get_viewname_class()` in each method
- Remove `self._viewname` from `__init__`

### Phase A10: Frontend HTML sanitization — associate attrs with tags [frontend/src/utils/html.ts]

#### A10.1 Associate allowed attributes with their parent tags
- Currently `ALLOWED_ATTR` is a flat list — `href` should only be on `<a>`, mention attrs only on `<span>`
- Restructure to tag-specific attribute map similar to backend's `ALLOWED_ATTRIBUTES` dict
- e.g., `{ "a": ["href"], "span": ["class", "data-id", "data-value"] }`

---

## Checklist -  Items

### RichTextEditor cleanup [frontend/src/components/RichTextEditor.vue]
- [x] Add comments explaining `isInternalChange` var and `setHTML` workflow
- [x] Remove `enableMentions` prop, always enable mentions
    - [x] Remove from `RichTextEditor.vue` props
    - [x] Remove `:enable-mentions` from `CommentForm.vue`
    - [x] Remove `:enable-mentions` from `FieldInput.vue`
- [x] Replace `fetch` with `axios` for `_search-users` endpoint
- [x] Add zod schema for `_search-users` response and parse
- [x] Ensure quill instance is properly destroyed on unmount

### FieldDisplay null/undefined handling [frontend/src/components/FieldDisplay.vue]
- [x] Decide and document null/undefined handling for text field in `FieldDisplay`

### Backend utils cleanup [djangoapp/utils.py]
- [x] Add comment explaining `_BOM` constant
- [x] Inline BOM cleaning into `sanitize_html`, remove `_clean_mention_spans` if possible

### Move CommentForm to RowUpdateList [frontend/src/pages/RowDetails.vue]
- [x] Move `<CommentForm>` and its logic from `RowDetails.vue` into `RowUpdateList.vue`
    - [x] Move associated state (`canCreateComment`, refresh logic)
    - [x] Pass `viewname` and `rowId` through `RowUpdateList`

### RowUpdateList formatValue [frontend/src/components/RowUpdateList.vue]
- [x] Make `formatValue` exhaustive over all `ColumnValue` types
    - [x] Fix `char_choice_field` showing `[object Object]`
    - [x] Fix `ref_fk` showing `[object Object]`
- [x] Add comment explaining `v-else` context at line 188

### FieldInput mention/prop cleanup [frontend/src/components/FieldInput.vue]
- [x] Check if `rowId` is used, remove if not
- [x] Enable mentions always, remove `placeholder`, `rowId`, `viewname` from `RichTextEditor` usage
- [x] Remove `viewname` and `rowId` from FieldInput props if no longer needed

### Quill editor class rename [RichTextEditor.vue, main.css, test_playwright.py]
- [x] Define `quill-editor` class on the editor element in `RichTextEditor.vue`
- [x] Update CSS in `main.css` to target `.quill-editor` instead of `.ql-editor`
- [x] Update Playwright test selectors from `.ql-editor` to `.quill-editor`

### Playwright test improvements [djangoapp/tests/test_playwright.py]
- [x] Use `User` instead of `ProxyUser` in mention tests
- [x] Be more specific about mention assertions (tag, `data-id`, content)

### TestUtils consolidation [djangoapp/tests/test_utils.py]
- [x] Consolidate legal tag tests into single test with multiline strings
- [x] Consolidate illegal tag tests into single test with multiline strings

### BaseView `_viewname` to local var [djangoapp/views.py]
- [x] Convert `self._viewname` to local variable in each method that uses it
- [x] Remove from `__init__`

### Frontend HTML sanitization attr-tag association [frontend/src/utils/html.ts]
- [x] Restructure `ALLOWED_ATTR` to tag-specific attribute map

---

##  items (batch 2)

| # | File | Line | Comment |
|---|------|------|---------|
| 21 | `frontend/src/utils/html.ts` | 35 | Use this library instead. It has allowedAttributes https://github.com/apostrophecms/apostrophe/tree/main/packages/sanitize-html#readme |
| 22 | `frontend/src/pages/RowDetails.vue` | 184 | These 3 methods and fetchRowUpdates should be in RowUpdateList component. Encapsulate the updates part to that component |
| 23 | `djangoapp/utils.py` | 233 | Just return sanitized, update the tests accordingly |
| 24 | `djangoapp/tests/test_utils.py` | 74 | Combine into one assert |
| 25 | `frontend/src/components/FieldInput.vue` | 82 | Enable mentions always. No placeholder, now rowId, no viewname (stale — already done, remove comment) |

### Detailed Plan -  Items (batch 2)

#### A11: Replace DOMPurify with sanitize-html [frontend/src/utils/html.ts]
- Replace `dompurify` with `sanitize-html` (apostrophecms/sanitize-html)
- `sanitize-html` has `allowedAttributes` as a tag-specific map natively
- Remove the DOMPurify hook workaround

#### A12: Move remaining RowDetails logic to RowUpdateList [frontend/src/pages/RowDetails.vue]
- Move `handleDeleteComment`, `handleEditComment`, `refreshRowUpdates`, `fetchRowUpdates` to `RowUpdateList`
- Pass `viewname`, `rowId` through props
- RowDetails only needs `deleteRow`

#### A13: Remove `_clean_mention_spans` from `sanitize_html` [djangoapp/utils.py]
- Remove the `_clean_mention_spans` call from `sanitize_html`
- Just return `sanitized` directly after BOM stripping
- Update tests accordingly (plain spans will now be kept, not unwrapped)

#### A14: Combine mention span assert into one [djangoapp/tests/test_utils.py]
- Combine the multiple `assertIn` calls into a single `assertEqual`

#### A15: Remove stale  comment [frontend/src/components/FieldInput.vue]
- Remove the  comment at line 82 since mentions are already always enabled

---

### Checklist -  Items (batch 2)

### Replace DOMPurify with sanitize-html [frontend/src/utils/html.ts]
- [x] Install `sanitize-html` package
- [x] Replace DOMPurify with sanitize-html, use `allowedAttributes` tag-specific map
- [x] Remove DOMPurify hook
- [x] Update type declarations if needed

### Move remaining RowDetails logic to RowUpdateList [frontend/src/pages/RowDetails.vue]
- [x] Move `handleDeleteComment` to `RowUpdateList`
- [x] Move `handleEditComment` to `RowUpdateList`
- [x] Move `fetchRowUpdates` and `refreshRowUpdates` to `RowUpdateList`
- [x] Pass `viewname`, `rowId` through `RowUpdateList` props
- [x] RowDetails only keeps `deleteRow`

### Remove `_clean_mention_spans` from `sanitize_html` [djangoapp/utils.py]
- [x] Remove `_clean_mention_spans` call, just return sanitized
- [x] Update tests for new behavior (plain spans preserved)

### Combine mention span assert [djangoapp/tests/test_utils.py]
- [x] Combine `assertIn` calls into single `assertEqual`

### Remove stale  comment [frontend/src/components/FieldInput.vue]
- [x] Remove comment at line 82

# Remove mentions

Remove mentions feature from the codebase. No more packages. Modify components.

`_search_users` endpoint is retained — it is used by `RowUpdateFilter.vue` for filtering, not just mentions.

---

## Detailed Plan - Remove Mentions

### Phase R1: Frontend - Remove quill-mention from RichTextEditor [frontend/src/components/RichTextEditor.vue]

#### R1.1 Remove quill-mention imports
- Remove `import "quill-mention/autoregister"`
- Remove `import "quill-mention/dist/quill.mention.css"`

#### R1.2 Remove mention-related types and schema
- Remove `SearchUsersResponseSchema` zod schema
- Remove `MentionItem` interface
- Remove `RenderMentionList` type
- Remove `axios` import if only used for `_search-users` (check other usages)

#### R1.3 Remove mention module from Quill config
- Remove the `mentionModule` object entirely
- Remove `mention: mentionModule` from `modules` config
- Quill modules should only have toolbar: `{ ...toolbarOptions }`

### Phase R2: Frontend - Uninstall quill-mention package

#### R2.1 Remove from package.json
- Run `npm uninstall quill-mention` in frontend directory
- Check for `@types/quill-mention` or any type declaration files related to quill-mention and remove

### Phase R3: Frontend - Remove mention CSS [frontend/src/main.css]

#### R3.1 Remove all mention styles
- Remove `.rich-text-display .mention` block
- Remove `.quill-editor .mention` block
- Remove `.mention-item` block
- Remove `.mention-name` block

### Phase R4: Backend - Remove span from sanitization [djangoapp/utils.py]

#### R4.1 Remove span from ALLOWED_TAGS
- Remove `"span"` from `ALLOWED_TAGS` set
- Remove `"span"` entry from `ALLOWED_ATTRIBUTES` dict
- Span tags only existed to support mention markup; with mentions gone, no need for spans

### Phase R5: Frontend - Remove span from sanitization [frontend/src/utils/html.ts]

#### R5.1 Remove span from ALLOWED_TAGS
- Remove `"span"` from `ALLOWED_TAGS` array
- Remove `span` entry from `ALLOWED_ATTRIBUTES` dict

### Phase R6: Backend - Update tests [djangoapp/tests/test_utils.py]

#### R6.1 Remove span/mention tests
- Remove `test_span_without_attrs_kept` — span is no longer an allowed tag
- Remove `test_mention_span_preserved` — mention spans no longer preserved
- Remove `test_malicious_span_attributes_stripped` — no longer relevant
- Remove `test_span_style_attribute_removed` — no longer relevant
- Add a test verifying span tags are stripped (since span is no longer allowed)

### Phase R7: Backend - Update Playwright tests [djangoapp/tests/test_playwright.py]

#### R7.1 Remove MentionPlaywrightTests class
- Delete entire `MentionPlaywrightTests` class (lines 3633-3727)
  - `test_mention_dropdown_appears_on_at_key`
  - `test_selecting_user_inserts_mention_span`
  - `test_mention_spans_rendered_in_comment_display`

### Phase R8: Frontend - Remove axios import if unused

#### R8.1 Check if axios is still needed in RichTextEditor
- If axios was only imported for the `_search-users` mention call, remove the import
- Check other components for axios usage — likely used elsewhere

---

## Checklist - Remove Mentions

### Frontend - RichTextEditor [frontend/src/components/RichTextEditor.vue]
- [x] Remove `import "quill-mention/autoregister"`
- [x] Remove `import "quill-mention/dist/quill.mention.css"`
- [x] Remove `SearchUsersResponseSchema` zod schema
- [x] Remove `MentionItem` interface and `RenderMentionList` type
- [x] Remove `axios` import (check if used elsewhere in this file)
- [x] Remove `mentionModule` object and `mention: mentionModule` from Quill config

### Frontend - Package cleanup [frontend/]
- [x] Run `npm uninstall quill-mention`
- [x] Remove any quill-mention type declaration files

### Frontend - CSS [frontend/src/main.css]
- [x] Remove `.rich-text-display .mention` styles
- [x] Remove `.quill-editor .mention` styles
- [x] Remove `.mention-item` styles
- [x] Remove `.mention-name` styles

### Backend - Sanitization [djangoapp/utils.py]
- [x] Remove `"span"` from `ALLOWED_TAGS`
- [x] Remove `"span"` entry from `ALLOWED_ATTRIBUTES`

### Frontend - Sanitization [frontend/src/utils/html.ts]
- [x] Remove `"span"` from `ALLOWED_TAGS`
- [x] Remove `span` entry from `ALLOWED_ATTRIBUTES`

### Backend - Test updates [djangoapp/tests/test_utils.py]
- [x] Remove `test_span_without_attrs_kept`
- [x] Remove `test_mention_span_preserved`
- [x] Remove `test_malicious_span_attributes_stripped`
- [x] Remove `test_span_style_attribute_removed`
- [x] Add test verifying `<span>` tags are stripped

### Backend - Test updates [djangoapp/tests/test_views.py]
- [x] Update expected output for mixed HTML test (span stripped to plain text)

### Backend - Playwright test removal [djangoapp/tests/test_playwright.py]
- [x] Remove `MentionPlaywrightTests` class entirely

### Verification
- [x] `./run checkall` passes

# Notifications

Have a `notify_users(self, context: NotifyContext) -> Sequence[User]` method for BaseBaseModel. Run this after persisting the changes. NotifyContext is a union of

- `CreateRowNotifyContext` — `type = "create_row"`, `user: User` (the user who caused this action)
- `UpdateRowNotifyContext` — `type = "update_row"`, `user`
- `CreateCommentNotifyContext` — `type = "create_comment"`, `user`, `comment: RowUpdate`
- `UpdateCommentNotifyContext` — `type = "update_comment"`, `user`, `comment: RowUpdate`

Have a new model `RowUpdateUserNotification` with `RowUpdate` and `user`. Unique together on both.

Create `RowUpdateUserNotification` objects for each user returned from `notify_users`. Ensure it's an upsert — e.g. if N `RowUpdateUserNotification` were created when a comment was created, trying to create those same ones when the comment is updated should not fail.

Have a `/notifications` page that returns 100 row updates from `RowUpdateUserNotification` at a time. New response schema: `{viewname, pk, row update}`. The model stores `modelname`, we return `viewname` to user (use `TABLES_MODELS_TO_VIEWS` reverse lookup). Functionality like `{viewname}/row-updates/<int:row_id>` for display. Also returns viewnames and count of notifications (for sidebar/filter). Parameters: `viewname` (filtering) and `page` (pagination).

Checkbox before each notification. If checked, button to delete checked ones. Button to clear all / clear all `{viewname}` (depending on filter). API endpoints for those.

Write tests for models, views and Playwright. Playwright tests don't need to be exhaustive.

---

## Detailed Plan — Notifications

### Phase N1: Backend — NotifyContext dataclasses

#### N1.1 Define NotifyContext types in `djangoapp/models.py`
- Define `NotifyOperation = Literal["create_row", "update_row", "create_comment", "update_comment"]`
- `CreateRowNotifyContext` — `user: User`, `type: Literal["create_row"]`
- `UpdateRowNotifyContext` — `user: User`, `type: Literal["update_row"]`
- `CreateCommentNotifyContext` — `user: User`, `type: Literal["create_comment"]`, `comment: RowUpdate`
- `UpdateCommentNotifyContext` — `user: User`, `type: Literal["update_comment"]`, `comment: RowUpdate`
- `NotifyContext = CreateRowNotifyContext | UpdateRowNotifyContext | CreateCommentNotifyContext | UpdateCommentNotifyContext`

### Phase N2: Backend — `RowUpdateUserNotification` model

#### N2.1 Create `RowUpdateUserNotification` model in `djangoapp/models.py`
- Fields: `row_update: ForeignKey(RowUpdate)`, `user: ForeignKey(User, related_name="+")`
- `UniqueConstraint(fields=["row_update", "user"])`
- No `created_at` — sort by `id` descending instead
- No `related_name` on `row_update` to avoid cluttering RowUpdate — use queries from this side

#### N2.2 Create migration
- `./run python manage.py makemigrations`

### Phase N3: Backend — `notify_users` method on BaseBaseModel

#### N3.1 Add `notify_users` instance method to `BaseBaseModel`
- Signature: `def notify_users(self, context: NotifyContext) -> Sequence[User]`
- Default implementation: return empty list (no notifications)
- Override in subclasses to return relevant users

#### N3.2 Add `_create_notifications` private method to `BaseBaseModel`
- Takes `row_update: RowUpdate` and `context: NotifyContext`
- Calls `self.notify_users(context)` to get users
- **Filters out `context.user` (the actor) from the recipient list** — users never get notified about their own actions
- Upserts `RowUpdateUserNotification` objects using `bulk_create` with `ignore_conflicts=True`

#### N3.3 Wire notification calls into existing save paths
- In `save_stuff`: after `_create_row_update`, call `self._create_notifications(row_update, context)` where context is built from `SaveContext`
- In `create_comment`: after `row_update.save()`, call `self._create_notifications(row_update, CreateCommentNotifyContext(...))`
- In `edit_comment` path (views.py `update_comment`): after `row_update.edit_comment(...)`, call `self._create_notifications(row_update, UpdateCommentNotifyContext(...))`
- Note: `delete_comment` does NOT trigger notifications (soft delete only)

### Phase N4: Backend — Notification API endpoints

#### N4.1 Add notification list endpoint
- Module-level function in `views.py` (not on `BaseView` since it's cross-model)
- URL: `GET /tables/notifications`
- Params: `viewname` (optional filter), `page` (default 1)
- Returns:
  - `notifications`: list of `{viewname: str, row_pk: int, row_update: RowUpdateResponse}` (100 per page)
  - `viewname_counts`: `{viewname: int}` — count of unread notifications per viewname
  - `total_count`: int — total notifications for user
  - `current_page`, `total_pages`
- Logic:
  - Query `RowUpdateUserNotification` for `request.user`, ordered by `-id`
  - If `viewname` param: filter by `row_update__modelname` mapped from viewname via reverse of `TABLES_MODELS_TO_VIEWS`
  - Paginate (100 per page)
  - For each notification: resolve `row_update.modelname` → `viewname` using `TABLES_MODELS_TO_VIEWS`
  - Build `RowUpdateResponse` using existing redaction logic (call `row.rowupdates(user)` for just that one row update, or build inline)
  - Return paginated response

#### N4.2 Add delete notifications endpoint
- URL: `POST /tables/notifications/delete`
- Body: `{notification_ids: list[int]}`
- Deletes `RowUpdateUserNotification` objects matching IDs and owned by `request.user`
- Returns `{deleted_count: int}`

#### N4.3 Add clear all notifications endpoint
- URL: `POST /tables/notifications/clear`
- Body: `{viewname?: string}` (optional)
- If `viewname` provided: delete all notifications for user where `row_update.modelname` matches
- If no `viewname`: delete ALL notifications for user
- Returns `{deleted_count: int}`

#### N4.4 Register URLs in `add_views()`
- Add to module-level patterns alongside `_debug` and `_search-users`

#### N4.5 Create notification count middleware
- Create middleware class in `djangoapp/middleware.py` (or inline in views)
- Uses Inertia Django shared props (`inertia.share()`) to inject `notification_count`
- Only runs for authenticated users — skip count query for anonymous
- Query: `RowUpdateUserNotification.objects.filter(user=request.user).count()`
- Register middleware in `settings.py` `MIDDLEWARE` list

### Phase N5: Documentation — README

#### N5.1 Add Notifications section to `README.md`
- Document `notify_users` method: signature, default behavior (returns empty list), how to override
- Document `_create_notifications` behavior: calls `notify_users`, filters out the actor, upserts `RowUpdateUserNotification`
- Explicitly state: users are never notified about their own actions, even if `notify_users` returns a list containing them
- Example: notify row owner on update

```python
class TaskModel(BaseModel):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)

    def notify_users(self, context: NotifyContext) -> Sequence[User]:
        if context.type == "update_row":
            return [self.owner] if self.owner else []
        if context.type == "create_comment":
            return [self.owner] if self.owner else []
        return []
```

- Document `RowUpdateUserNotification` model and its purpose
- Document notification API endpoints

### Phase N6: Backend — Response schemas

#### N6.1 Add notification response schemas in `djangoapp/responses.py`
- `NotificationItem(viewname: str, row_pk: int, row_update: RowUpdateResponse)`
- `NotificationListResponse(notifications: list[NotificationItem], viewname_counts: dict[str, int], total_count: int, current_page: int, total_pages: int)`
- `DeleteNotificationsResponse(deleted_count: int)`

### Phase N7: Frontend — Notifications page

#### N7.1 Create `Notifications.vue` page
- Route: Inertia page rendered by backend (or client-side route visiting `/tables/notifications`)
- Layout with `Layout.vue` wrapper
- Sidebar/filter showing viewnames with counts (from `viewname_counts`)
- Main content: paginated list of notifications
- Each notification shows:
  - Viewname as link to `{viewname}/row-details/{row_pk}`
  - Row update content (reusing `RowUpdateList`/`RowUpdateComment` rendering)
  - Checkbox for selection
- Bottom: "Delete selected" button, "Clear all" button, "Clear all {viewname}" button (contextual)
- Pagination controls

#### N7.2 Add navigation link to Layout
- Add "Notifications" link in `Layout.vue` with badge showing `notification_count` from Inertia shared props

#### N7.3 Add notification count to Inertia shared props via middleware
- Create Django middleware that injects `notification_count` into Inertia shared props
- Only when user is authenticated (skip for anonymous)
- Query: `RowUpdateUserNotification.objects.filter(user=request.user).count()`
- Use `inertia.share()` or the Inertia Django shared data mechanism to pass `notification_count` to every page

### Phase N8: Frontend — CSS for notifications page

#### N8.1 Add styles to `frontend/src/main.css`
- Notification list item styles
- Checkbox + content layout
- Viewname filter sidebar
- Badge styles for notification count
- Selected state for checkboxes

### Phase N9: Tests

#### N9.1 Model tests in `djangoapp/tests/test_models.py`
- Test `RowUpdateUserNotification` unique constraint
- Test `notify_users` returns empty list by default
- Test `_create_notifications` creates RowUpdateUserNotification objects
- Test `_create_notifications` upsert (calling twice doesn't duplicate)
- Test `_create_notifications` called after `save_stuff` (create row)
- Test `_create_notifications` called after `save_stuff` (update row)
- Test `_create_notifications` called after `create_comment`
- Test `_create_notifications` called after `update_comment`
- Test override of `notify_users` in subclass returns correct users
- Test `_create_notifications` excludes the actor (context.user) from recipients even if `notify_users` returns them

#### N9.2 View tests in `djangoapp/tests/test_views.py`
- Test `GET /tables/notifications` returns notifications for logged-in user
- Test `GET /tables/notifications` returns 404 for anonymous
- Test `GET /tables/notifications?viewname=firststuff` filters by viewname
- Test `GET /tables/notifications` pagination (page 1, page 2)
- Test `GET /tables/notifications` returns `viewname_counts`
- Test `POST /tables/notifications/delete` deletes selected notifications
- Test `POST /tables/notifications/delete` only deletes user's own notifications
- Test `POST /tables/notifications/clear` deletes all notifications
- Test `POST /tables/notifications/clear` with viewname deletes only that viewname's notifications

#### N9.3 Playwright tests in `djangoapp/tests/test_playwright.py`
- Test notifications page shows notification after row creation
- Test clicking notification navigates to row details
- Test delete selected notifications works
- Test clear all notifications works
- Test clear all notifications for currently filtered viewname
- Test viewname filter works

---

## Checklist — Notifications

### Backend — NotifyContext types
- [x] Define `NotifyOperation` literal type in [djangoapp/models.py]
- [x] Define `CreateRowNotifyContext` dataclass
- [x] Define `UpdateRowNotifyContext` dataclass
- [x] Define `CreateCommentNotifyContext` dataclass
- [x] Define `UpdateCommentNotifyContext` dataclass
- [x] Define `NotifyContext` union type

### Backend — RowUpdateUserNotification model
- [x] Create `RowUpdateUserNotification` model in [djangoapp/models.py]
    - [x] `row_update` ForeignKey to `RowUpdate`
    - [x] `user` ForeignKey to `User`
    - [x] `UniqueConstraint(fields=["row_update", "user"])`
    - [x] No `created_at` — sort by `-id`
- [x] Create database migration

### Backend — notify_users method
- [x] Add `notify_users(self, context: NotifyContext) -> Sequence[User]` to `BaseBaseModel`
    - [x] Default returns empty list
- [x] Add `_create_notifications(self, row_update: RowUpdate, context: NotifyContext)` to `BaseBaseModel`
    - [x] Calls `notify_users` to get user list
    - [x] Filters out `context.user` (actor) — even if `notify_users` returns them, no self-notification
    - [x] Upserts `RowUpdateUserNotification` via `bulk_create(..., ignore_conflicts=True)`
- [x] Wire into `save_stuff` after `_create_row_update`
    - [x] Build `CreateRowNotifyContext` or `UpdateRowNotifyContext` based on `context.existing_row`
    - [x] Call `_create_notifications`
- [x] Wire into `create_comment` after `row_update.save()`
    - [x] Build `CreateCommentNotifyContext`
    - [x] Call `_create_notifications`
- [x] Wire into `update_comment` after `edit_comment`
    - [x] Build `UpdateCommentNotifyContext`
    - [x] Call `_create_notifications`

### Backend — Response schemas
- [x] Add `NotificationItem` schema in [djangoapp/responses.py]
- [x] Add `NotificationListResponse` schema in [djangoapp/responses.py]
- [x] Add `DeleteNotificationsResponse` schema in [djangoapp/responses.py]

### Documentation
- [x] Add Notifications section to [README.md]
    - [x] Document `notify_users` method with signature, default behavior, how to override
    - [x] Document actor exclusion rule — users never notified about own actions
    - [x] Example: notify row owner on update / comment
    - [x] Document `RowUpdateUserNotification` model
    - [x] Document notification API endpoints

### Backend — Notification API endpoints
- [x] Add `GET /tables/notifications` endpoint in [djangoapp/views.py]
    - [x] Param `viewname` for filtering
    - [x] Param `page` for pagination (100 per page)
    - [x] Returns `NotificationListResponse`
    - [x] Maps `modelname` → `viewname` using `TABLES_MODELS_TO_VIEWS` reverse lookup
    - [x] Applies redaction via `row.rowupdates(user)`
- [x] Add `POST /tables/notifications/delete` endpoint
    - [x] Takes `notification_ids` list
    - [x] Deletes only user's own notifications
- [x] Add `POST /tables/notifications/clear` endpoint
    - [x] Optional `viewname` param
    - [x] Clears all or filtered notifications for user
- [x] Register URLs in `add_views()` pattern list

### Frontend — Notifications page
- [x] Create `Notifications.vue` in [frontend/src/pages/]
    - [x] Viewname filter sidebar with counts
    - [x] Paginated notification list
    - [x] Each item: checkbox, viewname link, row update content
    - [x] "Delete selected" button
    - [x] "Clear all" / "Clear all {viewname}" button
    - [x] Pagination controls
- [x] Add "Notifications" link in [frontend/src/components/Layout.vue]
    - [x] Badge with `notification_count` from Inertia shared props
- [x] Create Django middleware to inject `notification_count` as Inertia shared prop
    - [x] Only when user is authenticated
    - [x] Query `RowUpdateUserNotification.objects.filter(user=request.user).count()`

### Frontend — Styles
- [x] Add notification page styles to [frontend/src/main.css]
    - [x] Notification list item layout
    - [x] Checkbox + content alignment
    - [x] Viewname filter sidebar
    - [x] Badge for count
    - [x] Selected state

### Tests — Model tests
- [x] `RowUpdateUserNotification` model tests in [djangoapp/tests/test_models.py]
    - [x] Test unique constraint on `(row_update, user)`
    - [x] Test `notify_users` returns empty list by default
    - [x] Test `_create_notifications` creates notification objects
    - [x] Test `_create_notifications` upsert (no duplicates on repeated calls)
    - [x] Test `_create_notifications` triggered after create row
    - [x] Test `_create_notifications` triggered after update row
    - [x] Test `_create_notifications` triggered after create comment
    - [x] Test `_create_notifications` triggered after update comment
    - [x] Test overriding `notify_users` returns correct users
    - [x] Test `_create_notifications` excludes actor from recipients even when `notify_users` includes them

### Tests — View tests
- [x] Notification API tests in [djangoapp/tests/test_views.py]
    - [x] Test `GET /tables/notifications` returns user's notifications
    - [x] Test `GET /tables/notifications` requires auth
    - [x] Test `GET /tables/notifications?viewname=firststuff` filters correctly
    - [x] Test pagination (page 1 returns first 100, page 2 returns next)
    - [x] Test `viewname_counts` returned correctly
    - [x] Test `POST /tables/notifications/delete` deletes selected
    - [x] Test `POST /tables/notifications/delete` ignores other users' notifications
    - [x] Test `POST /tables/notifications/clear` deletes all
    - [x] Test `POST /tables/notifications/clear` with viewname filters

### Tests — Playwright tests
- [x] Notification Playwright tests in [djangoapp/tests/test_playwright.py]
    - [x] Test notification appears after row creation
    - [x] Test clicking notification navigates to row details
    - [x] Test delete selected notifications
    - [x] Test clear all notifications
    - [x] Test clear all notifications for currently filtered viewname
    - [x] Test viewname filter on notifications page

### Final
- [x] `./run checkall` passes

# Notification type changes

RowUpdateUserNotification should have user, row, datetime, content (json). No row_update at all. Content should be RowUpdateResponse in serialized form.

We have method row.rowupdates. Have a row.row_update_response(user, row_update) which returns RowUpdateResponse object. Store that in RowUpdateUserNotification. DRY logic between row.rowupdates and row.row_update_response, since they call .redact_row_updates.

Notification page can render the RowUpdateResponse coming as response. We will have link to row.

Store new object when comment is edited.

## Checklist

### Model changes (`djangoapp/models.py`)
- [x] Extract `_build_row_update_response(row_update, user)` private helper from `rowupdates()` [djangoapp/models.py:882-947]
- [x] Add `row_update_response(user, row_update)` public method [djangoapp/models.py:949-950]
- [x] Refactor `rowupdates()` to use `_build_row_update_response` per row_update (DRY) [djangoapp/models.py:952-958]
- [x] Restructure `RowUpdateUserNotification`: remove `row_update` FK, add `modelname`, `row_pk`, `datetime`, `content` (JSONField) [djangoapp/models.py:1302-1312]
- [x] Update `_create_notifications()` to build serialized `RowUpdateResponse` and store in `content` [djangoapp/models.py:678-694]

### View changes (`djangoapp/views.py`)
- [x] `_notifications_list()`: read from `notification.content` and `notification.modelname` [djangoapp/views.py:99-153]
- [x] `_notifications_clear()`: filter by `modelname` instead of `row_update__modelname` [djangoapp/views.py:167-178]
- [x] Remove `_build_row_update_response_for_notification()` (logic moved to model)
- [x] Remove unused import `RowUpdateRedactContext`

### Response changes (`djangoapp/responses.py`)
- [x] `NotificationItem.row_update` type changed from `RowUpdateResponse` to `dict[str, Any]` [djangoapp/responses.py:43-47]

### Migration (`djangoapp/migrations/0019_...`)
- [x] Create `RowUpdateUserNotification` with new fields instead of old `row_update` FK

### Test changes
- [x] `test_models.py`: Update filter queries from `row_update=` to `modelname=`, `row_pk=` [djangoapp/tests/test_models.py:1485-1522, 1630-1638]
- [x] `test_models.py`: Add content assertions to `test_create_notifications_creates_notification_objects` [djangoapp/tests/test_models.py:1490-1493]
- [x] ~~Update `test_create_notifications_upsert_no_duplicates`~~ — removed entirely in "Changes after review" phase
- [x] `test_views.py`: Update `_create_notification()` helper to use new model fields [djangoapp/tests/test_views.py:1061-1079]
- [x] `test_views.py`: Update `test_update_comment_creates_notification` — expects 2 notifications (create + update) [djangoapp/tests/test_views.py:1016-1049]
- [x] `test_views.py`: Update `test_notifications_pagination` to use `row_update_response` [djangoapp/tests/test_views.py:1117-1139]
- [x] `test_playwright.py`: Update `_create_notification()` helper [djangoapp/tests/test_playwright.py:3647-3660]
- [x] `test_playwright.py`: Update `test_clear_all_for_filtered_viewname` [djangoapp/tests/test_playwright.py:3727-3769]

### Remaining fixes
- [x] Fix mypy: rename `response` → `row_update_resp` in
    - [x] `test_update_comment_creates_notification` [djangoapp/tests/test_views.py:1027]
    - [x] `test_notifications_pagination` [djangoapp/tests/test_views.py:1128]
- [x] Run `./run lintfix`
- [x] Run `./run typecheck` — verify 0 new errors
- [x] Run `./run test --keepdb` — verify all pass
- [x] Run `./run playwrighttest` — verify all pass
- [x] Run `./run checkall` — final validation (lintfix, typecheck, test 278 pass, frontend lint, frontend type-check all pass)

##  items

### Backend: move NotifyingFirstStuff to models.py [djangoapp/tests/test_models.py:1471]
The `NotifyingFirstStuff` proxy model with `notify_users` is defined inline in every test method of `RowUpdateUserNotificationTest`. Move it to `djangoapp/models.py` as a proper proxy model subclass of `FirstStuff`, defined after `FirstStuff`.

- [x] Create `NotifyingFirstStuff` proxy model in `djangoapp/models.py` after `FirstStuff` class
- [x] Replace all inline `NotifyingFirstStuff` class definitions in `RowUpdateUserNotificationTest` with imports from models
    - [x] `test_create_notifications_creates_notification_objects` [djangoapp/tests/test_models.py:1472-1478]
    - [x] `test_create_notifications_upsert_no_duplicates` [djangoapp/tests/test_models.py:1506-1512]
    - [x] `test_create_notifications_triggered_after_create_row` [djangoapp/tests/test_models.py:1528-1536]
    - [x] `test_create_notifications_triggered_after_update_row` [djangoapp/tests/test_models.py:1550-1558]
    - [x] `test_create_notifications_triggered_after_create_comment` [djangoapp/tests/test_models.py:1572-1580]
    - [x] `test_create_notifications_excludes_actor_from_recipients` [djangoapp/tests/test_models.py:1617-1623]
- [x] Run `./run checkall`

### Backend: assert notification content in RowUpdateUserNotificationTest [djangoapp/tests/test_models.py:1488]
Currently tests only check `notifications.count()`. Should fetch the notification object and assert the `content` JSON field contains expected values (action, id, created_by, etc.).

- [x] `test_create_notifications_creates_notification_objects` — already partially done (checks `content["id"]` and `content["action"]`) [djangoapp/tests/test_models.py:1489-1493]
- [x] `test_create_notifications_upsert_no_duplicates` — assert both notifications have valid content
- [x] `test_create_notifications_triggered_after_create_row` — assert `content["action"] == "created_row"`, `content["created_by"]` is not None
- [x] `test_create_notifications_triggered_after_update_row` — assert `content["action"] == "updated_row"`
- [x] `test_create_notifications_triggered_after_create_comment` — assert `content["action"] == "commented"`, `content["comment_content"]` is not None
- [x] `test_create_notifications_excludes_actor_from_recipients` — assert `content["created_by"]` exists
- [x] Run `./run checkall`

### Backend: add detailed docstring to `notify_users` [djangoapp/models.py:674]
`notify_users` currently has no docstring. Add one explaining what it does, what it returns, and how subclasses should override it.

- [x] Add docstring to `notify_users` method [djangoapp/models.py:674-676]
- [x] Run `./run checkall`

### Frontend: add Zod schema for row-updates API response [frontend/src/components/RowUpdateList.vue:50]
`response.data` from the row-updates endpoint is not validated with Zod. The response shape matches `RowUpdateListResponse` from `responses.py` (`can_create_comment`, `edit_comment_timeout`, `delete_comment_timeout`, `updates`). Create a Zod schema in `schemas.ts` and parse `response.data` with it.

- [x] Add `RowUpdateListResponseSchema` to `frontend/src/schemas.ts` with fields:
    - `can_create_comment: z.boolean()`
    - `edit_comment_timeout: z.number().nullable()`
    - `delete_comment_timeout: z.number().nullable()`
    - `updates: z.array(RowUpdateResponseSchema)`
- [x] Parse `response.data` with `RowUpdateListResponseSchema.parse()` in `fetchRowUpdates` [frontend/src/components/RowUpdateList.vue:50-51]
- [x] Run `cd frontend && npm run lint:fix && npm run type-check && npm run lint`
- [x] Run `./run checkall`

### Frontend: toast and re-raise in fetchRowUpdates catch [frontend/src/components/RowUpdateList.vue:59]
The `catch` block in `fetchRowUpdates` sets `hasError.value = true` but doesn't show a toast. Should show error toast and re-raise the error.

- [x] Add `Toast.fire({ icon: "error", title: "Failed to load row updates" })` before `hasError.value = true`
- [x] Add `throw error` (capture error from catch parameter) so callers can handle it
- [x] Run `cd frontend && npm run lint:fix && npm run type-check && npm run lint`
- [x] Run `./run checkall`

### Frontend: re-raise in handleDeleteComment catch [frontend/src/components/RowUpdateList.vue:86]
The `catch` block in `handleDeleteComment` shows a toast but swallows the error. Should re-raise it.

- [x] Capture error from catch parameter and re-raise after toast
- [x] Run `cd frontend && npm run lint:fix && npm run type-check && npm run lint`
- [x] Run `./run checkall`

## Render column values in notifications page + DRY

### Extract shared utilities
- [x] Create `frontend/src/utils/rowUpdate.ts` with `formatDateTime`, `getActionLabel`, `formatValue`, `isTextField`, `getTextValue`
- [x] Create `frontend/src/components/RowColumnValues.vue` component for column values table rendering

### Refactor RowUpdateList.vue
- [x] Replace local helpers with imports from `utils/rowUpdate.ts`
- [x] Replace inline column values template with `<RowColumnValues>` component
- [x] Remove unused imports (`RowColumnValueSchema`, `RenderRawHtml`)

### Update Notifications.vue — column values
- [x] Import `RowColumnValues` component and shared utilities
- [x] Remove local `formatDateTime` and `getActionLabel` duplicates
- [x] Add `<RowColumnValues>` to notification template for non-comment updates

### Merge notifications API into Inertia page
- [x] Move `_notifications_list` logic into `_notifications_page` as Inertia props
    - [x] `notifications`, `viewname_counts`, `total_count`, `current_page`, `total_pages`, `active_viewname` as props
- [x] Remove `_notifications_list` function from `views.py`
- [x] Remove `path("notifications", _notifications_list)` URL pattern
- [x] Guard against unauthenticated users with `get_authenticated_user_as_schema` + `Http404`

### Update Notifications.vue — Inertia props
- [x] Replace `axios.get("/tables/notifications")` fetch with Inertia props
- [x] Use `router.visit` for pagination and viewname filtering
- [x] Use `router.reload` after delete
- [x] Remove `isLoading` spinner (Inertia handles loading state)
- [x] Remove `onMounted` fetch call

### Update backend tests
- [x] Rename `test_notifications_list_*` to `test_notifications_page_*`
- [x] Change URL from `/tables/notifications` to `/tables/notifications/page`
- [x] Update assertions (Inertia HTML response, not JSON)

### Verification
- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test --keepdb --noinput` — 279 tests pass
- [x] `cd frontend && npm run lint:fix && npm run type-check && npm run lint` passes

# Changes after review

anon users have comment field. Dont show that.
/tables/notifications - do we need it? Can we use the page only?
Readme - briefly mention the notification features a user can use, no need of `Notification API Endpoints`
Reduce pagination to 50
Have a model method to update comment, similar to create comment.
In `def _create_notifications`, we need to do self.row_update_response for each recipient, since privacy is different for each recipient
Why do we have `v-bind="row_id ? { 'row-id': row_id } : {}"`
No need of `test_create_notifications_upsert_no_duplicates` or any other upsert test in that test case. No need of test_overriding_notify_users_returns_correct_users
In test_notification_appears_on_notifications_page, check content of row update, check link to row. Remove next test
Put the test_clear_all_notifications and the other clear method together
Add classes for each button in same playwright class so that you dont need to `has-text`
Have test for select all
Reduce pagination to 50

---

## Detailed Plan — Changes after review

### Phase R1: Hide comment form for anonymous users

`can_create_comment(None)` returns True because `row_update_access_timeout` doesn't check for None user. Fix it to return False when user is None.

#### R1.1 Update `can_create_comment` in `djangoapp/models.py`
- Add `if user is None: return False` at the top of `can_create_comment`

### Phase R2: Remove `/tables/notifications` JSON API

Already done in previous iteration — the `_notifications_list` endpoint was removed and merged into `_notifications_page`.

### Phase R3: Update README — simplify notification docs

#### R3.1 Remove `Notification API Endpoints` section from `README.md`
- Remove the "Notification API Endpoints" table (lines 491-507)
- Keep the brief description of user-facing notification features under the Notifications heading
- Mention the notifications page at `/tables/notifications/page`, sidebar filtering, select/delete, clear all

### Phase R4: Reduce pagination to 50

#### R4.1 Change `per_page` in `_notifications_page`
- Change `per_page = 100` to `per_page = 50` in `djangoapp/views.py` `_notifications_page`

### Phase R5: Model method for update_comment

Currently `update_comment` view does validation, calls `row_update.edit_comment(new_content)`, then calls `row._create_notifications(...)`. Create a model method `BaseBaseModel.update_comment(user, row_update, new_content)` that mirrors `create_comment`.

#### R5.1 Add `update_comment` method to `BaseBaseModel`
- Signature: `def update_comment(self, user: User, row_update: RowUpdate, new_content: str) -> RowUpdate`
- Logic: validate user can update (via `get_rowupdate_for_update`), call `row_update.edit_comment(new_content)`, call `self._create_notifications(row_update, UpdateCommentNotifyContext(...))`, return row_update
- Raises ValueError or similar if not allowed

#### R5.2 Update view to call model method
- Simplify `BaseView.update_comment` to call `row.update_comment(user, row_update, comment_content)`

### Phase R6: Per-recipient `row_update_response` in `_create_notifications`

Currently `_create_notifications` builds one response for all recipients. But privacy differs per recipient (e.g., redacted columns). Build a response per recipient.

#### R6.1 Update `_create_notifications` in `djangoapp/models.py`
- Loop over recipients and call `self.row_update_response(u, row_update)` for each
- Create one `RowUpdateUserNotification` per recipient with their specific response

### Phase R7: Remove `v-bind="row_id ? ..."` from RowForm

#### R7.1 Simplify RowForm FieldInput binding
- `FieldInput` no longer uses `rowId` — remove the conditional `v-bind`
- Just pass `:viewname="viewname"` directly

### Phase R8: Remove unnecessary notification tests

#### R8.1 Remove from `djangoapp/tests/test_models.py`
- Remove `test_create_notifications_upsert_no_duplicates`
- Remove `test_overriding_notify_users_returns_correct_users`

### Phase R9: Improve Playwright notification tests

#### R9.1 Enhance `test_notification_appears_on_notifications_page`
- Check content of the row update (action label, field values)
- Check link `href` points to correct row details URL
- Remove `test_clicking_notification_navigates_to_row_details` (merged into above)

#### R9.2 Add CSS classes to notification buttons
- Add `class="clear-all-btn"` to Clear all button in `Notifications.vue`
- Add `class="delete-selected-btn"` to Delete selected button
- Update Playwright selectors to use class instead of `:has-text`

#### R9.3 Add test for select all
- Add `test_select_all_notifications` that checks the select all checkbox toggles all items

#### R9.4 Combine clear tests
- Merge `test_clear_all_notifications` and `test_clear_all_for_filtered_viewname` into one test

---

## Checklist — Changes after review

### Hide comment form for anonymous users
- [x] Add `if user is None: return False` to `can_create_comment` in [djangoapp/models.py]

### Remove /tables/notifications JSON API
- [x] Already removed in previous iteration

### Update README
- [x] Remove `Notification API Endpoints` section from [README.md]
- [x] Keep brief user-facing description of notification features

### Reduce pagination
- [x] Change `per_page` from 100 to 50 in `_notifications_page` [djangoapp/views.py]

### Model method for update_comment
- [x] Add `update_comment(user, row_update, new_content)` to `BaseBaseModel` [djangoapp/models.py]
- [x] Simplify `BaseView.update_comment` to use model method [djangoapp/views.py]

### Per-recipient row_update_response in _create_notifications
- [x] Loop over recipients, call `row_update_response` for each [djangoapp/models.py]

### Remove v-bind conditional from RowForm
- [x] Replace `v-bind="row_id ? { 'row-id': row_id } : {}"` with direct props [frontend/src/components/RowForm.vue]

### Remove unnecessary tests
- [x] Remove `test_create_notifications_upsert_no_duplicates` [djangoapp/tests/test_models.py]
- [x] Remove `test_overriding_notify_users_returns_correct_users` [djangoapp/tests/test_models.py]

### Improve Playwright notification tests
- [x] Enhance `test_notification_appears_on_notifications_page` — check content and link [djangoapp/tests/test_playwright.py]
- [x] Remove `test_clicking_notification_navigates_to_row_details` [djangoapp/tests/test_playwright.py]
- [x] Add CSS classes to notification buttons (`clear-all-btn`, `delete-selected-btn`) [frontend/src/pages/Notifications.vue]
- [x] Update Playwright selectors to use class names instead of `:has-text`
- [x] Add `test_select_all_notifications` [djangoapp/tests/test_playwright.py]
- [x] Merge `test_clear_all_notifications` and `test_clear_all_for_filtered_viewname` into one test

### Verification
- [x] `./run lintfix` passes
- [x] `./run typecheck` — 0 errors
- [x] `./run test --keepdb --noinput` — 277 tests pass
- [x] `cd frontend && npm run lint:fix && npm run type-check && npm run lint` passes

---

## Code Review — 2026-04-16

### Issues Found

#### 1. Stale `` comments not removed

Three `` comments remain in the codebase even though the tasks they describe were completed:

| File | Line | Comment | Status |
|------|------|---------|--------|
| `djangoapp/models.py` | 674 | `#  have detailed docstring` | [x] Removed |
| `djangoapp/tests/test_models.py` | 1469 | `#  create these models in models...` | [x] Removed |
| `djangoapp/tests/test_models.py` | 1478 | `#  assert by fetching object and checking contnt...` | [x] Removed |

#### 2. Missing model test for update_comment notification

The notification checklist (N9.1, line 1047) marks as done:
- `[x] Test _create_notifications triggered after update comment`

But `test_create_notifications_triggered_after_update_comment` does NOT exist in `djangoapp/tests/test_models.py`. Only a view-level test `test_update_comment_creates_notification` exists in `test_views.py:1016`. The model tests cover create_row, update_row, and create_comment — but not update_comment.

Status: [x] Added `test_create_notifications_triggered_after_update_comment` to `RowUpdateUserNotificationTest`.

#### 3. Unchecked items in "Remaining fixes" section

Lines 1242-1243 under "Notification type changes > Remaining fixes" are unchecked:
- `[ ] Run ./run playwrighttest — verify all pass`
- `[ ] Run ./run checkall — final validation`

Status: Running `./run checkall` to verify.

#### 4. Contradictory checklist entry for upsert test

Line 1228 says:
```
- [x] Update test_create_notifications_upsert_no_duplicates — changed expected count to 2
```
But line 1466 says:
```
- [x] Remove test_create_notifications_upsert_no_duplicates
```
The test was removed entirely in a later phase, making the earlier entry misleading.

Status: [x] Updated line 1228 to note the test was later removed entirely.

#### 5. View-level update_comment test only checks count, not content

`test_update_comment_creates_notification` at `test_views.py:1016-1049` asserts `notifs.count() == 1` but does not assert the notification's `content` field (e.g., `action`, `comment_content`), unlike the model tests for other operations.

Status: [x] Added content assertions for `action` and `comment_content` to the test.