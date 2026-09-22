<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { router } from "@inertiajs/vue3"
import PageTitle from "../components/PageTitle.vue"
import HumanizedTime from "../components/HumanizedTime.vue"
import {
  CountResponseSchema,
  NotificationPageResponseSchema,
  NotificationsPagePropsSchema,
  MessageResponseSchema,
  SelectedIdsSchema,
} from "../schemas.ts"
import type { NotificationItem } from "../schemas.ts"
import { getJSON, postJSON } from "../utils/http"
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
const hasMore = ref(p.has_more)

// Partial reloads (e.g. the test button's targeted refresh) swap page
// props reactively — without this watcher the list/count would stay a
// setup-time snapshot. Re-parsed per change: small, and stays zod-true.
const pageData = computed(() => NotificationsPagePropsSchema.parse(props.props))
// Bumped whenever a partial reload replaces the list wholesale — Load more
// captures the epoch before its fetch and drops responses that straddle a
// swap (otherwise stale-cursored appends would land on a fresh page-1 list
// and silently hide the rows in between for the session).
const listEpoch = ref(0)
watch(
  () => pageData.value.notifications,
  (rows) => {
    notifications.value = rows
    unreadCount.value = pageData.value.unread_count
    hasMore.value = pageData.value.has_more
    listEpoch.value++
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

// The test button exercises the REAL pipeline: the server stores a
// Notification row (list + badge) whose on_commit fan-out pushes to
// every subscribed device. Busy gates only the POST itself — the toast
// wait must not disable the button (a repeat click just sends another).
async function onSendTest(): Promise<void> {
  testBusy.value = true
  try {
    MessageResponseSchema.parse(await postJSON("/notifications/api/test"))
  } finally {
    testBusy.value = false
  }
  // The row is the result: one targeted partial reload refreshes the
  // list AND the shared badge count (the watcher above re-parses the
  // swapped props reactively).
  router.reload({ only: ["props", "unread_notifications"] })
  await showToast("success", "Test notification sent — shown in the app")
}

const testBusy = ref(false)

// Actions update the local list immediately (server responses confirm),
// then tell the navbar badge to refresh (window event — UserMenu.vue
// listens for it alongside the SW's postMessage).
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

// ── Checkbox selection (Gmail-style bulk actions) ──────────────────────────
// Selection is page-local client state over the rendered rows; the actions
// POST the id list (owner-scoped server-side), then update the local list
// in place — same immediate-feedback contract as the single-row actions.

const selected = ref(new Set<string>())

// Rows swap out from under the selection (partial reloads, deletes): prune
// ids that no longer render so "N selected" never counts ghosts.
watch(notifications, (rows) => {
  const live = new Set(rows.map((n) => n.public_id))
  selected.value = new Set([...selected.value].filter((id) => live.has(id)))
})

const selectedCount = computed(() => selected.value.size)
const allSelected = computed(
  () =>
    notifications.value.length > 0 &&
    selected.value.size === notifications.value.length,
)
const someSelected = computed(() => selected.value.size > 0)

function toggle(n: NotificationItem): void {
  const next = new Set(selected.value)
  if (next.has(n.public_id)) next.delete(n.public_id)
  else next.add(n.public_id)
  selected.value = next
}

function toggleAll(): void {
  selected.value = allSelected.value
    ? new Set()
    : new Set(notifications.value.map((n) => n.public_id))
}

// The select next to the select-all checkbox (Gmail's triage menu): pick
// which slice of the rendered rows the selection covers. Re-picking the
// option the <select> already shows fires no change event, so bulk actions
// and list swaps reset it to the placeholder ("Select…") — every mode stays
// reachable in one click.
function onSelectMode(event: Event): void {
  const el = event.target as HTMLSelectElement
  const mode = el.value
  const pick = (predicate: (_: NotificationItem) => boolean) =>
    new Set(notifications.value.filter(predicate).map((n) => n.public_id))
  if (mode === "all") selected.value = pick(() => true)
  else if (mode === "unread") selected.value = pick((n) => !n.read)
  else if (mode === "read") selected.value = pick((n) => n.read)
  else selected.value = new Set()
  el.value = ""
}

function resetSelectMode(): void {
  const el = document.querySelector<HTMLSelectElement>(
    ".notifications-select-mode",
  )
  if (el) el.value = ""
}

// ── Load more (50 rows at a time, cursor-paged) ─────────────────────────────
// The page renders the first chunk server-side; older rows append on demand
// via /api/page, cursoring on the last rendered row's public_id within the
// active kind filter.

const loadingMore = ref(false)

async function onLoadMore(): Promise<void> {
  const last = notifications.value[notifications.value.length - 1]
  if (!last || loadingMore.value) return
  const epoch = listEpoch.value
  loadingMore.value = true
  try {
    const params = new URLSearchParams({ after: last.public_id })
    if (p.kind) params.set("kind", p.kind)
    const page = NotificationPageResponseSchema.parse(
      await getJSON(`/notifications/api/page?${params.toString()}`),
    )
    // A partial reload swapped the list while we were fetching — drop the
    // response (its cursor belongs to the old list).
    if (epoch !== listEpoch.value) return
    // Appended rows are strictly older; selection keeps applying (its
    // prune watcher only needs to fire on wholesale swaps).
    notifications.value.push(...page.notifications)
    hasMore.value = page.has_more
  } finally {
    loadingMore.value = false
  }
}

async function onMarkSelectedRead(): Promise<void> {
  const ids = [...selected.value]
  CountResponseSchema.parse(
    await postJSON(
      "/notifications/api/read-selected",
      SelectedIdsSchema.parse({ public_ids: ids }),
    ),
  )
  const idSet = new Set(ids)
  let newlyRead = 0
  for (const n of notifications.value) {
    if (idSet.has(n.public_id) && !n.read) {
      n.read = true
      newlyRead++
    }
  }
  unreadCount.value = Math.max(0, unreadCount.value - newlyRead)
  selected.value = new Set()
  resetSelectMode()
  notifyBadge()
}

// Destructive on potentially many rows: confirm first (same contract as
// Clear all), then drop the rows locally and re-count the badge.
async function onDeleteSelected(): Promise<void> {
  const ids = [...selected.value]
  if (
    !(await confirmAction(
      `Delete ${ids.length} notification${ids.length === 1 ? "" : "s"}?`,
      "This cannot be undone.",
    ))
  )
    return
  CountResponseSchema.parse(
    await postJSON(
      "/notifications/api/delete-selected",
      SelectedIdsSchema.parse({ public_ids: ids }),
    ),
  )
  const idSet = new Set(ids)
  unreadCount.value = Math.max(
    0,
    unreadCount.value -
      notifications.value.filter((n) => idSet.has(n.public_id) && !n.read)
        .length,
  )
  notifications.value = notifications.value.filter(
    (n) => !idSet.has(n.public_id),
  )
  selected.value = new Set()
  resetSelectMode()
  notifyBadge()
}

// ── Kind filter (?kind=…) ───────────────────────────────────────────────────
// The kind is deemphasized data, not a badge: clicking it narrows the list
// via a real URL (shareable, back-button-able), and the chip clears it.

function filterByKind(kind: string): void {
  router.visit(`/notifications?kind=${encodeURIComponent(kind)}`)
}

function clearKindFilter(): void {
  router.visit("/notifications")
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
              Unavailable on this server — in-app notifications still work.
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
              System notifications arrive while your BROWSER runs — even with
              this tab closed; fully quitting the browser pauses them (queued up
              to a day). The in-app badge and this list only update while the
              app is open.
            </template>
          </div>
        </div>
        <!-- Controls cluster as ONE right-hand child: with text + group +
             button as three card-body children, justify-content-between
             spread them to opposite ends. -->
        <div class="d-flex align-items-center gap-2">
          <!-- v-if on the group too: denied-but-unsubscribed leaves zero
               buttons (canEnable excludes denied) — no empty btn-group. -->
          <div
            v-if="pushSupported && (canEnable || pushSubscribed)"
            class="btn-group"
            role="group"
          >
            <button
              v-if="canEnable"
              class="btn btn-sm btn-primary notifications-enable"
              :disabled="pushBusy"
              @click="onEnable"
            >
              Enable notifications
            </button>
            <template v-else-if="pushSubscribed">
              <button
                class="btn btn-sm btn-outline-secondary notifications-resubscribe"
                :disabled="pushBusy"
                @click="onResubscribe"
              >
                Resubscribe
              </button>
              <button
                class="btn btn-sm btn-outline-secondary notifications-disable"
                :disabled="pushBusy"
                @click="onDisable"
              >
                Disable
              </button>
            </template>
          </div>
          <!-- The test button, same card: records a REAL notification —
               row in the list, badge bump, push to every subscribed
               device — so it always renders (the in-app result needs no
               push configuration). -->
          <button
            class="btn btn-sm btn-outline-primary notifications-test"
            :disabled="testBusy"
            @click="onSendTest"
          >
            Send test
          </button>
        </div>
      </div>
    </div>

    <div v-if="p.kind" class="notifications-filter mb-2">
      <span class="text-muted">Kind:</span>
      <code>{{ p.kind }}</code>
      <a
        href="/notifications"
        class="notifications-filter-clear"
        @click.prevent="clearKindFilter"
        >clear</a
      >
    </div>

    <div v-if="notifications.length === 0" class="text-muted py-4">
      No notifications.
    </div>

    <div v-else class="notifications-list card">
      <div class="notifications-toolbar d-flex align-items-center gap-2">
        <input
          type="checkbox"
          class="form-check-input mt-0 notifications-select-all"
          aria-label="Select all notifications"
          :checked="allSelected"
          :indeterminate="someSelected && !allSelected"
          @change="toggleAll"
        />
        <select
          class="form-select form-select-sm w-auto notifications-select-mode"
          aria-label="Select messages"
          @change="onSelectMode"
        >
          <option value="" disabled selected>Select…</option>
          <option value="all">All</option>
          <option value="none">None</option>
          <option value="unread">Unread</option>
          <option value="read">Read</option>
        </select>
        <span
          v-if="selectedCount > 0"
          class="text-muted small notifications-selected-count"
        >
          {{ selectedCount }} selected
        </span>
        <button
          v-if="selectedCount > 0"
          class="btn btn-sm btn-outline-secondary notifications-mark-selected"
          @click="onMarkSelectedRead"
        >
          Mark read
        </button>
        <button
          v-if="selectedCount > 0"
          class="btn btn-sm btn-outline-danger notifications-delete-selected"
          @click="onDeleteSelected"
        >
          Delete
        </button>
      </div>
      <div
        v-for="n in notifications"
        :key="n.public_id"
        class="notification-item"
        :class="{ 'notification-unread': !n.read }"
        :data-kind="n.kind"
      >
        <input
          type="checkbox"
          class="form-check-input mt-0 notification-select"
          :aria-label="`Select: ${n.body}`"
          :checked="selected.has(n.public_id)"
          @change="toggle(n)"
        />
        <button
          type="button"
          class="btn btn-link notification-kind"
          :title="`Filter by ${n.kind}`"
          @click="filterByKind(n.kind)"
        >
          {{ n.kind }}
        </button>
        <div class="notification-body flex-grow-1">
          <a
            v-if="n.url"
            :href="n.url"
            class="notification-open"
            @click.prevent="onOpen(n)"
            >{{ n.body }}</a
          >
          <template v-else>{{ n.body }}</template>
        </div>
        <span class="notification-time text-muted small">
          <HumanizedTime :ms="n.created_at" />
        </span>
      </div>
      <div v-if="hasMore" class="notifications-load-more-row">
        <button
          class="btn btn-sm btn-outline-primary notifications-load-more"
          :disabled="loadingMore"
          @click="onLoadMore"
        >
          Load more
        </button>
      </div>
    </div>
  </div>
</template>
