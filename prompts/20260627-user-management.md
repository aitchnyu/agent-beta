# User management under `/users`

Two parts: (1) a small view-module consolidation, (2) port prevproject's full `/users` management (list/details/edit/history/search) with backend, frontend, and tests.

Reference: `prevproject/` is the source of truth. Per README, copy only what this feature needs; do not pull in tables/notifications/articles machinery.

## Resolved decisions

- **View layout:** collapse `djangoapp/views/home.py` + `djangoapp/views/login_for_test.py` into a single flat `djangoapp/views.py` (delete the `views/` package). User-management endpoints live in their own `djangoapp/views/users.py` (mirrors prevproject), imported by `urls.py`.
- **No pk/id leak (hard rule):** prevproject's `UserProfile` carries `id=user.pk`. In instant `UserProfile` is **pk-free** — only `public_id` + `title`. The frontend `UserSchema` drops the integer `id`. Every `/users` URL and response uses `public_id` only. (This deviates from prevproject's deferred-leak stance; instant enforces the rule from day one.)
- **Endpoints (all via django-ninja `NinjaAPI`, namespace `users-http`, mounted at `""` like prevproject):**
  - `GET /users/list` — superuser-only (404 otherwise); paginated table (25/orphans 5) + username jump-to-profile search
  - `GET /users/api/search?q=` — superuser-only; returns `{users:[{public_id, username, title}]}` for the multiselect
  - `GET /users/id/{public_id}` — public (anon allowed); `description`/`username` shown only when `has_public_profile`; admin attrs + `history_count` only for superuser viewers
  - `GET /users/edit/{public_id}` + `POST /users/edit/{public_id}` — superuser-only; editable set = first_name, last_name, email, description, has_public_profile, is_active, is_staff, is_superuser (**username read-only**); self-demotion blocked; `description` sanitized via `nh3`
  - `GET /users/history/{public_id}` — superuser-only; per-field diff entries
- **Model extensions on `User`:** `search_users` (pg_trgm `TrigramSimilarity` over first_name/last_name/username, similarity>0.1, ordered), `snapshot()`, `update(...)` (snapshot before/after + `UserHistory.record_edited`, no-op submit creates no entry). Add 3 GIN trigram indexes (`user_first_name_trgm_idx` etc.) + keep `db_table="auth_user"`.
- **History model:** `UserHistory` (target_user FK SET_NULL + `target_user_public_id_copy`, actor `user` FK SET_NULL, `time`, `action` choices, `_changes` JSONField; indexes on target_user + time; ordering -time) + pydantic types `StringChange`, `BoolChange`, `UserHistoryContent`, `UserSnapshot` (with `as_new`/`difference`), `UserHistoryEntryItem`, `UserHistory.record_created/record_edited/record_deleted`. All mirror prevproject.
- **Migration:** new `0002` — first op `TrigramExtension()` (instant's `0001` has none), then the 3 GIN indexes on `auth_user`, then `UserHistory`. (`0001` is already applied to the dev DB; do not regenerate it.)
- **Supporting modules to port:** `djangoapp/errors.py` (`ApiError` + `register_api_error_handlers`), `djangoapp/utils.py::sanitize_html` (nh3 whitelist), `djangoapp/tests/query_budget.py` (`QueryBudgetMixin/TestCase/InertiaTestCase` using `inertia.test.InertiaTestCase`). Switch instant's existing inertia unit tests off the hand-rolled `_inertia_props` helper onto `InertiaTestCase` props.
- **Frontend infra to port (deps + components):** add `quill`, `sweetalert2`, `vue-multiselect` to `frontend/package.json`; port `components/Layout.vue` (**trimmed**: navbar = signed-in user link to `/users/id/<public_id>` + logout + superuser-only `/users/list` link; **drop** prevproject's notification_count + `/tables/_debug`), `components/RenderRawHtml.vue`, `components/RichTextEditor.vue` (Quill), `utils/sweetalert.ts` (`showErrorToast`), a global axios wrapper (CSRF + `showErrorToast` on every call, per AGENTS frontend rule). Add `styles/users.scss` + `@use` in `main.scss`.
- **Frontend pages:** `UserList.vue` (table + multiselect jump-to-profile + pagination), `UserDetails.vue` (public attrs; admin panel + `History (N)` for superusers; description via `RenderRawHtml`), `UserEdit.vue` (form for the 8 fields, username read-only, description via `RichTextEditor`, submit via axios + `showErrorToast`), `UserHistory.vue` (diff entries, description rendered as HTML). Add zod schemas (`UserSchema` pk-free, `UserListItemSchema`, `UserListPropsSchema`, `UserDetailsPropsSchema`, `UserEditPropsSchema`, `UserHistoryPropsSchema`, `UserSearchItemSchema`, etc.).
- **Home page:** keep `Home.vue` as the signed-out landing; once `Layout` exists, authenticated pages share it. Login stays the Google link; logout moves into `Layout`.
- **Access rule:** any resource a user cannot access returns **404** (not 403) — matches prevproject and AGENTS.

## Plan

1. Consolidate views into `djangoapp/views.py`.
2. Port backend support modules (`errors`, `utils.sanitize_html`, query-budget test base).
3. Extend `User` (search/snapshot/update + GIN indexes) and add `UserHistory` + pydantic diff types; generate `0002`.
4. Port `views/users.py` (ninja router) + mount in `urls.py`.
5. Port frontend infra (deps, Layout/RenderRawHtml/RichTextEditor, sweetalert, axios wrapper, schemas, styles).
6. Port the four `User*.vue` pages.
7. Port unit tests (`tests/models/test_user.py`, `tests/views/test_users.py`); migrate existing inertia tests to `InertiaTestCase`.
8. Port playwright `tests/playwright/test_users.py` (edit/history e2e).
9. Lint + `./run checkall` to the finish.

## Checklist

### Phase 0: Consolidate views

- [x] create `djangoapp/views.py` containing `home` and `login_for_test` (moved verbatim from `views/home.py` + `views/login_for_test.py`)
- [x] delete `djangoapp/views/` package (`__init__.py`, `home.py`, `login_for_test.py`)
- [x] update `djangoapp/urls.py` imports to `from djangoapp.views import home, login_for_test`
- [x] `./run lintfix` + `./run typecheck` + `./run test` green (no behaviour change)

### Phase 1: Backend support modules

- [x] add `djangoapp/errors.py` (`ApiError`, `register_api_error_handlers`) verbatim from prevproject
- [x] add `djangoapp/utils.py` with `sanitize_html` (nh3 `ALLOWED_TAGS`/`ALLOWED_ATTRIBUTES` + BOM strip); `models/__init__.py`/imports updated
- [x] add `djangoapp/tests/query_budget.py` (`QueryBudgetMixin`, `QueryBudgetTestCase`, `QueryBudgetInertiaTestCase`) verbatim from prevproject
- [x] migrate `djangoapp/tests/test_home.py` off `_inertia_props` onto `inertia.test.InertiaTestCase` props; delete the hand-rolled helper
- [x] `./run lintfix` + `./run typecheck` + `./run test` green

### Phase 2: User model + history + pydantic types

- [x] extend `User` in `djangoapp/models/base.py`:
    - [x] `search_users` classmethod (TrigramSimilarity over first_name/last_name/username; empty q -> all by username)
    - [x] `snapshot()` -> `UserSnapshot`
    - [x] `update(*, first_name, last_name, email, description, has_public_profile, is_active, is_staff, is_superuser, user)` (snapshot + save + `UserHistory.record_edited` only on real change)
    - [x] `Meta.indexes`: 3 GIN trigram indexes (`gin_trgm_ops`), keep `db_table="auth_user"`
- [x] add pydantic types in `djangoapp/models/base.py`: `UserProfile` (**pk-free**: `public_id`, `title`), `StringChange`, `BoolChange`, `UserHistoryContent`, `UserSnapshot` (`as_new`/`difference`), `UserHistoryEntryItem`
- [x] add `UserHistory` model + `to_user_history_entry_item` + `record_created/record_edited/record_deleted`
- [x] re-export new symbols from `djangoapp/models/__init__.py`
- [x] `makemigrations djangoapp` -> `0002` (TrigramExtension first, then GIN indexes, then UserHistory)

### Phase 3: `/users` views

- [x] add `djangoapp/views/users.py` (port prevproject's): pydantic props/schemas (`UserListItem`, `UserListProps`, `UserDetailsProps`, `UserEditItem/Props`, `UserUpdateSchema` with sanitize+email validators, `UserHistoryProps`, `UserSearchItem/Response`, `MessageResponse`), helpers (`viewer_profile` pk-free, `superuser_or_404`, `get_user_or_404`), `users_router` ops (`/list`, `/api/search`, `/id/{public_id}`, `/edit/{public_id}` GET+POST, `/history/{public_id}`), `users_api = NinjaAPI(urls_namespace="users-http")` with error handlers
- [x] mount `users_api.urls` at `""` in `djangoapp/urls.py` (so paths are `/users/...`)

### Phase 4: Frontend infra

- [x] add deps to `frontend/package.json`: `quill`, `sweetalert2`, `vue-multiselect`; `npm install`
- [x] port `components/Layout.vue` (trimmed: user profile link + logout + superuser-only `/users/list`; no notification_count, no `/tables/_debug`)
- [x] port `components/RenderRawHtml.vue`, `components/RichTextEditor.vue`
- [x] port `utils/sweetalert.ts` (`showToast`, `showErrorToast`, `extractErrorMessage`); add a global axios wrapper (CSRF + `showErrorToast` in every catch) used by all submit calls
- [x] extend `src/schemas.ts`: pk-free `UserSchema`, `UserListItemSchema`, `UserListPaginationSchema`, `UserListFiltersSchema`, `UserListPropsSchema`, `UserSearchItemSchema`/`UserSearchResponseSchema`, `UserDetailsPropsSchema`, `UserEditItemSchema`/`UserEditPropsSchema`, `UserHistoryEntrySchema`/`UserHistoryChangesSchema`/`UserHistoryPropsSchema`
- [x] add `styles/users.scss` + `@use` in `main.scss`
- [x] `npm run lint:fix` + `npm run type-check` + `npm run lint` clean

### Phase 5: Frontend pages

- [x] `UserList.vue` — table (Full name->profile, Username, Email, Public, Staff, Superuser, Actions=Edit/History) + inactive-row fainter + single-select multiselect jump-to-profile (`/users/api/search`) + pagination
- [x] `UserDetails.vue` — public attrs; admin panel (email/public/staff/superuser/active) + `History (N)` only for `viewer_is_superuser`; description via `RenderRawHtml`; name fainter when inactive (admin context)
- [x] `UserEdit.vue` — form for the 8 editable fields (username read-only), description via `RichTextEditor`, submit to `/users/edit/{public_id}` via axios + `showErrorToast`, parse response with zod
- [x] `UserHistory.vue` — diff entries; `description` old/new via `RenderRawHtml`, other fields text
- [x] wire authenticated pages through `<Layout :user="props.user">`; move logout from `Home.vue` into `Layout`
- [x] `npm run lint:fix` + `npm run type-check` + `npm run lint` + `npm run build` clean

### Phase 6: Unit tests

- [x] `djangoapp/tests/models/test_user.py` — public_id auto-gen/unique/format, has_public_profile default, display_name (combine/strip/fallback), search_users ranking + empty-returns-all; snapshot round-trip; update mutates only the 8 fields (username/public_id untouched) + creates an "edited" `UserHistory` with correct diff, no-op submit creates none
- [x] `djangoapp/tests/views/test_users.py` (port prevproject, adapt to pk-free UserProfile + `QueryBudgetInertiaTestCase`):
    - [x] `/list`: anon/non-superuser 404, superuser 200, admin fields present, pagination totals, select-count constant as rows grow
    - [x] `/api/search`: anon/non-superuser 404, empty returns all (capped 20), username filter, item shape = public_id/username/title (no pk)
    - [x] `/id/{public_id}`: anon ok; description gated by `has_public_profile`; owner gated by own flag; `viewer_is_superuser` true/false; admin attrs for superuser only; missing 404
    - [x] `/edit`: anon/non-superuser 404, superuser 200, missing 404; submit updates fields, cannot change username, sanitizes description, records history, blocks self-demotion, rejects invalid email
    - [x] `/history`: anon/non-superuser 404, missing 404, superuser sees entries
- [x] `./run typecheck` + `./run test` green

### Phase 7: Playwright tests

- [x] port `djangoapp/tests/playwright/test_users.py`:
    - [x] `UserEditE2eTestCase` — edit page requires superuser (404); superuser edit saves first_name; updates description
    - [x] `UserHistoryE2eTestCase` — history page requires superuser (404); shows an edit diff
- [x] keep the existing `HomeAuthE2eTestCase`/`LoginForTestGateE2eTestCase` green; login-for-test now lives in `views.py`

### Phase 8: Lint + checkall

- [x] `./run lintfix` (backend ruff + frontend eslint)
- [x] `./run typecheck` (mypy) clean
- [x] frontend `npm run lint` + `npm run type-check` clean
- [x] `./run checkall` runs to the end (unit + playwright green)

## Status (implemented 2026-06-27)

All phases done. `./run checkall` exit 0: ruff clean, mypy 29 files, **53 unit tests**, **9 playwright tests**, frontend lint/type-check clean.

Deviations from the plan above (decisions made during implementation):

- **`views/users.py` -> `djangoapp/users_views.py`.** Phase 0 collapsed `home.py` + `login_for_test.py` into a flat `djangoapp/views.py` (module). Python then can't have both `djangoapp.views` (module) and `djangoapp.views.users`, so the ninja user-management router lives in `djangoapp/users_views.py` instead. Mounted identically in `urls.py`.
- **`UserProfile` is pk-free** as planned (`public_id` + `title` only); `UserSchema` on the frontend has no `id`. The superuser navbar link is gated via a per-page `is-superuser` prop on `Layout.vue` (list/edit/history pass `true`; details passes `viewer_is_superuser`).
- **Extra frontend deps:** `bootstrap` (CSS+JS, the ported pages use its classes) and `sanitize-html` (+types) for `RenderRawHtml`/`utils/html.ts`, beyond the plan's `quill`/`sweetalert2`/`vue-multiselect`. Added `src/styles/_variables.scss` (color/radius partial) since `users.scss` references SCSS vars not exposed by the compiled bootstrap CSS.
- **Lint:** added `PLR2004` to the tests per-file-ignores (status codes / page sizes are idiomatic in tests), alongside the existing `SLF001`.
- Restored `User.Meta.db_table = "auth_user"` which had been dropped from the model (Phase 0 surfaced it); migration `0002` adds `TrigramExtension()` as its first op, then the 3 GIN indexes, then `UserHistory`.
