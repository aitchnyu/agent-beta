# Design-phase mockups & diagrams (opencode chat)

Make the agent design features collaboratively — ER/state diagrams + Bootstrap
mockups rendered in the chat and the feature docs — behind a four-phase,
approval-gated workflow. Work through the checklist in order.

## Ground truth
- Chat renders assistant markdown via `marked` (`components/RichTextViewer.vue`
  `markdown=true`, `utils/filePreview.ts` `renderMarkdown`), sanitized by
  `sanitizeHtml` (`utils/html.ts`, DOMPurify).
- `.md` files render via `pages/FileViewer.vue` → `renderMarkdown` (same marked),
  now piped through `RichTextViewer` so enrichment is shared.
- highlight.js is registered for a fixed language set in `utils/filePreview.ts`
  (lazy chunk, pre-warmed in `main.ts`); Mermaid is a lazy dependency
  (`utils/mermaid.ts`, dynamic `import("mermaid")`).

## Checklist

### steer.md (agent behavior)
- [x] Four-phase workflow checklist (Design → Build → Verify → Deploy, strict
      approval gates — only "approved"/"go ahead"/"build it" advances, vague
      replies re-ask; scratch@Build; ask-before-`mergescratch`@Deploy) — already
      in steer.md, replacing the old "run the loop → mergescratch" rule.
- [x] Add a "Mockups & diagrams (Design phase)" subsection telling the agent to
      emit, as **raw HTML (not fences)**:
  - [x] `<div class="opencode-diagram">…mermaid…</div>` — `erDiagram` whenever DB
        tables/models come up (entities, fields, FKs, ownership),
        `stateDiagram-v2` for lifecycles; **no `<`/`>`/`&` in labels** (HTML-parsed
        — use the lookalikes `‹` `›` `∧`).
  - [x] `<div class="opencode-mockup">…bootstrap…</div>` — real Bootstrap markup
        + our CSS classes (read an existing page like `Home.vue` to match),
        responsive, view-only (no `action`/`href`).
  - [x] Note: marker block on its own lines, no indentation / no blank lines
        inside (else marked splits the raw-HTML block).
- [x] "Persist the design" rule: during Build, write the approved diagrams +
      mockups into `ourapp/docs/<feature>.md`. *(already in steer.md)*

### Renderer (shared by chat + .md viewer)
- [x] One enrichment path used by both: `RichTextViewer.vue` post-mount
      `enrich()` (neuter mockups + render diagrams); `FileViewer.vue` now renders
      markdown via `<RichTextViewer>`, so chat and `.md` render identically.
- [x] `.opencode-diagram` → Mermaid SVG: lazy `import("mermaid")` →
      `mermaid.render(id, source)`; async, falls back to raw source in the box on
      error / while loading (`utils/mermaid.ts`).
- [x] `.opencode-mockup` → keep the Bootstrap HTML in the box; neuter
      interactivity (`<form>`/`<a>` → strip action/href, `button`/`input`/… →
      disabled).

### Sanitizer
- [x] `utils/html.ts` `sanitizeHtml`: permissive DOMPurify — allow standard HTML
      + `class`/`style`; `FORBID_TAGS` script/iframe/object/embed/link/meta/base/
      style, `FORBID_ATTR` srcdoc/formaction, hook drops protocol-relative `//`
      URLs; keeps the two marker classes and Bootstrap classes (`row`/`col`/`btn`…).

### Styling
- [x] `_opencode.scss`: `.opencode-mockup` (box — border, padding, responsive,
      neutered) and `.opencode-diagram` (SVG container + error state).
- [x] Mermaid theme variables (app palette) set in `utils/mermaid.ts`
      `initialize` (`theme: "base"`).

### Dependency
- [x] Add `mermaid` to `frontend/package.json`; kept lazy (dynamic `import`) —
      build emits separate `mermaid.core` + per-diagram chunks, main bundle
      unchanged.

### Verify
- [x] `npm run type-check`, `npm run lint`, `npm run build` (all green).
- [ ] Chat: design a feature with a model → ER diagram renders as SVG + a page
      mockup renders as Bootstrap in a box (view-only); phase gates fire (no code
      before design approval; asks before `mergescratch`). *(manual)*
- [ ] Open `ourapp/docs/<feature>.md` in the file viewer → diagrams + mockups
      render identically to chat. *(manual)*
- [ ] Mermaid labels avoid `<`/`>`/`&`; main bundle unchanged (Mermaid stayed
      lazy). *(bundle confirmed lazy; label rule is agent-side)*
