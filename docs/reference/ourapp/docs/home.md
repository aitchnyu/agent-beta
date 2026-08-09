# Home

The landing page — the app's single public route, owned by the app (not the
framework).

## Route

- `GET /` → Inertia page `ours/Home`, props `{ is_authenticated, display_name, public_id }`.

## Behaviour

- Anonymous visitor: `is_authenticated=false`, empty `display_name`/`public_id`,
  plus a Google sign-in link rendered client-side.
- Authenticated viewer: their `display_name` and `public_id` (never the integer
  `pk`), plus a logout form.
- Links to the app's features — each shown only when this viewer can use it
  (e.g. todos, which 404s for anon, is hidden from signed-out visitors).

## Files

- Model: none. View: `views/home.py` (`router`, mounted at `/`).
- Frontend: `frontend/src/ours/pages/Home.vue`, schema in `ours/schemas.ts`.
- Tests: `tests/test_home_views.py`, `tests/test_home_playwright.py`.
