export const rowDetailsUrl = (
  viewname: string,
  rowId: string | number,
): string => `/tables/${viewname}/id/${rowId}`

export const listRowsUrl = (viewname: string, risonStr: string): string =>
  `/tables/${viewname}/list/-${risonStr}-`
