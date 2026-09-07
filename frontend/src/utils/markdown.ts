// Markdown-specific pure helpers, derived from the rendered document itself —
// no shared mutable state. Rides the lazy filePreview chunk (its only importer
// today is filePreview.ts; MarkdownView.vue reads the ids it assigned).

/** Slug for one heading: lowercase, letters/digits (Unicode — \p{L} keeps
 *  Han/CJK etc.)/`_`/`-` kept, runs of anything else → one "-", trimmed.
 *  Only truly symbol/emoji-only headings slug to null. */
function headingSlug(text: string): string | null {
  const slug = text
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}_ -]+/gu, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
  return slug || null
}

/** Assign id attributes to h1–h6 in already-rendered, sanitized markdown
 *  HTML: the ids are the targets of in-page #hash links and the outline
 *  (MarkdownOutline.vue). All state local to this call — html in, html out,
 *  no globals. Runs in renderMarkdown AFTER sanitization, so nothing strips
 *  the ids afterwards.
 *
 *  Uniqueness is tracked over ASSIGNED ids, not base slugs: "Foo", "Foo 2"
 *  (which slugs to foo-2), "Foo" must yield foo, foo-2, foo-3 — counting
 *  per base would re-emit foo-2. The section-N fallback (symbol/emoji-only
 *  headings) takes from the same pool, so a literal "Section 1" heading
 *  can't collide with it either.
 *
 *  Browser-only (DOMParser) — same assumption as sanitizeHtml's rewriting
 *  pass; every caller renders client-side. */
export function assignHeadingIds(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html")
  const headings = [...doc.querySelectorAll("h1,h2,h3,h4,h5,h6")]
  const taken = new Set<string>()
  let anonymous = 0
  for (const h of headings) {
    const base = headingSlug(h.textContent ?? "") ?? `section-${++anonymous}`
    let id = base
    let n = 1
    while (taken.has(id)) id = `${base}-${++n}`
    taken.add(id)
    h.id = id
  }
  return doc.body.innerHTML
}
