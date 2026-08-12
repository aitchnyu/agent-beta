import axios from "axios"
import { usePage } from "@inertiajs/vue3"
import { z } from "zod"

// Backend sink for uncaught browser errors. CSRF is not required for this
// endpoint (see djangoapp/views/client_errors.py), so both axios and the
// sendBeacon fallback land without a csrftoken cookie.
const ENDPOINT = "/client-errors"

// Cap the stack before sending — must stay in sync with
// djangoapp.views.client_errors._MAX_STACK_INPUT, or a long browser stack 422s
// (pydantic max_length) and the report is silently dropped.
const MAX_STACK_CHARS = 5000

// The contract for a client error report. Mirrors the backend
// `djangoapp.views.client_errors.ClientErrorBody` (camelCase wire keys — the
// pydantic model aliases userAgent/vueInfo), so there is one source of truth:
// payloads are validated against this schema before they're sent.
export const ClientErrorPayloadSchema = z.object({
  message: z.string(),
  stack: z.string(),
  filename: z.string(),
  lineno: z.number().nullable(),
  colno: z.number().nullable(),
  url: z.string(),
  userAgent: z.string(),
  vueInfo: z.string().optional(),
  public_id: z.string().nullable(),
})

export type ClientErrorPayload = z.infer<typeof ClientErrorPayloadSchema>

// The most recent payload — flushed via sendBeacon on pagehide ONLY while a POST
// is in flight (cleared on success), so an error that already landed isn't
// re-sent when the page later unloads.
let inFlightPayload: ClientErrorPayload | null = null
let pageHideListenerAdded = false

function wirePageHide(): void {
  if (
    pageHideListenerAdded ||
    typeof navigator === "undefined" ||
    !navigator.sendBeacon
  ) {
    return
  }
  pageHideListenerAdded = true
  window.addEventListener("pagehide", () => {
    if (!inFlightPayload) return
    try {
      navigator.sendBeacon(
        ENDPOINT,
        new Blob([JSON.stringify(inFlightPayload)], {
          type: "application/json",
        }),
      )
    } catch {
      // never let reporting throw
    }
  })
}

/** POST an error to the backend. Never throws; callers may ignore the promise. */
export async function reportClientError(
  payload: ClientErrorPayload,
): Promise<void> {
  // Validate against the shared contract; safeParse so a malformed payload can't
  // throw out of this reporter.
  const parsed = ClientErrorPayloadSchema.safeParse(payload)
  if (!parsed.success) return
  const valid = parsed.data
  valid.stack = valid.stack.slice(0, MAX_STACK_CHARS)
  inFlightPayload = valid
  wirePageHide()
  try {
    await axios.post(ENDPOINT, valid)
    // Delivered — drop the in-flight copy so the pagehide beacon doesn't
    // duplicate it. Keep it only while in flight / on failure.
    if (inFlightPayload === valid) inFlightPayload = null
  } catch {
    // ignore — reporting must never throw
  }
}

/**
 * Report from a window "error" event (carries filename/lineno/colno).
 *
 * Returns `false` (without reporting) for resource-load failures — a 404
 * `<script>` or broken `<img>` reaches the window error handler as an
 * ErrorEvent with no `error` object and an empty `message`; it isn't a JS
 * error, so callers should also skip the user-facing toast.
 */
export function reportErrorEvent(event: ErrorEvent): boolean {
  // Resource-load failures (broken <img>/<script>) bubble to the window error
  // handler with no `error` and no `message` — not a JS error, so skip it: the
  // page may otherwise be fine and the report would be empty noise.
  if (!event.message && event.error == null) return false
  const err = event.error
  const stack = err instanceof Error ? (err.stack ?? "") : ""
  // Prefer the Error's message (clean); fall back to the raw event.message,
  // which in Firefox includes the "Error: " prefix.
  void reportClientError({
    message: err?.message || event.message || "",
    stack,
    filename: event.filename || "",
    lineno: event.lineno ?? null,
    colno: event.colno ?? null,
    url: window.location.href,
    userAgent: navigator.userAgent,
    public_id: currentPublicId(),
  })
  return true
}

/** Report from a window "unhandledrejection" event (no line/col). */
export function reportRejection(event: PromiseRejectionEvent): void {
  const reason = event.reason
  const err = reason instanceof Error ? reason : undefined
  void reportClientError({
    message:
      err?.message ??
      (typeof reason === "string" ? reason : "Unhandled promise rejection"),
    stack: err?.stack ?? "",
    filename: "",
    lineno: null,
    colno: null,
    url: window.location.href,
    userAgent: navigator.userAgent,
    public_id: currentPublicId(),
  })
}

/**
 * Report a Vue-caught error. `info` is Vue's lifecycle hint (e.g. "render",
 * "setup function") — useful for categorizing where it blew up.
 */
export function reportVueError(err: unknown, info?: string): void {
  const e = err instanceof Error ? err : undefined
  void reportClientError({
    message: e?.message ?? (typeof err === "string" ? err : "Vue render error"),
    stack: e?.stack ?? "",
    filename: "",
    lineno: null,
    colno: null,
    url: window.location.href,
    userAgent: navigator.userAgent,
    vueInfo: info,
    public_id: currentPublicId(),
  })
}

// Read the viewer's public_id from the Inertia shared props (set by
// SharedPropsMiddleware). Informational only — the backend re-derives identity
// from request.user; this just lets a client_error record name its reporter.
function currentPublicId(): string | null {
  try {
    const user = (usePage().props as Record<string, unknown>).user as
      | { public_id?: string }
      | null
      | undefined
    return user?.public_id ?? null
  } catch {
    return null
  }
}
