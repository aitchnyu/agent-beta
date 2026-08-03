import { ref } from "vue"
import {
  isNotifySupported,
  notifyPermission,
  requestNotifyPermission,
} from "./notify"

// OS-notification permission state, isolated from the transport/transcript.
// The browser persists the permission across refreshes, so it's the source of
// truth — no separate preference is stored. Snapshotted at load
// (Notification.permission isn't reactive) and refreshed by enableNotifications().
export function useOpencodeNotifications() {
  const canNotify = isNotifySupported()
  const notifyGranted = ref(notifyPermission() === "granted")
  const notifyDenied = ref(notifyPermission() === "denied")

  // One-way enable (not a toggle): requests OS permission. Re-request only from
  // "default" — a denied prompt can't be re-asked programmatically, so the user
  // must change it in browser site settings (the warning reflects that via the
  // denied state). The browser persists the result, so granted stays granted.
  async function enableNotifications() {
    if (notifyGranted.value) return
    const result =
      notifyPermission() === "default"
        ? await requestNotifyPermission()
        : notifyPermission()
    notifyGranted.value = result === "granted"
    notifyDenied.value = result === "denied"
  }

  return { canNotify, notifyGranted, notifyDenied, enableNotifications }
}
