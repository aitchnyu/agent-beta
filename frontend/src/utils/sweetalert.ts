import Swal from "sweetalert2"
import type { AxiosError } from "axios"

type ToastIcon = "success" | "error" | "warning" | "info" | "question"

const Toast = Swal.mixin({
  toast: true,
  position: "bottom",
  showConfirmButton: false,
  timer: 3000,
  timerProgressBar: true,
})

export const showToast = (icon: ToastIcon, title: string): void => {
  Toast.fire({ icon, title })
}

export const showErrorToast = (e: unknown, fallback: string): void => {
  let title = fallback
  let detail = e instanceof Error ? e.constructor.name : ""
  if (e && typeof e === "object" && "isAxiosError" in e) {
    const ax = e as AxiosError
    if (ax.response) {
      const msg = extractErrorMessage(ax.response.data)
      if (msg) title = msg
      if (ax.response.status) detail = `HTTP ${ax.response.status}`
    } else {
      title = "Could not reach the server"
      detail = "Check your internet connection and try again."
    }
  }
  Toast.fire({ icon: "error", title, text: detail || undefined })
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
