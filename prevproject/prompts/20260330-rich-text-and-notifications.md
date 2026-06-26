## Initial Requirements
Comment and text field inputs should be Quill editor and we should store inputs as html.

Use Nh3 at Python side to whitelist tags and attributes https://pypi.org/project/nh3/ . We need a ts/js library to strip html for list view.

### Allow the following tags and attributes
    <p>, <br>
    <strong>, <em>
    <h1> through <h6>
    <ul>, <ol>, <li>
    <a> with href attribute
    <hr>
    <table>, <thead>, <tbody>, <tr>, <th>, <td>

### For text field
- create - use Quill, validate html content
- list rows - show plaintext of the html content
- details - show rendered html
- update - use Quill, validate html content

### For row updates
- for created text field - show rendered html in one column
- for updated text field - show rendered html in two columns

For row updates as comments
- create - use Quill, validate html content
- read - show rendered html
- update - use Quill, validate html content

### Rendered html
Have a <div class="rich-text-input"> for all places. Have classes like `rich-text-input.p` for all tags supported. Ensure headings are small since its supposed to be in the middle of normal size text.

### Quill
Have a Vue component which takes model, read and emit. Render a Quill editor and support the above tags.

---

## Detailed Plan

### Phase 1: Backend - HTML Sanitization with Nh3

#### 1.1 Add nh3 dependency
- Add `nh3` to pyproject.toml dependencies

#### 1.2 Create HTML sanitizer utility
- Create `djangoapp/utils.py` with:
  - `ALLOWED_TAGS` set: `p`, `br`, `strong`, `em`, `h1`-`h6`, `ul`, `ol`, `li`, `a`, `hr`, `table`, `thead`, `tbody`, `tr`, `th`, `td`
  - `ALLOWED_ATTRIBUTES` dict: `{"a": {"href"}}`
  - `sanitize_html(html: str) -> str` function using `nh3.clean()`

#### 1.3 Update TextField deserializer
- Modify `TextFieldDeserializer` in [`djangoapp/serializers.py`](djangoapp/serializers.py:892) to:
  - Import and use `sanitize_html()` 
  - Sanitize incoming HTML content before returning

#### 1.4 Update comment content validation
- Modify comment creation/update in [`djangoapp/views.py`](djangoapp/views.py) to sanitize HTML content

---

### Phase 2: Frontend - Quill Editor Component

#### 2.1 Add Quill dependencies
- Add to [`frontend/package.json`](frontend/package.json):
  - `quill` - The Quill editor
  - `@types/quill` - TypeScript definitions (if available)

#### 2.2 Create RichTextEditor Vue component
- Create [`frontend/src/components/RichTextEditor.vue`](frontend/src/components/RichTextEditor.vue):
  - Props: `modelValue: string`, `placeholder?: string`, `maxLength?: number`
  - Emits: `update:modelValue`
  - Initialize Quill with custom toolbar supporting:
    - Bold, Italic
    - Headings (h1-h6)
    - Lists (bullet, ordered)
    - Link
    - Table support
  - Handle v-model binding
  - Handle max length validation

#### 2.3 Create HTML-to-plaintext utility
- Create [`frontend/src/utils/html.ts`](frontend/src/utils/html.ts):
  - `htmlToPlaintext(html: string): string` - Strip HTML tags for list view display

---

### Phase 3: Frontend - TextField Integration

#### 3.1 Update FieldInput component
- Modify [`frontend/src/components/FieldInput.vue`](frontend/src/components/FieldInput.vue:78) to:
  - Import `RichTextEditor`
  - Replace `<input>` for TextField discriminator with `RichTextEditor`
  - Handle text field differently from char field

#### 3.2 Update FieldDisplay component  
- Modify [`frontend/src/components/FieldDisplay.vue`](frontend/src/components/FieldDisplay.vue) to:
  - Add case for TextField discriminator
  - Render HTML inside `<div class="rich-text-input">`

#### 3.3 Update ListRows page for plaintext display
- Modify [`frontend/src/pages/ListRows.vue`](frontend/src/pages/ListRows.vue) to:
  - Import `htmlToPlaintext` utility
  - For text fields in table cells, display plaintext version

---

### Phase 4: Frontend - Comment System Integration

#### 4.1 Update CommentForm component
- Modify [`frontend/src/components/CommentForm.vue`](frontend/src/components/CommentForm.vue:66) to:
  - Replace `<textarea>` with `RichTextEditor`
  - Update character limit logic for HTML content

#### 4.2 Update RowUpdateComment component
- Modify [`frontend/src/components/RowUpdateComment.vue`](frontend/src/components/RowUpdateComment.vue:98) to:
  - Replace `<textarea>` in edit mode with `RichTextEditor`
  - Render comment content as HTML in `<div class="rich-text-input">`

---

### Phase 5: Frontend - Row Updates Display

#### 5.1 Update RowUpdateList component
- Modify [`frontend/src/components/RowUpdateList.vue`](frontend/src/components/RowUpdateList.vue:69) to:
  - Import `htmlToPlaintext` utility
  - Update `formatValue()` to handle text discriminator
  - For text values, render HTML inside `<div class="rich-text-input">`

#### 5.2 Handle text field column values
- For `created_row`: render HTML in single column
- For `updated_row`: render old and new HTML values in two columns

---

### Phase 6: CSS Styling

#### 6.1 Add rich-text-input styles
- Add to [`frontend/src/main.css`](frontend/src/main.css):
  - `.rich-text-input` base styles
  - `.rich-text-input p`, `.rich-text-input br`
  - `.rich-text-input strong`, `.rich-text-input em`
  - `.rich-text-input h1` through `.rich-text-input h6` (smaller than default)
  - `.rich-text-input ul`, `.rich-text-input ol`, `.rich-text-input li`
  - `.rich-text-input a` with link styles
  - `.rich-text-input hr`
  - `.rich-text-input table`, `.rich-text-input thead`, `.rich-text-input tbody`, `.rich-text-input tr`, `.rich-text-input th`, `.rich-text-input td`

---

### Phase 7: Testing

#### 7.1 Backend tests
- Test `sanitize_html()` with various inputs
- Test TextField deserializer with HTML content
- Test comment creation/update with HTML

#### 7.2 Frontend tests
- Test RichTextEditor component
- Test htmlToPlaintext utility
- Test TextField display in list/details/update views

---

## Checklist

### Backend
- [x] Added nh3 to dependencies in [pyproject.toml]
- [x] Created `sanitize_html()` in [djangoapp/utils.py]
- [x] Updated `TextFieldDeserializer` in [djangoapp/serializers.py:892]
- [x] Updated comment validation in [djangoapp/views.py]

### Frontend - Components
- [x] Added quill dependency in [frontend/package.json]
- [x] Created RichTextEditor component in [frontend/src/components/RichTextEditor.vue]
- [x] Created `htmlToPlaintext()` in [frontend/src/utils/html.ts]
- [x] Updated FieldInput for TextField in [frontend/src/components/FieldInput.vue:78]
- [x] Updated FieldDisplay for TextField in [frontend/src/components/FieldDisplay.vue]
- [x] Updated CommentForm with RichTextEditor in [frontend/src/components/CommentForm.vue:66]
- [x] Updated RowUpdateComment with RichTextEditor in [frontend/src/components/RowUpdateComment.vue:104]
- [x] Updated RowUpdateList for text values in [frontend/src/components/RowUpdateList.vue:69]
- [x] Updated ListRows for plaintext display in [frontend/src/pages/ListRows.vue]

### Frontend - Styling
- [x] Added `.rich-text-input` styles in [frontend/src/main.css]
- [x] Added heading styles h1-h6 with smaller sizes
- [x] Added table styles within rich-text-input

### Testing
- [x] Added tests for `sanitize_html()`
- [x] Added tests for TextField HTML handling
- [x] Added tests for comment HTML handling
- [x] Manually tested Quill editor in create/update forms
- [x] Manually tested HTML rendering in details page
- [x] Manually tested plaintext display in list page
- [x] Manually tested HTML rendering in row updates

### Missing Tests (Review Found)
- [x] Add test for TextField HTML sanitization in create operation
  - Test that unsafe HTML tags (script, style, iframe, etc.) are stripped
  - Test that safe HTML tags (p, strong, em, h1-h6, ul, ol, li, a, table, etc.) are preserved
  - Location: djangoapp/tests/test_views.py (merged into test_create_row_sanitizes_text_field_html)
- [x] Add test for TextField HTML sanitization in update operation
  - Test that unsafe HTML tags are stripped on update
  - Test that safe HTML tags are preserved on update
  - Location: djangoapp/tests/test_views.py (merged into test_update_row_sanitizes_text_field_html)
- [x] Add test for comment HTML sanitization in create operation
  - Test that unsafe HTML tags are stripped from comments
  - Test that safe HTML tags are preserved in comments
  - Location: djangoapp/tests/test_views.py (merged into test_create_comment_sanitizes_html)
- [x] Add test for comment HTML sanitization in update operation
  - Test that unsafe HTML tags are stripped when editing comments
  - Test that safe HTML tags are preserved when editing comments
  - Location: djangoapp/tests/test_views.py (merged into test_update_comment_sanitizes_html)

### Final
- [x] Ran `./run lintfix` successfully
- [x] Ran `./run typecheck` successfully
- [x] Ran `./run test` successfully
- [x] Ran `./run checkall` successfully

---

## Items

### Code Improvements
- [x] Add comment explaining why `isInternalChange` var is needed in [frontend/src/components/RichTextEditor.vue:17]
- [x] Add comment explaining why not use `getSemanticHTML` in [frontend/src/components/RichTextEditor.vue:33]
- [x] Rename `.rich-text-input` to `.rich-text-display` to better state its purpose in [frontend/src/main.css:1300]

### Test Improvements
- [x] Use `self.assert*` methods only (not plain asserts) in [djangoapp/tests/test_utils.py:7]
- [x] Assert with full expected string, not with multiple `x in y` asserts in [djangoapp/tests/test_utils.py:8]

### HTML Utils - RenderRawHtml Component
- [x] Create `RenderRawHtml.vue` component in [frontend/src/components/RenderRawHtml.vue] which takes classnames prop and runs input through a sanitizer function
- [x] Create `sanitizeHtml()` function in [frontend/src/utils/html.ts] which removes any attacks from HTML
- [x] Replace all usages of `v-html` in codebase to use `RenderRawHtml` component instead
- [x] Add HTML sanitization check in `htmlToPlaintext()` function in [frontend/src/utils/html.ts:11]
- [x] Add option to `htmlToPlaintext()` to render blocks or br as space instead of \n, with space as default
- [x] Clean up multiple consecutive spaces into single space in `htmlToPlaintext()` function in [frontend/src/utils/html.ts]


