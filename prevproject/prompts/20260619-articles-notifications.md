## Replace publish/draft buttons with a published checkbox

In articles, we should not have a "Save as Draft" button. Instead, the create/edit form has a checkbox that sets the published date. A single "Save" button submits the form; whether the article is published is controlled entirely by the checkbox.

References: `prompts/20260602-dedicated-articles.md` (Article model `published_at`, Create/Update section, Roles).

### Plan

- The form's publish/draft state becomes a boolean `isPublished`, not a `publish` arg passed via the `submit` event. It lives in the reactive `ArticleFormData` (same pattern as `isCommentingEnabled`).
- Single "Save" button replaces the current "Publish" and "Save as Draft" buttons.
- A "Publish" switch (reuse the `form-check form-switch` style used by "Enable comments") binds to `form.isPublished`.
- Backend replaces `status: Literal["published", "draft"]` with `published: bool` in both submit schemas and in `Article.create()` / `Article.update()`. The existing date semantics are preserved:
  - `published=True` and `published_at is None` -> set `published_at = now`
  - `published=True` and `published_at` set -> keep the original date (do not bump it on re-save)
  - `published=False` -> `published_at = None`
- `published_at` (not a status string) remains the source of truth for draft/published display on list/details pages, so no display logic changes.
- `Literal` import stays (still used by `sort_by`, `role()`, etc. in both files).

### Checklist

#### Phase 21: Published checkbox

- [x] backend schemas (`djangoapp/views/articles.py`)
    - [x] `ArticleCreateSchema.status: Literal["published", "draft"] = "draft"` -> `published: bool = False`
    - [x] `ArticleUpdateSchema.status: Literal["published", "draft"]` -> `published: bool`
- [x] backend views (`djangoapp/views/articles.py`)
    - [x] `create_submit`: `status=payload.status` -> `published=payload.published` in `Article.create(...)`
    - [x] `edit_submit`: `status=payload.status` -> `published=payload.published` in `article.update(...)`
- [x] model (`djangoapp/models/base.py`)
    - [x] `Article.create()`: `status: Literal["published", "draft"] = "draft"` -> `published: bool = False`; body `published_at = timezone.now() if published else None`
    - [x] `Article.update()`: `status: Literal["published", "draft"]` -> `published: bool`; body keeps existing logic (`if published and self.published_at is None: set now; elif not published: clear`)
- [x] frontend form data (`frontend/src/schemas.ts`)
    - [x] add `isPublished: boolean` to `ArticleFormData`
- [x] frontend component (`frontend/src/components/ArticleForm.vue`)
    - [x] add a "Publish" switch (`form-check form-switch`, id `publishedCheckbox`) bound to `form.isPublished`, alongside the "Enable comments" switch
    - [x] remove the "Publish" and "Save as Draft" buttons
    - [x] add a single "Save" button (label "Saving..." while submitting)
    - [x] change emit signature from `submit: [publish: boolean]` to `submit: []`
- [x] frontend pages
    - [x] `ArticleCreate.vue`: init `form.isPublished = false`; `onSubmit()` sends `published: form.isPublished`; drop the `publish` param
    - [x] `ArticleEdit.vue`: init `form.isPublished = !!p.article.published_at`; `onSubmit()` sends `published: form.isPublished`; drop the `publish` param
- [x] unit tests (`djangoapp/tests/test_articles.py`)
    - [x] replace `status="published"` with `published=True` and `status="draft"` with `published=False` in all `Article.create()` / `Article.update()` calls
    - [x] update the `ArticleModelTests` class docstring bullet lines that mention `status=`
- [x] view tests (`djangoapp/tests/views/test_articles.py`)
    - [x] JSON payloads: `"status": "published"` -> `"published": true`, `"status": "draft"` -> `"published": false`
- [x] playwright tests (`djangoapp/tests/playwright/test_articles.py`)
    - [x] JSON payloads: `"status": "published"` -> `"published": true`
    - [x] `status="published"` kwargs in `Article.create()` -> `published=True`
    - [x] button interactions: replace `get_by_text("Publish")` / `get_by_text("Save as Draft")` clicks with toggle the `#publishedCheckbox` (on for publish, off for draft) then click "Save"
- [x] `./run checkall` passes

## Progress

Implemented in full. `status: Literal["published", "draft"]` removed from `ArticleCreateSchema`/`ArticleUpdateSchema` (`djangoapp/views/articles.py`) and from `Article.create()`/`Article.update()` (`djangoapp/models/base.py`); both submit views now pass `published=payload.published`. Date semantics preserved verbatim (`published_at = now if published else None` on create; set-now-when-unpublished / clear-when-unpublished on update; published re-save keeps the original date). `Literal` import retained (still used by `sort_by`/`role()`).

Frontend: `isPublished` added to `ArticleFormData` (`frontend/src/schemas.ts`); `ArticleForm.vue` emits `submit: []` with one "Save" button and a "Publish" `form-check form-switch` (id `publishedCheckbox`); `ArticleCreate.vue` inits `isPublished=false`, `ArticleEdit.vue` inits `isPublished=!!p.article.published_at`, both send `published: form.isPublished`.

Tests: unit/view/playwright payloads and kwargs updated. Note: the view-test/playwright JSON bodies are Python dict literals passed to `json.dumps`, so the boolean values are Python `True`/`False` (which `json.dumps` serializes to `true`/`false`), not the lowercase JSON tokens literally written in the checklist above. Playwright button clicks use `page.locator("#publishedCheckbox").check()`/`.uncheck()` (idempotent) then `page.get_by_role("button", name="Save").first.click()`.

`./run lintfix`, `./run typecheck` (59 files), `./run test` and `./run checkall` (169 playwright tests) all green.
