import DOMPurify from "dompurify"

// Permissive-but-safe config. We allow standard HTML (so agent replies keep
// their markup + classes/styles) and rely on DOMPurify's defaults to strip
// <script>, on* event handlers, and javascript:/vbscript: URIs. We add an
// explicit FORBID list for the embedding/active tags DOMPurify leaves alone
// by default (iframe/object/embed/link/…), plus a hook that drops
// protocol-relative (//host) URLs on every URL-bearing attribute. `class`
// and `style` are allowed on all tags (the .rich-diagram rendered-diagram
// class, Bootstrap row/col/btn…, and highlight.js hljs-* spans all
// survive).
const FORBID_TAGS = [
  "script",
  "iframe",
  "object",
  "embed",
  "link",
  "meta",
  "base",
  "style",
  // SVG is an XSS surface (onload, <script>, foreignObject)
  "svg",
]
const FORBID_ATTR = ["srcdoc", "formaction"]

// DOMPurify's defaults already block javascript:/vbscript: on href/src/action;
// this hook additionally drops protocol-relative (//host) URLs across every
// URL-bearing attribute (incl. xlink:href, poster, …). Stateless, so one global
// hook covers every call.
const URL_ATTRS = new Set([
  "href",
  "src",
  "action",
  "formaction",
  "xlink:href",
  "poster",
  "background",
  "cite",
])
DOMPurify.addHook("uponSanitizeAttribute", (_node, data) => {
  if (
    URL_ATTRS.has(data.attrName) &&
    typeof data.attrValue === "string" &&
    data.attrValue.startsWith("//")
  ) {
    data.keepAttr = false
  }
})

export interface SanitizeOptions {
  /** When set, scheme-less URLs in the HTML are resolved against this
   * markdown file's path: relative ones against its dir, leading-/ ones
   * against its worktree root; <img src> → /files/raw/<rel>, <a href> →
   * /files/<rel> (fragment preserved). Only /files/ URLs are ever produced
   * or passed through — every other scheme-less path is rewritten under the
   * /files/ prefix (backend-side confinement there). For <a href>, schemed
   * URLs (http:, mailto:, tel:, …) pass through untouched; <img src> only
   * passes http(s):/data: through, other schemes never reach the rewriter
   * in practice (DOMPurify's URI allowlist drops them). */
  resolveFrom?: string
}

// Worktree-relative resolution shared by img src and a href: a relative path
// resolves against the markdown file's dir; a leading-/ path resolves against
// the worktree root (the repo the file lives in — markdownRelPath's first
// segment, e.g. "main" or "scratch" under the browse root). A file at the
// browse root itself has no worktree segment and keeps browse-root semantics.
// Simple concatenation by design — dot segments stay in the produced URL
// verbatim and the backend's resolve-and-confine (PathWrapper) is the
// boundary for whatever arrives.
function resolveRelPath(src: string, markdownRelPath: string): string {
  const worktree = markdownRelPath.includes("/")
    ? markdownRelPath.slice(0, markdownRelPath.indexOf("/"))
    : ""
  const markdownDir = markdownRelPath.includes("/")
    ? markdownRelPath.slice(0, markdownRelPath.lastIndexOf("/"))
    : ""
  if (src.startsWith("/")) {
    const rel = src.slice(1)
    return worktree ? `${worktree}/${rel}` : rel
  }
  return markdownDir ? `${markdownDir}/${src}` : src
}

function resolveImageSrc(src: string, markdownRelPath: string): string {
  if (!src || /^(https?:|data:|\/files\/raw\/)/i.test(src)) return src
  return `/files/raw/${resolveRelPath(src, markdownRelPath)}`
}

// Links: rewrite ONLY scheme-less hrefs (relative or leading-/); anything
// with a scheme (http:, mailto:, tel:, callto:, …) passes through as-is, as
// do pure-fragment hrefs (in-page anchors) and already-/files/ URLs.
// Protocol-relative //… never reaches this: the uponSanitizeAttribute hook
// above already stripped it.
function resolveLinkHref(href: string, markdownRelPath: string): string {
  if (!href || /^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith("#")) {
    return href
  }
  if (href.startsWith("/files/")) return href
  const hashIndex = href.indexOf("#")
  const fragment = hashIndex >= 0 ? href.slice(hashIndex) : ""
  const path = hashIndex >= 0 ? href.slice(0, hashIndex) : href
  if (!path) return href
  return `/files/${resolveRelPath(path, markdownRelPath)}${fragment}`
}

export function sanitizeHtml(
  html: string,
  options: SanitizeOptions = {},
): string {
  if (!html) return ""
  const clean = DOMPurify.sanitize(html, {
    FORBID_TAGS,
    FORBID_ATTR,
    ALLOW_DATA_ATTR: false,
  })
  if (options.resolveFrom === undefined) return clean
  // Rewrite scheme-less img src + a href after sanitizing (only the markdown
  // path opts in). DOMParser is browser-native (no dep). Anchors/images whose
  // href/src the sanitizer STRIPPED (attribute gone) stay inert — re-adding
  // href="" would turn them into self-reload links.
  const doc = new DOMParser().parseFromString(clean, "text/html")
  for (const img of doc.querySelectorAll("img")) {
    const src = img.getAttribute("src")
    if (src !== null) {
      img.setAttribute("src", resolveImageSrc(src, options.resolveFrom))
    }
  }
  for (const a of doc.querySelectorAll("a")) {
    const href = a.getAttribute("href")
    if (href !== null) {
      a.setAttribute("href", resolveLinkHref(href, options.resolveFrom))
    }
  }
  return doc.body.innerHTML
}
