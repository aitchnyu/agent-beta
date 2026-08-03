# Upgrade to Inertia 3 + Vite 8, and remove axios

Upgrade the frontend to Inertia.js 3 and Vite 8, and **delete the `axios`
dependency** by migrating every direct `axios` call to Inertia 3's built-in HTTP
client / `useHttp` — including re-wiring Django CSRF for the new client.

## Status / blocker

- **Phase 1 (Vite 8): DONE + verified.** `vite ^8` + `@vitejs/plugin-vue ^6.0.8`,
  `rollupOptions` → `rolldownOptions`. Builds clean, GitDiff resolves, 0 console
  errors, 7/7 tests. `main.js` 1,097 kB.
- **Phase 2 (Inertia 3): BLOCKED — cannot adopt without patching the Django
  adapter.** Inertia 3 reads the initial page **only** from
  `<script data-page="app" type="application/json">` (`@inertiajs/core`
  `getInitialPageFromDOM`), but **inertia-django's latest release is 1.2.0 (Mar
  2025)**, which predates Inertia 3 (Mar 2026) and emits the v2
  `<div id="app" data-page>`. Result: `TypeError: Cannot read properties of null
  (reading 'component')` at runtime; no page renders. There is **no newer
  inertia-django** on PyPI to fix this. Bumped `@inertiajs/vue3` to ^3, hit this,
  reverted to ^2 (working state = Vite 8 + Inertia 2).
- **Phase 3 (remove axios): BLOCKED** — depends on Phase 2. On Inertia 2, axios
  is a hard dep of `@inertiajs/core` + `laravel-precognition`, and `useHttp`
  doesn't exist (it's an Inertia 3 feature).

**To unblock:** either (a) wait for an inertia-django release that emits the v3
`<script data-page type="application/json">` format; (b) patch/fork
inertia-django's render to emit that script tag; or (c) stay on Inertia 2 (then
axios can't be fully removed either). Until then, only Vite 8 is in.

## Context (ground truth)

- Versions: `@inertiajs/vue3 ^2.0.0`, `vite ^7.2.4`, `vue ^3.5.33`,
  `@vitejs/plugin-vue ^6`, `inertia-django>=1.2.0`, `vue-tsc 3.2`, TS 5.9.
- axios sites to remove: `main.ts` (import + global CSRF block),
  `pages/opencode/api.ts` (3 `axios.post`), `pages/UserEdit.vue`,
  `pages/UserList.vue`, `utils/sweetalert.ts` (`AxiosError` type),
  `docs/reference/.../NoteForm.vue` (reference), and the SSE prompt stream in
  `useOpencodeConnection.ts` (`axios.post(..., { adapter: "fetch" })`).
- CSRF today: `main.ts` sets `axios.defaults.xsrfCookieName="csrftoken"` +
  `xsrfHeaderName="X-CSRFTOKEN"`; all axios calls ride it (no per-call headers).
- `vite.config.js:13` uses `rollupOptions` (→ `rolldownOptions`). No
  `manualChunks`.
- 15 pages hand-wrap `<Layout>`; no `inertia:*` listeners; no `router.cancel()`;
  no `useForm`.
- Heavy CJS-ish deps that stress the new bundler: highlight.js, sanitize-html,
  marked, quill.

## Checklist

### Phase 1 — Vite 7 → 8
- [ ] Bump `vite` to `^8` in `package.json`
  - [ ] Align `@vitejs/plugin-vue` to a Vite-8-compatible release
- [ ] `vite.config.js`: rename `rollupOptions` → `rolldownOptions`
  - [ ] Move `entryFileNames` / `assetFileNames` under `rolldownOptions.output`
  - [ ] Keep the `with_cache_buster` asset filter + `emptyOutDir: true`
- [ ] Rebuild and verify (Rolldown replaces Rollup/esbuild)
  - [ ] `main.js` size is sane
  - [ ] **GitDiff still resolves** (eager `import.meta.glob` + resolve)
  - [ ] `filePreview.ts` static-import-in-GitDiff vs dynamic-in-DiffBody/FileViewer still works
  - [ ] `sanitize-html` / `marked` / `quill` resolve under the new CJS-interop rules
- [ ] `npm run type-check`, `npm run lint`, `npm run build` clean

### Phase 2 — Inertia 2 → 3
- [ ] Bump `@inertiajs/vue3` to `^3` in `package.json`
- [ ] `main.ts`: update `createInertiaApp` `resolve` signature
  - [ ] v3 passes `(name, props)` — props unused today; keep ignoring but update the param
- [ ] Confirm initial page still read from `base.html`'s `data-page` attribute
- [ ] Audit "future" options → defaults (history/encrypt behavior)
  - [ ] App sets none today; confirm navigation/back-forward unchanged
- [ ] Verify `inertia-django` 1.2 compat with the v3 client
  - [ ] Bump in `pyproject.toml` if incompatible
- [ ] `npm run type-check` clean

### Phase 3 — Remove axios (CSRF-first)
- [ ] **CSRF first** — configure Inertia 3's built-in client (request interceptor)
  - [ ] Read `csrftoken` cookie, set `X-CSRFTOKEN` header on mutating requests
  - [ ] Equivalent of today's global `axios.defaults`
  - [ ] **Prove with one real POST** (UserEdit save) before migrating the rest — or every POST 403s
- [ ] `pages/opencode/api.ts`: `axios.post` → `useHttp`
  - [ ] `postPermission`, `postAbort`, `postDeleteSession` (3 calls)
  - [ ] Keep `OpencodeActionResponseSchema.parse` on the result
- [ ] `pages/UserEdit.vue`: `axios.post(.../edit/<id>)` → `useHttp`
- [ ] `pages/UserList.vue`: `axios.get(.../api/search)` → `useHttp`
- [ ] `useOpencodeConnection.ts`: SSE prompt stream off axios
  - [ ] `axios.post(url, { adapter: "fetch", responseType: "stream" })` → plain `fetch(url, { method, body, signal })`
  - [ ] Keep the `AbortController` signal + `ReadableStream` via `parseSsePayloads`
  - [ ] (Inertia's client isn't a streaming client — use raw `fetch`)
- [ ] `utils/sweetalert.ts`: drop `AxiosError`
  - [ ] `showErrorToast` extracts message from v3 `HttpError` / generic `unknown`
  - [ ] Keep the fallback-message arg
- [ ] `main.ts`: remove the `axios` import + the `DOMContentLoaded` CSRF block
- [ ] `docs/reference/.../NoteForm.vue`: `axios.post` → `useHttp` (keep reference copy-paste-accurate)
  - [ ] Update README's axios wording if any
- [ ] `package.json`: remove `axios` from `dependencies`

## CSRF gotcha (the one non-trivial part)

- Django issues a `csrftoken` cookie and expects the `X-CSRFTOKEN` header (set
  today via `axios.defaults`).
- Inertia 3's built-in client is tuned to Laravel's `XSRF-TOKEN` cookie /
  `X-XSRF-TOKEN` header.
- Migrating without re-wiring → every state-changing request (UserEdit save,
  opencode permission/abort/delete, note create) returns **403 Forbidden**.
- Fix: client request interceptor reads `csrftoken` from `document.cookie` and
  sets `X-CSRFTOKEN`.
- The cookie is set by `{% csrf_token %}` in `base.html` on first GET (see
  `test_home_issues_csrftoken_cookie`).

## Verify

- [ ] `npm run type-check`, `npm run lint`, `npm run test`, `npm run build` clean
- [ ] **No axios in the bundle**
  - [ ] `grep -rn axios frontend/src` returns nothing
  - [ ] `axios` absent from `package.json`
  - [ ] `axios` not in the built `main.js`
- [ ] CSRF-critical manual checks (all succeed, no 403, errors still toast)
  - [ ] UserEdit save (POST)
  - [ ] UserList search (GET)
  - [ ] opencode permission / abort / delete (POSTs via `api.ts`)
  - [ ] reference NoteForm create
- [ ] SSE prompt stream still streams (the `fetch` migration)
  - [ ] A real agent turn renders reasoning + tool blocks + interactive permission flow end-to-end
- [ ] Navigation unchanged
  - [ ] git pages, /agent, /users render
  - [ ] back/forward works (history behavior after future→defaults)
