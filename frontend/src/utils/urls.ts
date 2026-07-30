// Builds the list URL for a model's rows with query params, reused by the list
// page and its pagination links so prev/next/page navigation keeps per_page and
// sort in sync.
export interface RowListQuery {
  page?: number
  per_page?: number
  sort?: string
}

export function rowListUrl(
  modelName: string,
  query: RowListQuery = {},
): string {
  const base = `/manage/models/${modelName}/list`
  const params = new URLSearchParams()
  if (query.page !== undefined) params.set("page", String(query.page))
  if (query.per_page !== undefined)
    params.set("per_page", String(query.per_page))
  if (query.sort !== undefined) params.set("sort", query.sort)
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

export function rowDetailUrl(modelName: string, publicId: string): string {
  return `/manage/models/${modelName}/id/${publicId}`
}
