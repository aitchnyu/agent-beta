// Web Push plumbing for the notifications feature (framework): service
// worker registration and (un)subscription against the app's API.
//
// The subscription state that survives page loads is the browser's own
// (pushManager.getSubscription) — nothing is mirrored into localStorage.
// Logout needs no client help: the session flush CASCADE-deletes the row
// (Session → UserSessionIndex → PushSubscription), and the one-shot
// just_logged_in flag drives rebindAfterLogin() on the next landing.

import { SubscribeResponseSchema } from "../schemas"
import { deleteJSON, postJSON } from "./http"

// Vite copies frontend/public/ verbatim under the static root (vite.config
// base) — the SW lives at a stable, unhashed URL.
export const PUSH_SW_URL = "/static/djangoapp/web-push-sw.js"

/**
 * Register the push service worker (once per load; the browser dedupes).
 * Failures are swallowed SILENTLY (no console.error — the global handlers
 * would toast/reports them, and an unsupported browser is not an error):
 * without the SW, in-app notifications keep working; only push delivery
 * is off.
 */
export function registerPushSW(): void {
  if (!("serviceWorker" in navigator)) return
  void navigator.serviceWorker.register(PUSH_SW_URL).catch(() => {})
}

/** VAPID public key (base64url) → the Uint8Array subscribe() expects. */
function urlBase64ToUint8Array(b64: string): Uint8Array<ArrayBuffer> {
  // base64url → base64, pad to a multiple of 4, decode to raw bytes. Built
  // over an explicit ArrayBuffer: TS 5.7+ types Uint8Array<ArrayBufferLike>
  // by default, and BufferSource-typed APIs want the ArrayBuffer flavor.
  const base64 = b64.replace(/-/g, "+").replace(/_/g, "/")
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4)
  const raw = window.atob(padded)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

/** The subscription's applicationServerKey as base64url (or null). */
function subscriptionServerKey(subscription: PushSubscription): string | null {
  // The DOM types give back an ArrayBuffer (browsers normalize the string
  // form subscribe() accepts into the raw bytes).
  const key = subscription.options?.applicationServerKey
  if (!key) return null
  const bytes = new Uint8Array(key)
  let binary = ""
  for (const b of bytes) binary += String.fromCharCode(b)
  return window
    .btoa(binary)
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
}

/** Whether this browser currently holds a push subscription. */
export async function isPushSubscribed(): Promise<boolean> {
  const registration =
    await navigator.serviceWorker.getRegistration(PUSH_SW_URL)
  if (!registration) return false
  return (await registration.pushManager.getSubscription()) !== null
}

/**
 * Post-login rebind: re-POST the browser's existing subscription so the
 * server row logout deleted is reborn, bound to the new session. Silent
 * by design — a background repair on the landing render must never
 * toast or console.error (browsers without push support throw from
 * getSubscription; nothing to do when no subscription is held).
 */
export async function rebindAfterLogin(): Promise<void> {
  try {
    const registration =
      await navigator.serviceWorker.getRegistration(PUSH_SW_URL)
    if (!registration) return
    const subscription = await registration.pushManager.getSubscription()
    if (!subscription) return
    await registerSubscription(subscription)
  } catch {
    // Background repair: every failure mode here is "leave it for the
    // notifications page's Enable/Resubscribe buttons".
  }
}

/** POST a subscription's shape to the server, validating the response. */
async function registerSubscription(
  subscription: PushSubscription,
): Promise<void> {
  const json = subscription.toJSON()
  const endpoint = json.endpoint
  const p256dh = json.keys ? json.keys.p256dh : undefined
  const auth = json.keys ? json.keys.auth : undefined
  if (!endpoint || !p256dh || !auth) {
    // Partial shape (browser bug / aborted subscription): drop it so a
    // retry starts clean instead of resubscribing the dead one.
    await subscription.unsubscribe()
    throw new Error("The browser returned an incomplete push subscription")
  }
  const response = SubscribeResponseSchema.parse(
    await postJSON("/notifications/api/subscriptions", {
      endpoint,
      p256dh,
      auth,
    }),
  )
  if (!response.subscribed) {
    throw new Error("The server did not accept the push subscription")
  }
}

/**
 * Ask permission, subscribe the browser, and register the subscription
 * server-side. Throws (→ the page toasts) on denial or any failure; the
 * caller decides how much state to reset.
 */
export async function enablePush(vapidPublicKey: string): Promise<void> {
  const permission = await Notification.requestPermission()
  if (permission !== "granted") {
    throw new Error("Notification permission was not granted")
  }
  const registration = await navigator.serviceWorker.register(PUSH_SW_URL)
  const existing = await registration.pushManager.getSubscription()
  let subscription = existing
  if (existing && subscriptionServerKey(existing) !== vapidPublicKey) {
    // Key rotation: the stored subscription is bound to the OLD VAPID
    // key — pushes signed by the new one would bounce. Drop it and
    // resubscribe under the current key.
    await existing.unsubscribe()
    subscription = null
  }
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
    })
  }
  await registerSubscription(subscription)
}

/**
 * Unsubscribe this browser (pushManager + server row). Best-effort by
 * design: the local subscription is dropped even when the server DELETE
 * fails — the server prunes dead endpoints on the next 404/410 push
 * anyway.
 */
export async function disablePush(): Promise<void> {
  const registration =
    await navigator.serviceWorker.getRegistration(PUSH_SW_URL)
  const subscription = registration
    ? await registration.pushManager.getSubscription()
    : null
  if (!subscription) return
  await deleteJSON("/notifications/api/subscriptions", {
    endpoint: subscription.endpoint,
  }).catch(() => {})
  await subscription.unsubscribe()
}

/**
 * Force a FRESH subscription for this browser, replacing any existing one
 * — the manual heal for "current browser lost its subscription" (drift,
 * expired keys, resurrected permissions): drop, resubscribe under the
 * current VAPID key, re-register server-side (update_or_create reuses the
 * row when the push service reissues the same endpoint).
 */
export async function resubscribePush(vapidPublicKey: string): Promise<void> {
  const permission = await Notification.requestPermission()
  if (permission !== "granted") {
    throw new Error("Notification permission was not granted")
  }
  const registration = await navigator.serviceWorker.register(PUSH_SW_URL)
  const existing = await registration.pushManager.getSubscription()
  if (existing) await existing.unsubscribe()
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  })
  await registerSubscription(subscription)
}
