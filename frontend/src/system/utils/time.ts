// Format an ISO timestamp in the viewer's local time, matching the
// UserHistory page style. Returns "—" for nullish input.
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
