// Shared helpers for the /files browser pages (FileBrowser + FileViewer).
// Centralizing the URL prefix avoids drift (a rename updates every link).

// URL for a repo-root-relative path: "" → repo root (/files/).
export function fileUrl(rel: string): string {
  return `/files/${rel}`
}

// Byte-serving endpoints (kept separate from the browse/view route).
export function rawUrl(rel: string): string {
  return `/files-raw/${rel}`
}

export function downloadUrl(rel: string): string {
  return `/files-download/${rel}`
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
