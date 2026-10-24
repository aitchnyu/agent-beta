import { HttpNetworkError, HttpResponseError } from "@inertiajs/core"
import DOMPurify from "dompurify"

import {
  ApiErrorSchema,
  DetailStringSchema,
  UserVisibleError,
} from "./pydanticErrors"

type ToastIcon = "success" | "error" | "warning" | "info" | "question"

// Lazy-load sweetalert2 on first use (cached) so it stays a separate chunk
type SwalDefault = (typeof import("sweetalert2"))["default"]
type SweetAlertToast = ReturnType<SwalDefault["mixin"]>

const TOAST_MS = 3000
// UserVisibleError toasts carry a link — links need dwell time.
const LONG_TOAST_MS = 8000

let toastPromise: Promise<SweetAlertToast | null> | null = null

async function loadToast(): Promise<SweetAlertToast | null> {
  if (toastPromise) return toastPromise
  toastPromise = (async () => {
    try {
      const mod = await import("sweetalert2")
      return mod.default.mixin({
        toast: true,
        position: "bottom",
        showConfirmButton: false,
        timer: TOAST_MS,
        timerProgressBar: true,
      })
    } catch (err) {
      // The toast chunk is a network fetch — it fails exactly when the app
      // is already struggling (broken dev server, offline network), i.e.
      // precisely when an error wants a toast. Swallow the failure (and
      // drop the cache so a later call may retry) — a rejecting loadToast
      // would turn every global error handler into an unhandled rejection
      // and close the infinite error → toast-fail → error loop.
      console.error("toast module failed to load:", err)
      toastPromise = null
      return null
    }
  })()
  return toastPromise
}

export const showToast = async (
  icon: ToastIcon,
  title: string,
): Promise<void> => {
  const toast = await loadToast()
  try {
    await toast?.fire({ icon, title })
  } catch (err) {
    // sweetalert2 itself may throw (broken DOM state) — never propagate.
    // TODO alert the user?
    console.error("toast fire failed:", err)
  }
}

/**
 * The server's authored message when the body carries one — an ApiError
 * body (ApiErrorSchema) or ninja's own {"detail": "<string>"} bodies.
 * Shown verbatim, the same trust as NinjaError custom msgs; a 422's
 * array detail never parses here.
 */
const serverMessage = (data: unknown): string | null => {
  const api = ApiErrorSchema.safeParse(data)
  if (api.success) return api.data.msg ?? null
  const detail = DetailStringSchema.safeParse(data)
  return detail.success ? detail.data.detail : null
}

/**
 * Toast copy per HTTP status — the message comes from the status code
 * when the body carries none. Unlisted statuses get a generic title; the
 * HTTP <n> detail line carries the status.
 */
const messageForStatus = (status: number): string => {
  if (status === 404) return "The requested entity was not found"
  if (status === 422) return "Validation error — submit it again"
  if (status >= 500) return "Something wrong on our end"
  return "That request didn't work"
}

export const showErrorToast = async (
  e: unknown,
  fallback: string,
): Promise<void> => {
  let title = fallback
  let detail = e instanceof Error ? e.constructor.name : ""
  let userHtml: string | null = null
  if (e instanceof UserVisibleError) {
    // The error carries its own user presentation (links need dwell time,
    // hence the longer timer).
    title = e.userTitle
    userHtml = sanitizeToastHtml(e.userHtml)
  } else if (e instanceof HttpResponseError) {
    title =
      serverMessage(e.response.data) ?? messageForStatus(e.response.status)
    if (e.response.status) detail = `HTTP ${e.response.status}`
  } else if (e instanceof HttpNetworkError) {
    title = "Could not reach the server"
    detail = "Check your internet connection and try again."
  }
  const toast = await loadToast()
  try {
    if (userHtml !== null) {
      await toast?.fire({
        icon: "error",
        title,
        html: userHtml,
        timer: LONG_TOAST_MS,
      })
    } else {
      await toast?.fire({ icon: "error", title, text: detail || undefined })
    }
  } catch (err) {
    // See showToast — the toast layer must never reject.
    // TODO alert the user?
    console.error("toast fire failed:", err)
  }
}

/**
 * Blocking confirm dialog for destructive actions. Resolves true only on an
 * explicit confirm; cancel/dismiss resolve false.
 */
export const confirmAction = async (
  title: string,
  text: string,
): Promise<boolean> => {
  const mod = await import("sweetalert2")
  const res = await mod.default.fire({
    icon: "warning",
    title,
    text,
    showCancelButton: true,
    confirmButtonText: "Confirm",
    confirmButtonColor: "#dc3545",
    // Destructive action: focus the safe choice so a stray Enter cancels.
    focusCancel: true,
  })
  return res.isConfirmed
}

/** Sanitize toast html to a safe tag subset (a + inline formatting only). */
const sanitizeToastHtml = (html: string): string =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["a", "b", "strong", "em", "code", "br"],
    ALLOWED_ATTR: ["href"],
  })
