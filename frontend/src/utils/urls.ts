// Builds the list URL for a table's rows with query params, reused by the
// list page and its pagination Links so prev/next/page navigation keeps
// per_page and sort in sync.
export interface RowListQuery {
  page?: number
  per_page?: number
  sort?: string
}

export function rowListUrl(
  appName: string,
  tableName: string,
  query: RowListQuery = {},
): string {
  const base = `/manage/apps/${appName}/${tableName}/list`
  const params = new URLSearchParams()
  if (query.page !== undefined) params.set("page", String(query.page))
  if (query.per_page !== undefined)
    params.set("per_page", String(query.per_page))
  if (query.sort !== undefined) params.set("sort", query.sort)
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

export function rowDetailUrl(
  appName: string,
  tableName: string,
  publicId: string,
): string {
  return `/manage/apps/${appName}/${tableName}/id/${publicId}`
}

// The app's main page: the `default` endpoint served at the app root.
export function appEndpointUrl(appName: string): string {
  return `/apps/${appName}`
}
