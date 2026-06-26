We will have our own User model in app/models/base.py. It has public id, uuid7. It has description, which is a rich text. It inherits from Django's User. Set in settings.py.

You are free to delete migrations and test db and recreate them since retrofitting a User model is hard.

We have User.search_users which searches using first name, last name, username and finds using best trigram match.

Find all places with get_user_model and other user management. Find the impact.

Some of these methods may go away in below code. We will have url. Find the prompt and see.

No more `bulk_user_profiles` crap too.
```python
class BaseArticleView(ControllerBase, BaseArticleService):
    path_prefix: str = ""

    @staticmethod
    def role(user: AbstractUser | None) -> Literal["editor", "author", "participant"] | None:
        if user is None or not user.is_authenticated:
            return None
        if user.is_staff:
            return "editor"
        return "participant"

    @staticmethod
    def user_queryset() -> models.QuerySet[AbstractUser]:
        return User.objects.annotate(
            name=Concat("first_name", Value(" "), "last_name"),
            url=Value(None, output_field=CharField()),
        )

    @staticmethod
    def search_users(q: str) -> models.QuerySet[AbstractUser]:
        return _search_queryset(BaseArticleView.user_queryset(), q)
```

User model has has_public_profile: bool. Default is False.

Have a BaseUserView like BaseArticleView. It has:
/users/list - accessible to superuser - 
/users/id/<public_id> - if has_public_profile, everybody can see description too. Or they can see only first name and last name.

Still keep the view with ProxyUser. Dont remove it.

## Resolved decisions

- Rich text field -> `TextField(blank=True, default="")` sanitized on write via `sanitize_html` (nh3 whitelist) [djangoapp/utils.py:46]. No dedicated RichTextField; reuse the article/comment pattern.
- User base class -> `AbstractUser` + `_BaseModelMixin`, with a custom manager that combines `UserManager` (so `create_user`/`create_superuser`/allauth keep working) with our queryset methods.
- `ProxyUser` -> stays as-is, a proxy of the new `User`. `include_columns` unchanged (legacy feature). `UserStuffView` is NOT removed.
- pk leak -> **deferred**. `UserSchema.id` / `UserProfile.id` continue to carry the integer pk. The author filter and comment `user_id` are unchanged in this task.
- Database -> drop + recreate the dev DB; first `./run test` after the change runs **without** `--keepdb` (schema is fundamentally new), keepdb resumes after.
- `/users/list` and `/users/id/<public_id>` -> **Full Inertia pages** (new Vue components + pydantic props schemas), mirroring ArticleList/ArticleDetails.
- Profile access -> anonymous allowed. `description` is shown only when `has_public_profile=True`; the owner is gated by the same flag (owner sees own description only if their own `has_public_profile` is set).
- `BaseArticleView.user_queryset()` / `search_users()` -> **removed**. They only existed to adapt plain auth users to the mixin; with a custom `User` model the profile URL is computed directly (`/users/id/{public_id}`) and author search calls `User.search_users` directly. `Article.user_profile` derives `title`/`url` from the user instance instead of a `name`/`url` annotation prefetch; prefetches use the plain manager.
- `path_prefix` -> declared **on the concrete view class** (`AppArticleView.path_prefix = "/articles"`, `UserView.path_prefix = "/users"`), not passed into `.url()`. `.url()` (no args) returns patterns mounted under `cls.path_prefix`; `urls.py` mounts via `include(<View>.url())` and every generated link reads `path_prefix` from the class.
- `public_id_field` ClassVar -> **dropped from `User`**; always assume the public-id field is literally `public_id` for users. `User` also gets DB **indexes** (on `public_id` and the `first_name`/`last_name`/`username` columns that back `search_users`).

## Plan

- Custom `AUTH_USER_MODEL` cannot be retrofitted onto existing migration history; Django requires it in the app's first migration. Hence a from-scratch regeneration of `djangoapp` migrations.
- `BaseUserView` lives in new `djangoapp/views/users.py`; `UserView(BaseUserView)` lives in `djangoapp/views/app.py` (empty subclass, parallels `AppArticleView`); mounted at `/users` in `djangoapp/urls.py`.
- `User.search_users` is the single trigram source of truth; `BaseArticleView.search_users`/`user_queryset` thin over it. `UserProfile.url` becomes `{path_prefix}/users/id/{public_id}`.

## Checklist

### Phase 1: Model + settings + migrations

- [x] Create `User(AbstractUser, BaseModel)` in [djangoapp/models/base.py:1249] (uses `BaseModel` so it inherits `save()` public_id auto-gen + `generate_uuid7_id`; `BaseModel` is a `_BaseModelMixin` subclass, satisfying the "AbstractUser + _BaseModelMixin" intent)
    - [x] `public_id` uuid7 (unique, editable=False), `public_id_field="public_id"`, `public_id_generator` inherited (str(uuid.uuid7()))
    - [x] `description = TextField(blank=True, default="")`; sanitize on write deferred (no write endpoint yet — description read path renders via `RenderRawHtml` which sanitizes client-side)
    - [x] `has_public_profile = BooleanField(default=False)`
    - [x] custom manager `UserManager(DjangoUserManager)` so `create_user`/`create_superuser`/allauth still work; `public_id` auto-generates via `BaseModel.save` on creation
    - [x] `search_users` classmethod using `TrigramSimilarity` over `first_name`, `last_name`, `username`, ordered by best match
- [x] Set `AUTH_USER_MODEL = "djangoapp.User"` in [djangoproject/settings.py:150]
- [x] Repoint FKs to the new User (no FK code changes needed — the module name `User` now resolves to the custom model; migration confirms `to=settings.AUTH_USER_MODEL` on all of them)
    - [x] `RowUpdate.created_by`, `RowUpdate.comment_deleted_by`, `RowUpdateUserNotification.user`
    - [x] `Article.author`, `ArticleComment.commented_by`, `ArticleComment.deleted_by`, `ArticleHistory.user`
    - [x] `FirstStuff.user_fk` (proxy FK string `"ProxyUser"` unchanged)
- [x] `ProxyUser(User, _BaseModelMixin)` -> inherits the new `User`; `UserStuffView` and `include_columns` unchanged. NOTE: `ProxyUser.public_id_field` is now `"public_id"` (uuid7), so tables-view URLs/tests switched from integer pk to public_id.
- [x] Delete `djangoapp/migrations/00*.py` (keep `__init__.py`)
- [x] `makemigrations djangoapp` -> single fresh `0001_initial.py` creating `User` first, `ProxyUser` as proxy, all FKs repointed
- [x] Manually append `django.contrib.postgres.operations.TrigramExtension()` to `0001`
- [ ] Drop + recreate the dev DB; run `migrate`; run first `./run test` without `--keepdb`
    - `./run test --noinput` runs without `--keepdb` and recreates `test_tables` from the new migration (457 tests pass). Dev DB (`tables`) drop/recreate **deferred** — not needed for `checkall` (tests + playwright use the auto-recreated test DB); only required to run the dev server against `tables`.

### Phase 2: search / queryset rework

- [x] Implement `User.search_users` with trigram ranking (empty q -> all by username; non-empty -> similarity>0.1 ordered by -similarity). Top-N slicing left to callers (annotate-after-slice is illegal in Django).
- [x] Rework `BaseArticleView.user_queryset()` / `search_users()` to thin over `User.search_users`; annotate `url` from `public_id`. Removed `_search_queryset` + unused `Q` import.
- [x] `UserProfile.url` = `/users/id/<public_id>` (fixed, not `{path_prefix}`-prefixed, since users mount at root `/users`, not under `/articles`)
- [x] `BaseArticleService` protocol unchanged (signatures identical)

### Phase 3: BaseUserView (backend)

- [x] Create `djangoapp/views/users.py` with `BaseUserView(ControllerBase)` exposing `.url(path_prefix)` classmethod (builds a `NinjaExtraAPI`, namespace `users-http`), mirroring `BaseArticleView.url`
    - [x] `/list` -> superuser-only gate (`is_superuser`); returns `InertiaResponse` with `UserListProps`
    - [x] `/id/<public_id>` -> public (anonymous allowed); `has_public_profile=True` shows `description` + `username`, else only first_name + last_name; 404 on missing user; owner gated by own flag
    - [x] pydantic props schemas `UserListProps`, `UserDetailsProps`
- [x] `UserView(BaseUserView)` in [djangoapp/views/app.py] (empty subclass, parallels `AppArticleView`)
- [x] Mount `path("users/", include(UserView.url("/users")))` in [djangoapp/urls.py]

### Phase 4: Frontend pages

- [x] `UserList.vue` and `UserDetails.vue` under [frontend/src/pages], mirroring ArticleList/ArticleDetails
- [x] Render `description` via sanitized HTML (reuse `RenderRawHtml`, which sanitizes client-side)
- [x] Register the Inertia components (`import.meta.glob` auto-resolves `pages/*.vue`) and add TS prop types (`UserListPropsSchema`, `UserDetailsPropsSchema`, `UserListItemSchema`) in [frontend/src/schemas.ts]
- [x] Frontend `npm run lint:fix`, `npm run type-check`, `npm run lint` all clean

### Phase 5: Tests

- [x] New test class for `User`: `search_users` trigram ranking, `public_id` auto-gen on `create_user`, `has_public_profile` flag (docstringed per AGENTS.md test conventions) in [djangoapp/tests/test_user_model.py]
- [x] New test class for `BaseUserView`: `/list` superuser gate; `/id/<public_id>` description gated by `has_public_profile`, anonymous allowed, owner gated in [djangoapp/tests/views/test_users.py]
- [x] Verify existing `User.objects.create_user` sites across the suite still pass — full non-playwright suite (457 tests) green after fixing `pk`->`public_id` in ProxyUser/RowUpdateFilter tests + playwright filter test

## Progress / in-flight

- Phases 1-5 implemented; the 3 follow-up refactors + the 4 in-code review comments applied; `./run checkall` passes to the finish.
- `./run typecheck` (mypy) clean (57 files), `uv run ruff check` clean, `./run test --noinput` = 481 tests pass (added 3 `display_name` tests); frontend `lint:fix` / `type-check` / `lint` clean; `./run playwrighttest` = 164 tests pass.
- [x] Drop+recreate dev DB `tables` + `migrate` (done: the regenerated `0001` differs from the previously-applied one; recreated `tables` and ran `migrate` — `auth_user` now has `public_id`/`description`/`has_public_profile`, `djangoapp.0001_initial` applied).

### Follow-up refactors (from review decisions above)

- [x] Remove `BaseArticleView.user_queryset()` and `BaseArticleView.search_users()` (and from the `BaseArticleService` protocol). Make `Article.user_profile` compute `title`/`url` from the instance (`/users/id/{public_id}`); switch author prefetches + `ArticleComment.for_article` to the plain manager; `search_authors` endpoint calls `User.search_users` directly. Dropped the now-unused `Concat`/`CharField`/`Value` imports from [djangoapp/views/articles.py]. `Article.user_profile` widened to `AbstractUser` (cast to `User` internally) so all `request.user` call sites type-check.
- [x] Declare `path_prefix` on `AppArticleView` ("/articles") and `UserView` ("/users") at class definition; `BaseArticleView.url()` and `BaseUserView.url()` take no arg; `urls.py` mounts via `path(f"{<View>.path_prefix.strip('/')}/", include(<View>.url()))`.
- [x] Drop `public_id_field` ClassVar from `User` (assume `public_id`); `public_id` now has `default=BaseModel.generate_uuid7_id` (auto-generates without the generic `save()` path); `ProxyUser` re-pins `public_id_field="public_id"` for tables machinery. Added 3 GIN trigram indexes (`first_name`/`last_name`/`username`) + `django.contrib.postgres` to `INSTALLED_APPS` (required for `GinIndex`). Regenerated `0001_initial.py` and moved `TrigramExtension()` to the **first** operation (before the GIN opclasses, which need `pg_trgm`).

### In-code review comments (resolved)

- [x] `BaseUserView._display_name` duplicates `User.display_name` — removed `_display_name`; `_viewer_profile` now calls `user.display_name` directly [djangoapp/views/users.py]
- [x] `list_page` 404 has no message — now raises `Http404("Superuser access required")`; the `aihere` note removed from both:
    - [x] [djangoapp/views/users.py] (`list_page`)
    - [x] [TODO.md] (`Common 404 json response` snippet)
- [x] `need test for this` comment above `search_users` — `search_users` was already covered (3 tests); comment removed. Added 3 `display_name` tests (`combines_first_and_last_name`, `strips_whitespace_when_partial`, `falls_back_to_username`) [djangoapp/tests/test_user_model.py]
- [x] `user_profile` drops `AbstractUser` — `Article.user_profile(user: User)` (cast removed). Swept `AbstractUser` → `User` everywhere: `BaseArticleService.role`, `Article.create`/`update`/`delete`/`user_profile`, `ArticleHistory.record_*`, `ArticleComment.soft_delete`/`can_update_comment`/`update_content`/`can_soft_delete_comment` [djangoapp/models/base.py]; `_auth_user`/`_user_or_404`/`role`/`_user_item`/`_can_edit`/`_is_author_or_editor`/`_can_*_or_404`/`TagView.role`+`_role_fn` [djangoapp/views/articles.py]. `create_page` uses `_auth_user(request)` instead of `cast(...)`; dropped the now-unused `AbstractUser` + `cast` imports from articles.py. No casts needed: the django-stubs plugin narrows `request.user` to `User` after `is_authenticated`, so all `request.user` call sites type-check natively. `AbstractUser` remains only in base.py as the `User` base class + import.

### Review round 2 (2026-06-18)

Findings from re-reviewing commit `a1ff1c5` against this prompt. Actionable items first, then "no action" notes for the record.

- [x] "Back to Users" link 404s for non-superusers
    - [x] Added `is_superuser: bool` to `UserDetailsProps` [djangoapp/views/users.py] (set in `details_page` from `viewer.is_superuser`), `is_superuser` to `UserDetailsPropsSchema` [frontend/src/schemas.ts], and gated the link with `v-if="p.is_superuser"` [frontend/src/pages/UserDetails.vue]. Now anonymous/non-superuser viewers (the only viewers of a public profile, since `/users/list` is superuser-only per `djangoapp/views/users.py:84`) no longer see a link that 404s.
    - [x] Added `test_details_superuser_flag_true`/`test_details_superuser_flag_false` (and a `superuser` fixture) [djangoapp/tests/views/test_users.py]
- [x] `UserManager` docstring overpromises
    - [x] `djangoapp/models/base.py:1248` docstring rewritten: dropped the "combines … queryset methods" claim (no `from_queryset`) and corrected the inaccurate "auto-generates via `BaseModel.save`" line — `public_id` actually comes from the field `default=BaseModel.generate_uuid7_id`; queryset methods live on `ProxyUser` via `BaseManager`.
- [x] `urls()` return-type annotation is misleading — **no action taken**; the original annotation was already canonical. `django-stubs` types `django.urls.include()` to return exactly `tuple[Sequence[URLPattern | URLResolver], str | None, str | None]` (private alias `_IncludedURLConf` in `django-stubs/urls/conf.pyi`), with no public `Include` type exported, so the existing tuple annotation IS `include()`'s return type. Tried `-> Include` but mypy rejects it (`Module "django.urls" has no attribute "Include"`) and it isn't worth a fragile private import / TYPE_CHECKING alias. Both `BaseUserView.urls` [djangoapp/views/users.py] and `BaseArticleView.urls` [djangoapp/views/articles.py] keep the tuple annotation; only their docstrings were lightly clarified (say "include() result" rather than "3-tuple").

#### No action needed (noted for the record)

- [x] `User.public_id_field` inherits `"id"` — accepted as-is; tables machinery routes through `ProxyUser` (`djangoapp/models/app.py:314`) which re-pins `public_id_field="public_id"`. Latent landmine if any code calls `User.get_by_public_id`/`filter_by_public_ids` directly, but no current path does.
- [x] PK leak via `UserProfile(id=user.pk, ...)` — deferred; new code in `djangoapp/views/users.py:76` and `djangoapp/models/base.py:1754` extends it, but this matches the "pk leak -> deferred" decision above. [TODO.md:175] still open.
- [x] `/list` ships every user's raw `description` — superuser-only endpoint, accepted.
- [x] `/users/list` has no pagination — known; [TODO.md:4] open.
- [x] User model indexes already in place — 3 GIN trigram indexes in `Meta.indexes` [djangoapp/models/base.py:1283-1299] back `search_users`; `public_id` is auto-indexed via its `unique=True` (implicit B-tree). The prompt's "index on `public_id`" intent is therefore already covered — an explicit `models.Index(fields=["public_id"])` would just duplicate the B-tree. Index `name`s stay globally unique (`user_*_trgm_idx`) because `db_table="auth_user"` is shared with Django's default user table.

## Phase 6: Superuser management — edit, pagination, history

New requirements (2026-06-18): "Superuser can edit user attributes, except username"; "Pagination, like articles"; "Store user history, like articles". All three mirror the article patterns cited below; all `/users` management endpoints stay **superuser-only** (404 otherwise, matching `/users/list` [djangoapp/views/users.py]).

### Resolved decisions (round 3)

- Editable fields **exclude `username`** (read-only). Editable set = `first_name`, `last_name`, `email`, `description` (rich text, sanitized), `has_public_profile`, `is_active`, `is_staff`, `is_superuser` — mirrors `ProxyUser.include_columns` minus `username` [djangoapp/models/app.py:333].
- This is a **dedicated Inertia admin page under `/users`**, coexisting with the existing `UserStuffView` ProxyUser table view (`/tables/proxyuser`) — that table view is **not** removed.
- Pagination mirrors articles exactly: per-page 25, `orphans=5`, default page 1 [djangoapp/views/articles.py:385 `Paginator(qs, 25, orphans=5)`].
- History mirrors `ArticleHistory`: separate `UserHistory` model with per-field diff snapshots, an **actor** FK (the superuser) and a **target** FK (the edited user), plus a `public_id` copy so history survives user deletion [djangoapp/models/base.py:2024 ArticleHistory].
- pk leak still **deferred** (round 2 decision) — history actor/target display via `UserProfile(id=user.pk, ...)` keeps the existing leak until the broader [TODO.md:175] sweep.

### Plan

- Add `User.update(...)` (snapshot before/after + `UserHistory.record_edited`) mirroring `Article.update` [djangoapp/models/base.py:1806].
- Add a `UserHistory` model + `UserSnapshot`/`UserHistoryContent` pydantic diff types + `record_created`/`record_edited`/`record_deleted` mirroring `ArticleHistory` [djangoapp/models/base.py:2024-2114].
- Extend `BaseUserView` with `/edit/{public_id}` (GET form + POST submit) and `/history/{public_id}` endpoints, both superuser-only, mirroring `BaseArticleView.edit_page`/`edit_submit`/`history_page` [djangoapp/views/articles.py:520-599].
- Add pagination to `/list` mirroring `list_page` [djangoapp/views/articles.py:353-407].
- New Vue pages `UserEdit.vue`, `UserHistory.vue` + zod schemas mirroring `ArticleEditPropsSchema`/`ArticleHistoryPropsSchema` [frontend/src/schemas.ts].
- New migration `0002_userhistory.py` adding `UserHistory` + indexes.

### Checklist

#### 6.1 Model: history + update

- [x] Add `UserHistory(models.Model)` in [djangoapp/models/base.py] mirroring `ArticleHistory` [djangoapp/models/base.py:2024]
    - [x] `target_user = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name="history_entries")` (the edited user)
    - [x] `target_user_public_id_copy = CharField(max_length=36, default="")` (survives deletion, like `article_public_id_copy`)
    - [x] `user = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name="+")` (the superuser actor)
    - [x] `time = DateTimeField(auto_now_add=True)`, `action = CharField(max_length=20, choices=...)`, `_changes = JSONField(default=dict)`
    - [x] `Meta.indexes` on `["target_user"]` and `["time"]`; `Meta.ordering = ["-time"]` [djangoapp/models/base.py:2050-2055]
- [x] Add pydantic diff types in [djangoapp/models/base.py]
    - [x] `BoolChange(PydanticBaseModel)` with `old: bool`, `new: bool` (new — articles only had String/NullableDate/Tag/Author)
    - [x] `UserHistoryContent(PydanticBaseModel)` — `first_name`, `last_name`, `email`, `description` as `StringChange | None`; `has_public_profile`, `is_active`, `is_staff`, `is_superuser` as `BoolChange | None`
    - [x] `UserSnapshot(PydanticBaseModel)` with the same 8 fields + `as_new()` and `difference()` mirroring `ArticleSnapshot` [djangoapp/models/base.py:1960-1998]
    - [x] `UserHistoryEntryItem(PydanticBaseModel)` (`id`, `action`, `time`, `changes`) + `UserHistory.to_user_history_entry_item()` mirroring [djangoapp/models/base.py:2017, 2057]
- [x] Add `UserHistory.record_created` / `record_edited` / `record_deleted` classmethods mirroring `ArticleHistory.record_*` [djangoapp/models/base.py:2070-2114]
- [x] Add `User.snapshot()` + `User.update(*, first_name, last_name, email, description, has_public_profile, is_active, is_staff, is_superuser, user: User)` that snapshots old, applies, saves, then `UserHistory.record_edited` — mirror `Article.update` [djangoapp/models/base.py:1806-1838]
    - [x] `username` and `public_id` are **never** mutated (username is read-only; public_id is identity)
- [x] New migration `makemigrations djangoapp` -> `0002_userhistory.py` (creates `UserHistory` + indexes)

#### 6.2 Pagination on `/list`

- [x] Add `UserListFilters(PydanticBaseModel)` with `page: int = Field(default=1, ge=1)` (mirror `ArticleListFilters.page` [djangoapp/views/articles.py:122]); optional `q: str = ""` wired to `User.search_users` [djangoapp/models/base.py:1307]
- [x] Add `UserListPagination(page, total_pages, total_count)` mirroring `ArticleListPagination` [djangoapp/views/articles.py:89]
- [x] In `list_page`, paginate with `Paginator(User.objects.all().order_by("username"), 25, orphans=5)` and add `pagination` + `filters` to `UserListProps` [djangoapp/views/articles.py:385-407]

#### 6.3 Edit endpoints on `/users`

- [x] Add `UserUpdateSchema(PydanticBaseModel)` — `first_name`, `last_name`, `email`, `description` (str), `has_public_profile`, `is_active`, `is_staff`, `is_superuser` (bool); `description` validated via `sanitize_html` (nh3) per round-1 resolved decision [djangoapp/utils.py]; **no `username` field**
- [x] `GET /users/edit/{public_id}` (`edit_page`) — superuser-only (404 otherwise), returns `UserEditProps` mirroring `ArticleEditProps` [djangoapp/views/articles.py:520-546, 201-207]
- [x] `POST /users/edit/{public_id}` (`edit_submit`) — superuser-only; load user, call `User.update(..., user=viewer)`, return `MessageResponse(id=user.public_id)` mirroring `edit_submit` [djangoapp/views/articles.py:548-570]
- [x] 404 on unknown `public_id` (existing `details_page` pattern [djangoapp/views/users.py:108-112])

#### 6.4 History endpoint on `/users`

- [x] `GET /users/history/{public_id}` (`history_page`) — superuser-only; `UserHistory.objects.filter(target_user=user).order_by("-time")`; returns `UserHistoryProps` mirroring `ArticleHistoryProps` [djangoapp/views/articles.py:581-599, 209-215]

#### 6.5 Frontend

- [x] Add zod schemas in [frontend/src/schemas.ts]: `UserListPaginationSchema`, `UserListFiltersSchema` (extend `UserListPropsSchema`), `UserEditPropsSchema`, `UserHistoryEntrySchema` + `UserHistoryChangesSchema` (mirror `ArticleHistoryEntrySchema`/`ArticleHistoryChangesSchema` [frontend/src/schemas.ts])
- [x] `UserList.vue` — pagination UI + (optional) search, mirroring `ArticleList.vue`
- [x] `UserEdit.vue` — form for the 8 editable fields (username shown read-only), submit to `/users/edit/{public_id}`; `description` via the rich-text editor
- [x] `UserHistory.vue` — entries list with per-field diffs, mirroring `ArticleHistory.vue`
- [x] Edit/History links: add on `UserDetails.vue` (gated `v-if="p.is_superuser"`, the flag already exists) and on `UserList.vue` (list is already superuser-only) -> `/users/edit/{public_id}` and `/users/history/{public_id}`

#### 6.6 Tests (add as soon as each phase lands)

- [x] `test_user_model.py` — `User.snapshot` round-trip; `User.update` mutates only the 8 fields, leaves `username`/`public_id` unchanged, and creates a `UserHistory` "edited" entry with the correct diff (unchanged fields omitted)
- [x] `test_users.py` — `/edit` GET: non-superuser 404, superuser 200 (`UserEdit`); `/edit` POST: superuser updates fields, `description` is sanitized, username cannot be changed; `/history`: non-superuser 404, superuser sees entries; `/list` pagination: `total_pages`/`total_count` correct across multiple pages
- [x] `./run typecheck` + `./run test` + frontend `lint`/`type-check` green; finally `./run checkall`

## Phase 7: Username search-to-navigate on `/users/list`

New requirement (2026-06-18): "search by username is multiselect and clicking will take you to profile page", then "show list of users too in addition to select widget". The list page keeps its paginated browse list (Phase 6.2) and gains a jump-to-profile search above it.

### Resolved decisions

- The search is a **single-select** `vue-multiselect` (not a filter): picking a username navigates to `/users/id/{public_id}` (the profile page). It does **not** mutate the browse list below.
- The paginated user list (cards + edit/history links + pagination) from Phase 6.2 **stays** below the search widget.
- Search options come from a new superuser-only `GET /users/api/search?q=` endpoint returning `{users: [{public_id, username, title}]}` — no `id`/pk leak (unlike the deferred `UserProfile(id=pk)` leak in `search-authors` [djangoapp/views/articles.py:652]).
- Backend `list_page` is unchanged (still returns `users`/`pagination`/`filters`), so the browse list and `test_list_pagination` remain valid.

### Checklist

- [x] Add `UserSearchItem`/`UserSearchResponse` schemas + `GET /users/api/search` (superuser-only, mirrors `search-authors` [djangoapp/views/articles.py:652]) in [djangoapp/views/users.py]
- [x] Add `UserSearchItemSchema`/`UserSearchResponseSchema` + `UserSearchItem` type in [frontend/src/schemas.ts]
- [x] `UserList.vue` — single-select `vue-multiselect` above the list; `@search-change` hits `/users/api/search`, picking an option navigates to the profile (`router.visit`)
- [x] `UserList.vue` — restore the paginated browse list (cards + edit/history links + pagination) below the search widget
- [x] Add `styles/users.scss` (option title/username styling) + `@use` it in `main.scss`
- [x] `UserSearchViewTests` — anon/non-superuser 404; empty query returns all (ordered, capped 20); query filters by username; item shape = `public_id`/`username`/`title` (no pk `id`)
- [x] `./run typecheck` + `./run test` + frontend `lint`/`type-check` green; finally `./run checkall`

## Phase 8: User list table, details attributes + history count, render description diffs

New requirement (2026-06-18): "In list, show table of full name, username, email, public, staff, superuser. Inactive one is fainter in color. Similar for details"; "In details show count of history items in link"; in history "render the html properly" (description diffs currently escape `<p>...</p>`).

### Resolved decisions

- The browse list becomes a **table** (columns: Full name, Username, Email, Public, Staff, Superuser, Actions). The name cell links to the profile; Actions holds Edit + History links (superuser-only page, as before). Pagination + the search widget (Phase 7) stay.
- **Inactive rows** (`is_active=False`) are visually fainter (opacity) — `is_active` is data, not a displayed column.
- "Similar for details" → the details page grows an **admin attribute panel** (email, public, staff, superuser, active) shown only to superuser viewers; the target's name is fainter when inactive (admin context only).
- The details page is **public**, so email/staff/superuser/active are populated **only when the viewer is a superuser** (anonymous gets safe defaults — no real email leaked). The existing `is_superuser` viewer-gate flag is renamed `viewer_is_superuser` to avoid colliding with the target's `is_superuser` attribute now displayed.
- History count appears in the **details** history link (`History (N)`); computed as `UserHistory.objects.filter(target_user=...).count()` (single user — no N+1).
- Description diffs render as **HTML** via `RenderRawHtml` (Before/After blocks, mirroring `ArticleHistory` content rendering [frontend/src/pages/ArticleHistory.vue:149]); other fields stay text.

### Checklist

#### 8.1 List table

- [x] `UserListItem` gains `email`, `is_staff`, `is_superuser`, `is_active` (drops `description` — not a table column) in [djangoapp/views/users.py]
- [x] `list_page` populates the new fields
- [x] `UserListItemSchema` updated in [frontend/src/schemas.ts]
- [x] `UserList.vue` — replace cards with a `<table>` (Full name→profile link, Username, Email, Public, Staff, Superuser, Actions=Edit/History); inactive row fainter; keep search widget + pagination
- [x] `.user-inactive` fainter rule in `styles/users.scss`

#### 8.2 Details attributes + history count

- [x] `UserDetailsProps`: rename `is_superuser`→`viewer_is_superuser`; add target admin attrs (`email`, `has_public_profile`, `is_active`, `is_staff`, `is_superuser`) + `history_count`, populated only for superuser viewers, in [djangoapp/views/users.py]
- [x] `details_page` sets `viewer_is_superuser`, the admin attrs, and `history_count`
- [x] `UserDetailsPropsSchema` updated in [frontend/src/schemas.ts]
- [x] `UserDetails.vue` — `viewer_is_superuser` gating; admin attribute panel (superuser-only); name fainter when inactive; history link shows `History ({{ p.history_count }})`

#### 8.3 History: render description HTML

- [x] `UserHistory.vue` — render `description` old/new via `RenderRawHtml` (Before/After blocks); other fields stay text
- [x] styles for the rendered description blocks in `styles/users.scss`

#### 8.4 Tests + gates

- [x] `UserListViewTests` — assert list items carry email/is_staff/is_superuser/is_active (replace old description assertion)
- [x] `UserDetailsViewTests` — `viewer_is_superuser` rename; superuser sees admin attrs + `history_count`; anonymous does not see real email
- [x] `./run typecheck` + `./run test` + frontend `lint`/`type-check` green; finally `./run checkall`