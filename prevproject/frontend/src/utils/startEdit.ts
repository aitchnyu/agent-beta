/**
 * Module-level slot for passing a column name across an Inertia page navigation.
 *
 * Problem: double-clicking a cell on the list page should navigate to the details
 * page and immediately open the edit form focused on that column. Inertia remounts
 * Vue components on navigation, so component-local state is lost. Window custom
 * events are fragile because the listener may not be registered yet when the event
 * fires.
 *
 * Solution: JS module state persists across Inertia navigations within the same
 * browser tab. The list page calls `pushStartEdit(colName)` before navigating.
 * The details page calls `popStartEdit()` in `onMounted` to consume the value.
 */

let _pendingField: string | null = null

/**
 * Stash a column name before navigating to the details page.
 *
 * Called from `ListRowsContent.navigateToEdit` just before `router.visit()`.
 * The value survives the Inertia page transition and is consumed by
 * `popStartEdit()` on the next page.
 */
export function pushStartEdit(colName: string): void {
  _pendingField = colName
}

/**
 * Consume and return the stashed column name, or null if none was set.
 *
 * Called from `RowDetailsContent.onMounted`. If a non-null value is
 * returned, the details page opens in edit mode with that field focused.
 * The value is cleared after reading (single-consume).
 */
export function popStartEdit(): string | null {
  const v = _pendingField
  _pendingField = null
  return v
}
