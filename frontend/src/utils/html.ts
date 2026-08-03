import DOMPurify from "dompurify"

const ALLOWED_TAGS: string[] = [
  "p",
  "br",
  "strong",
  "em",
  "code",
  "pre",
  "kbd",
  "samp",
  "blockquote",
  "span", // highlight.js wraps tokens in <span class="hljs-…">
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "ul",
  "ol",
  "li",
  "a",
  "hr",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "img",
]

// `class` is allowed so highlight.js token spans keep their colour. ALLOWED_ATTR
// is a global pre-filter (the union of what any tag may carry); the hook below
// then enforces the per-tag mapping.
const ALLOWED_ATTR: string[] = ["href", "src", "class"]
const ATTRS_BY_TAG: Record<string, string[]> = {
  a: ["href"],
  img: ["src"],
  code: ["class"],
  pre: ["class"],
  span: ["class"],
}

// Enforce the per-tag attribute allow-list, then block protocol-relative URLs
// (//host) — the old allowProtocolRelative:false. DOMPurify's defaults already
// drop javascript:/data: schemes; this hook adds per-tag precision + the
// protocol-relative block. Stateless, so one global hook covers every call.
DOMPurify.addHook("uponSanitizeAttribute", (node, data) => {
  const allowed = ATTRS_BY_TAG[node.nodeName.toLowerCase()]
  if (!allowed || !allowed.includes(data.attrName)) {
    data.keepAttr = false
    return
  }
  // Only URL-bearing attributes (href/src) can be protocol-relative; `class`
  // (the only other attr that survives the per-tag check above) never carries a
  // URL, so gate the // check to these two.
  const value = data.attrValue
  if (
    (data.attrName === "href" || data.attrName === "src") &&
    typeof value === "string" &&
    value.startsWith("//")
  ) {
    data.keepAttr = false
  }
})

export interface SanitizeOptions {
  /** When set, relative image src in the HTML is rewritten to /files-raw/<rel>
   * resolved against this markdown file's repo-root-relative path. */
  rewriteImagesFrom?: string
}
function resolveImageSrc(src: string, markdownRelPath: string): string {
  if (!src || /^(https?:|data:|\/files-raw\/)/i.test(src)) return src
  const markdownDir = markdownRelPath.includes("/")
    ? markdownRelPath.slice(0, markdownRelPath.lastIndexOf("/"))
    : ""
  const resolvedRelPath = src.startsWith("/")
    ? src.slice(1)
    : markdownDir
      ? `${markdownDir}/${src}`
      : src
  return `/files-raw/${resolvedRelPath}`
}

export function sanitizeHtml(
  html: string,
  options: SanitizeOptions = {},
): string {
  if (!html) return ""
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: false,
  })
  if (options.rewriteImagesFrom === undefined) return clean
  // Rewrite relative image src after sanitizing (only the markdown path opts
  // in). DOMParser is browser-native (no dep); DOMPurify kept <img src> intact
  // (relative srcs aren't protocol-relative, so the hook above leaves them).
  const doc = new DOMParser().parseFromString(clean, "text/html")
  for (const img of doc.querySelectorAll("img")) {
    img.setAttribute(
      "src",
      resolveImageSrc(img.getAttribute("src") ?? "", options.rewriteImagesFrom),
    )
  }
  return doc.body.innerHTML
}
