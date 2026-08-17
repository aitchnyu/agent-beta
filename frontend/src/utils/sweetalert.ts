import { HttpNetworkError, HttpResponseError } from "@inertiajs/core"

type ToastIcon = "success" | "error" | "warning" | "info" | "question"

// Lazy-load sweetalert2 on first use (one-time, cached) so it stays a separate
// chunk and out of the host bundle. Each helper fire-and-forgets after load.
type SwalDefault = (typeof import("sweetalert2"))["default"]
type SweetAlertToast = ReturnType<SwalDefault["mixin"]>
let toastPromise: Promise<SweetAlertToast> | null = null

async function loadToast(): Promise<SweetAlertToast> {
  if (!toastPromise) {
    toastPromise = (async () => {
      const mod = await import("sweetalert2")
      return mod.default.mixin({
        toast: true,
        position: "bottom",
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
      })
    })()
  }
  return toastPromise
}

export const showToast = async (
  icon: ToastIcon,
  title: string,
): Promise<void> => {
  const toast = await loadToast()
  await toast.fire({ icon, title })
}

export const showErrorToast = async (
  e: unknown,
  fallback: string,
): Promise<void> => {
  let title = fallback
  let detail = e instanceof Error ? e.constructor.name : ""
  if (e instanceof HttpResponseError) {
    const msg = extractErrorMessage(safeParseJson(e.response.data))
    if (msg) title = msg
    if (e.response.status) detail = `HTTP ${e.response.status}`
  } else if (e instanceof HttpNetworkError) {
    title = "Could not reach the server"
    detail = "Check your internet connection and try again."
  }
  const toast = await loadToast()
  await toast.fire({ icon: "error", title, text: detail || undefined })
}

/**
 * Pull a human message from a ninja/ApiError JSON body.
 * Handles `{"detail": "msg"}`, `{"message": "msg"}`, a bare string,
 * and arbitrary dict bodies.
 */
const extractErrorMessage = (body: unknown): string => {
  if (typeof body === "string") return body
  if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>
    const detail = obj.detail
    if (typeof detail === "string") return detail
    if (typeof obj.message === "string") return obj.message
  }
  return ""
}

/** Parse a response body string as JSON, returning null for empty/invalid. */
const safeParseJson = (data: string): unknown => {
  try {
    return data ? (JSON.parse(data) as unknown) : null
  } catch {
    return null
  }
}
