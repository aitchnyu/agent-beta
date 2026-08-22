import ky, { HTTPError, TimeoutError } from "ky"
import type { Options } from "ky"
import { HttpNetworkError, HttpResponseError } from "@inertiajs/core"

// One HTTP layer for every standalone (non-page-visit) request, on ky — a
// zero-dependency fetch wrapper (~3KB gzip; axios would cost ~4x for features
// this codebase doesn't use). Inertia page visits keep using Inertia's own
// internal client; UserList's search box uses the useHttp hook. ky is
// fetch-based, so the same layer can serve streaming responses (XHR clients
// buffer the whole response and cannot stream) should one be needed again.
//
// CSRF: Django's csrftoken cookie -> X-CSRFToken header on every request via
// the beforeRequest hook (the cookie is set on every response by
// inertia.middleware.InertiaMiddleware).
//
// retry: 0 and no default timeout — callers own their re-poll/backoff timing,
// and a long-lived stream must never be cut by a timer.
//
// Rejections are normalized to @inertiajs/core's error classes
// (HttpResponseError / HttpNetworkError), so callers and showErrorToast see
// ONE taxonomy no matter which layer threw (here, useHttp, or a page visit).
// A raw AbortError (user/system cancel) propagates untouched so callers can
// distinguish cancels from failures.

const api = ky.create({
  retry: 0,
  timeout: false,
  hooks: {
    beforeRequest: [
      ({ request }) => {
        const token = csrfToken()
        if (token) request.headers.set("X-CSRFToken", token)
      },
    ],
  },
})

/** Django CSRF token from the csrftoken cookie. */
function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

async function normalizeError(err: unknown): Promise<never> {
  if (err instanceof HTTPError) {
    let body = ""
    try {
      body = await err.response.text()
    } catch {
      // body unreadable/already consumed — report empty
    }
    throw new HttpResponseError(
      `Request failed with status ${err.response.status}`,
      {
        status: err.response.status,
        data: body,
        headers: Object.fromEntries(err.response.headers.entries()),
      },
      err.response.url,
    )
  }
  if (err instanceof TimeoutError) {
    throw new HttpNetworkError(err.message)
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    throw err
  }
  throw new HttpNetworkError(
    err instanceof Error ? err.message : "Network request failed",
    undefined,
    err instanceof Error ? err : undefined,
  )
}

// Callers get `unknown` on purpose: every consumer feeds the result through a
// zod schema (schemas.ts), which is where response shapes are declared. The
// JSON string/number/boolean overloads exist for endpoints returning a bare
// scalar (e.g. a count), which .json<T>() would otherwise type as never-ish.

export async function getJSON(
  url: string,
  opts: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<unknown> {
  // Options are built conditionally so nothing is passed as an explicit
  // `undefined` (the project enables exactOptionalPropertyTypes).
  const req: Options = {}
  if (opts.signal) req.signal = opts.signal
  if (opts.timeoutMs) req.timeout = opts.timeoutMs
  try {
    return await api.get(url, req).json()
  } catch (err) {
    return normalizeError(err)
  }
}

export async function postJSON(url: string, data?: unknown): Promise<unknown> {
  const req: Options = {}
  if (data !== undefined) req.json = data
  try {
    return await api.post(url, req).json()
  } catch (err) {
    return normalizeError(err)
  }
}

/**
 * POST that resolves with the streaming fetch Response (body unread) — for
 * SSE endpoints. Non-2xx rejects (normalized) before the body is touched;
 * the Response's `body` ReadableStream is consumed by the caller.
 */
export async function streamPost(
  url: string,
  data: unknown,
  opts: { signal?: AbortSignal } = {},
): Promise<Response> {
  const req: Options = {
    json: data,
    headers: { Accept: "text/event-stream" },
  }
  if (opts.signal) req.signal = opts.signal
  try {
    return await api.post(url, req)
  } catch (err) {
    return normalizeError(err)
  }
}
