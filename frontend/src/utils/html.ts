import sanitizeHtmlLib from "sanitize-html"

const ALLOWED_TAGS: string[] = [
  "p",
  "br",
  "strong",
  "em",
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

const ALLOWED_ATTRIBUTES: Record<string, string[]> = {
  a: ["href"],
  img: ["src"],
}

export function sanitizeHtml(html: string): string {
  if (!html) return ""

  return sanitizeHtmlLib(html, {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: ALLOWED_ATTRIBUTES,
    allowProtocolRelative: false,
  })
}
