// App helpers live under ours/utils/. 
// Collapse a note body to one line for list previews.
export function noteSummary(body: string, max = 100): string {
  const oneLine = body.replace(/\s+/g, " ").trim()
  return oneLine.length > max ? oneLine.slice(0, max) + "…" : oneLine
}
