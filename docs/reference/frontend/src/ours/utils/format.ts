// App helpers live under ours/utils/.
// Collapse free text to one line for list previews.
export function oneLineSummary(body: string, max = 100): string {
  const oneLine = body.replace(/\s+/g, " ").trim()
  return oneLine.length > max ? oneLine.slice(0, max) + "…" : oneLine
}
