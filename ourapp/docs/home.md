# Home (+ the mockup hatch)

The landing page — plus the generic mockup route every mockup page serves from.

## Route

- `GET /` → Inertia page `ours/Home`, no page props (login state is the shared
  viewer prop `user`, injected by SharedPropsMiddleware).
- `GET /mockup/MockupTodos` → Inertia page `ours/MockupTodos` (superuser-only; 404
  otherwise), no props.

## Behaviour

- Anonymous visitor: the shared `user` prop is null and the page renders a
  login-helper block — "You are not logged in. You may ask your agent:"
  with two example prompts (create a superuser + send a login link; send a
  login link for an existing user). No auth chrome lives on the page —
  sign-in dropdown and user menu (with logout) are the framework navbar's.
- Authenticated viewer: the shared `user` prop carries their display name and
  `public_id` (never the integer `pk`); the page shows the placeholder's
  feature pointers as explained
  points — `ourapp/` (backend), `frontend/src/ours/` (frontend),
  `docs/reference/` (the complete worked example).
- `/mockup/MockupTodos` renders a static todo list mirroring the reference app's
  todos page under the `div.mockup` crosshatch wrapper — the shipped example
  of the mockup convention (`agentconfig/steer.md` § Mockups).
  Unlike a feature mockup it never graduates; append `?final=1` to drop the
  crosshatch and see the "graduated" look (the README's mockup screenshot
  pair comes from these two views).

## Files

- Model: none.
- View: `views/home.py` (`router`, mounted at `/` — owns both routes).
- Frontend: `frontend/src/ours/pages/Home.vue`,
  `frontend/src/ours/pages/MockupTodos.vue` (no schemas of their own — the
  page reads the shared viewer props via `utils/sharedProps.ts`).
- Tests: `tests/test_home_views.py` (the page's own e2e module was retired
  with the auth chrome: the anon landing elements are exercised by the
  framework e2e suite, and the mockup route's superuser gate is covered by
  the framework screenshot pass).
