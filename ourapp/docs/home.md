# Home (+ mockup demo)

The landing page — plus the repo's permanent mockup demo route.

## Route

- `GET /` → Inertia page `ours/Home`, props `{ is_authenticated, display_name, public_id }`.
- `GET /mockup-todos` → Inertia page `ours/MockupTodos` (superuser-only; 404
  otherwise), no props.

## Behaviour

- Anonymous visitor: `is_authenticated=false`, empty `display_name`/`public_id`,
  plus a Google sign-in link rendered client-side.
- Authenticated viewer: their `display_name` and `public_id` (never the integer
  `pk`), plus a logout form.
- `/mockup-todos` renders a static todo list mirroring the reference app's
  todos page under the `div.mockup` crosshatch wrapper — the shipped example
  of the mockup convention (`agentconfig/steer.md` § Mockups and diagrams).
  Unlike a feature mockup it never graduates; append `?final=1` to drop the
  crosshatch and see the "graduated" look (the README's mockup screenshot
  pair comes from these two views).

## Files

- Model: none.
- View: `views/home.py` (`router`, mounted at `/` — owns both routes).
- Frontend: `frontend/src/ours/pages/Home.vue`,
  `frontend/src/ours/pages/MockupTodos.vue`, schema in `ours/schemas.ts`.
- Tests: `tests/test_home_views.py`, `tests/test_home_playwright.py` (the
  mockup route's superuser gate is covered by the framework screenshot pass).
