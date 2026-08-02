// Desktop notifications for permission prompts and turn-end. Fired only when
// the page is backgrounded (document.hidden) — i.e. exactly when you've tabbed
// away and would otherwise miss a permission prompt. Opt-in: enabled via the
// warning at the bottom of the chat page (one-way, not a toggle).

export function isNotifySupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window
}

export function notifyPermission(): NotificationPermission {
  return isNotifySupported() ? Notification.permission : "denied"
}

export async function requestNotifyPermission(): Promise<NotificationPermission> {
  if (!isNotifySupported()) return "denied"
  try {
    return await Notification.requestPermission()
  } catch {
    return Notification.permission
  }
}

// Fire a desktop notification. Silent unless the page is hidden (you're already
// watching) and only fires the toast when the user has granted permission.
export function notify(title: string, body?: string) {
  if (typeof document === "undefined" || !document.hidden) return
  try {
    if (notifyPermission() !== "granted") return
    new Notification(title, body ? { body } : undefined)
  } catch {
    // notifyPermission/Notification can throw on insecure origins or where a
    // service worker is required; silently skip in that case.
  }
}
