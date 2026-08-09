# Home

The landing page — the only feature in the placeholder app.

## Route

- `GET /` → Inertia page `ours/Home`, props `{ is_authenticated, display_name, public_id }`.

## Behaviour

- Anonymous visitor: `is_authenticated=false`, empty `display_name`/`public_id`,
  plus a Google sign-in link rendered client-side.
- Authenticated viewer: their `display_name` and `public_id` (never the integer
  `pk`), plus a logout form.

## Files

- Model: none.
- View: `views/home.py` (`router`, mounted at `/`).
- Frontend: `frontend/src/ours/pages/Home.vue`, schema in `ours/schemas.ts`.
- Tests: `tests/test_home_views.py`, `tests/test_home_playwright.py`.
