## TdSchema refactoring

Encapsulate label, value, and bottom border inside Td components. Accept `raw_value` prop instead of pre-parsed `value`; let each component parse via zod internally. Remove discriminator/union pattern in favor of class-based `initialize()` on each schema. Replace `field_value_to_td` dispatch with extensible dict of functions.

---

## Checklist

### Backend — Rename TdSchema classes and remove discriminator [§BR-td-rename]

- [x] Rename `CharFieldTdSchema` → `CharFieldContent` in `responses.py` [§BR-td-char] [responses.py:408]
    - [x] Remove `discriminator` field from the class
- [x] Rename `TextFieldTdSchema` → `TextContent` [§BR-td-text] [responses.py:414]
    - [x] Remove `discriminator` field
- [x] Rename `ArticleContentTdSchema` → `ArticleContent` [§BR-td-article] [responses.py:420]
    - [x] Remove `discriminator` field
- [x] Rename `IntegerFieldTdSchema` → `IntegerFieldContent` [§BR-td-int] [responses.py:426]
    - [x] Remove `discriminator` field
- [x] Rename `BooleanFieldTdSchema` → `BooleanFieldContent` [§BR-td-bool] [responses.py:432]
    - [x] Remove `discriminator` field
- [x] Rename `DecimalFieldTdSchema` → `DecimalFieldContent` [§BR-td-dec] [responses.py:438]
    - [x] Remove `discriminator` field
- [x] Rename `DateTimeFieldTdSchema` → `DateTimeFieldContent` [§BR-td-dt] [responses.py:444]
    - [x] Remove `discriminator` field
- [x] Rename `FileFieldTdSchema` → `FileFieldContent` [§BR-td-file] [responses.py:456]
    - [x] Remove `discriminator` field
- [x] Rename `ForeignKeyFieldTdSchema` → `ForeignKeyFieldContent` [§BR-td-fk] [responses.py:462]
    - [x] Remove `discriminator` field
- [x] Remove `BaseTdSchema.discriminator` field — only `component` and `value` remain (renamed to `BaseContent`) [§BR-td-base] [responses.py:401-404]
- [x] Remove `TdSchema` union type — replaced with `ContentSchema` [§BR-td-union] [responses.py:468-478]
- [x] Update all imports and usages of renamed classes across codebase

### Backend — Add `.initialize(schema, raw_value)` classmethod to each Content class [§BR-td-init]

- [x] Add abstract `@classmethod initialize(cls, schema, raw_value) -> BaseContent` on `BaseContent` [§BR-td-init-method] [responses.py:401]
- [x] `CharFieldContent.initialize` — asserts `isinstance(raw_value, str)`, resolves choice label [§BR-td-init-char]
- [x] `TextContent.initialize` — asserts `isinstance(raw_value, str)` [§BR-td-init-text]
- [x] `ArticleContent.initialize` — asserts `isinstance(raw_value, str)` [§BR-td-init-article]
- [x] `IntegerFieldContent.initialize` — asserts `isinstance(raw_value, int)`, resolves choice label [§BR-td-init-int]
- [x] `BooleanFieldContent.initialize` — asserts `isinstance(raw_value, bool)` [§BR-td-init-bool]
- [x] `DecimalFieldContent.initialize` — asserts `isinstance(raw_value, str)` (serialized by API) [§BR-td-init-dec]
- [x] `DateTimeFieldContent.initialize` — asserts `isinstance(raw_value, str)` (serialized by API) [§BR-td-init-dt]
- [x] `FileFieldContent.initialize` — asserts `isinstance(raw_value, dict)` [§BR-td-init-file]
- [x] `ForeignKeyFieldContent.initialize` — asserts `isinstance(raw_value, dict)`, builds `ForeignKeyContentValue` [§BR-td-init-fk]

### Backend — Replace `field_value_to_td` with extensible dict [§BR-td-dict]

- [x] Replace `field_value_to_td` function with `CONTENT_MAP` dict + dispatch [§BR-td-dict-replace] [serializers.py:885-918]
    - [x] `CONTENT_MAP: dict[str, type[BaseContent]]` mapping `"char"` → `CharFieldContent`, etc.
    - [x] `field_value_to_td(schema, raw_value)` becomes: `cls = CONTENT_MAP[disc]; return cast(ContentSchema, cls.initialize(schema, raw_value))`
- [x] Remove `aihere` comments at `serializers.py:885` and `serializers.py:891` [§BR-td-dict-cleanup]

### Backend — Null component for None values [§BR-td-null]

- [x] Create `NullContent(BaseContent)` with `component = "/components/cells/NullTd"` and `value = None` [§BR-td-null-comp] [responses.py]
    - [x] `field_value_to_td` returns `NullContent.initialize(schema, raw_value)` when `raw_value is None`
- [x] Remove `if td is not None:` guards in `views/base.py` list_rows and row_details — always set the cell value [§BR-td-null-guard]
- [x] Create `frontend/src/components/cells/NullTd.vue` — renders `—` (em dash)
- [x] Remove `<span v-else class="text-muted">—</span>` fallback and `v-if` guard in `RowDetailsContent.vue` [§BR-td-null-fe]
- [x] Remove `v-if` guard in `ListRowsContent.vue` list cell rendering

### Backend — Add docstrings to `ArticleContentView` methods [§BR-docstring]

- [x] Add docstrings to `create_row`, `update_row`, `row_details` overrides in `ArticleContentView` [§BR-doc] [views/base.py:1253]
- [x] Remove `aihere` comment at `views/base.py:1254`
- [x] Use `cast(Article, context.row)` in `row_details` for type safety [views/base.py:1264]

### Frontend — Remove TdSchema discriminator/union in Zod schemas [§FE-td-zod]

- [x] Remove `discriminator` field from each Td Zod schema [§FE-td-zod-disc] [schemas.ts]
- [x] Replace `z.discriminatedUnion` with `z.union` for `ContentSchema` (renamed from `TdSchema`) [§FE-td-zod-union] [schemas.ts]
- [x] Rename types: `TdSchemaType` → `ContentType`, export per-variant types
- [x] Update `tdComponents.ts` — `getTdComponent(content: ContentType)` [§FE-td-comp]
- [x] Update `RowDetailsProps` and `ListRowsProps` to use `ContentSchema`
- [x] Remove `aihere` comment at `schemas.ts:299`
- [x] Remove `aihere` comment at `RowDetailsContent.vue:66`

### Skipped — Make `RowDetailsContext` generic [§BR-ctx-generic]

- [x] Attempted generic `RowDetailsContext[T]` — reverted due to mypy requiring type args at every call site
    - [x] Kept `row: _BaseModelMixin` with `cast(Article, context.row)` in `ArticleContentView` instead
- [x] Removed `aihere` comment at `views/base.py:1267`

### Tests [§T-td-refactor]

- [x] All 372 existing tests pass (no test changes needed — no tests directly imported Td classes)

### Lint/Typecheck [§Lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (372 tests)
- [ ] `./run playwrighttest` passes (not run due to test DB conflict — pre-existing)

## Image quota and media summary

Article model has `CONTENT_IMAGES_TOTAL_BYTES = 50 * 1024 * 1024` by default. ArticleImage has a `size` field. Dont allow total to exceed the limit per article - server responds and we get a flash message. [§IQ-req]

In `ArticleContent`, we will provide extra data. In article details, after the rich text in content, we will show `2.5Mb of media`. When we expand that text, we will see a thumbnail of each image and how much the size is. Put it in a box with border. [§IQ-media]

---

### Checklist

### Backend — ArticleImage size field [§IQ-size]

- [x] Add `size = models.PositiveBigIntegerField(default=0, help_text="Size of the uploaded image in bytes")` to `ArticleImage` [§IQ-size-field] [models/base.py:1554]
    - [x] Add `verbose_name` / `help_text` to all `ArticleImage` fields:
        - [x] `uuid_id`: `"Unique identifier for the image"`
        - [x] `article`: `"The article this image belongs to"`
        - [x] `image`: `"The uploaded image file"`
        - [x] `size`: `"Size of the uploaded image in bytes"`
    - [x] Set `size` from `image.size` in `ArticleImage.save()` before `super().save()` [§IQ-size-save]
- [x] Add migration for `ArticleImage.size` [§IQ-size-migration]

### Backend — `Article.CONTENT_IMAGES_TOTAL_BYTES` class variable [§IQ-limit]

- [x] Add `CONTENT_IMAGES_TOTAL_BYTES: ClassVar[int] = 50 * 1024 * 1024` to `Article` model [§IQ-limit-var] [models/base.py:1525]
    - [x] Add `verbose_name` / `help_text` to all `Article` fields:
        - [x] `title`: `"Article title"`
        - [x] `content`: `"Rich text content with embedded images"`
        - [x] `editor`: `"User who authored the article"`
    - [x] Subclasses (e.g. `Article2`) can override with a different limit

### Backend — Enforce quota on upload [§IQ-upload]

- [x] In `ArticleContentView.upload_article_image`, before creating `ArticleImage` [§IQ-upload-check] [views/base.py:1270]
    - [x] Sum `ArticleImage.objects.filter(article_id=row.pk).aggregate(total=Sum("size"))["total"]` (or `0` if no images)
    - [x] Add `image_file.size` to total; if exceeds `model.CONTENT_IMAGES_TOTAL_BYTES`, return `HttpError(400, "...")` with message like `"Image would exceed quota (48.5MB of 50MB used)"`
    - [x] `size` auto-set from `image.size` in `ArticleImage.save()`
- [x] Add test: upload succeeds when under quota [§IQ-upload-test-ok]
- [x] Add test: upload rejected when over quota, error message contains quota info [§IQ-upload-test-reject]

### Backend — Media summary data in ArticleContent [§IQ-content-data]

- [x] Extend `ArticleContent` Pydantic model in `responses.py` to carry media summary [§IQ-content-schema] [responses.py:445]
    - [x] Add optional `media_summary` field: `media_summary: ArticleMediaSummary | None = None`
    - [x] New `ArticleMediaSummary(PydanticBaseModel)`: `total_bytes: int`, `quota_bytes: int`, `images: list[ArticleImageSummary]`
    - [x] New `ArticleImageSummary(PydanticBaseModel)`: `uuid_id: str`, `filename: str`, `size: int`, `image_url: str`
- [x] In `ArticleContentView.row_details`, build media summary from `ArticleImage.objects.filter(article=row)` [§IQ-content-build] [views/base.py:1261]
    - [x] Pass `media_summary=...` to `ArticleContent(value=row.content, media_summary=...)`
    - [x] Only populate `media_summary` if user can edit the row (else `None`) — editor-only feature, readers dont see image management

### Frontend — Extend `ArticleContentValueSchema` [§IQ-fe-schema]

- [x] Add `ArticleMediaSummarySchema` and `ArticleImageSummarySchema` to `schemas.ts` [§IQ-fe-schema-def] [schemas.ts]
    - [x] `ArticleImageSummarySchema = z.object({ uuid_id: z.string(), filename: z.string(), size: z.number(), image_url: z.string() })`
    - [x] `ArticleMediaSummarySchema = z.object({ total_bytes: z.number(), quota_bytes: z.number(), images: z.array(ArticleImageSummarySchema) })`
- [x] Extend `ArticleContentValueSchema` with optional `media_summary: ArticleMediaSummarySchema.nullable().optional()` [§IQ-fe-schema-ext]

### Frontend — Media summary UI in `ArticleContentTd.vue` [§IQ-fe-ui]

- [x] After the `RenderRawHtml`, render media summary section [§IQ-fe-ui-render] [components/cells/ArticleContentTd.vue]
    - [x] Show `X.XMb of media` as clickable text (computed from `media_summary.total_bytes`)
    - [x] On click/expand, show a bordered box listing each image:
        - [x] Image (`<img>` with `image_url`, scaled down via CSS)
        - [x] Filename and human-readable size
    - [x] Use `v-if="summary && summary.images.length > 0"` to guard
- [x] Add CSS classes to `media-summary.scss` (no scoped/inline styles) [§IQ-fe-ui-css]
    - [x] `.media-summary` for the container
    - [x] `.media-summary-toggle` for the clickable text
    - [x] `.media-summary-box` for the expanded bordered box
    - [x] `.media-summary-image` for each image row

### Backend — Image URL for article images [§IQ-thumb]

- [x] Use existing download URL as the image source [§IQ-thumb-url]
    - [x] In `ArticleImageSummary.image_url`, use `f"/tables/api/{vn}/download-article-image/{row_id}/{img.uuid_id}"` (same URL, browser will scale down via CSS)

### Tests [§IQ-tests]

- [x] Backend: `ArticleImage` saves `size` field correctly [§IQ-t-size]
- [x] Backend: upload respects `CONTENT_IMAGES_TOTAL_BYTES` quota [§IQ-t-quota]
- [x] Backend: `ArticleContent` response includes `media_summary` with correct data [§IQ-t-summary]
- [x] Backend: `ArticleContent` response has `media_summary=None` when no images or user cannot edit [§IQ-t-no-images]

### Frontend — Image upload error toast [§IQ-error-toast]

- [x] In `ArticleContentInput.vue`, replace silent `catch` in `uploadImage` with `showToast("error", ...)` using the server error message [§IQ-toast-catch] [components/inputs/ArticleContentInput.vue:82]
    - [x] Import `showToast` from `../../utils/sweetalert`
    - [x] Parse `axios` error response: `err.response?.data?.detail ?? "Image upload failed"`
    - [x] Show `showToast("error", message)` so user sees why upload was rejected

### Frontend — Show total quota in media summary [§IQ-quota-display]

- [x] In `ArticleContentTd.vue`, show quota alongside total (e.g. `1.5MB of 50MB media`) [§IQ-quota-label] [components/cells/ArticleContentTd.vue:23]
    - [x] Remove `<!-- aihere show total quota -->` comment after implementing
    - [x] Use `humanSize(summary.quota_bytes)` for the quota portion

### Frontend — Fix ContentSchema stripping extra fields [§IQ-passthrough]

- [x] Change `RowDetailsProps.cell_values` from `z.record(z.string(), ContentSchema)` to `z.record(z.string(), ContentSchema.passthrough())` so `media_summary` isn't stripped [schemas.ts:416]
- [x] Same for `ListRowsProps.rows` catchall: `ContentSchema.passthrough()` [schemas.ts:589]

### Playwright tests [§IQ-e2e]

- [x] Image upload quota exceeded shows error toast [§IQ-e2e-quota] [tests/playwright/test_articles.py]
    - [x] Create article, override `CONTENT_IMAGES_TOTAL_BYTES` to 200, upload image exceeding quota
    - [x] Assert error toast appears (`.swal2-popup.swal2-toast`)
    - [x] Assert toast text contains "exceed quota"
- [x] Media summary shows on article details page [§IQ-e2e-media] [tests/playwright/test_articles.py]
    - [x] Create article with image, navigate to details page
    - [x] Assert `.media-summary-toggle` is visible with "media" text
    - [x] Click toggle, assert `.media-summary-box` appears with image thumbnails

### Code cleanup — existing aihere comments [§IQ-aihere-cleanup]

- [x] `ArticleContentTd.vue:23` — `<!-- aihere show total quota -->` — removed, quota now shown [§IQ-ac-23]
- [x] `test_articles.py:240` — `# aihere ArticleImage must have file` — removed comment [§IQ-ac-240]
- [x] `views/base.py:1272` — `# aihere no need to wait for images.exists(), send it anyway` — removed guard, use `list()` instead [§IQ-ac-1272]
- [x] `views/base.py:1274` — `# aihere is this local import necessary? Comment why` — moved `ArticleImageSummary`, `ArticleMediaSummary` to top-level imports [§IQ-ac-1274]
- [x] `views/base.py:1290` — `# aihere dont send filename to client` — removed `filename` from backend `ArticleImageSummary`, frontend schema, and Vue template [§IQ-ac-1290]
- [x] `views/base.py:1332` — `# aihere move this to top` — moved `human_size` to top-level imports [§IQ-ac-1332]
- [x] `media-summary.scss:1` — `// aihere move this to another file and add comments why this is used.` — replaced with doc comment [§IQ-ac-scss]

### Lint/Typecheck [§IQ-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes
- [x] `./run checkall` passes

### Refactoring — Extract media_summary to method [§IQ-refactor-media-summary]

- [x] Extract the media_summary building logic from `ArticleContentView.row_details` into `_build_media_summary` [§IQ-refactor-method] [views/base.py:1264-1301]
    - [x] Moves the try/except block, ArticleImage query, ArticleMediaSummary construction into its own method
    - [x] `row_details` calls `media_summary = self._build_media_summary(context.user, row)`
    - [x] `except Http404` is now directly after `fields_or_404` in `_build_media_summary`

### New aihere items [§IQ-aihere-new]

- [x] `models/base.py:1560` — changed `CharField(max_length=36, unique=True)` to `UUIDField(unique=True, default=uuid.uuid7)` for `uuid_id` [§IQ-ac-uuid]
    - [x] Migration `0032_articleimage_uuid_field` created
    - [x] Removed manual `self.uuid_id = str(uuid.uuid7())` from `save()` (UUIDField handles default)
    - [x] Added `ValidationError` catch in `download_article_image` for invalid UUID strings
    - [x] Removed `test_image_size_zero_when_no_file` test (now invalid — image file is required)
- [x] `models/base.py:1564` — added `db_index=True` explicitly to `article` ForeignKey [§IQ-ac-fk-index]
- [x] `models/base.py:1579` — added `assert self.image` in `ArticleImage.save()` to enforce file presence [§IQ-ac-assert]


## Cover image
We show cover image in list. Article has first_image, a nullable char field that validates with uuid. When we save Article, we save uuid of the first ArticleImage present in content html. In list view, we now return this in rows: 
 

```
		"content": {
			"component": "/components/cells/TextFieldTd",
			"value": "bbb"
		},
```

Override list_rows so content will give:
```
		"content": {
			"component": "custom/CoverImageTd",
			"value": "bbb",
            "cover_image_url": "/tables/api/article/download-article-image/1/019e45e9-9c0a-71c4-8984-4d0f636ef449",
            "url": "/tables/article/row-details/3"
		},
```

That new component will be square, will center the image and in the bottom half will have content text (stripped of html) as a translucent overlay. Text will also link to url.

### Checklist — Cover image [§CI]

#### Backend — `Article.first_image` field [§CI-field]

- [x] Add `first_image = models.UUIDField(null=True, blank=True, help_text="UUID of the first ArticleImage in content HTML")` to `Article` model [§CI-field-add] [models/base.py:1525]
    - [x] Validate it's a valid ArticleImage uuid for this article (or just trust the auto-extraction)
- [x] Create migration for `first_image` [§CI-field-migration]

#### Backend — Auto-populate `first_image` on save [§CI-save]

- [x] In `Article.save_stuff` (or `save`), after content is set, extract the first `<img src=".../{uuid}">` from `self.content` using `_extract_article_image_ids` [§CI-save-extract] [models/base.py:1538]
    - [x] Set `self.first_image` to the first extracted UUID, or `None` if no images
    - [x] Only update if content changed (or always — simpler and safe)

#### Backend — Override `list_rows` in `ArticleContentView` [§CI-list]

- [x] After the base `list_rows` builds `cell_values_list`, override the `content` cell for each row [§CI-list-override] [views/base.py:~1230]
    - [x] If `row.first_image` is not None, build `cover_image_url` using the download-article-image URL pattern
    - [x] Build `url` as `/tables/article/row-details/{row.public_id}`
    - [x] Replace the `content` cell dict with: `{component: "custom/CoverImageTd", value: stripped_content, cover_image_url: ..., url: ...}`
    - [x] Strip HTML from content for the `value` field (use `sanitize_html` or `html.unescape` + tag removal)

#### Backend — Strip HTML utility [§CI-strip]

- [x] Add `strip_html(html: str) -> str` to `djangoapp/utils.py` — removes all tags, returns plain text [§CI-strip-func]
    - [x] Can use `html.parser` or regex; just needs to produce readable plain text

#### Frontend — `CoverImageTd.vue` component [§CI-component]

- [x] Create `frontend/src/components/custom/CoverImageTd.vue` [§CI-comp-create]
    - [x] Accept `content` prop (parsed via Zod: `component`, `value`, `cover_image_url`, `url`)
    - [x] Square container with centered cover image (object-fit: cover)
    - [x] Bottom half: translucent overlay with stripped content text
    - [x] Text links to `url` (wrap in `<a>` or use `@click` + router)
    - [x] Fallback when `cover_image_url` is null/missing: show text only (like `TextFieldTd`)

#### Frontend — Zod schema for CoverImageTd [§CI-schema]

- [x] Uses `ContentSchema.passthrough()` — component validates what it needs [§CI-schema-def]

#### Frontend — CSS for cover image [§CI-css]

- [x] Add styles to `cover-image-td.scss` [§CI-css-add]
    - [x] `.cover-image-td` — square container
    - [x] `.cover-image-td__img` — `object-fit: cover; width: 100%; height: 100%`
    - [x] `.cover-image-overlay` — translucent bottom overlay
    - [x] `.cover-image-text` — text styling, links to details

#### Tests [§CI-tests]

- [x] Backend: `Article.save_stuff` sets `first_image` from content HTML [§CI-t-save]
- [x] Backend: `Article.save_stuff` clears `first_image` when content has no images [§CI-t-clear]
- [x] Backend: `list_rows` returns `cover_image_url` and `url` in content cell [§CI-t-list]
- [ ] Playwright: list page shows cover image thumbnails for articles with images [§CI-t-e2e] (pre-existing playwright DB conflict)

#### Lint/Typecheck [§CI-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (385 tests)
- [ ] `./run checkall` passes (playwright not run — pre-existing)

### Code cleanup — aihere items [§CI-aihere]

- [x] Make pydantic schema for cover image content cell, use it to dump [views/base.py:1285]
- [x] Fix `CoverImageContentSchema`: `url` is `z.string()` not nullable [schemas.ts:293]
- [x] Fix `CoverImageTd.vue`: remove `v-if="url"` guard and `?? null` on url since always present
- [x] Compute exact `src` value and assert equality in playwright test [test_articles.py:448]
- [x] Compute exact overlay text and assert equality in playwright test [test_articles.py:453]
- [x] Compute exact `href` value and assert equality in playwright test [test_articles.py:457]

## Title in details, 
In details page we have h1 showing title. But we want this in h2:

```
viewname (link to view) > row title
```

Check _debug_view to check how to generate link. Send both viewname and link to client.  

Rename `row-details` endpoint to `id`. You will have to sweep whole codebase and fix bugs.
```
http://127.0.0.1:8000/tables/article/row-details/3
http://127.0.0.1:8000/tables/article/id/3
```

Similarly `list-rows` to `list`. Also change serialization keys to be briefer. filter_map to f, all discriminator to d, pagination to p, page_number to page, per_page to per, row_update_filter to uf, operator to op. In code we will use `x.discriminator = "fk"` but serialized key will be d.
``` 
http://127.0.0.1:8000/tables/article/list-rows/-(filter_map:(editor:(discriminator:fk,mode:any,options:!('1'))),pagination:(page_number:1,per_page:25))-
http://127.0.0.1:8000/tables/article/list/-(f:(editor:(d:fk,mode:any,options:!('1'))),p:(page:1,per:25))-
```

---

### Plan

Three independent-but-related changes: (1) title breadcrumb in details page, (2) endpoint URL renames, (3) serialization key shortening. All three touch the same files, so implement in order to avoid conflicts.

**Affected files (all three changes combined):**
- Backend: `views/base.py` (URL patterns, `_list_rows`/`_row_details`, Pydantic models `ListPageSchema`/`PaginationSchema`), `filters.py` (all filter classes), `responses.py` (`RowColumnValueSchema`, `RowFormResponseSchema`, input schemas), `serializers.py` (FK URL construction)
- Frontend: `schemas.ts` (all Zod schemas with renamed keys), `ListPageSchemaWrapper.ts` (URL generation, raw object construction), `ForeignKeyFieldTd.vue`, `ListRowsContent.vue`, `RowDetailsContent.vue`, `RowForm.vue`, `UpdateRow.vue`, `SearchHeader.vue`, `Notifications.vue`, `SlotDemoRowDetails.vue`, `utils/rowUpdate.ts`
- Tests: `test_views.py`, `test_articles.py`, `test_models.py`, `test_filters.py`, `test_playwright.py`, `test_articles.py` (playwright)

### Checklist

#### Backend — Add view URL to RowDetailsProps [§TD-props]

- [x] Add `view_url: str` field to `RowDetailsProps` pydantic model in `responses.py` [§TD-props-field]
- [x] In `_row_details` (views/base.py:891), construct `view_url` using `reverse(f"tables-http:list-{viewname}", ...)` and pass to `RowDetailsProps` [§TD-props-build]
    - [x] Use `self.list_page_schema().model_dump(exclude_none=True)` as kwargs for reverse (same pattern as `_debug_view` at line 228)

#### Frontend — Title breadcrumb in RowDetailsContent [§TD-fe]

- [x] Add `view_url: z.string()` to `RowDetailsProps` Zod schema in `schemas.ts` [§TD-fe-schema]
- [x] In `RowDetailsContent.vue`, replace `<h1>{{ p.title }}</h1>` with `<h2>` containing: [§TD-fe-h2]
    - [x] `<Link :href="p.view_url">{{ p.viewname }}</Link>` (viewname as link to list page)
    - [x] ` > {{ p.title }}` (row title as plain text)
- [x] Add CSS for the breadcrumb separator and link styling in `main.css` [§TD-fe-css]
- [x] Delete row redirect uses `p.view_url` instead of constructing list URL manually

#### Backend — Rename `row-details` endpoint to `id` [§EP-rd]

- [x] In `get_url_patterns` (views/base.py:1214), change URL pattern from `{viewname}/row-details/<str:row_id>` to `{viewname}/id/<str:row_id>` [§EP-rd-url]
- [x] Change URL name from `row-details-{viewname}` to `id-{viewname}` [§EP-rd-name]
- [x] Update `get_viewname_class` docstring (line 697) — example URL `row-details/60` → `id/60` [§EP-rd-doc]
- [x] Update `_debug_view` reverse call (line 227) — `tables-http:list-rows-` stays (separate rename), but any `row-details` reverse references update to `tables-http:id-` [§EP-rd-debug]
- [x] Update all URL string construction in backend: [§EP-rd-urls]
    - [x] `serializers.py:580` — FK URL: `f"/tables/{viewname}/row-details/..."` → `f"/tables/{viewname}/id/..."`
    - [x] `views/base.py:1289` — cover image content URL: `row-details/{row_id}` → `id/{row_id}`
    - [x] `views/base.py:1310` — media summary image URL uses download URL (not row-details), no change needed

#### Backend — Rename `list-rows` endpoint to `list` [§EP-lr]

- [x] In `get_url_patterns` (views/base.py:1209), change URL pattern from `{viewname}/list-rows/-<risonargs:params>-` to `{viewname}/list/-<risonargs:params>-` [§EP-lr-url]
- [x] Change URL name from `list-rows-{viewname}` to `list-{viewname}` [§EP-lr-name]
- [x] Update all `reverse()` calls referencing `tables-http:list-rows-`: [§EP-lr-reverse]
    - [x] `_debug_view` (line 227)
    - [x] `test_playwright.py:list_rows_url` helper (line 137-141)
- [x] Update `add_views` docstring/comments referencing `list-rows` [§EP-lr-doc]

#### Frontend — Update all URL strings for `row-details` → `id` and `list-rows` → `list` [§EP-fe]

- [x] Create `utils/urls.ts` with `rowDetailsUrl(viewname, rowId)` and `listRowsUrl(viewname, risonStr)` helper functions [§EP-fe-utils]
- [x] `ListPageSchemaWrapper.ts:102` — uses `listRowsUrl()` [§EP-fe-wrapper]
- [x] `ForeignKeyFieldTd.vue:10` — uses `rowDetailsUrl()` [§EP-fe-fk]
- [x] `ListRowsContent.vue:268` — uses `rowDetailsUrl()` [§EP-fe-list-rows]
- [x] `RowDetailsContent.vue:39` — delete redirect uses `p.view_url` [§EP-fe-details]
- [x] `RowForm.vue:105,112` — uses `rowDetailsUrl()` [§EP-fe-form]
- [x] `UpdateRow.vue:21` — uses `rowDetailsUrl()` [§EP-fe-update]
- [x] `SearchHeader.vue:43` — uses `rowDetailsUrl()` [§EP-fe-search]
- [x] `Notifications.vue:188` — uses `rowDetailsUrl()` [§EP-fe-notif]
- [x] `SlotDemoRowDetails.vue:27,33` — uses `rowDetailsUrl()` [§EP-fe-slot]

#### Backend — Shorten serialization keys: Pydantic aliases [§SK-be]

All aliased models use `_AliasModel` base class with `ConfigDict(populate_by_name=True, serialize_by_alias=True, validate_by_alias=True)`.

- [x] Create `_AliasModel(PydanticBaseModel)` base class in `views/base.py` with `populate_by_name=True, serialize_by_alias=True, validate_by_alias=True` [§SK-be-base]
- [x] `PaginationSchema` extends `_AliasModel`: [§SK-be-pag]
    - [x] `page_number` → `Field(alias="page")`
    - [x] `per_page` → `Field(alias="per")`
- [x] `ListPageSchema` extends `_AliasModel`: [§SK-be-lps]
    - [x] `pagination` → `Field(alias="p")`
    - [x] `filter_map` → `Field(alias="f")`
    - [x] `row_update_filter` → `Field(alias="uf")`
- [x] All filter classes in `filters.py`: `FilterABC` has `ConfigDict(populate_by_name=True, serialize_by_alias=True, validate_by_alias=True)`, all `discriminator` fields use `Field(alias="d")` [§SK-be-filt]
    - [x] Applies to all 14 filter classes
- [x] Filter `operator` fields → `Field(alias="op")`: [§SK-be-op]
    - [x] `IntegerComparisonFilter.operator`, `DecimalComparisonFilter.operator`, `DatetimeComparisonFilter.operator`
- [x] `BaseFieldSchema`, `BaseInputSchema`, `BaseRowValueSchema` in `responses.py` each have `ConfigDict(populate_by_name=True, serialize_by_alias=True, validate_by_alias=True)`, all discriminator fields use `Field(alias="d")` [§SK-be-rowcol]
- [x] `SuccessResponse`, `ValidationErrorResponse` extend `_AliasModel` with `alias="d"` on discriminator [§SK-be-formresp]
- [x] `FieldSchema` / `InputSchema` / `ContentSchema` unions: discriminated unions work with aliased discriminator field [§SK-be-union]
- [x] `model_dump()` calls do NOT pass `by_alias=True` — handled by `serialize_by_alias=True` in ConfigDict [§SK-be-dump]
- [x] `create_row_submit` and `update_row_submit` return `dict[str, Any]` with explicit `.model_dump(by_alias=True)` since Ninja doesn't propagate aliases through nested validation [§SK-be-ninja]
- [x] Ninja router uses `by_alias=True`: `OurRouter(exclude_none=True, by_alias=True)` [§SK-be-router]

#### Frontend — Shorten serialization keys: Zod schemas [§SK-fe]

- [x] `PaginationSchema`: `page_number` → `page`, `per_page` → `per` [§SK-fe-pag]
- [x] All filter schemas: `discriminator` → `d` in every Zod literal field [§SK-fe-filt]
    - [x] 14 filter schemas updated
    - [x] `FilterSchema` discriminated union key: `z.discriminatedUnion("d", [...])`
    - [x] `DecimalComparisonFilter` type definition: `d` instead of `discriminator`
- [x] Filter `operator` fields → `op` [§SK-fe-op]
    - [x] `IntegerComparisonFilterSchema`, `DecimalComparisonFilterSchema`, `DatetimeComparisonFilterSchema`
    - [x] Local interfaces in `IntegerComparisonBox.vue`, `DecimalComparisonBox.vue`, `DatetimeComparisonBox.vue` updated
- [x] `ListPageSchema`: `pagination` → `p`, `filter_map` → `f`, `row_update_filter` → `uf` [§SK-fe-lps]
- [x] `RowColumnValueSchema` / individual value schemas: `discriminator` → `d` [§SK-fe-rowcol]
- [x] `InputSchema` / field schemas: `discriminator` → `d` [§SK-fe-input]
- [x] `RowFormResponseSchema`: `discriminator` → `d`, update discriminated union key [§SK-fe-formresp]
- [x] Update all TypeScript code accessing renamed keys: [§SK-fe-code]
    - [x] `ListPageSchemaWrapper.ts` — raw object construction uses `d`, `f`, `p`, `uf`, `page`, `per`, `op`
    - [x] `utils/rowUpdate.ts` — `cv.discriminator` → `cv.d`
    - [x] `ListRowsContent.vue` — `list_page_schema.f`, `list_page_schema.uf`, `pagination.page`
    - [x] `RowForm.vue` — `data.d`
    - [x] All filter Vue components — `.discriminator` → `.d`, `.operator` → `.op`

#### Tests — Update URLs and key names [§T-url]

- [x] `test_views.py`: [§T-url-views]
    - [x] All `row-details` URL strings → `id`
    - [x] All `list-rows` URL strings → `list`
    - [x] Rison key names: `filter_map:` → `f:`, `discriminator:` → `d:`, `pagination:` → `p:`, `page_number:` → `page:`, `per_page:` → `per:`, `row_update_filter:` → `uf:`, `operator:` → `op:`
    - [x] Test assertions on `"discriminator"` JSON key → `"d"`
    - [x] Test assertions on `"page_number"` error message → `"page"`
    - [x] URL reverse name changes: `tables-http:list-rows-*` → `tables-http:list-*`
- [x] `test_articles.py`: [§T-url-articles]
    - [x] All `row-details` → `id`, `list-rows` → `list`
    - [x] Rison key names updated
    - [x] Test assertions on `"discriminator"` → `"d"`
    - [x] URL in cover image content assertion
- [x] `test_models.py`: [§T-url-models]
    - [x] FK URL construction assertions: `row-details` → `id`
    - [x] Column filter assertions with `"discriminator"` key → `"d"`
- [x] `test_filters.py`: [§T-url-filters]
    - [x] Constructor keyword args use alias names: `d=`, `op=`, `f=`, etc.
    - [x] Any URL or serialized output assertions updated
- [x] `test_playwright.py` and `test_articles.py` (playwright): [§T-url-pw]
    - [x] All `row-details` → `id`, `list-rows` → `list` in `wait_for_url`, `goto`, `assertEqual` URL assertions
    - [x] `list_rows_url` helper: reverse name from `tables-http:list-rows-` → `tables-http:list-`
    - [x] Rison key names in URL patterns
    - [x] Fixed `table.list-table` → `table.list-rows-table` (CSS class was incorrectly renamed by sed)

#### README [§DOC]

- [x] Update `README.md` filter documentation table — all URL examples change `filter_map` → `f`, `discriminator` → `d`, `operator` → `op` [§DOC-readme]

#### Lint/Typecheck [§LR-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (385 tests)
- [x] Frontend `npm run lint:fix` passes
- [x] Frontend `npm run type-check` passes
- [x] `./run checkall` passes (385 unit + 147 playwright)


## ValueWrapper refactoring

Introduce a `ValueWrapper` class hierarchy so each Django field type has one wrapper object that knows the field definition + raw value and exposes `.as_json()`, `.as_td()`, `.as_input()`. Replace the three separate dispatch systems (`JSON_VALUE_SERIALIZERS`, `CONTENT_MAP`/`field_value_to_td`, `field_schema_to_input`) with this single abstraction. Merge `fields` + `field_values` on the frontend so each input is self-contained. Add `annotate_fk_titles()` standalone function for batch FK title resolution, eliminating `_NOT_FILLED` sentinel and `add_titles_to_foreign_key_columns()`.

Avoid n+1 queries

---

### Checklist

#### Backend — Create `ValueWrapper` classes [§VW-classes]

- [x] Create `ForeignKeyTitleData` dataclass in `serializers.py`: `public_id: str`, `title: str` [§VW-fk-title-data]
- [x] Create `BaseValueWrapper` dataclass with `field: DjangoField`, `value: Any`, `instance`, `fk_titles: FkTitlesMap | None` [§VW-base]
    - [x] Abstract methods: `as_json() -> JSONValue`, `as_td() -> BaseContent`, `as_input() -> InputSchema`
- [x] Create `CharValueWrapper(BaseValueWrapper)` [§VW-char]
- [x] Create `TextValueWrapper` [§VW-text]
- [x] Create `IntegerValueWrapper` [§VW-int]
- [x] Create `BooleanValueWrapper` [§VW-bool]
- [x] Create `DecimalValueWrapper` [§VW-dec]
- [x] Create `DateTimeValueWrapper` [§VW-dt]
- [x] Create `FileValueWrapper` [§VW-file]
- [x] Create `ForeignKeyValueWrapper` [§VW-fk]
- [x] Create dispatch dict `VALUE_WRAPPER_TYPES` [§VW-dispatch]

#### Backend — `annotate_fk_titles()` standalone function [§VW-annotate]

- [x] Add module-level function `annotate_fk_titles(columns, rows) -> FkTitlesMap` in `models/base.py` [§VW-annotate-func]

#### Backend — `value_wrappers()` method on `_BaseModelMixin` [§VW-method]

- [x] Add `value_wrappers(self, columns, fk_titles=None) -> dict[str, BaseValueWrapper]` to `_BaseModelMixin` [§VW-method-add]
    - [x] FK fields pass `value=None` to avoid N+1 during construction
- [x] Delete `fields_api_values()` (no longer called) [§VW-method-delegate]

#### Backend — Update `views/base.py` to use new API [§VW-views]

- [x] `list_rows()` — uses `annotate_fk_titles` + `value_wrappers` + `.as_td()` [§VW-views-list]
- [x] `row_details()` — uses `value_wrappers` + `.as_td()` [§VW-views-details]
- [x] `create_row()` — uses `value_wrappers` on blank instance + `.as_input()` [§VW-views-create]
- [x] `update_row()` — uses `value_wrappers` + `.as_input()`, no separate `field_values` [§VW-views-update]

#### Backend — Delete dead code from `serializers.py` [§VW-delete]

- [x] Delete 9 `_serialize_*_to_api` functions (~130 lines) [§VW-delete-serialize]
- [x] Delete `JSON_VALUE_SERIALIZERS` dict [§VW-delete-json-dict]
- [x] Delete `CONTENT_MAP` dict + `field_value_to_td()` function [§VW-delete-td]
- [x] Delete `field_schema_to_input()` function (~65 lines) [§VW-delete-input]
- [x] Delete `_NOT_FILLED` sentinel [§VW-delete-sentinel]
- [x] Delete `add_titles_to_foreign_key_columns()` from `models/base.py` [§VW-delete-add-titles]
- [x] Rename `ROW_VALUE_SERIALIZERS` → `ROWUPDATE_VALUE_SERIALIZERS` + all call sites [§VW-rename]
- [x] Remove all aihere comments addressed by this refactoring [§VW-aihere]
- [x] Delete `JsonValueSerializerTests` and `FieldSchemaToInputTests` from test_serializers.py (72 tests removed)

#### Frontend — Merge `fields` + `field_values` into self-contained `fields` [§VW-fe-merge]

- [x] Backend: remove `field_values` from `CreateRowProps` / `UpdateRowProps` pydantic models in `views/base.py` [§VW-fe-be-props]
- [x] Backend: update `FileFieldInputSchema.default` type from `str | None` to `dict[str, str] | None` in `responses.py` [§VW-fe-file-default-be]
- [x] `schemas.ts`: remove `field_values: z.any()` from `CreateRowProps` [§VW-fe-schema]
- [x] `schemas.ts`: update `FileFieldInputBase.default` type to `z.any().nullable()` [§VW-fe-file-default]
- [x] `CreateRow.vue`: remove `:initial-field-values` prop [§VW-fe-create]
- [x] `UpdateRow.vue`: remove `:initial-field-values` prop [§VW-fe-update]
- [x] `RowForm.vue` [§VW-fe-rowform]
    - [x] Remove `initialFieldValues` prop
    - [x] Initialize `fieldValues` from each field's `default`

#### Lint/Typecheck [§VW-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (313 tests)
- [x] `cd frontend && npm run lint:fix` passes
- [x] `cd frontend && npm run type-check` passes
- [x] `./run checkall` passes (313 unit + 147 playwright)

### Code cleanup — aihere items [§VW-aihere-cleanup]

- [x] `models/base.py:588` — explain why `raw_value = None` for FK fields in `value_wrappers()` [§VW-ac-explain]
- [x] `models/base.py:1272` — remove redundant `str()` casts on `.public_id`; audit whole codebase [§VW-ac-str]
- [x] `models/base.py:1270` — change `FkTitlesMap` from flat `dict[tuple[str, int], ForeignKeyTitleData]` to nested `dict[str, dict[int, ForeignKeyTitleData]]` [§VW-ac-nest]
- [x] `test_serializers.py:217` — add replacement tests: `ValueWrapperAsJsonTests` (12), `ValueWrapperAsTdTests` (5), `ValueWrapperAsInputTests` (10), `AnnotateFkTitlesTests` (3) [§VW-ac-tests]

## Server rendering
We have a behavior regression. In details view, text fields used to render html. Find out which commit introduced this problem.

value_wrappers will take a param context which is Literal['list', 'details', 'input']. In details view, we will call `.value_wrappers(...,'details')`, TextValueWrapper.as_td will return TextContent with value stripped of html tags and trimmed to 200 characters with ellipsis if it exceeds. TextFieldTd will assume value is plain text instead of html and wont strip tags itself. In list view, it will call a TextFieldHtmlTd (create it) which renders html.

If browser is detected, render a Django template to string and add it to the inertia response. Just render the cell values and title, no comments etc. Default title of page is Tables. Supply title in Inertia response in list and details page. For details page, have a `go up` link. If browser is NOT detected, return the rendered template directly as HTML.

Add something like this to BaseView:
```
def is_browser(request):
    return bool(request.headers.get("X-Inertia"))
```

Like we have as_td, have as_html. It returns html snippets, stripped of html tags if need be. For text, in list view, value stripped of html tags and trimmed to 200 characters with ellipsis if it exceeds; for details, render html.

Use Django template language. Maybe have a filter `|ashtml` in Django template.

For time, render the timezone. Use timezone in settings.py.

For Article, have meta tags for title, cover image and description (stripped html)

`TextValueWrapper` reference implementation:
```python
@dataclass
class TextValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        return self.value if self.value is not None else None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        assert isinstance(json_val, str)
        if self.context == "details":
            return TextHtmlContent(value=sanitize_html(json_val))
        return TextContent(value=truncate_text(strip_html(json_val)))

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, TextFieldSchema)
        return TextFieldInputSchema(
            name=schema.name,
            required=schema.required,
            length=schema.length,
            default=self.value if self.value is not None else schema.default,
        )

    def as_html(self) -> str:
        if self.value is None:
            return "—"
        if self.context == "details":
            return sanitize_html(self.value)
        return truncate_text(strip_html(self.value))
```

---

### Plan

Three related changes: (1) context-aware `value_wrappers` with different text rendering for list vs details, (2) `as_html()` method on ValueWrapper for server-side rendering via Django templates, (3) Django template SSR rendered to string and added to inertia response for browsers / returned directly for non-browsers + page titles + Article meta tags.

**Key insight**: For text, `as_td()` and `as_html()` produce the same per-context output:
- `as_td()` list → stripped plain text via `TextContent` (TextFieldTd), details → raw HTML via `TextHtmlContent` (TextFieldHtmlTd)
- `as_html()` list → stripped plain text (compact SSR summary), details → raw HTML (rich SSR)

Templates receive `fields` and `cell_values` and use `|ashtml` filter to render each wrapper. `RowDetailsContext` (row, user, columns, column_schemas) is the input to `_row_details`, which returns `RowDetails2Context` (th_columns, cell_values).

**Affected files:**
- Backend: `serializers.py` (BaseValueWrapper + all subclasses get `context` + `as_html()`), `responses.py` (TextHtmlContent), `views/base.py` (`is_browser()`, SSR branching, page title, `value_wrappers()` calls, `RowDetails2Context`), `models/base.py` (`value_wrappers()` signature), `utils.py` (truncate helper), `templatetags/` (`|ashtml` filter)
- Templates: `templates/inertia/base.html` (dynamic title), new `templates/tables/ssr_list.html`, new `templates/tables/ssr_details.html`
- Frontend: `TextFieldTd.vue` (remove htmlToPlaintext, value is now plain text), new `TextFieldHtmlTd.vue` (renders HTML for details), `schemas.ts` (TextHtmlValueSchema)
- Tests: `test_views.py`, `test_serializers.py`, `test_articles.py`

### Checklist

#### Backend — Add `context` parameter to `value_wrappers` and `BaseValueWrapper` [§SR-ctx]

Each wrapper now knows whether it's rendering for list, details, or input. This lets `as_td()` and `as_html()` produce different output per context (e.g. stripped text in list, raw HTML in details).

- [ ] Add `context: Literal['list', 'details', 'input']` field to `BaseValueWrapper` dataclass [§SR-ctx-base] [serializers.py:738]
    - [ ] Default value `'list'` for backward compatibility
- [ ] Update `value_wrappers()` on `_BaseModelMixin` to accept and pass `context` [§SR-ctx-method] [models/base.py:571]
    - [ ] Signature: `value_wrappers(self, columns, context='list') -> dict[str, BaseValueWrapper]`
    - [ ] Pass `context=context` to `wrapper_cls(...)` constructor
- [ ] Update all call sites in `views/base.py`: [§SR-ctx-calls]
    - [ ] `list_rows()`: `wrappers = row.value_wrappers(columns, context='list')`
    - [ ] `row_details()`: `wrappers = ctx2.row.value_wrappers(ctx2.th_columns, context='details')`
    - [ ] `create_row()`: `wrappers = blank.value_wrappers(columns, context='input')`
    - [ ] `update_row()`: `wrappers = row.value_wrappers(columns, context='input')`

#### Backend — `TextValueWrapper.as_td()` context-aware [§SR-text-td]

In list context, strip HTML and truncate to 200 chars so TextFieldTd renders brief plain text. In details context, keep full HTML and use new TextHtmlContent for TextFieldHtmlTd. Follow the reference implementation above.

- [ ] In `TextValueWrapper.as_td()`, check `self.context`: [§SR-text-td-logic] [serializers.py:790]
    - [ ] If `'list'`: strip HTML via `strip_html()`, trim to 200 chars with ellipsis if exceeds, return `TextContent(value=stripped_text)`
    - [ ] If `'details'`: sanitize HTML via `sanitize_html()` (whitelisted tags only), return `TextHtmlContent(value=sanitized_html)`
- [ ] Add `truncate_text(text: str, max_length: int = 200) -> str` helper to `djangoapp/utils.py` [§SR-text-trunc] [utils.py]
    - [ ] Returns `text[:max_length] + "…"` if `len(text) > max_length`, else `text`
    - [ ] Tries to break at last space before `max_length` to avoid mid-word truncation

#### Backend — `TextHtmlContent` Pydantic model [§SR-html-content]

New content type for details-view text cells that carry full HTML content.

- [ ] Create `TextHtmlContent(BaseContent)` in `responses.py` [§SR-html-model] [responses.py:454]
    - [ ] `component: str = "/components/cells/TextFieldHtmlTd"`
    - [ ] `value: str` (raw HTML)

#### Frontend — `TextFieldHtmlTd.vue` component [§SR-fe-html-td]

New component for details-view text cells. Renders sanitized HTML via RenderRawHtml (which applies `sanitizeHtml` from `utils/html.ts` — same tags/attrs whitelist as backend `sanitize_html`). Backend also sanitizes before sending, so this is defense-in-depth. Also adds the Zod schema and registers the component in tdComponents.

- [ ] Create `frontend/src/components/cells/TextFieldHtmlTd.vue` [§SR-html-comp]
    - [ ] Accept `content` prop (parsed via Zod: `TextHtmlValueSchema`)
    - [ ] Renders HTML using `<ExpandableCell>` + `<RenderRawHtml>` (same pattern as ArticleContentTd)
- [ ] Add `TextHtmlValueSchema` to `schemas.ts`: `ContentSchema.extend({ value: z.string() })` [§SR-html-schema]
- [ ] Register `TextFieldHtmlTd` in `tdComponents.ts` for component path `/components/cells/TextFieldHtmlTd` [§SR-html-reg]

#### Frontend — Update `TextFieldTd.vue` to render plain text [§SR-fe-text-td]

Since the backend now sends stripped plain text in list context (via `strip_html()`), TextFieldTd no longer needs to strip HTML itself. Remove the `htmlToPlaintext` call — just render `parsed.value` directly.

- [ ] Remove `htmlToPlaintext` import and call from `TextFieldTd.vue` [§SR-text-plain] [components/cells/TextFieldTd.vue:4,10]
    - [ ] Change to `const flatText = String(parsed.value)` — value is now always plain text from backend
    - [ ] Remove `import { htmlToPlaintext } from "../../utils/html"`

#### Backend — `as_html()` method on ValueWrapper classes [§SR-as-html]

New method alongside `as_td()` that returns HTML snippet strings for server-side rendering. For text, `as_html()` follows the same pattern as `as_td()`: list returns stripped+truncated plain text, details returns raw HTML. DateTime includes timezone from settings.

Each `as_html()` returns an HTML snippet string for server-side rendering. Behavior depends on `self.context`.

- [ ] Add abstract `as_html() -> str` method to `BaseValueWrapper` [§SR-html-base] [serializers.py:738]
- [ ] `TextValueWrapper.as_html()`: [§SR-html-text]
    - [ ] `'list'` context: `strip_html()` + `truncate_text()` → plain text snippet
    - [ ] `'details'` context: `sanitize_html()` → whitelisted HTML (safe for direct rendering)
- [ ] `CharValueWrapper.as_html()`: return `str(self.value)` or `""` [§SR-html-char]
- [ ] `IntegerValueWrapper.as_html()`: return `str(self.value)` or `""` [§SR-html-int]
- [ ] `BooleanValueWrapper.as_html()`: return `"Yes"` / `"No"` / `""` [§SR-html-bool]
- [ ] `DecimalValueWrapper.as_html()`: return `str(self.value)` or `""` [§SR-html-dec]
- [ ] `DateTimeValueWrapper.as_html()`: return formatted datetime with timezone abbreviation [§SR-html-dt]
    - [ ] Use `timezone.localtime(value).strftime("%Y-%m-%d %H:%M %Z")` — timezone from `settings.TIME_ZONE`
- [ ] `FileValueWrapper.as_html()`: return `value.name` or `"—"` [§SR-html-file]
- [ ] `ForeignKeyValueWrapper.as_html()`: return FK title text or `"—"` (reuse `as_json()` title) [§SR-html-fk]
- [ ] `NullContent` equivalent: wrappers with `None` values return `"—"` in their respective `as_html()` [§SR-html-null]

#### Backend — `is_browser()` method on `BaseView` [§SR-is-browser]

Detects Inertia frontend vs non-browser (crawlers, curl). Uses `X-Inertia` header presence.

- [ ] Add static method `is_browser(request) -> bool` on `BaseView` [§SR-browser-method] [views/base.py:695]
    - [ ] `return bool(request.headers.get("X-Inertia"))`

#### Backend — Django template filter `|ashtml` [§SR-filter]

Template filter that calls `.as_html()` on a `BaseValueWrapper` instance, returning a `SafeString`.

- [ ] Create template filter `ashtml` in `djangoapp/templatetags/` (or existing templatetag module) [§SR-filter-def]
    - [ ] Takes a `BaseValueWrapper` instance, calls `.as_html()`, returns `mark_safe(result)`
- [ ] Load the filter in SSR templates via `{% load ... %}`

#### Backend — Dynamic page title in Inertia props [§SR-title]

Add `page_title` to list and details props. List uses capitalized viewname, details uses `"{title} — {viewname}"`. Update base.html to use it.

- [ ] Add `page_title: str = "Tables"` field to `ListRowsProps` [§SR-title-list] [views/base.py:567]
- [ ] Add `page_title: str = "Tables"` field to `RowDetailsProps` [§SR-title-details] [views/base.py:367]
- [ ] In `_list_rows()`, set `page_title` to capitalized viewname (e.g. "Article") [§SR-title-list-set]
- [ ] In `_row_details()`, set `page_title` to `f"{title} — {viewname}"` [§SR-title-details-set]
- [ ] Update `base.html` to read title from Inertia page data: [§SR-title-html] [templates/inertia/base.html:7]
    - [ ] Change `<title>Tables</title>` to `<title>{{ page_title }}</title>`
    - [ ] Extract `page_title` from the Inertia page props in the template context

#### Backend — `RowDetails2Context` dataclass [§SR-ctx2]

`_row_details` returns `RowDetails2Context` which holds the computed rendering data: `th_columns` and `cell_values`. The input `RowDetailsContext` holds row, user, columns, column_schemas.

- [ ] Create `RowDetails2Context` dataclass [§SR-ctx2-def] [views/base.py]
    - [ ] `th_columns: Sequence[DjangoField]`
    - [ ] `cell_values: dict[str, BaseValueWrapper]`
- [ ] Update `_row_details()` to return `RowDetails2Context` [§SR-ctx2-return]
- [ ] Update all call sites to use `ctx2.th_columns` and `ctx2.cell_values`

#### Backend — Server-side rendering with Django templates [§SR-ssr]

Always render the Django template. When browser IS detected, render template to string and add to inertia response props. When browser is NOT detected, return the rendered template directly as HTML. Two new templates: `ssr_list.html` (table) and `ssr_details.html` (fields + "go up" link). No comments, no filters, no edit controls. Templates receive `fields` and `cell_values`, using `|ashtml` filter.

- [ ] Create `djangoapp/templates/tables/ssr_list.html` Django template [§SR-ssr-list-tpl]
    - [ ] `{% load ... %}` for `|ashtml` filter
    - [ ] Renders: `<h1>{{ page_title }}</h1>`
    - [ ] Table with headers from `fields` and rows from `cell_values` via `{{ cell_value|ashtml }}`
    - [ ] No comments, no filters, no pagination controls
- [ ] Create `djangoapp/templates/tables/ssr_details.html` Django template [§SR-ssr-details-tpl]
    - [ ] `{% load ... %}` for `|ashtml` filter
    - [ ] Renders: `<h1>{{ page_title }}</h1>`
    - [ ] "Go up" link: `<a href="{{ view_url }}">↑ Go up</a>`
    - [ ] Field labels + cell values from `fields` / `cell_values` via `{{ cell_value|ashtml }}`
    - [ ] No comments, no edit/delete buttons
- [ ] In `_list_rows()`, always render `ssr_list.html` to string: [§SR-ssr-list-branch]
    - [ ] If `is_browser()`: add rendered HTML string to inertia props (e.g. `ssr_html=rendered`), return `InertiaResponse`
    - [ ] If not browser: return `HttpResponse(rendered)` directly
    - [ ] Template context: `{page_title, fields=context.th_columns, cell_values=cell_values}`
- [ ] In `_row_details()`, always render `ssr_details.html` to string: [§SR-ssr-details-branch]
    - [ ] If `is_browser()`: add rendered HTML string to inertia props, return `InertiaResponse`
    - [ ] If not browser: return `HttpResponse(rendered)` directly
    - [ ] Template context: `{page_title, view_url, fields=ctx2.th_columns, cell_values=ctx2.cell_values}`

#### Backend — Article meta tags for SSR [§SR-article-meta]

For Article details, inject og:title, og:description (stripped HTML), and og:image (cover image) into the SSR template `<head>`.

- [ ] In `ArticleContentView.row_details`, add meta tags to SSR context: [§SR-meta-article]
    - [ ] `meta_title`: `row.title`
    - [ ] `meta_description`: `strip_html(row.content)` trimmed to ~160 chars
    - [ ] `meta_image`: cover image URL from `row.first_image` (if set)
- [ ] In `ssr_details.html`, render `<meta>` tags when provided: [§SR-meta-tpl]
    - [ ] `<meta property="og:title" content="{{ meta_title }}">`
    - [ ] `<meta property="og:description" content="{{ meta_description }}">`
    - [ ] `<meta property="og:image" content="{{ meta_image }}">` (conditional)

#### Tests [§SR-tests]

Covers context-aware as_td(), truncate_text(), as_html() per wrapper type, is_browser(), SSR HTML output, and Article meta tags.

- [ ] Backend: `TextValueWrapper.as_td()` returns `TextContent` with stripped text in 'list' context [§SR-t-text-list]
- [ ] Backend: `TextValueWrapper.as_td()` returns `TextHtmlContent` with raw HTML in 'details' context [§SR-t-text-details]
- [ ] Backend: `truncate_text()` truncates at word boundary and adds ellipsis [§SR-t-truncate]
- [ ] Backend: `as_html()` returns correct snippets for each wrapper type [§SR-t-as-html]
- [ ] Backend: `as_html()` for DateTimeValueWrapper includes timezone [§SR-t-dt-tz]
- [ ] Backend: `is_browser()` returns True when `X-Inertia` header present [§SR-t-is-browser]
- [ ] Backend: `_list_rows` adds SSR HTML to inertia response when browser detected [§SR-t-ssr-list-browser]
- [ ] Backend: `_list_rows` returns HTML directly when not browser [§SR-t-ssr-list-nobrowser]
- [ ] Backend: `_row_details` adds SSR HTML to inertia response with "go up" link when browser detected [§SR-t-ssr-details-browser]
- [ ] Backend: `_row_details` returns HTML with "go up" link when not browser [§SR-t-ssr-details-nobrowser]
- [ ] Backend: `_row_details` for Article includes og: meta tags [§SR-t-meta]
- [ ] Backend: `|ashtml` template filter renders wrapper correctly [§SR-t-filter]
- [ ] Frontend: `TextFieldHtmlTd` renders HTML content [§SR-t-fe-html]

#### Lint/Typecheck [§SR-lint]

- [ ] `./run lintfix` passes
- [ ] `./run typecheck` passes
- [ ] `./run test` passes
- [ ] `cd frontend && npm run lint:fix` passes
- [ ] `cd frontend && npm run type-check` passes
- [ ] `./run checkall` passes

## Props refactoring

### Backend — Rename `field_names` to `column_names` in Create/Update props [§PR-rename]

- [x] Rename `field_names` → `column_names` in `CreateRowProps` pydantic model [§PR-rename-create] [views/base.py:388]
- [x] `UpdateRowProps` inherits from `CreateRowProps`, so automatically picks up `column_names` [§PR-rename-update]
- [x] Update all backend call sites that set `field_names=`: `create_row()`, `update_row()` in `views/base.py` [§PR-rename-be-calls]

### Frontend — Rename `field_names` to `column_names` [§PR-fe-rename]

- [x] Update `CreateRowProps` Zod schema: `field_names` → `column_names` in `schemas.ts` [§PR-fe-schema] [schemas.ts:612]
- [x] Update `RowForm.vue`: prop name, `props.field_names` → `props.column_names`, `v-for` iteration [§PR-fe-rowform] [RowForm.vue:13,36,81,159]
- [x] Update `CreateRow.vue`: `:field_names` → `:column_names` [§PR-fe-create] [CreateRow.vue:20]
- [x] Update `UpdateRow.vue`: `p.field_names` → `p.column_names`, `:field_names` → `:column_names` [§PR-fe-update] [UpdateRow.vue:19,31]

### Backend — Add `column_names` to list/details props [§PR-col-names]

- [x] Add `column_names: list[str]` to `ListRowsProps` [§PR-cn-list] [views/base.py:571]
- [x] Add `column_names: list[str]` to `RowDetailsProps` [§PR-cn-details] [views/base.py:369]
- [x] In `_list_rows()`, set `column_names=list(result.th_columns.keys())` [§PR-cn-list-set]
- [x] In `_row_details()`, set `column_names=list(ctx2.th_columns.keys())` [§PR-cn-details-set]

### Frontend — Use `column_names` from props [§PR-fe-col-names]

- [x] Add `column_names: z.array(z.string())` to `ListRowsProps` Zod schema in `schemas.ts` [§PR-fe-cn-list]
- [x] Add `column_names: z.array(z.string())` to `RowDetailsProps` Zod schema in `schemas.ts` [§PR-fe-cn-details]
- [x] `ListRowsContent.vue`: use `p.column_names` for column iteration instead of `p.columns` for ordering [§PR-fe-cn-listrows]

### Backend — `ListRowsProps.columns` and `columns_raw` as dicts [§PR-list-dict]

- [x] Change `columns: list[ThSchema]` → `columns: dict[str, ThSchema]` in `ListRowsProps` [§PR-list-dict-columns] [views/base.py:573]
- [x] Change `columns_raw: list[Any]` → `columns_raw: dict[str, Any]` in `ListRowsProps` [§PR-list-dict-raw] [views/base.py:574]
- [x] In `_list_rows()`, pass `columns=result.th_columns` (already a dict) instead of `th_list` [§PR-list-dict-set]
- [x] In `_list_rows()`, build `columns_raw` as dict keyed by name instead of list [§PR-list-dict-raw-set]

### Frontend — `ListRowsProps.columns` and `columns_raw` as dicts [§PR-fe-list-dict]

- [x] Change `columns: z.array(ThSchema)` → `columns: z.record(z.string(), ThSchema)` in `ListRowsProps` Zod schema [§PR-fe-list-dict-columns] [schemas.ts:593]
- [x] Change `columns_raw: z.array(FieldSchema)` → `columns_raw: z.record(z.string(), FieldSchema)` in Zod schema [§PR-fe-list-dict-raw] [schemas.ts:594]
- [x] `ListRowsContent.vue`: update `p.columns_raw.find(c => c.name === columnName)` → `p.columns_raw[columnName]` [§PR-fe-list-dict-find] [ListRowsContent.vue:149]
- [x] `ListRowsContent.vue`: update `v-for` iteration over `p.columns_raw` to use dict values/entries [§PR-fe-list-dict-iter] [ListRowsContent.vue:175]
- [x] `ListRowsContent.vue`: update `v-for="column in p.columns"` to use dict values or `column_names` [§PR-fe-list-dict-cols] [ListRowsContent.vue:253,272]

### Backend — `RowDetailsProps.fields` as dict [§PR-details-dict]

- [x] Change `fields: list[ThSchema]` → `fields: dict[str, ThSchema]` in `RowDetailsProps` [§PR-details-dict-fields] [views/base.py:374]
- [x] In `_row_details()`, pass `fields=ctx2.th_columns` (already a dict) instead of `list(ctx2.th_columns.values())` [§PR-details-dict-set]

### Frontend — `RowDetailsProps.fields` as dict [§PR-fe-details-dict]

- [x] Change `fields: z.array(ThSchema)` → `fields: z.record(z.string(), ThSchema)` in `RowDetailsProps` Zod schema [§PR-fe-details-dict] [schemas.ts:422]
- [x] `RowDetailsContent.vue`: update `v-for="field in p.fields"` to iterate dict values [§PR-fe-details-dict-iter] [RowDetailsContent.vue:62]

### Backend — Annotate `cell_values_list` and simplify row construction [§PR-annotate]

- [x] Annotate `cell_values_list` with proper type in `list_rows()`: `list[dict[str, str | BaseContent]]` [§PR-ann-list] [views/base.py:852]
- [x] Verify `.as_td()` always returns `BaseContent` (never `None`) — remove `inertia_rows` loop, pass `rows=result.cell_values` directly [§PR-ann-null]
- [x] Pass `rows=result.cell_values` directly to `ListRowsProps.rows` without building `inertia_rows` separately [§PR-ann-direct]

### Lint/Typecheck [§PR-lint]

- [x] `./run lintfix` passes
- [x] `./run typecheck` passes
- [x] `./run test` passes (349 tests)
- [x] `cd frontend && npm run lint:fix` passes
- [x] `cd frontend && npm run type-check` passes
- [x] `./run checkall` passes (349 unit + 147 playwright)

### Backend — `columns_schemas` returns dict [§PR-colschemas]

- [x] Change `columns_schemas()` return type from `list[Any]` to `dict[str, BaseFieldSchema]` [§PR-cs-ret] [models/base.py:549]
- [x] Update `ListRowsContext.column_schemas`, `ListRows2Context.column_schemas`, `RowDetailsContext.column_schemas` from `list` to `dict` [§PR-cs-ctx] [views/base.py]
- [x] Update `validate_filters`, `human_row_references`, `_find_field_schema` signatures: `dict` → `Mapping[str, BaseFieldSchema]` for covariance [§PR-cs-sigs] [views/base.py]
- [x] Replace `_find_field_schema` loop with dict `.get()` lookup [§PR-cs-find] [views/base.py]
- [x] Replace `validate_filters` inner loop with `column_schemas.get(col_name)` [§PR-cs-val] [views/base.py]
- [x] Update all `for cs in column_schemas` → `for name, cs in column_schemas.items()` in `list_rows()` and `row_details()` [§PR-cs-iter]
- [x] Simplify `columns_raw_dict` build — now just `columns_raw = column_schemas` since it's already a dict [§PR-cs-raw]
- [x] Update test files: `test_filters.py` and `test_models.py` — all mock `columns` changed from list to dict [§PR-cs-tests]