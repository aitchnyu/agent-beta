// web-push-sw.js — the Web Push service worker (framework notifications).
//
// Plain JS on purpose: Vite copies frontend/public/ verbatim into the
// static root, unbundled and unhashed — a stable URL the page registers
// once (utils/push.ts). It DELIBERATELY never controls pages: registered
// under /static/djangoapp/ with no Service-Worker-Allowed header, its
// scope excludes app pages, so it intercepts zero fetches. It exists to
// receive `push` events (delivery works with the tab closed), show the
// system notification, and message/focus windows on click.
//
// Because it controls no pages, clients.matchAll needs
// includeUncontrolled: true — the default (controlled-only) would always
// return an empty list here. Window matching keys on the app origin for
// the same reason (page URLs never live under the SW's /static scope).
//
// Payload shape (djangoapp/models/notifications.py::_push):
//   { public_id, kind, body, url }

self.addEventListener("push", (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    // Malformed payload: still show a generic notification — a push
    // arrived, and silence reads as a broken feature.
    data = {}
  }
  const body = typeof data.body === "string" ? data.body : "New notification"
  const url =
    typeof data.url === "string" && data.url ? data.url : "/notifications"
  // One waitUntil covers display AND the client pings: display must not
  // hinge on the round trip, and the SW must not be terminated before the
  // pings land (which would kill the live bell update).
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(body, {
        // tag dedupes: the same notification redelivered replaces its toast
        // instead of stacking a second one.
        tag:
          typeof data.public_id === "string" ? data.public_id : "notification",
        data: { url },
      }),
      self.clients
        .matchAll({ type: "window", includeUncontrolled: true })
        .then((clientList) => {
          for (const client of clientList) {
            client.postMessage({ type: "notifications-changed" })
          }
        }),
    ]),
  )
})

self.addEventListener("notificationclick", (event) => {
  event.notification.close()
  // Same-origin guard by URL parsing (mirrors the page-side handler):
  // an external-URL payload would be spec-rejected by openWindow anyway;
  // better to fall through to the default page.
  let target = "/notifications"
  if (
    event.notification.data &&
    typeof event.notification.data.url === "string"
  ) {
    try {
      const url = new URL(event.notification.data.url, self.location.origin)
      if (url.origin === self.location.origin) {
        target = url.pathname + url.search
      }
    } catch {
      // Unparseable: default target.
    }
  }
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        // Focus an existing app window and ask it to navigate to the deep
        // link (NotificationsBell.vue routes the message via Inertia). With
        // no window open (the news-site case), open one.
        const appClient = clientList.find((c) =>
          c.url.startsWith(self.location.origin + "/"),
        )
        if (appClient) {
          appClient.postMessage({ type: "notifications-navigate", url: target })
          return appClient.focus()
        }
        return self.clients.openWindow(target)
      }),
  )
})
