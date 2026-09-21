<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { router } from "@inertiajs/vue3"
import PageTitle from "../components/PageTitle.vue"
import HumanizedTime from "../components/HumanizedTime.vue"
import {
  NotificationsPagePropsSchema,
  TestNotificationResponseSchema,
} from "../schemas.ts"
import type { NotificationItem } from "../schemas.ts"
import { deleteJSON, postJSON } from "../utils/http"
import { showToast, confirmAction } from "../utils/sweetalert"
import {
  disablePush,
  enablePush,
  isPushSubscribed,
  resubscribePush,
} from "../utils/push"

const props = defineProps<{
  props: object
}>()

const p = NotificationsPagePropsSchema.parse(props.props)
const notifications = ref<NotificationItem[]>(p.notifications)
const unreadCount = ref(p.unread_count)

// Partial reloads (e.g. the test button's targeted refresh) swap page
// props reactively — without this watcher the list/count would stay a
// setup-time snapshot. Re-parsed per change: small, and stays zod-true.
const pageData = computed(() => NotificationsPagePropsSchema.parse(props.props))
watch(
  () => pageData.value.notifications,
  (rows) => {
    notifications.value = rows
    unreadCount.value = pageData.value.unread_count
  },
)

// Browser push state (client-side truth — the server only knows whether
// VAPID is configured at all). The BUTTON state keys on the actual
// SUBSCRIPTION (permission alone lies: it stays "granted" after Disable,
// and a granted-but-unsubscribed browser is still push-less). permission
// only gates the messaging for the denied case; pushSupported false on
// browsers without the Push API.
const pushPermission = ref(
  typeof Notification !== "undefined" ? Notification.permission : "default",
)
const pushSubscribed = ref(false)
const pushBusy = ref(false)
const pushSupported =
  typeof Notification !== "undefined" && "PushManager" in window

const canEnable = computed(
  () =>
    p.push_enabled &&
    pushSupported &&
    pushPermission.value !== "denied" &&
    !pushSubscribed.value,
)

// The subscription check is async (SW registration round trip); until it
// resolves both buttons stay hidden (pushBusy starts true for that read).
onMounted(() => {
  if (!pushSupported) return
  void isPushSubscribed()
    .then((subscribed) => {
      pushSubscribed.value = subscribed
    })
    .catch(() => {})
})

// Enable: permission prompt → subscribe → register server-side. The
// explicit button (never an auto-prompt) is the gesture the permission
// dialog needs. Errors propagate to the global pipeline (toast +
// /client-errors); the catch only repairs local state on the way out.
async function onEnable(): Promise<void> {
  pushBusy.value = true
  try {
    await enablePush(p.vapid_public_key)
    pushPermission.value = "granted"
    pushSubscribed.value = true
    await showToast("success", "Notifications enabled on this device")
  } catch (e) {
    // Re-read the browser truth on the way out: a DENIED prompt flips
    // Notification.permission, and the ref must follow or the button
    // stays + every retry throws instantly with no prompt.
    if (typeof Notification !== "undefined") {
      pushPermission.value = Notification.permission
    }
    pushSubscribed.value = await isPushSubscribed().catch(() => false)
    throw e
  } finally {
    pushBusy.value = false
  }
}

async function onDisable(): Promise<void> {
  pushBusy.value = true
  try {
    await disablePush()
    pushSubscribed.value = false
    await showToast("success", "Notifications disabled on this device")
  } catch (e) {
    pushSubscribed.value = await isPushSubscribed().catch(() => true)
    throw e
  } finally {
    pushBusy.value = false
  }
}

// Manual heal: drop this browser's subscription and make a FRESH one
// (new keys, server row re-registered) — for when pushes stopped
// arriving on this device.
async function onResubscribe(): Promise<void> {
  pushBusy.value = true
  try {
    await resubscribePush(p.vapid_public_key)
    pushPermission.value = "granted"
    pushSubscribed.value = true
    await showToast("success", "Resubscribed — try a test notification")
  } catch (e) {
    if (typeof Notification !== "undefined") {
      pushPermission.value = Notification.permission // same truth as onEnable
    }
    pushSubscribed.value = await isPushSubscribed().catch(() => false)
    throw e
  } finally {
    pushBusy.value = false
  }
}

// Pure delivery check: pushes to every subscription of this user — the
// browser toast on each device IS the result. Nothing in-app happens by
// design (no row, no badge bump, no reload): a stored test row would
// pollute the list and defeat the point of testing ONLY the push path.
async function onSendTest(): Promise<void> {
  testBusy.value = true
  try {
    const { count } = TestNotificationResponseSchema.parse(
      await postJSON("/notifications/api/test"),
    )
    if (count > 0) {
      await showToast("success", `Test push sent to ${count} device(s)`)
    } else {
      await showToast(
        "warning",
        "No devices to push to — enable notifications first",
      )
    }
  } finally {
    testBusy.value = false
  }
}

const testBusy = ref(false)

// Actions update the local list immediately (server responses confirm),
// then tell the Layout to refresh its badge count (window event —
// Layout.vue listens for it alongside the SW's postMessage).
function notifyBadge(): void {
  window.dispatchEvent(new Event("notifications-changed"))
}

async function onMarkRead(item: NotificationItem): Promise<void> {
  await postJSON(`/notifications/api/${item.public_id}/read`)
  if (!item.read) {
    item.read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    notifyBadge()
  }
}

// A row's body is a deep link when it carries a URL: click navigates
// (Inertia visit) and marks it read in passing.
async function onOpen(item: NotificationItem): Promise<void> {
  await onMarkRead(item)
  if (item.url) router.visit(item.url)
}

async function onDelete(item: NotificationItem): Promise<void> {
  await deleteJSON(`/notifications/api/${item.public_id}`)
  if (!item.read) unreadCount.value = Math.max(0, unreadCount.value - 1)
  notifications.value = notifications.value.filter(
    (n) => n.public_id !== item.public_id,
  )
  notifyBadge()
}

async function onMarkAllRead(): Promise<void> {
  await postJSON("/notifications/api/read-all")
  for (const n of notifications.value) n.read = true
  unreadCount.value = 0
  notifyBadge()
}

// Clear-all is destructive (rows are gone for good — "till deleted" is
// the whole lifecycle): confirm first, then wipe the local list.
async function onClearAll(): Promise<void> {
  if (
    !(await confirmAction(
      "Delete all notifications?",
      "This cannot be undone.",
    ))
  )
    return
  await postJSON("/notifications/api/clear")
  notifications.value = []
  unreadCount.value = 0
  notifyBadge()
}
</script>

<template>
  <PageTitle value="Notifications" />
  <div class="container notifications-page">
    <div class="d-flex align-items-center justify-content-between mt-2 mb-3">
      <h1 class="mb-0">Notifications</h1>
      <div class="d-flex gap-2">
        <button
          v-if="unreadCount > 0"
          class="btn btn-sm btn-outline-secondary notifications-read-all"
          @click="onMarkAllRead"
        >
          Mark all read
        </button>
        <button
          v-if="notifications.length > 0"
          class="btn btn-sm btn-outline-danger notifications-clear"
          @click="onClearAll"
        >
          Clear all
        </button>
      </div>
    </div>

    <div class="notifications-push card mb-3">
      <div class="card-body d-flex align-items-center justify-content-between">
        <div>
          <strong>Browser notifications</strong>
          <div class="text-muted small">
            <template v-if="!p.push_enabled">
              Not configured on this server (VAPID keys missing) — in-app
              notifications still work.
            </template>
            <template v-else-if="!pushSupported">
              This browser does not support Web Push.
            </template>
            <template v-else-if="pushPermission === 'denied'">
              Blocked in this browser — allow notifications for this site in the
              browser settings, then reload.
            </template>
            <template v-else-if="pushSubscribed">
              Enabled on this device — notifications arrive even with the tab
              closed.
            </template>
            <template v-else>
              Show system notifications, even with this tab closed.
            </template>
          </div>
        </div>
        <!-- v-if on the group too: denied-but-unsubscribed leaves zero
             buttons (canEnable excludes denied) — no empty btn-group. -->
        <div
          v-if="pushSupported && (canEnable || pushSubscribed)"
          class="btn-group btn-group-sm"
          role="group"
        >
          <button
            v-if="canEnable"
            class="btn btn-primary notifications-enable"
            :disabled="pushBusy"
            @click="onEnable"
          >
            Enable notifications
          </button>
          <template v-else-if="pushSubscribed">
            <button
              class="btn btn-outline-secondary notifications-resubscribe"
              :disabled="pushBusy"
              @click="onResubscribe"
            >
              Resubscribe
            </button>
            <button
              class="btn btn-outline-secondary notifications-disable"
              :disabled="pushBusy"
              @click="onDisable"
            >
              Disable
            </button>
          </template>
        </div>
      </div>
    </div>

    <!-- Only when the server can push at all: with VAPID off the button
         would only ever toast "no devices" — an impossible action. -->
    <div
      v-if="p.push_enabled && pushSupported"
      class="d-flex justify-content-end mb-3"
    >
      <button
        class="btn btn-sm btn-outline-primary notifications-test"
        :disabled="testBusy"
        @click="onSendTest"
      >
        Send test notification
      </button>
    </div>

    <div v-if="notifications.length === 0" class="text-muted py-4">
      No notifications.
    </div>

    <div v-else class="notifications-list">
      <div
        v-for="n in notifications"
        :key="n.public_id"
        class="notification-item card mb-2"
        :class="{ 'notification-unread': !n.read }"
      >
        <div class="card-body d-flex align-items-start gap-2">
          <div class="flex-grow-1">
            <a
              v-if="n.url"
              :href="n.url"
              class="notification-open"
              @click.prevent="onOpen(n)"
            >
              <span class="badge bg-secondary me-1">{{ n.kind }}</span>
              {{ n.body }}
            </a>
            <template v-else>
              <span class="badge bg-secondary me-1">{{ n.kind }}</span>
              {{ n.body }}
            </template>
            <div class="text-muted small">
              <HumanizedTime :ms="n.created_at" />
            </div>
          </div>
          <span
            v-if="!n.read"
            class="badge text-bg-primary notification-unread-dot"
            >new</span
          >
          <button
            v-if="!n.read"
            class="btn btn-sm btn-outline-secondary notification-mark-read"
            @click="onMarkRead(n)"
          >
            Mark read
          </button>
          <button
            class="btn btn-sm btn-outline-danger notification-delete"
            @click="onDelete(n)"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
