<script setup lang="ts">
// The navbar bell. The unread count's home turf is the Inertia shared prop
// ``unread_notifications`` (SharedPropsMiddleware): fresh on every page
// visit, no polling. Live updates between visits — a Web Push arriving,
// the notifications page's own actions, or the tab being refocused — come
// through as refresh nudges (the service worker's postMessage, a window
// event, a visibilitychange), each handled by a partial reload of just
// that prop (server truth, one round trip).
// SW registration lives here too (the SW serves the bell first and
// foremost); all notification wiring is in this file, leaving Layout.vue
// a one-line consumer.
import { computed, onBeforeUnmount, onMounted } from "vue"
import { Link, router, usePage } from "@inertiajs/vue3"
import { SharedPropsSchema } from "../schemas"
import { registerPushSW, rebindAfterLogin } from "../utils/push"

const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
const unreadCount = computed(() => shared.value.unread_notifications)

function refreshCount(): void {
  // Partial reload: re-render the current page server-side, receiving
  // only the shared count back. router.reload() dispatches the visit and
  // returns void; any failure surfaces through the app's global Inertia
  // error handlers like any navigation.
  router.reload({ only: ["unread_notifications"] })
}

// SW → page messages: "a push arrived" refreshes the badge; "navigate"
// deep-links an open window (notificationclick in the SW). event.data is
// UNTRUSTED (any same-origin script can postMessage): unknown shapes are
// ignored, and navigate URLs are constrained to same-origin paths.
async function onSWMessage(event: MessageEvent): Promise<void> {
  const data = event.data as { type?: unknown; url?: unknown } | null
  if (!data || typeof data !== "object" || typeof data.type !== "string") {
    return
  }
  if (data.type === "notifications-changed") {
    refreshCount()
    return
  }
  if (data.type === "notifications-navigate" && typeof data.url === "string") {
    // Same-origin only, checked by URL PARSING (string prefixes are
    // bypassable with control chars — "/\t/evil.com" is
    // protocol-relative): resolve against the origin and compare.
    try {
      const url = new URL(data.url, window.location.origin)
      if (url.origin === window.location.origin)
        router.visit(url.pathname + url.search)
    } catch {
      // Unparseable URL: nothing to navigate to.
    }
  }
}

function onNotificationsChanged(): void {
  refreshCount()
}

// Returning to an idle tab (visibilitychange → visible) is exactly when a
// stale badge gets noticed — and the one state no other path covers: a
// browser WITHOUT push, parked on one page, gets no SW message and no
// navigation. One partial reload per tab-focus closes that gap; rapid
// toggles are fine, Inertia cancels superseded in-flight requests.
function onVisibilityChange(): void {
  if (document.visibilityState === "visible") refreshCount()
}

onMounted(() => {
  registerPushSW()
  navigator.serviceWorker?.addEventListener("message", onSWMessage)
  window.addEventListener("notifications-changed", onNotificationsChanged)
  document.addEventListener("visibilitychange", onVisibilityChange)
  // One-shot post-login rebind: logout deleted this browser's server
  // row; re-POST the still-held subscription so delivery resumes
  // invisibly (silent by design — see rebindAfterLogin).
  if (shared.value.just_logged_in) void rebindAfterLogin()
})

onBeforeUnmount(() => {
  navigator.serviceWorker?.removeEventListener("message", onSWMessage)
  window.removeEventListener("notifications-changed", onNotificationsChanged)
  document.removeEventListener("visibilitychange", onVisibilityChange)
})
</script>

<template>
  <!-- Badge-only bell (no visible label): the number IS the affordance —
       always shown, 0 included, red when unread work waits, muted at zero.
       aria-label keeps the link meaningful to screen readers (a bare
       number is not a name). -->
  <Link
    href="/notifications"
    class="nav-link notifications-bell"
    aria-label="Notifications"
  >
    <span
      class="badge notifications-badge"
      :class="unreadCount > 0 ? 'text-bg-danger' : 'text-bg-secondary'"
      >{{ unreadCount }}</span
    >
  </Link>
</template>
