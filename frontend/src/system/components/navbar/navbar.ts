import type { InjectionKey, Ref } from "vue"

// The navbar's provide/inject contract, typed once (the module-helper
// convention, like git/fileTree.ts).
export const navbarCompactKey: InjectionKey<Ref<boolean>> =
  Symbol("navbarCompact")
export const navbarCloseMenuKey: InjectionKey<() => void> =
  Symbol("navbarCloseMenu")

// Escape closing is innermost-first: the dropdown that consumed an
// Escape marks the event so parents skip it — no stopImmediatePropagation,
// which would silence every other app-wide Escape handler.
type EscapeEvent = KeyboardEvent & { navDropdownClosed?: boolean }
export function markEscape(e: KeyboardEvent): void {
  ;(e as EscapeEvent).navDropdownClosed = true
}
export function isEscapeMarked(e: KeyboardEvent): boolean {
  return (e as EscapeEvent).navDropdownClosed === true
}
