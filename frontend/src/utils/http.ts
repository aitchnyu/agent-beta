import ky, { HTTPError, TimeoutError } from "ky"
import type { Options } from "ky"
import { HttpNetworkError, HttpResponseError } from "@inertiajs/core"
import type { z } from "zod"
import { type NinjaError, ninjaErrorFrom } from "./pydanticErrors"
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

/** Rethrow a ky error as the ONE taxonomy (see header). Never resolves. */
async function normalizeError(err: unknown): Promise<never> {
  if (err instanceof HTTPError) {
    // ky already read the body into err.data when it built the error
    // (parsed JSON for JSON responses, raw text otherwise) — the response
    // stream is consumed, so err.response.text() would reject.
    throw new HttpResponseError(
      `Request failed with status ${err.response.status}`,
      {
        status: err.response.status,
        data: err.data,
        headers: Object.fromEntries(err.response.headers.entries()),
      },
      err.response.url,
    )
  }
  if (err instanceof TimeoutError) {
    // ky's timeout fires before any socket error: report as network.
    throw new HttpNetworkError(err.message)
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    // Caller-initiated cancel, not a failure — propagate untouched so
    // consumers can distinguish the two.
    throw err
  }
  // Everything else (fetch network errors, unexpected throws): network
  // class, original error chained as the cause.
  throw new HttpNetworkError(
    err instanceof Error ? err.message : "Network request failed",
    undefined,
    err instanceof Error ? err : undefined,
  )
}

// Body comes back as `unknown` on purpose: callers parse it with a zod
// schema (schemas.ts), which is where response shapes are declared. A 422
// throws like any other error — use the ninja* helpers below when a form
// needs the validation errors inline.

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
 * POST a FormData as multipart (file uploads — bytes cannot ride JSON). The
 * FormData is passed as the body untouched so fetch sets the multipart
 * boundary
 */
export async function postForm(url: string, form: FormData): Promise<unknown> {
  try {
    const response = await api.post(url, { body: form })
    const type = response.headers.get("content-type") ?? ""
    if (!type.includes("json")) return undefined
    return await response.json()
  } catch (err) {
    return normalizeError(err)
  }
}

export async function deleteJSON(
  url: string,
  data?: unknown,
): Promise<unknown> {
  const req: Options = {}
  if (data !== undefined) req.json = data
  try {
    return await api.delete(url, req).json()
  } catch (err) {
    return normalizeError(err)
  }
}

/**
 * POST that resolves with the streaming fetch Response (body unread) — for
 * SSE endpoints. Non-2xx rejects (normalized) before the body is touched;
 * the Response's `body` ReadableStream is consumed by the caller.
 */
// TODO need this after web agent was removed?
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

// -- ninja helpers -----------------------------------------------------------
//
// Success is parsed by the schema; a 422 comes back as a NinjaError;
// everything else throws like the plain helpers above.

/** A 422 becomes a NinjaError; anything else rethrows via the taxonomy. */
async function asNinjaErrorOrThrow(err: unknown): Promise<NinjaError> {
  if (err instanceof HTTPError && err.response.status === 422) {
    // ky already read the body into err.data (parsed JSON or raw text).
    const ninja = ninjaErrorFrom(err.data)
    if (ninja) return ninja
  }
  return normalizeError(err)
}

export async function ninjaPost<Schema extends z.ZodType>(
  schema: Schema,
  url: string,
  data?: unknown,
): Promise<z.infer<Schema> | NinjaError> {
  const req: Options = {}
  if (data !== undefined) req.json = data
  let body: unknown
  try {
    body = await api.post(url, req).json()
  } catch (err) {
    return asNinjaErrorOrThrow(err)
  }
  return schema.parse(body) as z.infer<Schema>
}

export async function ninjaGet<Schema extends z.ZodType>(
  schema: Schema,
  url: string,
  opts: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<z.infer<Schema> | NinjaError> {
  const req: Options = {}
  if (opts.signal) req.signal = opts.signal
  if (opts.timeoutMs) req.timeout = opts.timeoutMs
  let body: unknown
  try {
    body = await api.get(url, req).json()
  } catch (err) {
    return asNinjaErrorOrThrow(err)
  }
  return schema.parse(body) as z.infer<Schema>
}

export async function ninjaDelete<Schema extends z.ZodType>(
  schema: Schema,
  url: string,
  data?: unknown,
): Promise<z.infer<Schema> | NinjaError> {
  const req: Options = {}
  if (data !== undefined) req.json = data
  let body: unknown
  try {
    body = await api.delete(url, req).json()
  } catch (err) {
    return asNinjaErrorOrThrow(err)
  }
  return schema.parse(body) as z.infer<Schema>
}
