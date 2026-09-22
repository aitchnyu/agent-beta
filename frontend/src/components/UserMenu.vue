<script setup lang="ts">
// The navbar's signed-in user menu. Owns:
// - the button: username + unread badge (shared prop ``unread_notifications``)
// - the dropdown: Profile / Notifications / Logout links
// - badge refresh between visits: SW postMessage, window event,
//   visibilitychange → partial reload of just that prop
// - push SW registration + the one-shot post-login subscription rebind
import { computed, onBeforeUnmount, onMounted } from "vue"
import { Link, router, usePage } from "@inertiajs/vue3"
import { getCsrfToken } from "../utils/csrf"
import { SharedPropsSchema } from "../schemas"
import type { User } from "../schemas"
import DropdownMenu from "./DropdownMenu.vue"
import { registerPushSW, rebindAfterLogin } from "../utils/push"

defineProps<{
  user: User
}>()

const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
const unreadCount = computed(() => shared.value.unread_notifications)
const csrfToken = computed(() => getCsrfToken())

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
function onSWMessage(event: MessageEvent): void {
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
  <!-- The badge is part of the username button (always shown, 0 included,
       red when unread work waits, muted at zero) -->
  <DropdownMenu align="right" class="layout-user-menu" :caret="false">
    <template #trigger>
      <span class="btn btn-sm btn-outline-primary layout-user-button">
        <!-- No aria-label: the accessible name is the content — username
             plus the badge count, which is the point of the button. -->
        {{ user.title }}
        <span
          class="badge notifications-badge"
          :class="unreadCount > 0 ? 'text-bg-danger' : 'text-bg-secondary'"
          >{{ unreadCount }}</span
        >
        <!-- Caret lives INSIDE the button box (the summary-level one
             renders detached outside it). -->
        <span class="layout-user-caret" aria-hidden="true">▾</span>
      </span>
    </template>
    <Link
      :href="`/users/id/${user.public_id}`"
      class="layout-menu-link user-menu-profile"
      >Profile</Link
    >
    <Link href="/notifications" class="layout-menu-link user-menu-notifications"
      >Notifications</Link
    >
    <form
      action="/accounts/logout/"
      method="post"
      class="layout-user-logout-form"
    >
      <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken" />
      <button class="layout-menu-link user-menu-logout" type="submit">
        Logout
      </button>
    </form>
  </DropdownMenu>
</template>
