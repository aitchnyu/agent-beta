# Home

The landing page — the app's single public route, owned by the app (not the
framework).

## Route

- `GET /` → Inertia page `ours/Home`, props `{ is_authenticated, display_name, public_id, fact_of_day }`.

## Behaviour

- Anonymous visitor: `is_authenticated=false`, empty `display_name`/`public_id`,
  plus a Google sign-in link rendered client-side.
- Authenticated viewer: their `display_name` and `public_id` (never the integer
  `pk`), plus a logout form.
- `fact_of_day`: today's Fact of the Day (one fixed pick per local date, chosen
  by the Huey cron in `tasks/`); `null` when the fact pool is empty.
- Links to the app's features — each shown only when this viewer can use it
  (e.g. todos, which 404s for anon, is hidden from signed-out visitors).

## Files

- Model: none. View: `views/home.py` (`router`, mounted at `/`).
- Frontend: `frontend/src/ours/pages/Home.vue`, schema in `ours/schemas.ts`.
- Tests: `tests/test_home_views.py` (the page has no e2e module of its own —
  its auth chrome lives in the framework navbar, covered by the framework
  e2e suite).
