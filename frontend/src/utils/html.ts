import sanitizeHtmlLib from "sanitize-html"

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

// `class` is allowed on code/pre/span so highlight.js token spans keep their colour.
const ALLOWED_ATTRIBUTES: Record<string, string[]> = {
  a: ["href"],
  img: ["src"],
  code: ["class"],
  pre: ["class"],
  span: ["class"],
}

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

  const config: Parameters<typeof sanitizeHtmlLib>[1] = {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: ALLOWED_ATTRIBUTES,
    allowProtocolRelative: false,
  }
  if (options.rewriteImagesFrom !== undefined) {
    const markdownRelPath = options.rewriteImagesFrom
    config.transformTags = {
      img: (_tag, attribs) => ({
        tagName: "img",
        attribs: {
          ...attribs,
          src: resolveImageSrc(attribs.src ?? "", markdownRelPath),
        },
      }),
    }
  }
  return sanitizeHtmlLib(html, config)
}
