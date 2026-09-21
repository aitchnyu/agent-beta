"""E2e for the notifications bell + list page flows (no real push delivery).

Real Web Push can't be exercised end-to-end (it needs the browser's real
push service + granted permission); these tests cover everything around
it: the shared-props badge, the list page's mark-read/delete/clear flows,
and the badge updating after actions via the partial reload.
"""

from __future__ import annotations

from django.test import override_settings

from djangoapp.models import Notification
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


@override_settings(VAPID_PRIVATE_KEY="e2e-test-key")
class NotificationsE2e(BasePlaywrightTestCase):
    """Bell badge + /notifications page flows, end-to-end.

    - test_bell_badge_shows_unread_count, the navbar badge carries the shared-props count
    - test_mark_read_updates_badge, Mark read on the page drops the badge by one
    - test_delete_removes_row, Delete removes the row (and it stays gone on reload)
    - test_clear_all_wipes_list, Clear all (confirmed) empties the page and the badge
    - test_send_test_notification, the test button pushes only — toast, no row, no badge
    """

    # Class-level VAPID: the Send-test button renders only when the server
    # can push (the dev .env carries the sentinel).

    def _seed(self, count: int) -> None:
        for i in range(count):
            Notification.record(
                recipient=self.user, kind="task.done", body=f"notification {i}", url=""
            )

    def test_bell_badge_shows_unread_count(self) -> None:
        """The navbar badge shows the seeded unread count."""
        self._seed(2)
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".notifications-bell")
        self.assertEqual(page.text_content(".notifications-badge"), "2")

    def test_mark_read_updates_badge(self) -> None:
        """Bell → page → Mark read lowers the badge (partial reload)."""
        self._seed(2)
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".notifications-badge")
        page.click(".notifications-bell")
        page.wait_for_selector(".notification-mark-read")
        # Badge (persistent Layout) still reads 2 while the page shows rows.
        self.assertEqual(page.text_content(".notifications-badge"), "2")
        page.click(".notification-mark-read >> nth=0")
        # The page updates the Layout badge via a partial reload of the
        # shared prop; wait for it to settle to 1.
        page.wait_for_function(
            "() => document.querySelector('.notifications-badge')?.textContent === '1'"
        )
        self.assertEqual(page.locator(".notification-unread").count(), 1)

    def test_delete_removes_row(self) -> None:
        """Delete removes the row and stays gone after a reload."""
        self._seed(1)
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notification-delete")
        page.click(".notification-delete")
        page.wait_for_selector(".notification-delete", state="detached")
        # Re-visit instead of page.reload(): with a service worker
        # registered, Firefox + playwright's reload() has been observed to
        # hang past the 2s budget; a fresh goto exercises the same
        # server-rendered truth.
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notification-item", state="detached")

    def test_clear_all_wipes_list(self) -> None:
        """Clear all (sweetalert confirm) empties the list and the badge."""
        self._seed(2)
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".notifications-badge")
        page.click(".notifications-bell")
        page.wait_for_selector(".notifications-clear")
        page.click(".notifications-clear")
        page.click(".swal2-confirm")
        page.wait_for_selector(".notification-item", state="detached")
        # Badge gone (count 0 renders without the span).
        page.wait_for_selector(".notifications-badge", state="detached")

    def test_send_test_notification(self) -> None:
        """The test button toasts and leaves NO row/badge (push-only probe)."""
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notifications-test")
        page.click(".notifications-test")
        # Zero subscriptions in this browser → the warning toast is the
        # contract; a stored row would defeat the push-only point.
        page.wait_for_selector(".swal2-container")
        page.wait_for_selector(".notification-item", state="detached")
        page.wait_for_selector(".notifications-badge", state="detached")
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 0)
