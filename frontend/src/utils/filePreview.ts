// Rich preview: markdown (via marked) + syntax highlighting (highlight.js).
// This module is only ever dynamically imported (GitDiff, FileViewer) and
// pre-warmed at boot in main.ts, so Vite keeps it (+ its deps and theme CSS)
// as a separate lazy chunk out of the host bundle.
//
// Only specific languages are registered (not the full `highlight.js`, which bundles
// ~190 languages ≈ 1 MB): the extensions classified by `detectLanguage` (in
// `utils/files.ts`) plus a few more likely to appear in markdown fenced blocks.
import hljs from "highlight.js/lib/core"
import python from "highlight.js/lib/languages/python"
import xml from "highlight.js/lib/languages/xml"
import json from "highlight.js/lib/languages/json"
import javascript from "highlight.js/lib/languages/javascript"
import typescript from "highlight.js/lib/languages/typescript"
import bash from "highlight.js/lib/languages/bash"
import css from "highlight.js/lib/languages/css"
import diffGrammar from "highlight.js/lib/languages/diff"
import scss from "highlight.js/lib/languages/scss"
import yaml from "highlight.js/lib/languages/yaml"
import markdownGrammar from "highlight.js/lib/languages/markdown"
import plaintext from "highlight.js/lib/languages/plaintext"
import { marked } from "marked"
import { markedHighlight } from "marked-highlight"

import { sanitizeHtml } from "./html"

for (const [name, def] of [
  ["python", python],
  ["xml", xml],
  ["html", xml],
  ["json", json],
  ["javascript", javascript],
  ["js", javascript],
  ["typescript", typescript],
  ["ts", typescript],
  ["bash", bash],
  ["sh", bash],
  ["shell", bash],
  ["css", css],
  ["scss", scss],
  ["yaml", yaml],
  ["yml", yaml],
  ["markdown", markdownGrammar],
  ["md", markdownGrammar],
  ["plaintext", plaintext],
  ["text", plaintext],
  ["diff", diffGrammar],
] as const) {
  hljs.registerLanguage(name, def)
}

marked.use(
  markedHighlight({
    langPrefix: "hljs language-",
    emptyLangClass: "",
    highlight(code, lang) {
      const language = lang && hljs.getLanguage(lang) ? lang : "plaintext"
      return hljs.highlight(code, { language }).value
    },
  }),
)

/** Render markdown to sanitized HTML, rewriting relative image src → /files/raw/. */
export function renderMarkdown(
  markdownText: string,
  markdownRelPath: string,
): string {
  const html = marked.parse(markdownText, { async: false }) as string
  return sanitizeHtml(html, { rewriteImagesFrom: markdownRelPath })
}

/** Highlight a whole code file; returns sanitized inner HTML (span tokens).
 *  Sanitized for defense-in-depth even though highlight.js escapes its input. */
export function highlightCode(code: string, language: string): string {
  const lang = hljs.getLanguage(language) ? language : "plaintext"
  return sanitizeHtml(hljs.highlight(code, { language: lang }).value)
}

/** Highlight a unified diff (the `diff` grammar: + / - / @@ lines). Sanitized. */
export function highlightDiff(diff: string): string {
  return sanitizeHtml(hljs.highlight(diff, { language: "diff" }).value)
}
