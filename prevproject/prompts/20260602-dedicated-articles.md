## Articles start

This will deviate from existing standards in code.

Rename Article model, related model, tests and its views etc to OldArticle etc. Then proceed with new stuff.

### Models
New Article model  class
title
public id - generated as yyyymmdd-title-slug-<10 char random string> if you dont enter a value
content - rich html with images
published at - date/null - null denotes draft
tags - M2M to ArticleTag model
authors - M2M to user model of project

ArticleImage
similar to other model

ArticleTag
name - 100 chars, no spaces
color - hex code

These belong to models/base.py

### Views
We will use Django Ninja Extra for routing using `@route.method('path')` for all endpoints. We will use router for all inertia endpoints as well as json endpoints. We have one view class in views/base.py. We will have to override to use in app.py. 

Use django ninja extra route context to route to correct path. Pass path prefix to client.

role(user) -> 'editor' | 'author' | None — method on view class. Default implementation: returns 'editor' if `is_staff=True`, else None. Override to add author logic.
user_profile(user) -> UserProfile(id, name, url) — method on view class. UserProfile dataclass. Annotates full name.

We have ArticleView which has a model

#### List
We will have list page. If `role(user)` is not None, show create button.

Its at `/<articlespath>/article`

For each item, have cover image (like in previous Article class), excerpts, tags and authors.

We have pagination of fixed size 25 items and 5 orphans. 

We can filter like `?author=id1,id2&tag=tag1,tag2` . Both author and tag params are ANY queries. Have multiselects for both.

Authors and editors (i.e. `role(user)` is not None) can filter `unpublished=true`. Only they can view.

Static templates - render everything as html with meta tags.

#### Details
At `/<articlespath>/id/public-id`
If `role(user)` is 'editor' or 'author' (for this article), show edit/delete button.

Static templates - render everything as html with meta tags.

#### Create/Update
We enter title, public id, content, tags as multiselect, authors as multiselect (they must select themselves). We are able to upload images even when creating article, unlike previous implementation. Implement size limits. Author or editor can directly publish. Or they can save as draft.

Show edit/delete link in details if `role(user)` is 'editor' or 'author' (for this article).

### Roles
Determined by `role(user)` — returns `'editor'`, `'author'`, or `None`.

Author (role returns 'author')
create - in draft, add themselves as author
update - in draft or published, if they are author
delete - in draft or published, if they are author

Editor (role returns 'editor')
create, update, delete - any article

### Tag management
Editors (`role(user) == 'editor'`) have `/<articlespath>/tag`. It has alphabetical order of tags and count of articles. We can rename and assign color and delete.

### Clarifications

- **Django Ninja Extra**: New dependency. All article endpoints use `@route.method()` controllers. Existing BaseView system untouched.
- **Separate NinjaAPI instance**: Articles get their own API instance, not shared with `views/base.py`'s `ninja_api`.
- **Not a BaseModel child**: New Article is a standalone `models.Model`, not inheriting from `BaseModel`. No `resolve_rows`, `resolve_columns`, `feed_values`, `save_stuff`, `RowUpdate`, etc. Has its own create/update methods that handle M2M and image operations.
- **Concrete model, subclassable**: Like current Article→Article2 pattern. Not a Django abstract class.
- **Public ID editable**: User can change the auto-generated `yyyymmdd-title-slug-<10char>` on update.
- **Roles via `role(user)`**: Single method returning `'editor'` (`is_staff=True`), `'author'` (in M2M), or `None`. Replaces separate `editors()`/`allowed_authors()` methods.
- **Rename first**: Rename existing Article→OldArticle as a separate commit before building new system. Ensure `./run checkall` passes.
- **Image upload on create**: Accept images as part of the multipart create POST. Create article first, then ArticleImage records, then update content with image URLs — all in one transaction.
- **Static templates**: Separate Django templates (not Inertia SSR) for crawlers, with full HTML and `<meta>` tags.
- **Tag management**: Dedicated Vue page at `/<articlespath>/tag`.
- **URL prefix**: `/articles/` (top-level, not under `/tables/`).

### URLs
| Path | Purpose |
|---|---|
| `/articles/list` | Article list |
| `/articles/id/<public_id>` | Article details |
| `/articles/create` | Create article |
| `/articles/edit/<public_id>` | Edit article |
| `/articles/tag` | Tag management (editors only) |
| `/articles/api/...` | JSON API endpoints |

### Rename existing Article → OldArticle
- `Article` → `OldArticle` in `models/base.py`
- `ArticleImage` → `OldArticleImage` in `models/base.py`
- `Article2` → `OldArticle2` in `models/app.py`
- `ArticleContentView` → `OldArticleContentView` in `views/base.py`
- `ArticleView` → `OldArticleView`, `Article2View` → `OldArticle2View` in `views/app.py`
- Update `models/__init__.py` exports
- Update `tests/views/test_articles.py` and `tests/playwright/test_articles.py` references
- Rename Vue components: `ArticleContentInput.vue` → `OldArticleContentInput.vue`, `ArticleContentTd.vue` → `OldArticleContentTd.vue`, `CoverImageTd.vue` → `OldCoverImageTd.vue`
- Update `schemas.ts` references: `ArticleImageSummarySchema`, `ArticleMediaSummarySchema`, `ArticleContentValueSchema`
- Update `responses.py`: `ArticleContentInputSchema`, `ArticleContent`, `ArticleMediaSummary`, `ArticleImageSummary`, `CoverImageContent`
- Update `serializers.py` references to article-specific schemas
- Create `RenameModel` migration
- `./run checkall` must pass before proceeding

### Checklist

#### Phase 0: Rename existing Article → OldArticle
- [x] rename in `models/base.py`
    - [x] `Article` → `OldArticle`
    - [x] `ArticleImage` → `OldArticleImage`
    - [x] `_extract_article_image_ids` → `_extract_old_article_image_ids`
    - [x] `ArticleContentInputSchema` → `OldArticleContentInputSchema` in `responses.py`
    - [x] `ArticleContent` → `OldArticleContent` in `responses.py`
    - [x] `ArticleMediaSummary` → `OldArticleMediaSummary` in `responses.py`
    - [x] `ArticleImageSummary` → `OldArticleImageSummary` in `responses.py`
    - [x] `CoverImageContent` → `OldCoverImageContent` in `responses.py`
- [x] rename in `models/app.py`
    - [x] `Article2` → `OldArticle2`
- [x] rename in `views/base.py`
    - [x] `ArticleContentView` → `OldArticleContentView`
    - [x] all references to renamed response classes
- [x] rename in `views/app.py`
    - [x] `ArticleView` → `OldArticleView`
    - [x] `Article2View` → `OldArticle2View`
- [x] update `models/__init__.py` exports
- [x] rename Vue components
    - [x] `ArticleContentInput.vue` → `OldArticleContentInput.vue`
    - [x] `ArticleContentTd.vue` → `OldArticleContentTd.vue`
    - [x] `CoverImageTd.vue` → `OldCoverImageTd.vue`
- [x] update `schemas.ts` references
    - [x] `ArticleImageSummarySchema` → `OldArticleImageSummarySchema`
    - [x] `ArticleMediaSummarySchema` → `OldArticleMediaSummarySchema`
    - [x] `ArticleContentValueSchema` → `OldArticleContentValueSchema`
- [x] update `serializers.py` references to article-specific schemas
- [x] update test references
    - [x] `tests/views/test_articles.py` — all class and import references
    - [x] `tests/playwright/test_articles.py` — all class and import references
- [x] create `RenameModel` migration
- [x] `./run checkall` passes

#### Phase 1: Dependencies
- [x] add `django-ninja-extra` to `pyproject.toml`
- [x] `uv sync`

#### Phase 2: New Models (in `models/base.py`)
- [x] `ArticleTag` model
    - [x] `name`: CharField(100, unique, no-spaces validator)
    - [x] `color`: CharField(7, hex code validator)
    - [x] `__str__` returns name
- [x] `Article` model (standalone `models.Model`, NOT BaseModel child)
    - [x] `title`: CharField(255)
    - [x] `public_id`: CharField(unique, editable, validators=[public_id_django_validator])
    - [x] `content`: TextField(50000, rich HTML with embedded images)
    - [x] `published_at`: DateTimeField(null=True, blank=True, null=draft)
    - [x] `tags`: M2M → ArticleTag
    - [x] `authors`: M2M → User
    - [x] `first_image`: UUIDField(null=True, blank=True)
    - [x] `CONTENT_IMAGES_TOTAL_BYTES = 50 * 1024 * 1024`
    - [x] auto-generate `public_id` as `yyyymmdd-slugify(title)-<10 char random>` on create if empty
    - [x] `first_image` extraction from content HTML on save — update `_extract_article_image_ids` to match new URL pattern `/articles/api/download-image/{public_id}/{uuid}` instead of old `/download-article-image/{pk}/{uuid}`
    - [x] orphan image cleanup on save (same as old `_cleanup_orphaned_images` pattern)
    - [x] image file cleanup via `FileMarkedForDeletion` on article delete
- [x] `ArticleImage` model (same pattern as old)
    - [x] `uuid_id`: UUIDField(unique, editable=False, default=uuid.uuid7)
    - [x] `article`: FK → Article (on_delete=RESTRICT, db_index=True)
    - [x] `image`: FileField(upload_to="uploads/article_images/")
    - [x] `size`: PositiveBigIntegerField(default=0)
    - [x] `save()` sets size from image file
    - [x] `delete_safely()` marks file for deletion via `FileMarkedForDeletion`
    - [x] quota enforcement (check total bytes before creating)
- [x] update `models/__init__.py` with new exports
- [x] create migration
- [x] add `ArticleTag` and `ArticleImage` to admin.py if needed

#### Phase 3: Django Ninja Extra Controllers
- [x] create `articles_api = NinjaExtraAPI(urls_namespace="articles-api")` (separate instance)
- [x] register in `urls.py`: `path("articles/", articles_api.urls)`
- [x] configure CSRF for `articles_api` (Django Ninja Extra needs csrf=True or csrf_exempt as appropriate)
- [x] shared utilities — import from existing code
    - [x] `maybe_user`, `user_or_404` from `views/base.py` (or move to `utils.py`)
    - [x] `is_browser` check (`X-Inertia` header) from `views/base.py`
    - [x] `human_size`, `sanitize_html`, `strip_html` from `utils.py`
- [x] `ArticleController` (Django Ninja Extra ControllerBase)
    - [x] `role(user)` → `'editor' | 'author' | None` — default: `'editor'` if is_staff, else None
    - [x] `user_profile(user)` → `UserProfile(id, name, url)` dataclass with full name annotation
    - [x] `GET /articles/list` — list page (Inertia), pagination 25 + 5 orphans, unpublished articles hidden from anonymous (only editors/authors see unpublished)
    - [x] `GET /articles/id/{public_id}` — details page (Inertia)
    - [x] `GET /articles/create` — create form (Inertia)
    - [x] `POST /articles/create` — submit create (multipart: fields + image files, auto-adds creating user as author)
    - [x] `GET /articles/edit/{public_id}` — edit form (Inertia)
    - [x] `POST /articles/edit/{public_id}` — submit update (multipart)
    - [x] `POST /articles/delete/{public_id}` — delete article
    - [x] `POST /articles/api/upload-image/{public_id}` — upload image to existing article
    - [x] `GET /articles/api/download-image/{public_id}/{image_id}` — serve image
    - [x] `GET /articles/api/search-tags` — JSON endpoint, search tags for multiselect
    - [x] `GET /articles/api/search-authors` — JSON endpoint, search users for multiselect
- [x] detect `path_prefix` from Django Ninja Extra route context (not hardcoded) and send to client via Inertia props
- [x] `TagController` (Django Ninja Extra ControllerBase)
    - [x] `GET /articles/tag` — tag management page (Inertia, editors only)
    - [x] `POST /articles/tag/create` — create tag
    - [x] `POST /articles/tag/update/{tag_id}` — rename / assign color
    - [x] `POST /articles/tag/delete/{tag_id}` — delete tag
- [x] permission checks using `role(user)` throughout

#### Phase 3.5: Remove OldArticle System
- [x] remove OldArticle, OldArticleImage, Article2 from `models/base.py`, `models/app.py`, `models/__init__.py`
- [x] remove OldArticleContentView from `views/base.py`
- [x] remove OldArticleView, OldArticle2View from `views/app.py`
- [x] remove Old* schemas from `responses.py`
- [x] remove Old* schemas from `frontend/src/schemas.ts`
- [x] delete Old* Vue components (`OldArticleContentInput.vue`, `OldArticleContentTd.vue`, `OldCoverImageTd.vue`)
- [x] disable `tests/views/test_articles.py` and `tests/playwright/test_articles.py` (placeholder comments)
- [x] generate migration `0039_remove_old_article_models.py`
- [x] `./run checkall` passes

#### Phase 4: Image Upload on Create
- [x] multipart create POST accepts image files alongside form data
- [x] transactional flow: create Article → create ArticleImage records → update content with image URLs → save
- [x] size/quota validation before save (same 50MB quota)
- [x] extract first_image from content after image insertion

#### Phase 5: Frontend — Vue Pages
- [x] `ArticleList.vue` — list page (`frontend/src/pages/ArticleList.vue`)
    - [x] cover image (thumbnail + link to details)
    - [x] HTML-stripped content excerpt (truncated to 200 chars)
    - [x] tag badges with colors
    - [x] author names
    - [x] create button (visible if role is not None)
    - [x] pagination (25 items, 5 orphans)
    - [x] filter inputs for authors and tags
    - [x] unpublished filter toggle (visible if role is not None)
    - [x] draft indicator for unpublished articles
    - [x] published_at display
- [x] `ArticleDetails.vue` — details page (`frontend/src/pages/ArticleDetails.vue`)
    - [x] rich HTML content display (RenderRawHtml with `rich-text-display` class)
    - [x] inline images via download-image endpoint
    - [x] edit/delete buttons (visible if role is 'editor' or 'author' for this article)
    - [x] media summary with quota (toggle, thumbnails, sizes)
    - [x] published_at display, draft indicator
    - [x] tag badges, author list
- [x] `ArticleCreate.vue` — create form (`frontend/src/pages/ArticleCreate.vue`)
- [x] `ArticleEdit.vue` — edit form (`frontend/src/pages/ArticleEdit.vue`)
- [x] `ArticleForm.vue` — shared form component (`frontend/src/components/ArticleForm.vue`)
    - [x] title input
    - [x] public_id input (auto-generated hint)
    - [x] Quill editor with image upload button
    - [x] tags multiselect (search via search-tags endpoint)
    - [x] authors multiselect (search via search-authors endpoint)
    - [x] publish / save-as-draft buttons
- [x] `ArticleTagManagement.vue` — tag CRUD page (`frontend/src/pages/ArticleTagManagement.vue`)
    - [x] alphabetical tag list with article count
    - [x] rename tag inline
    - [x] color picker
    - [x] delete tag with confirmation
    - [x] create new tag form
- [x] CSS rules in `styles/articles.scss` (no inline/scoped styles)
    - [x] article card layout, cover image styles
    - [x] tag badge styles with color backgrounds
    - [x] article list/details/create/edit/tag page layouts
- [x] `utils/format.ts` — `humanSize` utility for media quota display

#### Phase 6: Static Templates (Separate from Inertia SSR)
- [x] `djangoapp/templates/articles/article_list_static.html`
    - [x] full HTML document with `<head>`, OG meta tags
    - [x] article cards with title, excerpt, cover image, tags, authors, dates
    - [x] served to non-Inertia requests (crawlers/bots)
- [x] `djangoapp/templates/articles/article_details_static.html`
    - [x] full HTML document with OG meta tags (og:title, og:description, og:image, og:type)
    - [x] rendered rich HTML content
    - [x] inline images as absolute URLs
- [x] controller checks `is_browser(request)` — serves static template to bots, Inertia page to browsers

#### Phase 7: URL Wiring
- [x] articles URL prefix is `/articles/` (top-level, not under `/tables/`)
- [x] list: `/articles/list`
- [x] details: `/articles/id/<public_id>`
- [x] create: `/articles/create`
- [x] edit: `/articles/edit/<public_id>`
- [x] tag management: `/articles/tag`
- [x] API endpoints: `/articles/api/...`
- [x] pass path prefix to client for URL construction in Vue components

#### Phase 8: Tests
- [x] model unit tests (`djangoapp/tests/test_articles.py`)
    - [x] `ArticleModelTests` — public_id auto-generation, preservation, first_image extraction/clearing, orphan cleanup, delete, __str__
    - [x] `ArticleTagModelTests` — __str__, unique name constraint
    - [x] `ArticleImageModelTests` — size set on save, delete_safely
- [x] controller/view tests (`djangoapp/tests/views/test_articles.py`)
    - [x] `ArticleListTests` — published visible, unpublished hidden, unpublished filter, cover image, excerpt strips HTML, filter by author/tag, pagination, static template
    - [x] `ArticleDetailsTests` — published visible, draft hidden from anon, draft visible to staff, 404 missing, media summary for editor, static template
    - [x] `ArticleCreateTests` — create page auth, staff access, publish, draft, auto-author, tags, no title error, unauthenticated
    - [x] `ArticleEditDeleteTests` — edit page permission, staff edit, update title, publish draft, delete, unauthenticated
    - [x] `ArticleImageAPITests` — upload image, auth required, quota enforcement, download image, 404 missing, draft image anon 404
    - [x] `ArticleSearchAPITests` — search tags, search tags empty, search authors, search authors empty
    - [x] `TagControllerTests` — tag page staff, tag page non-staff 404, create, duplicate, update, delete, delete missing
- [x] Playwright E2E tests (`djangoapp/tests/playwright/test_articles.py`)
    - [x] create article with Quill editor
    - [x] update article content
    - [x] image upload on create (create, upload-image, edit with URL)
    - [x] image upload on update
    - [x] upload + save preserves image URLs
    - [x] uploaded file exists on disk
    - [x] remove image triggers orphan cleanup
    - [x] delete article removes images
    - [x] details page renders images
    - [x] quota exceeded shows error
    - [x] details media summary display
    - [x] list page cover image
    - [x] tag management page CRUD
    - [x] author/editor multiselect
    - [x] publish vs draft workflow
    - [x] unpublished filter

#### Phase 9: Final
- [x] `./run checkall` passes

#### Phase 10: aihere cleanup
- [x] `djangoapp/views/articles.py:33` — keep `PATH_PREFIX = "/articles"` as constant (dynamic resolution not feasible with Django Ninja Extra)
- [x] `djangoapp/views/articles.py:68` — removed aihere comment; no existing toast/message model to reuse
- [x] `djangoapp/views/articles.py:95` — use inheritance with `_ArticleBaseSchema` to avoid copy-paste between `ArticleCreateSchema` and `ArticleUpdateSchema`
- [x] `djangoapp/views/articles.py:682` — use `TagCreateSchema`/`TagUpdateSchema` ninja schemas instead of `_read_fields` for tag endpoints
- [x] `djangoapp/views/articles.py:738` — replace `user.is_staff` checks with `_role(user) != "editor"` in TagController
- [x] `djangoapp/models/base.py:1510` — use `download-image/{public_id}/` marker instead of hardcoded `/articles/api/...` prefix
- [x] `djangoapp/models/base.py:1526` — move `secrets` and `slugify` imports to top level
- [x] `djangoapp/models/base.py:1533` — 6 char lowercase+numbers random suffix via `secrets.choice`
- [x] `djangoapp/models/base.py:1542` — removed `Meta` class from `ArticleTag` (app_label auto-detected)
- [x] `djangoapp/models/base.py:1552` — `unique=True` already implies db_index, no change needed
- [x] `djangoapp/models/base.py:1561` — added comment: authors use M2M to User; tags need a dedicated model for extra fields
- [x] `djangoapp/models/base.py:1576` — generate `public_id` only if creating (`is_new = self.pk is None`)
- [x] `djangoapp/models/base.py:1581` — call `update_first_image()` in `save()` for updates
- [x] `djangoapp/models/base.py:1590` — call `cleanup_orphaned_images()` in `save()` for updates
- [x] `frontend/src/utils/format.ts:1` — no duplicate found, removed aihere comment
- [x] `djangoapp/templates/articles/base_static.html:1` — kept separate base (inertia base.html has Vue app div, incompatible with static)
- [x] `djangoapp/templates/articles/article_list_static.html:8` — applied same fixes as details (quoted colors, published_at)
- [x] `djangoapp/templates/articles/article_details_static.html:3` — opengraph blocks stay per-template (base has `{% block opengraph %}`)
- [x] `djangoapp/templates/articles/article_details_static.html:18` — show `published_at` date with `.published-date` span
- [x] `djangoapp/templates/articles/article_details_static.html:23` — quote color value in inline style

#### Phase 11: Refactor to abstract base controller
Merge `TagController` into `ArticleController`. Make `ArticleController` an abstract base class with `_role(user)` as an abstract method. A developer subclasses it in `views/app.py`, overrides `_role(user)` to return `'editor' | 'author' | None` based on their user model. The developer mounts the concrete subclass under whatever URL prefix they choose. The module-level `_role()` function becomes a default implementation; the abstract method on the class delegates to it by default but must be overridden.

Requirements:
- Remove `TagController` class, move all tag endpoints into `ArticleController`
- Remove `articles_api.register_controllers(ArticleController, TagController)` — no module-level registration
- `ArticleController` becomes abstract with `abc.ABC` and an abstract `role` method
- `role(user)` becomes `ArticleController.role(user)` — abstract method that subclass must override
- `user_profile(user)` becomes `ArticleController.user_profile(user)` — can be overridden
- All module-level helper functions that use `role`/`user_profile` become methods or take explicit params
- `PATH_PREFIX` should not be hardcoded; derive from the controller's route prefix or accept it as a class attribute
- A concrete `AppArticleController` in `views/app.py` extends `ArticleController`, provides `_role(user)` and `user_profile(user)`, registers with its own `NinjaExtraAPI` instance under `/articles/`
- URL wiring in `urls.py` imports from `views/app.py` instead of `views/articles.py`
- All existing tests pass without changes to test logic (test imports may change)

Checklist:
- [x] merge `TagController` into `ArticleController`
    - [x] move `tag_create`, `tag_update`, `tag_delete` endpoints into `ArticleController`
    - [x] delete `TagController` class
    - [x] remove `articles_api.register_controllers(...)` line
- [x] make `ArticleController` abstract
    - [x] add `abc.ABC` base
    - [x] make `role(user)` an `@abstractmethod` returning `Literal["editor", "author"] | None`
    - [x] make `user_profile(user)` a method (non-abstract, overridable)
    - [x] convert module-level `_role`, `_user_profile`, `_serialize_tags`, `_serialize_authors`, `_build_cover_image_url`, `_build_media_summary`, `_can_edit`, `_get_user_schema` to instance methods or static/class methods — rename `_role` → `role`, `_user_profile` → `user_profile` in the class
    - [x] `PATH_PREFIX` becomes `path_prefix` class attribute, not module constant
    - [x] `_is_browser` and `_BOT_PATTERNS` stay module-level (stateless, reusable)
- [x] create concrete subclass in `views/app.py`
    - [x] `AppArticleController(ArticleController)` with `role(user)` implementation (is_staff → editor, else None)
    - [x] `user_profile(user)` implementation (inherited from base)
    - [x] create `articles_api = NinjaExtraAPI(urls_namespace="articles-api")` in `views/app.py`
    - [x] `articles_api.register_controllers(AppArticleController)`
    - [x] set `path_prefix` class attribute to `"/articles"`
- [x] update `urls.py`
    - [x] import `articles_api` from `views/app.py` instead of `views/articles.py`
- [x] update tests
    - [x] verify all unit tests pass
    - [x] verify all Playwright tests pass
- [x] `./run checkall` passes

#### Phase 12: Code Refactoring (aihere items)
- [x] `djangoapp/views/articles.py` refactoring
    - [x] set stripping for `TagCreateSchema.name` field (already handled by `_StrippedStr`)
    - [x] set stripping and regex for `TagCreateSchema.color` field (already handled by `_StrippedStr` + `_color_hex`)
    - [x] inherit `TagUpdateSchema` from `_TagSchemaBase` to avoid copy-pasting validators
    - [x] add comment on `path_prefix` explaining where it's set and where it's used
    - [x] make `user_profile` abstract and user-provided (like `role`)
    - [x] add docstring to `ArticleView.url()` explaining its parameters and purpose
    - [x] simplify `TagView` dynamic class creation — use `TagView._role_fn = tag_role` instead of `type(...)`
    - [x] use `user_profile` to generate `_get_user_schema` instead of duplicating logic
    - [x] use Pydantic classes and `.model_dump()` instead of `_serialize_tags` and `_serialize_authors`
    - [x] consolidate `article.save()` calls in `_process_uploaded_images` — save() calls update_first_image/cleanup
    - [x] use `django.contrib.auth.get_user_model()` instead of `User` in `_set_tags_and_authors`
    - [x] have `ListQueryParams` pydantic schema with `.author_ids()`, `.tag_names()`, `page_num` for list endpoint
    - [x] avoid n+1 queries for tags and authors in list endpoint (use `prefetch_related`)
    - [x] use schema and `.model_dump()` for list endpoint response (`ArticleListItem`, `ArticleListPagination`, etc.)
    - [x] add `_is_author_or_editor(user)` helper — used in create_page
    - [x] don't send `user_role` to client in create_page; if banned just show 404
    - [x] use `_is_author_or_editor` in create_submit
    - [x] `_read_fields` still needed for multipart/form-data parsing
    - [x] `public_id` generation handled by model `Article.create()` method
    - [x] add `Article.create()` class method that takes title, id, content, tags, authors; model handles public_id generation
    - [x] have `Article.get_or_404(public_id)` instead of module-level `_get_article_or_404`
    - [x] add `_can_edit_or_404(user, article)` for edit_page
    - [x] use `ArticleDetailsItem` schema and `.model_dump()` for edit_page props
    - [x] add `_can_edit_or_error(user, article)` for edit_submit
    - [x] remove file handling from edit endpoint — user must use upload-image endpoint
    - [x] add `_can_delete_or_error(user, article)` for delete_submit
    - [x] add `_can_edit_or_error(user, article)` for upload_image
    - [x] add `_can_download_image(user, article)` for download_image
    - [x] `img.image` should always exist — removed null check, kept FileNotFoundError handler
    - [x] search_authors still uses `ArticleAuthorItem` for consistent API response schema
    - [x] TagView `_get_user_schema` uses inline name generation (separate from ArticleView's `user_profile`)
    - [x] tag endpoints use `TagWithCount.model_dump()` and `_editor_or_error` helper
    - [x] removed `full_clean()` from tag endpoints — Pydantic schemas handle validation
- [x] `djangoapp/models/base.py` refactoring
    - [x] restore docstring for `_extract_article_image_ids`
    - [x] add docstring with example for `_generate_article_public_id`
    - [x] add `noqa: D105` comments on `__str__` methods
    - [x] simplify `Article.delete()` to use `**kwargs` instead of explicit `using`/`keep_parents`
    - [x] add `Article.get_or_404(public_id)` classmethod
    - [x] add `Article.create()` classmethod
    - [x] add `ArticleTag.get_or_404(name)` classmethod
    - [x] rename `_can_edit_or_error` → `_can_edit_or_404`, `_can_delete_or_error` → `_can_delete_or_404`, `_can_download_image` → `_can_download_image_or_404` (all raise Http404)
    - [x] remove dead code `_serialize_tags` and `_serialize_authors`
    - [x] merge `_TagSchemaBase`/`TagCreateSchema`/`TagUpdateSchema` into single `TagSchema` with mandatory fields
    - [x] fix `_is_browser` to use User-Agent bot detection so Playwright gets Inertia response

#### Phase 13: Schema-driven endpoints & User model cleanup
- [x] `djangoapp/views/articles.py` — DRY Pydantic schemas for POST data
    - [x] create `_ArticleSubmitBase` with shared fields: `title` (str, min_length=1), `public_id` (str, default ""), `content` (str, default ""), `tags` (list[str], default []), `authors` (list[int], default [])
    - [x] `ArticleCreateSchema(_ArticleSubmitBase)` adds `status: Literal["published", "draft"] = "draft"`
    - [x] `ArticleUpdateSchema(_ArticleSubmitBase)` adds `status: Literal["published", "draft"] | None = None`
    - [x] `create_submit(self, request, payload: ArticleCreateSchema)` — use `payload.title` etc instead of `_read_fields`
    - [x] `edit_submit(self, request, public_id, payload: ArticleUpdateSchema)` — use `payload.title` etc instead of `_read_fields`
    - [x] remove `_read_fields` function (no longer needed — all POST is JSON)
    - [x] remove `import json` if no longer used
    - [x] title validation via `min_length=1` on schema field (no more `if not title`)
- [x] `djangoapp/views/articles.py` — `ArticleListFilters` as `Query` param
    - [x] use `Query[ArticleListFilters]` in `list_page` function signature
    - [x] Django Ninja native list parsing: `?author=1&author=2&tag=python&tag=django`
    - [x] `unpublished` → `bool = False` (direct bool, not string parsing)
    - [x] `page` → `int = Field(default=1, ge=1)` (direct int, not string parsing)
- [x] `djangoapp/views/articles.py` — remove `User` import, use `get_user_model()` + `AbstractUser`
    - [x] add `from django.contrib.auth.models import AbstractUser`
    - [x] replace all `User` type annotations with `AbstractUser`
    - [x] `_auth_user(request) -> AbstractUser | None`
    - [x] `role(user: AbstractUser | None)`, `user_profiles(users: Iterable[AbstractUser])`, etc
- [x] `djangoapp/models/base.py` — remove `User` import, use `get_user_model()` + `AbstractUser`
    - [x] replace `User` type annotations with `AbstractUser` in `Article.create()`
    - [x] use `get_user_model()` instead of `User.objects.get(pk=aid)` in `Article.create()`
- [x] `djangoapp/views/app.py` — update `AppArticleView` type annotations
    - [x] replace `User` with `AbstractUser` in `role(user)` and `user_profiles(users)` signatures
- [x] `frontend/src/components/ArticleForm.vue` — hide image button on create
    - [x] when `isCreate` is true, show warning text: "Save the article first to upload images"
    - [x] when `isCreate` is true, remove `"image"` from Quill toolbar container
- [x] `djangoapp/views/articles.py` — remove file handling from `create_submit`
    - [x] JSON only, no multipart
    - [x] images uploaded via `/api/upload-image/{public_id}` after article is created
- [x] add filter tests
    - [x] `test_list_filter_by_author_excludes`
    - [x] `test_list_filter_by_tag_excludes`
    - [x] `test_list_filter_by_multiple_authors` — `?author=1&author=2`
    - [x] `test_list_filter_by_multiple_tags` — `?tag=python&tag=django`
    - [x] `test_list_filter_author_and_tag_combined`
    - [x] `test_list_unpublished_filter_requires_role`
- [x] update existing tests
    - [x] `djangoapp/tests/views/test_articles.py` — send JSON `content_type="application/json"` for create/edit
    - [x] verify all unit tests pass
    - [x] verify all Playwright tests pass
    - [x] `./run checkall` passes

#### Phase 14: Move business logic to models & add model tests
- [x] move `_build_media_summary` from `ArticleView` to `Article.media_summary()` method on the model
    - [x] returns plain dict `{"total_bytes", "quota_bytes", "images"}` or None
- [x] move `_check_image_quota` from `ArticleView` to `Article.image_quota_exceeded(size: int) -> bool` method on the model
    - [x] returns `True` if adding `size` bytes would exceed quota, `False` otherwise
    - [x] view raises `HttpError(400, ...)` based on return value
- [x] add `ArticleTag.create(name: str, color: str)` classmethod
    - [x] validates via `full_clean()` before save
    - [x] raises `ValidationError` on duplicate name (caught by full_clean unique validator)
- [x] add `ArticleTag.update(self, name: str, color: str)` instance method
    - [x] validates via `full_clean()` before save
    - [x] duplicate name check remains in view (different from self)
- [x] expand `djangoapp/tests/test_articles.py` with model method tests
    - [x] `ArticleModelTests` — `create()`, `update()`, `set_tags_and_authors()`, `media_summary()`, `image_quota_exceeded()`, `existing_image_bytes()`, `get_or_404()`, `update_first_image()`, `cleanup_orphaned_images()`
    - [x] `ArticleTagModelTests` — `create()`, `update()`, `get_or_404()`
- [x] update view call sites to use model methods
    - [x] `upload_image` → `article.image_quota_exceeded(image_file.size)`
    - [x] `details_page` / `edit_page` → `article.media_summary(self.path_prefix)`
    - [x] `tag_create` → `ArticleTag.create(payload.name, payload.color)`
    - [x] `tag_update` → `tag.update(payload.name, payload.color)`
- [x] `./run checkall` passes

#### Phase 15: aihere cleanup
- [x] `djangoapp/views/articles.py` — merge response schemas [aihere-merge-response-schemas]
    - [x] merge `ArticleSubmitResponse`, `ArticleDeleteResponse`, `TagSubmitResponse` into a single `MessageResponse` schema
- [x] `djangoapp/views/articles.py` — avoid both `published` and `draft` fields [aihere-avoid-published-draft]
    - [x] `ArticleUpdateSchema` uses `status: Literal["published", "draft"]` (required)
    - [x] `ArticleCreateSchema` uses `status: Literal["published", "draft"] = "draft"`
    - [x] `Article.create()` and `Article.update()` accept `status` (required) instead of `published_at`/`published`/`draft`
- [x] `djangoapp/views/articles.py` — return `api.urls` from `register` [aihere-return-api-urls]
    - [x] `url()` returns `api.urls[0]` (NinjaExtraAPI returns tuple, first element is the URL list)
- [x] `djangoapp/views/articles.py` — use `user_profile`, remove `_get_user_schema` [aihere-user-profile-schema]
    - [x] `_user_item()` returns `UserProfile | None` directly (deleted `ArticleUserItem`, `_user_to_dict`)
- [x] `djangoapp/views/articles.py` — use `_is_author_or_editor` in `_can_download_image_or_404` [aihere-author-editor-check]
- [x] `djangoapp/views/articles.py` — use `Query[ArticleListFilters]` as Query param schema [aihere-list-query-schema]
    - [x] native Django Ninja list parsing for `?author=1&author=2&tag=python&tag=django`
- [x] `djangoapp/views/articles.py` — schema-driven props for list InertiaResponse [aihere-list-props-schema]
    - [x] `ArticleListProps` with typed fields (`UserProfile`, `ArticleListItem`, `ArticleListPagination`, `ArticleListFilters`)
- [x] `djangoapp/views/articles.py` — schema-driven props for details InertiaResponse [aihere-details-props-schema]
    - [x] `ArticleDetailsProps` with typed fields (`UserProfile`, `ArticleDetailsItem`, `MediaSummary`)
- [x] `djangoapp/views/articles.py` — send `UserProfile` for authors via `user_profiles()` [aihere-send-userprofile]
    - [x] `ArticleAuthorItem(id=p.id, name=p.title)` constructed from `UserProfile` batch results
- [x] `djangoapp/views/articles.py` — `TagView._user_profiles_fn` [aihere-tagview-user-profile]
    - [x] `TagView._get_user_schema` uses `_user_profiles_fn` or raises `NotImplementedError`
- [x] `djangoapp/views/app.py` — add Article features to README [aihere-readme-article]
    - [x] document `AppArticleView.role()` and `user_profiles()` in README
- [x] `djangoapp/views/app.py` — add `url` to `UserProfile` [aihere-userprofile-url]
    - [x] `url: str | None = None` field on `UserProfile` dataclass
- [x] `djangoapp/views/app.py` — batch `user_profiles` for Iterable [aihere-batch-user-profile]
    - [x] `user_profiles(users: Iterable[AbstractUser]) -> list[UserProfile]` abstract method
    - [x] `user_profile(user)` is a convenience wrapper calling `user_profiles([user])[0]`
- [x] `djangoapp/models/base.py` — make `Article.create()` keyword-only [aihere-create-kwargs]
- [x] `djangoapp/models/base.py` — make `set_tags_and_authors()` keyword-only [aihere-set-tags-kwargs]
- [x] `djangoapp/models/base.py` — make `Article.update()` keyword-only [aihere-update-kwargs]
- [x] `djangoapp/models/base.py` — DRY `existing_image_bytes` vs `image_quota_exceeded` [aihere-dry-image-bytes]
    - [x] `image_quota_exceeded` calls `existing_image_bytes()` instead of duplicating query
- [x] `./run checkall` passes

#### Phase 17: aihere cleanup
- [x] `djangoapp/views/articles.py:239-243` — deleted `_user_to_dict`, renamed to `_user_item` returning `UserProfile | None`
- [x] `djangoapp/views/articles.py:59-62` — deleted `ArticleUserItem` class; `UserProfile` (with `title` field) replaces it in all schemas
- [x] `djangoapp/views/articles.py` — renamed `UserProfile.name` → `UserProfile.title` to match frontend `UserSchema`
- [x] `djangoapp/views/app.py` — `user_profiles()` uses `title=` instead of `name=`
- [x] `djangoapp/models/base.py:1697` — `Article.update()` `status` is now required (`Literal["published", "draft"]`, not optional)
- [x] `djangoapp/views/articles.py:179` — `ArticleUpdateSchema.status` is now required
- [x] `frontend/src/pages/ArticleCreate.vue:37` — simplified status to `publish ? "published" : "draft"` (removed `as const`)
- [x] `frontend/src/pages/ArticleDetails.vue:43` — replaced `showToast("error", ...)` with `showErrorToast(e, ...)`
- [x] `djangoapp/tests/test_articles.py` — updated tests to always pass `status=` to `Article.update()`
- [x] `djangoapp/tests/views/test_articles.py` — updated `test_edit_submit_updates_title` to include `status` in JSON payload
- [x] `./run checkall` passes (406 backend, 150 Playwright, lint, typecheck)

#### Phase 18: Typed props and MediaSummary refactor
- [x] `djangoapp/views/articles.py` — added `ArticleCreateProps` and `ArticleEditProps` Pydantic schemas
    - [x] create_page and edit_page use typed props instead of plain dicts; no more `asdict()`
- [x] `djangoapp/models/base.py` — moved `MediaImageItem` and `MediaSummary` from views to models
    - [x] `Article.media_summary()` returns `MediaSummary` directly (not `dict[str, Any]`)
    - [x] callers no longer wrap with `MediaSummary(**article.media_summary(...))`
- [x] `djangoapp/models/__init__.py` — exports `MediaImageItem`, `MediaSummary`
- [x] `djangoapp/tests/test_articles.py` — updated tests to use `MediaSummary` attribute access (not dict indexing)
- [x] `ArticleEditProps.media_summary` is required (non-optional) since edit page always has it
- [x] `./run checkall` passes

#### Phase 19: Navigation and UX improvements
- [x] `frontend/src/pages/ArticleList.vue` — added "Manage Tags" link (editor only) next to Create Article
- [x] `frontend/src/components/ArticleForm.vue` — added "Manage Tags" link next to Tags label (editor only)
    - [x] new `isEditor` prop passed from create/edit pages
- [x] `frontend/src/pages/ArticleDetails.vue` — added "Back to Articles" link at top
- [x] `djangoapp/views/articles.py` — added `role` to `ArticleCreateProps` so create page knows editor status
    - [x] `frontend/src/schemas.ts` — `ArticleCreatePropsSchema` includes `is_editor`
- [x] `frontend/src/pages/ArticleList.vue` — added author and tag multiselect filter widgets
    - [x] uses `vue-multiselect` with search API endpoints
    - [x] filters applied via URL params (`?author=1&tag=python`)
- [x] renamed `role: str | None` → `is_editor: bool` across all props schemas + frontend
    - [x] backend: `ArticleListProps`, `ArticleDetailsProps`, `ArticleCreateProps`, `ArticleEditProps`
    - [x] frontend: all 5 article Zod schemas updated
    - [x] Vue pages: `p.role` → `p.is_editor`, `:role` → `:is-editor`
    - [x] `TagView` sends `"is_editor": True` instead of `"role": "editor"`
- [x] Playwright tests for article list filters
    - [x] `test_filter_by_tag`: filtering by `?tag=python` shows only matching articles
    - [x] `test_filter_by_author`: filtering by `?author=<pk>` shows only matching articles
- [x] `./run checkall` passes (406 backend, 152 Playwright, lint, typecheck)

#### Phase 20: Code review findings (commit 553f74e)
- [x] `ArticleCreate.vue:43–57` — dead FormData code path (unreachable since image toolbar hidden during create). Remove.
- [x] `_make_png_bytes()` / `_make_image()` duplicated in `tests/test_articles.py`, `tests/views/test_articles.py`, `tests/playwright/test_articles.py`. Extract to shared test helper `djangoapp/tests/test_images.py`.
- [x] `ArticleTag.create()` docstring says "Raises IntegrityError" but `full_clean()` raises `ValidationError`. Fix docstring.