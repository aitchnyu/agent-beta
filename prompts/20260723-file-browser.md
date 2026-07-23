# Superuser file browser at `/files/...`

A read-only Inertia file browser over the repo tree (root = `BASE_DIR`),
superuser-only (non-superuser → 404, never 403 — same gate as `/manage/apps`,
`/agent/`). Directories list their entries (folders first); files preview as
text or render as images; any file can be downloaded or served raw. The "Files"
button in the nav lands at `apps/`, and you can navigate up to the repo root but
no higher.

- `/files/apps` — default landing (the Files button).
- `/files/apps/TriviaFacts/frontend/src/main.ts` — view a text file.
- `/files/djangoapp/views/opencode.py` — anywhere in the repo.
- `/files/` — repo root listing.
- `/files-download/<path>` — download raw bytes (attachment).
- `/files-raw/<path>` — serve raw bytes inline (real `Content-Type`, for `<img>`).

## Routing (`djangoapp/urls.py`)

One route with an optional capture (a single `<path:rel>` converter can't match
the empty root, so use a regex):

```python
re_path(r"^files(?:/(?P<rel>.*))?$", file_browser, name="files"),
```

`rel` is repo-root-relative. ⚠️ The optional group means `/files` (no trailing
slash) arrives as `rel=None` while `/files/` arrives as `rel=""` —
:class:`PathWrapper` normalizes both (`(rel or "").strip().rstrip("/")`).

## Backend (`djangoapp/views/files.py`)

`file_browser(request, rel="")`:

1. **Gate** — `require_superuser(request)` (shared helper in
   `djangoapp/views/__init__.py`, reused by manage/opencode) → 404 otherwise.
2. **Resolve + confine** — `target = PathWrapper(rel)`. `PathWrapper.__init__`
   resolves `(_REPO_ROOT / rel).resolve()` and raises `Http404` unless the result
   is `_REPO_ROOT` or `is_relative_to(_REPO_ROOT)` (Python 3.9+; project is
   py314). This blocks `..`, absolute paths, and symlink escapes; a missing path
   also 404s.
3. **Download / raw** — on **separate endpoints** (`_serve` is their shared body):
   - `file_download` (`/files-download/<rel>`) → `as_attachment=True`, `application/octet-stream`.
   - `file_raw` (`/files-raw/<rel>`) → `as_attachment=False`, `target.mime()`
     **but only when `target.is_image()`** (404 otherwise). Used by `<img>`;
     the image-only gate is what keeps raw serving from being a same-origin XSS sink.
   Both 404 if the target isn't a file. `FileResponse` streams, so no size cap.
   (`file_browser` renders only — it no longer serves bytes.)
4. **Directory** — `target.list_entries(include_hidden=…)` returns `FileEntry`s
   (`name`, `is_dir`, `is_image`, `size`, `mtime` as epoch-ms), folders-first
   then alphabetical, hiding `.venv`/`node_modules`/`.git`/`__pycache__` unless
   `?hidden=1`. Renders `FileBrowser` with entries + breadcrumb + parent +
   `contains_hidden_entries`, via `host_template_data()`.
5. **File** — classification renders `FileViewer`:
   - **image** — ext in `_IMAGE_EXTENSIONS` → `kind="image"` (the `<img>` fetches
     via `/files-raw/<rel>`; nothing inlined).
   - **text** — no NUL byte in the first 8 KB (`_TEXT_SNIFF_BYTES`) and size ≤
     `_TEXT_MAX_SIZE` (~1 MB) → `kind="text"` + content. (Heuristic caveat:
     UTF-16/UTF-32 carry NUL bytes and read as binary — acceptable for a dev tool.)
   - **binary** → `kind="binary"` ("not previewable").

`PathWrapper` also exposes `.breadcrumbs()` / `.parent()` / `.stat()` /
`.looks_like_text()` / `.read_text()` / `.open_bytes()` / `.mime()` /
`.list_entries()` — keeping the view functions thin and unit-testable by
patching `_REPO_ROOT` to a tempdir.

## Security (the important parts)

- **Path confinement** in `PathWrapper` (`.resolve()` + `is_relative_to`) — the
  only real traversal exposure; must not be bypassable.
- **Superuser-only** (404 otherwise).
- **No `v-html` for text** — rendered via Vue interpolation (escaped) in `<pre>`;
  a file could contain `<script>`.
- **Raw serving is `<img>`-only** — `/files-raw/<rel>` 404s unless the target is
  an image (`_IMAGE_EXTENSIONS`). This is the real guard: it stops arbitrary
  `text/html` / `image/svg+xml` from being served inline in the app's
  authenticated origin (a same-origin stored-XSS sink). CSP (`script-src 'self'`)
  is a defense-in-depth backstop, not the primary boundary — and it is
  report-only in `DEBUG`, so it must not be relied on.
- **Read-only** — viewing only; the agent edits via its own tools.
- Sensitive files at the repo root are reachable/downloadable by a superuser by
  design (`.env`, `db.sqlite3`). The gate is the safety boundary.

## Frontend (`frontend/src/`)

- **`utils/files.ts`** (shared) — `fileUrl(rel)` (the single `/files/` prefix),
  `rawUrl(rel)` (`/files-raw/...`), `downloadUrl(rel)` (`/files-download/...`),
  `formatSize(bytes)` ("256 B", "1.5 KB"). (Time formatting lives in
  `HumanizedTime.vue`, not here.)
- **`pages/FileBrowser.vue`** — breadcrumb (root → … → current), entries table
  (icon, name → Inertia `<Link>`, humanized size, `HumanizedTime` mtime).
  Host SPA nav via `<Link>`.
- **`pages/FileViewer.vue`** — breadcrumb + header (name, size, kind, mtime) +
  Download (`downloadUrl(rel)`), then:
  - text → `<pre>` monospace (escaped);
  - image → `<img :src="rawUrl(rel)">`;
  - binary → "not previewable."
- **`schemas.ts`** — `FileCrumbSchema`, `FileEntrySchema`, `FileBrowserPropsSchema`
  (`contains_hidden_entries`), `FileViewerPropsSchema` (`kind`, `text`; no
  `image_url`). **Host props nesting**: the view wraps props under a `props` key
  (`{"props": ...}`); each SFC does `defineProps<{ props: object }>()` then
  parses `props.props` (matches `manage.py`/`AppList.vue`).
- **`styles/_files.scss`** (imported in `main.scss`).

## Files button (`frontend/src/components/Layout.vue`)

Superuser "Files" link next to Apps/Users → `/files/apps`.

## Checklist (implemented)

### Backend
- [x] promote `_require_superuser` → shared `require_superuser` in `views/__init__.py`; manage/opencode/files reuse it
- [x] `djangoapp/views/files.py` — `PathWrapper` (confine via `is_relative_to(_REPO_ROOT)`), `file_browser`, `_serve`
- [x] `/files-download/<rel>` (attachment, octet-stream) and `/files-raw/<rel>` (inline, real MIME, **image-only**)
- [x] dir listing (entries + breadcrumb + parent + `contains_hidden_entries`); hide `.venv`/`node_modules`/`.git`/`__pycache__` (`?hidden=1`)
- [x] file classify: image (via `/files-raw`) / text (≤1 MB, NUL-sniff) / binary; `mtime` as epoch-ms
- [x] render Inertia `FileBrowser`/`FileViewer` with `{"props": ...}` + `host_template_data()`
- [x] `djangoapp/urls.py` — one `re_path(r"^files(?:/(?P<rel>.*))?$", ...)` (+ import `re_path`)

### Frontend
- [x] `utils/files.ts` — `fileUrl`, `rawUrl`, `downloadUrl`, `formatSize`
- [x] `FileBrowser.vue` — breadcrumb + entries (friendly size/mtime)
- [x] `FileViewer.vue` — text `<pre>` (escaped) / `<img :src="rawUrl(rel)">` / binary + Download
- [x] both SFCs parse `props.props` (host nesting)
- [x] zod schemas in `schemas.ts`
- [x] `styles/_files.scss`

### Nav
- [x] superuser "Files" link in `Layout.vue` → `/files/apps`

### Tests (`djangoapp/tests/views/test_files.py`)
- [x] non-superuser/anon → 404
- [x] `..` / absolute / symlink-escape → 404 (`PathWrapper` unit test + download/raw HTTP tests)
- [x] `/files` and `/files/` both serve the root (rel `None` vs `""`)
- [x] dir listing + breadcrumb; hidden dirs filtered
- [x] text file content present and escaped
- [x] image → `<img>` (bytes inline, real MIME via `/files-raw`; `PathWrapper` unit)
- [x] binary → "not previewable"
- [x] `/files-download` → attachment bytes (`Content-Disposition`)

### Verify
- [x] `uv run ruff check` · `uv run mypy .` · frontend `lint`/`type-check`/`build-only` · `./run djangomanage test djangoapp.tests.views`

## Notes / decisions

- **One route** (regex optional capture), not two — a `<path>` converter can't
  match the empty root; the optional group yields `rel=None` for `/files`.
- **Repo-root scope, `apps/` default** — the Files button lands at `apps/`; you
  can go up to the repo root but not above.
- **Images served raw, not inlined** — `/files-raw/<rel>` (inline, real MIME,
  **image-only gate**) lets `<img>` fetch the bytes; no base64 payload bloat,
  browser-cacheable. The image-only check (not CSP) is the boundary that keeps
  raw serving from being a same-origin HTML/SVG XSS sink.
- **Separate serving endpoints** — `/files-download/<rel>` and `/files-raw/<rel>`,
  not query params on `/files/...`; `_serve` is their shared body, `file_browser`
  renders only. Distinct prefixes (not suffix routes) since `<path:rel>` captures
  slashes.
- **Friendly formatting** — `mtime` (epoch-ms) and `size` (bytes) rendered
  client-side. `HumanizedTime` (`components/`) shows relative time; click toggles to
  absolute where the date leads and the time + tz are deemphasized. The relative
  formatter lives inside the component; `formatSize`/URL helpers in `utils/files.ts`.
- **`PathWrapper`** consolidates resolution/confinement, breadcrumbs, parent, stats,
  listing, classification, and serving — the view stays thin. Path math uses
  `pathlib.PurePosixPath` (`parent`/`parts`), not hand-rolled split/join. Unit-tested
  by patching `_REPO_ROOT` to a tempdir. (Renamed from `FileTarget`.)
- **`?hidden=true`** — the value `true` (case-insensitive) reveals excluded dirs
  (`.venv`/`node_modules`/`.git`/`__pycache__`); the listing's
  `contains_hidden_entries` drives a Show/Hide toggle in `FileBrowser.vue`.
  (The toggle only ever sends `?hidden=true`.)
- **Shared superuser gate** — `require_superuser` lives once in `views/__init__.py`,
  reused by manage/opencode/files (the prior per-module copies were removed).
- **Playwright E2E** (`djangoapp/tests/playwright/test_files.py`) covers listing,
  breadcrumb, text preview, entry navigation, and the time toggle (`--tag playwright`).
  Uses Python assert methods; `networkidle` navigation + targeted `wait_for` keep it
  flake-free across Inertia hydration.

## Review follow-ups (post-commit d73131c)

Findings from a multi-dimensional review of the commit, with status.

### Security
- [x] **`/files-raw` was a same-origin XSS sink.** It served *any* file inline with
  its guessed `Content-Type`, so a repo `evil.html` rendered as `text/html` in the
  authenticated app origin. **Fix:** `file_raw` now 404s unless `target.is_image()`
  (raw's only consumer is `<img>`). CSP is a backstop, not the boundary — and it is
  report-only in `DEBUG`.
- [x] **Doc corrected** — the old "raw image serving is safe under CSP" claim was
  replaced; the image-only gate is now documented as the boundary.
- Path confinement (`resolve` + `is_relative_to`) and the 404-not-403 gate were
  verified sound; no change needed.

### Correctness
- [x] `formatSize(1024)` returned `"1.0 KB"`; now `"1 KB"` (exact units stay integral).
- [x] `FileViewerProps.parent` typed `str` with an `or ""` workaround; now `str | None`
  to match `PathWrapper.parent()`, dropping the workaround.
- `FileEntry.is_image` is computed for directories too (a dir named `foo.png` shows 🖼)
  — cosmetic, left as-is.

### Tests
- [x] Raw-serving test reworked: no tracked image exists in the repo, so it patches
  `_REPO_ROOT` to a tempdir with a real PNG and asserts inline serving + Content-Type.
- [x] Added `test_raw_non_image_404` (a `.txt` 404s on `/files-raw`).
- [x] Added Playwright `test_text_preview_is_html_escaped` — previews a tracked file
  with markup (`frontend/src/pages/FileBrowser.vue`) and asserts Vue interpolation
  escaped it (no live element). Catches a `v-html` regression.
- Not added: HTTP test for the `?hidden=true` toggle revealing dirs; empty-dir render
  test. Existing unit coverage on `list_entries(include_hidden=True)` is deemed enough.

### Frontend / docs
- [x] Removed the stray self-question comment in `FileBrowser.vue`.
- [x] Reconciled stale references in this prompt: `FileTarget` → `PathWrapper`,
  `?download=1`/`?raw=1` query params → `/files-download` / `/files-raw` routes,
  `formatMtime`/`fullMtime` → `HumanizedTime` component, `?hidden` truthy-values →
  `true` only.

### Verify
- [x] `uv run ruff check` · `uv run mypy .` · `./run test` · frontend `lint`/`type-check`/`build-only` · `./run playwrighttest`
