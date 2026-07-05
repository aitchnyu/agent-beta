// Minimal toast helper (adapt the host's utils/sweetalert). The rule: never
// swallow errors silently — surface them as a toast, and never re-throw after.
import Swal from "sweetalert2"

export function showErrorToast(err: unknown, fallback: string): void {
  const text = err instanceof Error ? err.message : String(err ?? fallback)
  Swal.fire({
    toast: true,
    position: "top-end",
    icon: "error",
    title: text || fallback,
    showConfirmButton: false,
    timer: 4000,
    timerProgressBar: true,
  })
}
