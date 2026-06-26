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

/**
 * Convert HTML content to plaintext by stripping HTML tags.
 * Used for displaying text field content in list views.
 *
 * @param html - The HTML string to convert
 * @param useSpaceForBlocks - If true, render blocks and br as space instead of \n (default: true)
 * @returns Plain text with HTML tags removed
 */
export function htmlToPlaintext(
  html: string,
  useSpaceForBlocks: boolean = true,
): string {
  if (!html) return ""

  const sanitizedHtml = sanitizeHtml(html)

  const tempDiv = document.createElement("div")
  tempDiv.innerHTML = sanitizedHtml

  const blockOrBrReplacement = useSpaceForBlocks ? " " : "\n"

  tempDiv.querySelectorAll("br").forEach((br) => {
    br.replaceWith(blockOrBrReplacement)
  })

  const blockElements = [
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "tr",
  ]
  blockElements.forEach((tag) => {
    tempDiv.querySelectorAll(tag).forEach((el) => {
      el.insertAdjacentText("afterend", blockOrBrReplacement)
    })
  })

  let text = tempDiv.textContent || ""

  text = text.replace(/ +/g, " ")

  if (!useSpaceForBlocks) {
    text = text.replace(/\n{3,}/g, "\n\n")
  }

  text = text.trim()

  return text
}
