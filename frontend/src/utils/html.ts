import DOMPurify from "dompurify"

// Permissive-but-safe config. We allow standard HTML (so the agent's Bootstrap
// mockups keep their markup + classes/styles) and rely on DOMPurify's defaults
// to strip <script>, on* event handlers, and javascript:/vbscript: URIs. We add
// an explicit FORBID list for the embedding/active tags DOMPurify leaves alone
// by default (iframe/object/embed/link/…), plus a hook that drops
// protocol-relative (//host) URLs on every URL-bearing attribute. `class` and
// `style` are allowed on all tags (the two marker classes .opencode-diagram /
// .opencode-mockup, Bootstrap row/col/btn…, and highlight.js hljs-* spans all
// survive). Mockup interactivity is neutered separately in RichTextViewer.
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
  /** When set, relative image src in the HTML is rewritten to /files/raw/<rel>
   * resolved against this markdown file's repo-root-relative path. */
  rewriteImagesFrom?: string
}
function resolveImageSrc(src: string, markdownRelPath: string): string {
  if (!src || /^(https?:|data:|\/files\/raw\/)/i.test(src)) return src
  const markdownDir = markdownRelPath.includes("/")
    ? markdownRelPath.slice(0, markdownRelPath.lastIndexOf("/"))
    : ""
  const resolvedRelPath = src.startsWith("/")
    ? src.slice(1)
    : markdownDir
      ? `${markdownDir}/${src}`
      : src
  return `/files/raw/${resolvedRelPath}`
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
