## Consistent API error handling (backend) + error toasts (frontend)

Make every `raise HttpError`/`Http404` in API endpoints return a consistent,
message-bearing JSON response, and ensure every frontend API call surfaces
those messages (and any unhandled error) as an error toast.

### Context / the two route families

- **Ninja API operations** (`ninja_api`, `articles_api`, `users_api`, and the
  `OurRouter` methods in `BaseView.get_router` → search-rows, row-updates,
  create-comment, create-row-submit, update-row-submit, delete-row, etc.) →
  ninja's exception handlers apply. These return JSON.
- **Django `path()` views** (`BaseView.get_url_patterns` → list/id/create-row/
  update-row pages, `_notifications_page`, etc.) → Django's default handler.
  These render Inertia/HTML.

Overriding ninja's `Http404`/`HttpError` handlers affects only JSON endpoints;
page-rendering 404s still render the Django 404 page. Page-load 404s cannot be
toasted (SPA not mounted) — out of scope by design.

### Decisions (confirmed)

- `ApiError` payload, when given, **replaces the whole JSON body** verbatim
  (e.g. `{"code":"dup","message":"Tag exists"}`). `message` is kept for logging.
  When payload is `None`, body is `{"detail": message}`.
- Search endpoints (search-authors, search-tags, search-users) **toast on error**
  like every other call (no silent-fail).

### Plan

#### Backend

- New `djangoapp/errors.py`:
  - `class ApiError(HttpError)` with `__init__(status_code, message, payload=None)`.
  - `register_api_error_handlers(api)` registering:
    - `ApiError` → `body = exc.payload if exc.payload is not None else {"detail": str(exc)}`;
      `api.create_response(request, body, status=exc.status_code)`.
    - `Http404` → `{"detail": str(exc) or "Not Found"}` (propagates `Http404("msg")`
      and the model `*_or_404` helpers, instead of ninja discarding the message).
- Call `register_api_error_handlers` on all three: `ninja_api` (base.py:74),
  `articles_api` (articles.py:828), `users_api` (users.py:343).
- Standardize raises:
  - All `raise HttpError(...)` (articles.py ×6, users.py ×1) → `raise ApiError(...)`
    with a clear message; use `payload=` where structured detail helps (image/tag
    endpoints).
  - Bare `raise Http404` / `raise Http404 from None` **inside ninja operations**
    (BaseView submit/comment methods, `_search_users_api`, etc.) →
    `raise ApiError(404, "<context>") from None`.
  - `*_or_404` model helpers (`Article.get_or_404`, `Article.get_or_404_with_annotations`,
    `ArticleTag.get_or_404`) stay as `Http404` (now message-aware via the handler);
    add a short context message to each.
  - `raise Http404` in Django page views (`list_page`, `details_page`,
    `_notifications_page`, `_create_row`/`_update_row` page wrappers) → keep as
    `Http404` (renders HTML 404 page for full-page navigation).

#### Frontend

- Enhance `showErrorToast` (`utils/sweetalert.ts`):
  - `detail` is string → use it.
  - `detail` is dict → use `detail.message` if present, else stringify.
  - body is a dict without `detail` → use `body.message`, else stringify.
  - no body / network error → `fallback`.
  - always surface `HTTP <status>` in toast text.
- Audit every axios call → wrap in try/catch and call `showErrorToast(e, fallback)`
  in the catch (replace any static `showToast("error", ...)`):
  - `RowDetailsContent.vue:34`, `RowUpdateList.vue:51/78/93`, `Notifications.vue:94/111`.
  - `CommentForm.vue:44`, `RowForm.vue:109`, `ForeignKeyFilter.vue:58/83`,
    `ForeignKeyMultiselect.vue:70`, `RowUpdateFilter.vue:61` (verify catch bodies).
  - Search endpoints (toast on error): `ArticleList.vue:66/73`,
    `ArticleForm.vue:137/148`, `UserList.vue:25`, `RowUpdateFilter.vue:51`.
- Global safety net in `main.ts`:
  - `app.config.errorHandler` → `showErrorToast(err, "Something went wrong")`.
  - `window.addEventListener("unhandledrejection", ...)` → same.
  - `window.addEventListener("error", ...)` → same.

#### Tests / verification

- Backend: assert each `ApiError`/`Http404`-in-API path returns expected JSON
  `{detail}` + status; add a payload-dict test.
- Frontend: rely on Playwright for toast rendering on a failing call.
- `./run lintfix`, `./run typecheck`, `./run test`, then `./run checkall` green.

### Checklist

#### Phase 1: Backend error type + handler

- [x] create `djangoapp/errors.py` with `ApiError(HttpError)` and
      `register_api_error_handlers(api)`
- [x] `ApiError` handler returns payload dict verbatim, else `{"detail": message}`
- [x] `Http404` handler returns `{"detail": str(exc) or "Not Found"}`
- [x] register handlers on `ninja_api` (base.py), `articles_api` (articles.py),
      `users_api` (users.py)

#### Phase 2: Standardize backend raises

- [x] `raise HttpError(...)` -> `raise ApiError(...)` in
    - [x] articles.py (6 spots: image upload/lookup, tag create/update)
    - [x] users.py:310
- [x] bare `raise Http404` / `from None` inside ninja operations -> `ApiError(404, ...)`
    - [x] base.py BaseView submit/comment methods (1062/1067/1096/1132/1186/1210/1213/1231/1236/1254/1258)
    - [x] base.py `_search_users_api` (91)
    - [x] articles.py API endpoints (276/291/297/303/501/533/555/566/588/618/623/677/724/727/747/750)
    - [x] users.py API endpoint (174)
- [x] add context messages to model `*_or_404` helpers
    - [x] `Article.get_or_404` (models/base.py:1836)
    - [x] `Article.get_or_404_with_annotations` (models/base.py:1844)
    - [x] `ArticleTag.get_or_404` (models/base.py:1715)
- [x] keep `raise Http404` in Django page views (list_page, details_page,
      `_notifications_page`, `_create_row`/`_update_row` wrappers)

#### Phase 3: Frontend `showErrorToast` + global handlers

- [x] enhance `showErrorToast` (string/dict/message/fallback + HTTP status)
- [x] `app.config.errorHandler` in main.ts
- [x] `unhandledrejection` listener in main.ts
- [x] `error` listener in main.ts

#### Phase 4: Frontend axios call audit (try/catch + showErrorToast)

- [x] RowDetailsContent.vue (replace static toast)
- [x] RowUpdateList.vue (3 catches)
- [x] Notifications.vue (2 catches)
- [x] CommentForm.vue
- [x] RowForm.vue
- [x] ForeignKeyFilter.vue (2)
- [x] ForeignKeyMultiselect.vue
- [x] RowUpdateFilter.vue (verify + search call)
- [x] ArticleList.vue (search-authors, search-tags)
- [x] ArticleForm.vue (search-tags, search-authors)
- [x] UserList.vue (search)
- [x] verify all other axios calls already use showErrorToast

#### Phase 5: Tests

- [x] backend test: ApiError string -> `{detail}` + status
- [x] backend test: ApiError payload dict -> body verbatim
- [x] backend test: Http404("msg") in API -> `{detail: msg}`
- [x] backend test: bare Http404 in API -> `{detail: "Not Found"}`
- [x] Playwright: failing API call renders error toast with message

#### Phase 6: Lint + checkall

- [x] `./run lintfix`
- [x] `./run typecheck`
- [x] `./run test`
- [x] `cd frontend && npm run lint:fix`
- [x] `cd frontend && npm run type-check`
- [x] `cd frontend && npm run lint`
- [x] `./run checkall` green
