No need of url in UserProfile. We now know how exactly to generate url. Generate in frontend or whereever. check whereever UserProfile is used.
Remove view classes for /users and /articles. Make them regular functions. Just add their api to urls.py. Remove ninja extra.

In views/app.py, have these to resolve editors and participants:

@article_editors
def _article_editors() -> QuerySet[User]:
    return User.objects.filter(is_superuser=True)

@article_participants
def _article_participants() -> QuerySet[User]:
    return User.objects.all()

These decorators will set the callables. If decorators are not set, raise NotImplementedError

We have only editors and participant roles. If a participant is added as author to an article they have author privilege to that article.
Only editor can create articles, participants can be authors of articles
Dont have author role - list drafts where you are author.
Author can edit or delete their articles, editors can do it for any article

Update the readme. Mention what the decorators do.
In readme, write down permission tables for articles create,details,list,update and delete and same operations for comments

## Context (from prior prompts)

- Dedicated articles live in `djangoapp/views/articles.py` (`BaseArticleView` + `TagView`) and the `Article`/`ArticleTag`/`ArticleImage`/`ArticleComment`/`ArticleHistory` models in `djangoapp/models/base.py`. See [prompts/20260602-dedicated-articles.md].
- Custom `User` model + `BaseUserView` profile/admin pages live in `djangoapp/views/users.py` and `djangoapp/models/base.py`. See [prompts/20260617-user-model.md].
- The tables system (`djangoapp/views/base.py`) already uses plain `ninja.NinjaAPI` + a `Router` subclass (`OurRouter`), **not** ninja-extra. Only the articles and users controllers use `ninja_extra` (`ControllerBase`, `NinjaExtraAPI`, `api_controller`, `route`) — so removing ninja-extra is scoped to those two files + `settings.INSTALLED_APPS` + `pyproject.toml`.

## Resolved decisions

- **`UserProfile.url` removal**: Drop the `url` field from `UserProfile` [djangoapp/models/base.py:1996-1999]. To let the frontend build `/users/id/{public_id}` itself, add a `public_id: str` field to `UserProfile`. Keep `id` (pk) as-is for now — the broader pk-leak sweep ([TODO.md:152], [TODO.md:175]) stays deferred and is **out of scope** here. (Alternative, not chosen: repurpose `UserProfile.id` to be the public id; rejected because it cascades into the author filter `?author=` and `ArticleCommentsResponse.user_id`, which the pk-leak decisions explicitly deferred.)
- **ninja-extra removal → plain ninja `Router`**: Articles and users become module-level `ninja.Router`s with `@router.get/post` **functions** (no `self`, no controller class), mirroring the existing `BaseView.get_router()` pattern [djangoapp/views/base.py:1265]. Each area keeps its own `NinjaAPI` instance (distinct `urls_namespace`) and is mounted directly in `djangoapp/urls.py`.
- **`path_prefix`**: Module-level constants (`ARTICLES_PATH_PREFIX = "/articles"`, `USERS_PATH_PREFIX = "/users"`), already the direction from [prompts/20260602-dedicated-articles.md] Phase 10. No more `cls.path_prefix`.
- **Roles collapse to two resolvers**: The 4-tier `role()` (`"editor" | "author" | "participant" | None`) is removed. In its place: `article_editors` / `article_participants` **registration decorators** that store a `() -> QuerySet[User]` callable; calling them when unset raises `NotImplementedError`. Membership is checked via the querysets; **authorship is per-article** (`article.author_id == user.pk`), never a global role.
- **Model-side access (no circular import)**: Editors/participants resolvers are registered onto the `Article` model as ClassVar callables (same late-binding trick as the current `Article._service` / `Article.set_article_service` [djangoapp/models/base.py:1778,1791-1793]), so model methods like `ArticleComment.can_soft_delete_comment` [djangoapp/models/base.py:2416-2422] can test editorship without importing views.
- **Create is editor-only** (behaviour change): participants can no longer create drafts. Only editors create, and an editor may assign any participant as the article's `author`. A participant who is the `author` of an article gains edit/delete on **that** article and sees **that** draft in lists.

## Plan

1. Remove `UserProfile.url`; add `UserProfile.public_id`; regenerate links client-side.
2. Add the `article_editors` / `article_participants` decorator registry + predicate helpers; register default resolvers in `views/app.py`; rewire model-side editor checks.
3. Convert `views/articles.py` from a ninja-extra controller to plain-ninja `Router` functions using the new predicates.
4. Convert `views/users.py` from a ninja-extra controller to plain-ninja `Router` functions.
5. Wire both routers into `djangoapp/urls.py`; drop `ninja_extra` from `settings.INSTALLED_APPS` and `pyproject.toml`; `uv sync` / remove from lockfile.
6. Update all affected tests (unit + playwright).
7. Rewrite the README articles/users sections (decorators + permission tables).
8. `./run checkall` green.

## Checklist

### Phase 1: `UserProfile` — drop `url`, add `public_id`

- [x] `djangoapp/models/base.py` — `UserProfile`
    - [x] remove `url: str | None = None`
    - [x] add `public_id: str`
- [x] update every `UserProfile(...)` construction site to pass `public_id=` and drop `url=`
    - [x] `Article.user_profile` (`public_id=user.public_id`)
    - [x] `ArticleComment.for_article` deleted-user fallback (`public_id=""`)
    - [x] `viewer_profile` (was `BaseUserView._viewer_profile`) in `views/users.py`
- [x] `frontend/src/schemas.ts` — `UserSchema`
    - [x] drop `url: z.string().nullable().optional()`
    - [x] add `public_id: z.string()` (optional — the shared `UserSchema` is also used by tables pages that never carry it)
- [x] frontend — build `/users/id/{public_id}` from `public_id` instead of reading `.url`
    - [x] `frontend/src/components/article-history/AuthorChange.vue` (href from `value.public_id`)
    - [x] any other `UserProfile`/`UserSchema` `.url` consumer swept clean (`RowColumnValues.vue` FK `.url` is a separate schema, left it)
- [x] `djangoapp/tests/**` — no `UserProfile.url` reads / `UserProfile(url=...)` constructions remain

### Phase 2: Editors/participants registry + predicates

- [x] `djangoapp/models/base.py` — replace `BaseArticleService`/`_service` with resolver ClassVars on `Article`
    - [x] remove `BaseArticleService` protocol
    - [x] remove `_service: ClassVar[...]` + `set_article_service`
    - [x] add `_editors_fn: ClassVar[Callable[[], QuerySet[User]] | None] = None` and `_participants_fn` equivalent
    - [x] add `Article.set_editors(fn)` / `Article.set_participants(fn)` classmethods (late-bound registration)
    - [x] add `Article.editors()` / `Article.participants()` returning the querysets; raise `NotImplementedError` when the resolver is unset
    - [x] add `Article.is_editor(user)` and `Article.is_participant(user)` membership predicates (authenticated + queryset `.filter(pk=user.pk).exists()`)
    - [x] narrow predicate signatures to `User` (not `User | None`): `is_editor`, `is_participant`, `is_author`, `can_be_edited_by` all take a non-null `User`. Callers that previously passed an anonymous user (`auth_user(request)`) now guard `None` first — `is_editor/is_author` at `list_page`/`details_page` use `Article.is_editor(user) if user is not None else False`; `can_be_edited_by` inside `viewable_or_404`/`can_download_image_or_404` is gated on `user is not None and ...`. `is_participant`'s sole caller was already guarded.
- [x] `djangoapp/views/articles.py` — decorator + predicate layer
    - [x] define `article_editors(fn)` / `article_participants(fn)` registration decorators that call `Article.set_editors(fn)` / `Article.set_participants(fn)` and return `fn`
    - [x] **no module-level predicates** — the model already exposes `Article.is_editor(user)` [djangoapp/models/base.py:1814], `Article.is_participant(user)` [djangoapp/models/base.py:1820], `Article.is_author(user, article)` [djangoapp/models/base.py:1826], `Article.can_be_edited_by(user, article)` [djangoapp/models/base.py:1830]. Call them directly at every site; do **not** add thin `is_editor`/`is_participant`/`is_author`/`can_edit` wrappers in `views/articles.py`. Specifically: every `can_edit(user, article)`-shaped check becomes `article.can_be_edited_by(user)` (or `Article.can_be_edited_by(user, article)` where only the class is in scope)
    - [x] remove the `_user_item(user)` wrapper — it only did `return Article.user_profile(user)`; every caller now invokes `Article.user_profile(user)` directly (inlined `... if user is not None else None` where the user may be anonymous)
    - [x] remove the old `role()` staticmethod and every `role(user) == "editor"|"author"|"participant"` / `_is_author_or_editor` branch; rewrite each against the new predicates (list/details/create/edit/delete/comment/tag/image/subscribe)
- [x] `djangoapp/models/base.py` — rewire model-side role usage
    - [x] `ArticleComment.can_soft_delete_comment` uses `article.is_editor(user)` instead of `Article._service.role(user)`
- [x] `djangoapp/views/app.py` — register default resolvers (exact code from the prompt)
    - [x] `@article_editors def _article_editors() -> QuerySet[User]: return User.objects.filter(is_superuser=True)`
    - [x] `@article_participants def _article_participants() -> QuerySet[User]: return User.objects.all()`
    - [x] imports: `article_editors`, `article_participants` from `djangoapp.views.articles`; `QuerySet` from `django.db.models`

### Phase 3: `views/articles.py` → plain-ninja `Router` functions

- [x] replace `ninja_extra` import with `from ninja import Router, NinjaAPI`
    - [x] remove `ControllerBase`, `NinjaExtraAPI`, `api_controller`, `route`
- [x] delete `BaseArticleView` and `TagView` classes
    - [x] `ARTICLES_PATH_PREFIX = "/articles"` module constant; all `self.path_prefix` → `ARTICLES_PATH_PREFIX`
    - [x] every `@route.get/.post` method becomes a module-level `@articles_router.get/.post` function; drop `self`
- [x] create `articles_router = Router()` and (in `views/app.py` or `views/articles.py`) `articles_api = NinjaAPI(urls_namespace="articles-http")` + `articles_api.add_router(ARTICLES_PATH_PREFIX.strip("/"), articles_router)`
- [x] page endpoints as functions: `list_page`, `details_page`, `create_page`, `create_submit`, `edit_page`, `edit_submit`, `delete_submit`, `history_page`
    - [x] create permission: editor-only (`editor_or_404`), no longer `_is_author_or_editor`
    - [x] author assignment kept editor-gated (`Article.is_editor(user)` may set `author_id`)
- [x] api endpoints as functions: `upload_image`, `download_image`, `search_tags`, `search_authors`, `list_comments`, `create_comment`, `update_comment`, `delete_comment`, `subscribe`, `unsubscribe`
- [x] tag endpoints folded into the same router as functions: `tag_page`, `tag_create`, `tag_update`, `tag_delete` (editor-only via `editor_or_404`)
- [x] rename all module-level helpers that currently start with `_` (legacy convention) — drop the leading underscore and update every call site:
    - [x] `_is_browser` → `is_browser`
    - [x] `_auth_user` → `auth_user`
    - [x] `_user_or_404` → `user_or_404`
    - [x] `_build_cover_image_url` → `build_cover_image_url`
    - [x] `_can_download_image_or_404` → `can_download_image_or_404`
    - [x] `_viewable_or_404` → `viewable_or_404`
    - [x] `_published_or_404` → `published_or_404`
    - [x] `_editor_or_404` → `editor_or_404`
    - [x] `_render_static_list` → `render_static_list`
    - [x] `_render_static_details` → `render_static_details`
    - note: leave pydantic validators `_name_no_spaces` / `_color_hex` (the leading underscore is required by pydantic's validator naming) unless those are moved off the prefix too
- [x] replace the `cls.urls()` classmethod with whatever `urls.py` consumes (the `articles_api.urls`)

### Phase 4: `views/users.py` → plain-ninja `Router` functions

- [x] replace `ninja_extra` import with `from ninja import Router, NinjaAPI`
- [x] delete `BaseUserView` class
    - [x] `USERS_PATH_PREFIX = "/users"` module constant; `self.path_prefix` → `USERS_PATH_PREFIX`
    - [x] `@route.get/.post` methods → `@users_router.get/.post` functions; drop `self`
- [x] create `users_router = Router()` and `users_api = NinjaAPI(urls_namespace="users-http")` + `users_api.add_router(USERS_PATH_PREFIX.strip("/"), users_router)`
- [x] page + api functions: `list_page`, `details_page`, `edit_page`, `edit_submit`, `history_page`, `search`
- [x] `views/app.py` — drop `class UserView(BaseUserView)` (no longer a class; nothing to subclass)
- [x] replace the `cls.urls()` classmethod with the `users_api.urls` / include result
- [x] rename all module-level helpers that currently start with `_` (legacy convention) — drop the leading underscore and update every call site:
    - [x] `_viewer_profile` → `viewer_profile`
    - [x] `_superuser_or_404` → `superuser_or_404`
    - [x] `_get_user_or_404` → `get_user_or_404`
    - note: leave pydantic validators `_sanitize_description` / `_validate_email` (leading underscore required by pydantic validator naming)

### Phase 5: URL wiring + dependency removal

- [x] `djangoapp/urls.py`
    - [x] mount articles: `path("", articles_api.urls)` (single api carries page + api routes)
    - [x] mount users the same way: `path("", users_api.urls)`
    - [x] remove `AppArticleView.urls()` / `UserView.urls()` calls
- [x] `djangoproject/settings.py` — remove `"ninja_extra"` from `INSTALLED_APPS`
- [x] `pyproject.toml` — remove `django-ninja-extra` dependency
- [x] `uv sync` (drop from lockfile)
- [x] grep sweep: no remaining `ninja_extra` / `NinjaExtraAPI` / `api_controller` / `ControllerBase` / `from ninja_extra` references

### Phase 6: Tests

- [x] `djangoapp/tests/test_articles.py` — model tests
    - [x] replace editor fixtures/`role` assumptions with `is_editor` membership (editors now `is_superuser=True`); update `ArticleCommentModelTests.can_soft_delete_comment` cases
    - [x] drop any `Article.set_article_service` setup; resolvers registered via the app import chain
- [x] `djangoapp/tests/views/test_articles.py` — controller/view tests
    - [x] update create-permission tests: participants now get 404 on create (behaviour change); create page is editor-only
    - [x] replace `role`-based expectations with editor/participant/author expectations throughout
- [x] `djangoapp/tests/views/test_users.py` — no `BaseUserView`/`UserView` import references; re-run green
- [x] `djangoapp/tests/test_user_model.py` — unaffected; re-run to confirm
- [x] `djangoapp/tests/playwright/test_articles.py` — editor fixtures now superusers; image/comment flows green
- [x] add coverage for the new behaviour
    - [x] participant cannot create (404); editor can create and assign a participant as author
    - [x] participant-author can edit/delete their own article; cannot edit others'
    - [x] participant sees own drafts with `?unpublished`; does not see others' drafts
    - [x] `NotImplementedError` raised when editors/participants resolvers are unset
- [x] `./run typecheck` clean; `./run test` green

### Phase 7: README

- [x] `README.md` — Articles section
    - [x] replace the `BaseArticleView` subclass example with the `@article_editors` / `@article_participants` registration snippet and explain what the decorators do (register the resolver callables; `NotImplementedError` if unset)
    - [x] drop the old overridable-methods table (`role`, `user_queryset`, `search_users`)
    - [x] update the mounting snippet to the new `urls.py` wiring
    - [x] replace the permissions table with the new editor/participant/anonymous model (see tables below)
    - [x] note `UserProfile` now carries `public_id` (no `url`); links built client-side as `/users/id/{public_id}`
- [x] `README.md` — Users section
    - [x] update mounting snippet (no `UserView` subclass / `.urls()`)
    - [x] keep the existing user permissions table (superuser-only admin unchanged)
- [x] Permission tables (articles) — create, list, details, update, delete:

  | Operation | editor | participant | anonymous |
  |---|---|---|---|
  | **list** | all articles; `?unpublished` shows every draft | published only by default; `?unpublished` adds their own drafts | published only |
  | **details** | any article | published + their own drafts | published only |
  | **create** | yes; may assign any participant as `author` | no (404) | no (404) |
  | **update** | any article | only articles where they are `author` | no (404) |
  | **delete** | any article | only articles where they are `author` | no (404) |

- [x] Permission tables (comments) — list, create, update, delete:

  | Operation | editor | participant | anonymous |
  |---|---|---|---|
  | **list (read)** | on any article they can view | on published + their own-draft articles | on published only |
  | **create** | on published articles | on published articles | no (404) |
  | **update** | own comment, within the edit timeout | own comment, within the edit timeout | no (404) |
  | **delete (soft)** | any comment | own comment, or any comment on an article they author | no (404) |

- [x] note in README: drafts (no `published_at`) are readable only by editors and the article's author; commenting and subscribing are disabled on drafts (404); first comment auto-subscribes the commenter (unchanged)

### Phase 8: Final

- [x] `./run lintfix`
- [x] `./run typecheck`
- [x] `./run test`
- [x] `cd frontend && npm run lint:fix && npm run type-check && npm run lint`
- [x] `./run playwrighttest` (isolate failing tests per `docs/playwright-debugging.md`)
- [x] `./run checkall` passes to the finish

## More refactors 
In list and details page, we should have a link to user profile for author

When we create a tag in tag management page, its not refreshed and new tags dont appear. Find other tag operations that return stale values.

Remove _render_static_list. Rename _is_browser and detects only if its an intertia request.

Render _render_static_details for all InertiaResponse, except when it it detects an inertia request. Render it such that its not visible if browser can run scripts.

get_user_model is still used in codebase. Remove those.

## Plan (More refactors)

9. Render the author name in the article list and details as a link to `/users/id/{public_id}`, mirroring `AuthorChange.vue` [frontend/src/components/article-history/AuthorChange.vue:9-16]. The author profile already carries `public_id` via `Article.user_profile` [djangoapp/models/base.py:1852-1857] and `UserSchema.public_id` [frontend/src/schemas.ts:26].
10. Fix the tag management page so created/updated/deleted tags refresh; audit and fix every other tag surface that goes stale after a tag mutation.
11. Remove `render_static_list` (+ the list static template); reduce `is_browser` to inertia-only detection (rename to `is_inertia_request`, drop bot heuristics).
12. Serve the static article details for every details-page response except inertia requests, hidden from JS-capable browsers so the SPA stays the visible UI and crawlers still read the content.
13. Remove every `get_user_model()` usage; import `User` directly from `djangoapp.models.base` [djangoapp/models/base.py:1262].
14. `./run checkall` green.

## Checklist (More refactors)

### Phase 9: Author profile links in list + details

- [x] `frontend/src/pages/ArticleList.vue` — author is a link
    - [x] wrap the author name at the card meta line [frontend/src/pages/ArticleList.vue:213] in a `<Link :href="/users/id/${article.author.public_id}">` when `article.author.public_id` is present, else plain text (same guard as `AuthorChange.vue:10`)
    - [x] reuse the `Link` import already in the file [frontend/src/pages/ArticleList.vue:2]; build the URL from the `/users` prefix (existing convention — `AuthorChange.vue:11` hardcodes `/users/id/...`); added `article-author-link` class for testability
- [x] `frontend/src/pages/ArticleDetails.vue` — author is a link
    - [x] wrap `By {{ p.article.author.title }}` [frontend/src/pages/ArticleDetails.vue:96] the same way (link when `public_id` present)
- [x] playwright coverage
    - [x] article list card author link href is `/users/id/{public_id}` (`test_list_author_links_to_profile`)
    - [x] article details "By …" author link href is `/users/id/{public_id}` (`test_details_author_links_to_profile`)
- [ ] optional (deferred): introduce a shared frontend `USERS_PATH_PREFIX` constant instead of repeating `/users`, and switch `AuthorChange.vue:11` + the two new sites to it

### Phase 10: Tag management refresh + stale audit

- [x] `frontend/src/pages/ArticleTagManagement.vue` — fix the stale list
    - [x] root cause: `p` is parsed once at setup [frontend/src/pages/ArticleTagManagement.vue:16], so `p.tags` never updates after `router.reload()` [frontend/src/pages/ArticleTagManagement.vue:34,54,66]
    - [x] made `p` a `computed` over `props.props` so newly created tags appear and edits/deletes reflect immediately
    - [x] create/update/delete all refresh the table (verified via `test_tag_management_ui_refresh`)
- [x] audit other tag surfaces for staleness after a tag create/update/delete
    - [x] `frontend/src/pages/ArticleList.vue` — `tagOptions` seeded only from `selected_tags`; a tag created on the management page is invisible in the filter until re-searched (`searchTags` hits `search-tags` fresh) — accepted (server-searched, always fresh on query)
    - [x] `ArticleCreate`/`ArticleEdit` tag pickers — go through `search-tags` [djangoapp/views/articles.py:651-660], so they surface new tags on search (no fix needed)
    - [x] article list/details card tag badges — driven by per-article `tags`; only change on article save, not tag edit — no stale value reachable
- [x] playwright coverage: `test_tag_management_ui_refresh` — create a tag from the UI, assert it appears in the management table without a manual reload

### Phase 11: `is_browser` → inertia-only; remove `render_static_list`

- [x] `djangoapp/views/articles.py`
    - [x] renamed `is_browser` to `is_inertia_request` and reduced its body to `return bool(request.headers.get("X-Inertia"))` (matches the tables-system predicate [djangoapp/views/base.py:733-735]); updated every call site
    - [x] removed `_BOT_PATTERNS`
    - [x] deleted `render_static_list` and the `if not is_inertia_request(request): return render_static_list(...)` branch in `list_page`; `list_page` always returns the `InertiaResponse`
    - [x] removed the now-unused `article.url` / `article.authors_list` shaping that only `render_static_list` consumed
- [x] delete `djangoapp/templates/articles/article_list_static.html` (removed; grep confirms no code references)
- [x] unit test: `is_inertia_request` returns True only when `X-Inertia` header is set (False for plain UA, no UA, bot UA) — `ArticleStaticRenderingTests.test_is_inertia_request_only_with_header`

### Phase 12: Static details for every response except inertia

- [x] `djangoapp/views/articles.py` — `details_page`
    - [x] always returns the `InertiaResponse`; when the request is NOT an inertia request, also renders `render_static_details` + `render_article_og_head` and injects them via `InertiaResponse(template_data=...)` (`seo_head_extra` + `noscript_html`) so crawlers read the article
    - [x] hides the static details from JS-capable browsers by rendering it inside `<noscript>` in `inertia/base.html` (no inline/scoped styles)
    - [x] keeps the `<noscript>` content out of the inertia partial response (template_data is ignored on X-Inertia requests by the inertia library) to avoid shipping duplicate markup on SPA navigations
- [x] `djangoapp/templates/articles/article_details_static.html` — repurposed as the noscript fragment; author name links to `/users/id/{public_id}` via `author_public_id` from `render_static_details` context
- [x] playwright/unit coverage
    - [x] `ArticleStaticRenderingTests.test_non_inertia_has_noscript_fallback` — non-inertia GET of `/articles/id/{public_id}` contains the article body in the `<noscript>` block
    - [x] `ArticleStaticRenderingTests.test_inertia_omits_fallback` — inertia response omits the `<noscript>` block (JSON only); SPA renders the interactive view (covered by existing playwright details tests, all green)

### Phase 13: Remove `get_user_model()`

- [x] production code
    - [x] `djangoapp/views/base.py` — added `User` to the `from djangoapp.models.base import (...)` block (no circular import — `models.base` does not import views), dropped `from django.contrib.auth import get_user_model`, replaced `user_model = get_user_model()` with `User`
    - [x] `djangoapp/management/commands/createrows.py` — replaced import + `User = get_user_model()` with `from djangoapp.models.base import User`
- [x] test code — replaced `from django.contrib.auth import get_user_model` + `User = get_user_model()` with `from djangoapp.models.base import User` in
    - [x] `djangoapp/tests/test_articles.py`
    - [x] `djangoapp/tests/views/test_views.py` (module-level `User`) and the in-method `user_model = get_user_model()`
    - [x] `djangoapp/tests/views/test_users.py`
    - [x] `djangoapp/tests/test_user_model.py`
    - [x] `djangoapp/tests/test_models.py` (also removed a now-unused `# type: ignore[valid-type]`)
    - [x] `djangoapp/tests/test_filters.py`
    - [x] `djangoapp/tests/test_serializers.py`
    - [x] `djangoapp/tests/playwright/test_notifications.py`
    - [x] `djangoapp/tests/test_deletenotifications.py`
    - [x] `djangoapp/tests/test_createrows.py`
    - [x] `djangoapp/tests/playwright/test_articles.py`
    - [x] `djangoapp/tests/playwright/test_users.py`
    - [x] `djangoapp/tests/playwright/test_playwright.py`
- [x] grep sweep: no remaining `get_user_model` references in `djangoapp/` (only the historical `prompts/*.md` mentions stay)

### Phase 14: Final (More refactors)

- [x] `./run lintfix`
- [x] `./run typecheck`
- [x] `./run test` (548 tests)
- [x] `cd frontend && npm run lint:fix && npm run type-check && npm run lint`
- [x] `./run playwrighttest` (176 tests; isolated article suites run individually first)
- [x] `./run checkall` passes to the finish

## Checklist: static/SEO rendering follow-ups

Captures the code-level follow-up notes left after Phase 12 (the seo/noscript template_data wiring).

- [x] `djangoapp/views/articles.py` — `render_static_details` (removed; replaced by template-include)
    - [x] pass the schema object to the template instead of the hand-built `context` dict — `details_page` passes `{"article": props.article}` (the `ArticleDetailsItem` object) as `noscript_template_data`
    - [x] move the `published_date` formatting (`fromisoformat(...).strftime(...)`) into the template — `article_details_static.html` uses `{{ article.published_at|parse_iso|date:"M d, Y" }}`
    - [x] render `published_date` in the local timezone — `parse_iso` returns an aware datetime and Django's `|date` renders it in `TIME_ZONE` (`USE_TZ=True`)
- [x] `djangoapp/views/articles.py` — `details_page` template_data block
    - [x] both `render_static_details` (removed) and `render_article_og_head`→`article_og_head` take the schema object (`ArticleDetailsProps`), not the dumped dict
    - [x] `article_og_head` returns a `HeadTags` schema (title, type, description, cover_image_url) passed to the template
    - [x] `inertia/base.html` renders head tags from the `head_tags` schema object it receives
    - [x] `inertia/base.html` takes `noscript_template_name` + `noscript_template_data` and renders the fragment via the `render_fragment` filter (no pre-rendered html string shipped from the view)
    - [x] consolidated so only `base.html` is needed — dropped `article_details_og.html` (og now inline in `base.html`); `article_details_static.html` is included by name
- [x] `djangoapp/tests/views/test_articles.py` — `ArticleStaticRenderingTests`
    - [x] moved the `assertContains` content checks into `assert_article_content(response)` shared helper
- [x] templatetags consolidated into a single `djangoapp/templatetags/common_filters.py` (`render_fragment`, `parse_iso` merged in; `fragments.py` deleted; `json_filters.py` renamed to `common_filters.py`)
- [x] `./run checkall` green