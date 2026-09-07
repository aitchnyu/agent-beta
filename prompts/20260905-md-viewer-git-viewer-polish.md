# Markdown viewer polish (outline, links, mermaid fences) + git viewer links, split diffs, status words

## Handwritten requirements (2026-09-05)

When I view md file, I want to see outline of headlines in the top. It should expand if more than 300px.

Hash links in md view doesnt work, ensure those links are rendered correctly. Same for links to other files.

Have tests for all of these.

We had mockups and mermaid in md using html classes. Now render mermaid using ```mermaid``` markup and ensure it renders

We used to have this:

<div class="rich-diagram">
```stateDiagram-v2
    [*] --> pending : generated from the schedule
    pending --> completed : user completes
    completed --> pending : undo
    completed --> [*]
```
</div>

Steer also has messages like: use the HTML-safe lookalikes `‹` `›` `∧`

We will no longer have html in markdown for mockup and mermaid.

Git uncommitted files and commit viewer will link to file url
Diffs will be rendered in two panes or one pane depending on viewport width

Also is U the symbol for new file as in `U ourapp/tests/test_chores_playwright.py`. Have new, mod, del next to filenames with color coding

## Current state

- `FileViewer.vue` markdown path: `renderMarkdown` (marked v18 — **no heading ids
  by default**) → `sanitizeHtml` → `RichTextViewer` `v-html`.
- `RichTextViewer.vue` renders mermaid **only** from `.rich-diagram` raw-HTML
  marker divs (`utils/mermaid.ts` `renderDiagram`); fenced \`\`\`mermaid blocks
  today highlight as plaintext and stay as code.
- `sanitizeHtml` (`utils/html.ts`) rewrites relative `<img src>` (via
  `rewriteImagesFrom`) but **not** `<a href>` — relative links to other files are
  dead; headings carry no ids so `#hash` links have no target.
- Git viewer: `GitUncommitted.vue` shows U/M/A/D letters (grey untracked,
  strikethrough deleted); `GitCommit.vue` shows a `bg-secondary` badge with the
  full status word. Both link each file **only to its diff route** — no link to
  the file itself.
- `GitDiff.vue`: hljs `diff` grammar, one unified pane at every viewport width.
- `agentconfig/steer.md` § Design doc: mermaid inside `<div
  class="rich-diagram">` markers with the no-indent / no-blank-line rules and
  the `‹` `›` `∧` lookalike line — exactly the HTML-in-markdown machinery this
  work retires. (Mockups already became real Vue pages on 2026-08-25.)

## Decisions (already made — implement to these)

- **Status words replace letters**: `untracked`/`added` → **new**, `modified` →
  **mod**, `deleted` → **del**, next to the filename with color coding — new
  `text-success`, mod `text-warning`, del `text-danger` (+ strikethrough kept).
  The backend status strings (`untracked|added|modified|deleted`) are an API
  contract and do NOT change; the frontend maps them. (Supersedes the earlier
  "is U the right symbol" question — words + colors beat any letter.)
- **Mermaid via fences, markers tolerated**: steer/docs switch to \`\`\`mermaid
  fenced blocks; `RichTextViewer` keeps rendering legacy `.rich-diagram` divs so
  already-written docs (scratch history) still display. Fences need none of the
  marker's formatting rules — indentation and blank lines inside are fine, and
  `<`/`>`/`&` are literal (the `‹ › ∧` lookalike line dies with the markers).
  *(Superseded 2026-09-07: the marker path was REMOVED after review — mockups
  are real Vue pages and no marker content exists outside scratch history;
  fences are the only mermaid source now, and the `neuterMockups`/
  `.rich-mockup` machinery went with them.)*
- **"No HTML in markdown" is a content convention, not a sanitizer tightening**:
  `sanitizeHtml` stays permissive (agent replies and Quill fields are still
  HTML); nothing in the pipeline starts rejecting HTML — steer just stops
  instructing anyone to write it in markdown docs.
- **Split-vs-unified switching is CSS-only**: both formats rendered up front,
  toggled by a media query (no JS resize listener — deterministic for Playwright
  viewport tests).
- **Diff rendering moved to diff2html** (2026-09-06, supersedes the original
  hand-rolled parser plan): `SplitDiff.vue` now mounts two `Diff2HtmlUI`
  instances (one per `outputFormat`) behind the same 768px media query, with the
  shared hljs from `filePreview.getHighlighter()`, `diffStyle: "word"` for
  intra-line highlights, and `highlightLanguages` from
  `EXTENSION_TO_LANGUAGE`. diff2html + its CSS ship as a lazy chunk; the custom
  `utils/diff.ts` parser was deleted. `npm audit --omit=dev` shows no
  diff2html-chain advisories.

## Plan

### 1. Heading ids + outline (TOC)

- `filePreview.ts` `renderMarkdown`: add a marked heading renderer that slugifies
  the heading text into an `id` (dedupe repeats with `-2`, `-3`… suffixes;
  DOMPurify's default config keeps `id` — `ALLOW_DATA_ATTR: false` doesn't
  touch it).
- New `MarkdownOutline.vue`: given the rendered container, collect `h1`–`h6`
  (level, text, id) and render a `<nav data-outline>` above the rendered
  markdown in `FileViewer.vue`'s markdown branch. Collapsed cap: `max-height:
  300px`; when the outline is taller, show an expand toggle
  (`[data-outline-toggle]`, `aria-expanded`) that removes the cap.
- Scroll-to-hash on load: when `location.hash` matches a heading id, scroll it
  into view after the preview resolves (full page loads do this natively;
  Inertia navigations need the explicit scroll).

### 2. Hash links + links to other files

- Hash links: plain `<a href="#slug">` anchors inside `v-html` are not
  intercepted by Inertia (same mechanism as the existing `#files-raw-source`
  link), so heading ids from (1) make them work as-is.
- Inter-file links: extend the post-sanitize `DOMParser` pass in `sanitizeHtml`
  to rewrite relative `<a href>` exactly like images (`resolveImageSrc`
  semantics: resolve against the md file's dir, leading `/` = repo root) →
  `/files/<resolved>`; preserve any `#fragment`; leave `http(s):`, `mailto:`,
  `data:`, `#…`-only, and existing `/files/…` hrefs untouched. Generalize the
  option (`rewriteImagesFrom` → one `resolveFrom` for both img src and a href).

### 3. Mermaid from \`\`\`mermaid fences

- `RichTextViewer.enrich`: alongside `.rich-diagram`, select
  `pre > code.language-mermaid` (marked's `langPrefix` yields
  `hljs language-mermaid`), read `textContent` (unescapes the hljs spans),
  mark rendered, and replace the `<pre>` with the `renderDiagram` SVG — same
  `dataset.richRendered` guard and same failure fallback (leave source, add
  `rich-diagram-error` class) as the marker path.
- The `markedHighlight` pass will have tokenized the fence as plaintext —
  harmless, discarded with the spans.

### 4. steer.md

- § Design doc: `<div class="rich-diagram">` marker instructions → \`\`\`mermaid
  fenced blocks (drop the no-indent/no-blank-line rules and their rationale);
  delete the `‹` `›` `∧` lookalike line (fences escape nothing — `<`, `>`, `&`
  are literal inside them).
- Sweep remaining "html in markdown for mockup/mermaid" phrasing to match the
  real-pages mockup model.

### 5. Git viewer links to the file url

- `GitUncommitted.vue`: each row keeps its diff link; add a secondary muted
  `Link` (e.g. a small "file" affordance) → `fileUrl(f.path)` (`/files/<path>`).
- `GitCommit.vue`: same secondary link per file row, next to the badge.
- Both use the existing `fileUrl` helper (`utils/files.ts`) — no URL drift.

### 6. Split diffs (two panes / one pane by viewport)

- **Implemented via diff2html** (see Decisions) instead of the parser sketched
  here: `SplitDiff.vue` renders two `Diff2HtmlUI` containers (side-by-side ≥768px,
  line-by-line below), syntax-highlighted with the shared hljs instance;
  styling overrides in `main.scss` (`.diff-view`).

### 7. Status words + color coding

- `GitUncommitted.vue`: `statusLetter` → `statusWord` (`new`/`mod`/`del`) and
  `statusClass` → color classes per Decisions; fixed-width label for alignment.
- `GitCommit.vue`: badge text maps through the same words + colors.
- `main.scss`: `.git-letter` → status-label class; comment updated.

## Tests

- Playwright (new md-viewer cases; fixture md files in the files fixture dir):
  outline renders `[data-outline]` with the doc's headings; a >300px outline
  shows the toggle and expands on click; a `#hash` link click scrolls the
  target heading into view; a relative link to another file navigates to
  `/files/<resolved>`; a \`\`\`mermaid fence renders an SVG (no
  `.rich-diagram-error`).
- Playwright `test_git.py`: status words new/mod/del with their color classes;
  file-url links present on uncommitted + commit rows; split diff shows two
  panes at a wide viewport and one column at a narrow one (`set_viewport_size`).
- Views `test_git.py`: word/link assertions updated (letters gone).
- Full gates: `./run lint`/`lintfix` + `typecheck`, `./run test`,
  `./run playwrighttest djangoapp.tests.playwright.test_git` + new md module.

## Checklist

- [x] Markdown outline + anchors
    - [x] marked heading-id renderer (slug + dedupe) in `filePreview.ts`
    - [x] `MarkdownOutline.vue` (top placement, 300px cap, expand toggle, aria)
    - [x] `FileViewer.vue` mounts the outline for `kind === "markdown"`; scroll-to-hash on load
- [x] Links
    - [x] `sanitizeHtml` rewrites relative `<a href>` → `/files/<resolved>` (fragments kept, external/absolute untouched)
- [x] Mermaid fences
    - [x] `RichTextViewer` renders `code.language-mermaid` via `renderDiagram` (error fallback intact)
    - [x] legacy `.rich-diagram` markers keep rendering *(later removed —
          see the superseding note in Decisions; fences are the only path)*
- [x] steer.md — fenced-mermaid guidance replaces marker rules; `‹ › ∧` line removed
- [x] Git viewer
    - [x] file-url links on uncommitted + commit file rows (`fileUrl`)
    - [x] status words new/mod/del + colors in `GitUncommitted.vue`, `GitCommit.vue`, `main.scss`
    - [x] diff2html-backed `SplitDiff.vue`; `GitDiff.vue` renders side-by-side / line-by-line by viewport width (custom `utils/diff.ts` parser superseded and deleted)
- [x] Tests
    - [x] playwright: outline render + expand over 300px
    - [x] playwright: hash-link scroll + inter-file link navigation
    - [x] playwright: mermaid fence renders SVG
    - [x] playwright: status words/colors + file-url links
    - [x] playwright: side-by-side diff wide + line-by-line narrow (d2h selectors)
    - [x] views `test_git.py` — gained `test_commit_file_diff_root` (below)
- [x] `./run lint` + `./run typecheck` + `./run test` + playwright suites green

## Outcome (2026-09-06)

All green: frontend `lint` + `type-check` + `build`; `./run typecheck` (ruff +
mypy, 100 files); `./run test` (172 unit tests); `./run playwrighttest` (33
tests — 4 new md-viewer cases, git suite updated for words/colors/file-links
and the diff2html diff viewer); `./run checkframework2` (full VM rebuild +
deploy + smoke) twice — the second run with diff2html. Fixtures:
`djangoapp/tests/filefixtures/` gained `other.md` + `sub/other.md`; `sample.md`
grew headings (25+, to exceed the 300px outline cap), link cases, and a
\`\`\`mermaid fence. New files are intent-to-added (`git add -N`) so the VM
seed (`git ls-files`-driven) ships them.

## Addendum (2026-09-07, review round)

- **Root-commit diff fix** (folded into the git-viewer commit):
  `diff_commit` passed GitPython's `git.NULL_TREE` sentinel through the
  `repo.git.diff` plumbing call, where it stringifies to its enum name
  (`fatal: bad revision`) — root-commit file diffs 500'd on the VM. Fixed by
  diffing against the empty-tree SHA `4b825dc6…` (SHA-1 repos; documented),
  with `test_commit_file_diff_root` as the regression test.
- **Chunking hardening** (folded into the preload/chunking commit, later
  superseded): the `mermaid-shared` group computed from mermaid's dependency
  closure plus `frontend/scripts/check-chunks.mjs` guarded the entry's chunk
  graph at build time. *(Superseded 2026-09-07 by the simplification folded
  into the md-viewer commit: ONE lazy mermaid bundle + a small eager
  `vendor-shared` chunk — two hand-written regexes, no closure walk, no
  check script. The tripwire is now behavioral:
  `test_no_mermaid_requests_without_diagrams` in test_files.py fails if a
  diagram-free page fetches any `mermaid-*` chunk.)*
- **Security fixes from the review round** (this tree, uncommitted at the
  time of writing): `/files/raw` SVG responses carry
  `Content-Security-Policy: sandbox` (top-level SVG navigation can otherwise
  execute scripts same-origin). A client-side dot-segment normalizer
  (`normalizeUnder`) was implemented for the URL rewriter and then REMOVED by
  operator decision: the rewriter's contract is only-/files/ URLs for
  scheme-less paths (backend `PathWrapper` resolve-and-confine is the
  boundary), not emission-time confinement.
