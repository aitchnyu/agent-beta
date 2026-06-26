from djangoapp.models.app import CategoryModel, FirstStuff
from djangoapp.models.base import RowUpdate, RowUpdateUserNotification, User
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase


class NotificationE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the notifications page."""

    def setUp(self) -> None:
        super().setUp()
        self.other_user = User.objects.create_user(username="otheruser", password="otherpass")
        self.row = FirstStuff.objects.create(char_field="test row")

    def _create_notification(
        self,
        user: User,
        action: str = "created_row",
    ) -> RowUpdateUserNotification:
        row_update = RowUpdate.objects.create(
            action=action,
            created_by=self.other_user,
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            row_public_id=self.row.public_id,
            _values=[],
        )
        response = self.row.row_update_response(self.other_user, row_update)
        return RowUpdateUserNotification.objects.create(
            modelname=self.row.modelname(),
            row_pk=self.row.pk,
            row_public_id=self.row.public_id,
            user=user,
            content=response.model_dump(mode="json"),
        )

    def test_notification_appears_on_notifications_page(self) -> None:
        """Test notification appears with correct content and link."""
        self._create_notification(self.user)
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/notifications/page")
        page.wait_for_selector(".notifications-list")
        items = page.locator(".notification-item")
        self.assertEqual(items.count(), 1)

        link = items.first.locator(".notification-link")
        self.assertEqual(
            link.get_attribute("href"),
            f"/tables/firststuff/id/{self.row.pk}",
        )
        text = items.first.text_content()
        assert text is not None
        self.assertIn("firststuff", text)
        self.assertIn("Created", text)

        link.click()
        page.wait_for_url("**/tables/firststuff/id/*")
        self.assertIn(f"/tables/firststuff/id/{self.row.pk}", page.url)

    def test_delete_selected_notifications(self) -> None:
        """Test deleting selected notifications."""
        self._create_notification(self.user)
        page = self.logged_in_page
        page.goto(
            f"{self.live_server_url}/tables/notifications/page", wait_until="domcontentloaded"
        )
        page.wait_for_selector(".notification-checkbox")
        page.locator(".notification-checkbox").first.click()
        page.locator(".delete-selected-btn").click()
        page.wait_for_selector(".swal2-popup")
        page.goto(
            f"{self.live_server_url}/tables/notifications/page", wait_until="domcontentloaded"
        )
        page.wait_for_selector(".notifications-layout")
        self.assertEqual(RowUpdateUserNotification.objects.filter(user=self.user).count(), 0)

    def test_select_all_notifications(self) -> None:
        """Test select all checkbox toggles all notifications."""
        self._create_notification(self.user)
        self._create_notification(self.user)
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/notifications/page")
        page.wait_for_selector(".notifications-list")

        checkboxes = page.locator(".notification-checkbox")
        self.assertEqual(checkboxes.count(), 2)

        page.locator(".select-all-label input[type='checkbox']").click()
        checked = page.locator(".notification-checkbox:checked")
        self.assertEqual(checked.count(), 2)

        page.locator(".select-all-label input[type='checkbox']").click()
        checked = page.locator(".notification-checkbox:checked")
        self.assertEqual(checked.count(), 0)

    def test_clear_all_notifications(self) -> None:
        """Test clearing all notifications and clearing filtered viewname only."""
        self._create_notification(self.user)

        row2 = CategoryModel.objects.create(name="cat row")
        ru2 = RowUpdate.objects.create(
            action="created_row",
            created_by=self.other_user,
            modelname="djangoapp.CategoryModel",
            row_pk=row2.pk,
            _values=[],
        )
        response2 = row2.row_update_response(self.other_user, ru2)
        RowUpdateUserNotification.objects.create(
            modelname=row2.modelname(),
            row_pk=row2.pk,
            user=self.user,
            content=response2.model_dump(mode="json"),
        )

        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/notifications/page")
        page.wait_for_selector(".clear-all-btn")

        page.locator(".clear-all-btn").click()
        page.wait_for_selector(".swal2-container")
        page.locator(".swal2-confirm").click()
        page.wait_for_selector(".no-notifications")
        self.assertEqual(RowUpdateUserNotification.objects.filter(user=self.user).count(), 0)

    def test_viewname_filter_on_notifications_page(self) -> None:
        """Test filtering notifications by viewname in the sidebar."""
        self._create_notification(self.user)
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/notifications/page")
        page.wait_for_selector(".notifications-list")
        firststuff_btn = page.locator(".filter-btn:has-text('firststuff')")
        self.assertTrue(firststuff_btn.count() > 0)
        firststuff_btn.click()
        page.wait_for_selector(".notifications-list")
        items = page.locator(".notification-item")
        self.assertEqual(items.count(), 1)
