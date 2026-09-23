"""E2e for the notifications user-menu badge + list page flows (no real push).

Real Web Push can't be exercised end-to-end (it needs the browser's real
push service + granted permission); these tests cover everything around
it: the shared-props badge, the list page's checkbox-selection mark-read/
delete flows, the kind filter, and the badge updating after actions via
the partial reload.
"""

from __future__ import annotations

import re

from django.utils import timezone
from playwright.sync_api import expect

from djangoapp.models import Notification
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class NotificationsE2e(BasePlaywrightTestCase):
    """User-menu badge + /notifications page flows, end-to-end.

    - test_menu_badge_shows_unread_count, the navbar button carries the shared-props count
    - test_menu_dropdown_links, the dropdown exposes Profile / Notifications / Logout
    - test_select_and_mark_read_updates_badge, checkbox select + toolbar Mark read lowers the badge
    - test_select_and_delete_removes_rows, checkbox select + toolbar Delete (confirmed) removes rows
    - test_select_mode_unread_picks_unread, the toolbar select picks exactly the unread rows
    - test_load_more_appends_rows, Load more pages 50-at-a-time until exhausted
    - test_kind_filter_narrows_list, a kind click filters the list via ?kind=
    - test_clear_all_wipes_list, Clear all (confirmed) empties the page and the badge
    - test_send_test_notification, the test button records a real row (toast + list + badge)
    """

    def _seed(self, count: int) -> None:
        for i in range(count):
            Notification.record(
                recipient=self.user, kind="task.done", body=f"notification {i}", url=""
            )

    def _seed_rows(self, count: int) -> None:
        """Bulk rows for paging tests — plain creates, no push scheduling."""
        Notification.objects.bulk_create(
            Notification(recipient=self.user, kind="task.done", body=f"row {i}")
            for i in range(count)
        )

    def _open_notifications_page(self) -> None:
        """Navigate via the user menu's dropdown link (stable class hook)."""
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-user-menu")
        page.click(".layout-user-menu summary")
        page.click(".user-menu-notifications")

    def test_menu_badge_shows_unread_count(self) -> None:
        """The navbar button's badge shows the seeded unread count."""
        self._seed(2)
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-user-menu")
        expect(page.locator(".notifications-badge")).to_have_text("2")

    def test_menu_dropdown_links(self) -> None:
        """The dropdown opens and lists Profile / Notifications / Logout."""
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.click(".layout-user-menu summary")
        page.wait_for_selector(".layout-user-menu .layout-menu-panel")
        expect(page.locator(".layout-user-menu .layout-menu-link")).to_have_count(3)
        expect(page.locator(".user-menu-profile")).to_have_attribute(
            "href", re.compile(r"/users/id/")
        )

    def test_select_and_mark_read_updates_badge(self) -> None:
        """Select one row → toolbar Mark read lowers the badge by one."""
        self._seed(2)
        page = self.page
        self._open_notifications_page()
        page.wait_for_selector(".notification-item")
        # Badge (persistent Layout) still reads 2 while the page shows rows.
        expect(page.locator(".notifications-badge")).to_have_text("2")
        page.locator(".notification-select").first.click()
        page.wait_for_selector(".notifications-mark-selected")
        page.click(".notifications-mark-selected")
        # The page updates the navbar badge via a partial reload of the
        # shared prop; expect() retries until it settles to 1.
        expect(page.locator(".notifications-badge")).to_have_text("1")
        expect(page.locator(".notification-unread")).to_have_count(1)

    def test_select_and_delete_removes_rows(self) -> None:
        """Select both rows → toolbar Delete (confirmed) empties the list."""
        self._seed(2)
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notification-item")
        page.click(".notifications-select-all")
        page.click(".notifications-delete-selected")
        page.click(".swal2-confirm")
        page.wait_for_selector(".notification-item", state="detached")
        expect(page.locator(".notifications-badge")).to_have_text("0")
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())

    def test_select_mode_unread_picks_unread(self) -> None:
        """The toolbar select's Unread option selects exactly the unread rows."""
        self._seed(3)
        # Mark the newest row read directly in the ORM — the state the
        # row-link's API call would produce (that path itself has no
        # E2E coverage yet).
        newest = Notification.objects.filter(recipient=self.user).order_by("-created_at").first()
        assert newest is not None
        Notification.objects.filter(pk=newest.pk).update(read_at=timezone.now())
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notification-item")
        page.select_option(".notifications-select-mode", "unread")
        expect(page.locator(".notifications-selected-count")).to_have_text("2 selected")
        page.select_option(".notifications-select-mode", "read")
        expect(page.locator(".notifications-selected-count")).to_have_text("1 selected")

    def test_load_more_appends_rows(self) -> None:
        """55 rows render 50 first; Load more appends the tail and stops."""
        self._seed_rows(55)
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notification-item")
        expect(page.locator(".notification-item")).to_have_count(50)
        page.click(".notifications-load-more")
        expect(page.locator(".notification-item")).to_have_count(55)
        # The tail chunk had no more behind it — the button is gone.
        page.wait_for_selector(".notifications-load-more", state="detached")

    def test_kind_filter_narrows_list(self) -> None:
        """Clicking a kind navigates to ?kind= and filters the rows."""
        Notification.record(recipient=self.user, kind="invoice.paid", body="money")
        Notification.record(recipient=self.user, kind="task.done", body="work")
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notification-item")
        page.click('.notification-item[data-kind="invoice.paid"] .notification-kind')
        # The app's URL is slash-terminated (/notifications/), so the glob
        # matches the slashed form of the filtered URL.
        page.wait_for_url("**/notifications/?kind=invoice.paid")
        expect(page.locator(".notification-item")).to_have_count(1)
        expect(page.locator(".notification-kind")).to_have_text("invoice.paid")
        # The chip clears back to the full list.
        page.click(".notifications-filter-clear")
        page.wait_for_url("**/notifications/")
        expect(page.locator(".notification-item")).to_have_count(2)

    def test_clear_all_wipes_list(self) -> None:
        """Clear all (sweetalert confirm) empties the list and the badge."""
        self._seed(2)
        page = self.page
        self._open_notifications_page()
        page.wait_for_selector(".notifications-clear")
        page.click(".notifications-clear")
        page.click(".swal2-confirm")
        page.wait_for_selector(".notification-item", state="detached")
        # The badge never disappears — it says 0.
        expect(page.locator(".notifications-badge")).to_have_text("0")

    def test_send_test_notification(self) -> None:
        """The test button records a real row: toast, list row, badge bump."""
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        page.wait_for_selector(".notifications-test")
        page.click(".notifications-test")
        # The row IS the result: it lands in the list (the page's partial
        # reload swaps props in) and bumps the navbar badge (shared prop in
        # the same reload).
        page.wait_for_selector(".swal2-container")
        page.wait_for_selector(".notification-item")
        expect(page.locator(".notifications-badge")).to_have_text("1")
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
