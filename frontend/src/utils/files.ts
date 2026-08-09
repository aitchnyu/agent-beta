// Shared helpers for the /files browser pages (FileBrowser + FileViewer).
// Centralizing the URL prefix avoids drift (a rename updates every link).

// URL for a repo-root-relative path: "" → repo root (/files/).
export function fileUrl(rel: string): string {
  return `/files/${rel}`
}

// Byte-serving endpoints (kept separate from the browse/view route).
export function rawUrl(rel: string): string {
  return `/files/raw/${rel}`
}

export function downloadUrl(rel: string): string {
  return `/files/download/${rel}`
}

// Humanized byte size: 512 → "512 B", 1500 → "1.5 KB", 1024 → "1 KB".
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ["KB", "MB", "GB", "TB"]
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  // One decimal for small fractional values (1.5 KB); drop it when whole (1 KB).
  const decimals = value < 10 && value % 1 !== 0 ? 1 : 0
  return `${value.toFixed(decimals)} ${units[unit]}`
}

// Extension → highlight.js language. The frontend is the sole source of truth for
// which files get syntax highlighting (the backend only classifies
// text/markdown/image/binary — it knows nothing of highlight.js languages).
const EXTENSION_TO_LANGUAGE: Record<string, string> = {
  py: "python",
  vue: "xml",
  html: "xml",
  json: "json",
  ts: "typescript",
  js: "javascript",
  css: "css",
  scss: "scss",
  yml: "yaml",
  yaml: "yaml",
  sh: "bash",
  bash: "bash",
}

/** Returns the highlight.js language for a filename, or undefined when it isn't a
 *  recognized code file (→ render as plain text). */
export function detectLanguage(filename: string): string | undefined {
  const dot = filename.lastIndexOf(".")
  if (dot < 0) return undefined
  return EXTENSION_TO_LANGUAGE[filename.slice(dot + 1).toLowerCase()]
}
