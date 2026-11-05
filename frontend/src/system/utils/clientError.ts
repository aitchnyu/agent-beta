import { usePage } from "@inertiajs/vue3"
import type { z } from "zod"
import { ClientErrorBody, post_submit } from "../schemas/client_errors_sdk"

// Backend sink for uncaught browser errors. CSRF is not required for this
// endpoint (see djangoapp/views/client_errors.py), so both the Inertia client
// POST and the sendBeacon fallback land without a csrftoken cookie.
const ENDPOINT = "/client-errors"

// Clamp the capped fields BEFORE parsing: the generated schema mirrors the
// backend Field max_lengths (djangoapp.views.client_errors) and REJECTS
// over-length values instead of truncating them, so an unclamped long stack
// or message would fail safeParse and the report would be silently dropped.
const MAX_CHARS = {
  message: 2000,
  stack: 5000,
  filename: 500,
  url: 2000,
  userAgent: 500,
  vueInfo: 200,
} as const

// The payload contract is the GENERATED one (client_errors_sdk.ts, built from
// the backend ClientErrorBody — camelCase wire keys via the pydantic aliases).
export type ClientErrorPayload = z.infer<typeof ClientErrorBody>

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
  // Validate against the shared contract (clamped first — see MAX_CHARS);
  // safeParse so a malformed payload can't throw out of this reporter.
  const clamped = { ...payload }
  for (const field of Object.keys(MAX_CHARS) as Array<keyof typeof MAX_CHARS>) {
    const value = clamped[field]
    if (typeof value === "string") clamped[field] = value.slice(0, MAX_CHARS[field])
  }
  const parsed = ClientErrorBody.safeParse(clamped)
  if (!parsed.success) return
  const valid = parsed.data
  inFlightPayload = valid
  wirePageHide()
  try {
    await post_submit(valid)
    // Delivered — drop the in-flight copy so the pagehide beacon doesn't
    // duplicate it. Keep it only while in flight / on failure.
    if (inFlightPayload === valid) {
      inFlightPayload = null
    }
  } catch {
    // ignore — reporting must never throw; the in-flight copy stays for
    // the pagehide beacon to retry.
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

/**
 * Report an Inertia visit failure (router httpException/networkError
 * events). main.ts preventDefault()s those events, so they never become
 * unhandled rejections — without this they toast but stay invisible to
 * the client-errors log.
 */
export function reportVisitError(err: unknown, context: string): void {
  const e = err instanceof Error ? err : undefined
  void reportClientError({
    message:
      e?.message ??
      (typeof err === "string" ? err : `Visit failed (${context})`),
    stack: e?.stack ?? "",
    filename: "",
    lineno: null,
    colno: null,
    url: window.location.href,
    userAgent: navigator.userAgent,
    vueInfo: context,
    public_id: currentPublicId(),
  })
}

// Read the viewer's public_id from the Inertia shared props (set by
// SharedPropsMiddleware). Informational only — the backend re-derives identity
// from request.user; this just lets a client_error record name its reporter.
function currentPublicId(): string | null {
  try {
    const user = (usePage().props as Record<string, unknown>).user as
      { public_id?: string } | null | undefined
    return user?.public_id ?? null
  } catch {
    return null
  }
}
