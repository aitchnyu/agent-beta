from typing import TYPE_CHECKING

from django.test import tag

from djangoapp.models.base import User

from .test_playwright import BasePlaywrightTestCase

if TYPE_CHECKING:
    from playwright.sync_api import Page


@tag("playwright")
class UserEditE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the superuser user-edit page.

    Tests verify the edit form loads for a superuser, a field change is
    saved via the POST endpoint, the page redirects to the profile, and
    the DB reflects the edit (which also records a UserHistory entry).

    - test_edit_page_saves_first_name: change first name, submit, redirect, DB updated
    - test_edit_page_updates_description: type into the rich-text editor, submit, DB updated
    - test_edit_page_requires_superuser: anonymous viewer gets 404 on the edit form
    """

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Old",
            last_name="Name",
            email="old@example.com",
        )

    def _login_superuser(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.superuser.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def test_edit_page_saves_first_name(self) -> None:
        """Change first name on the edit form; submit redirects and persists."""
        page = self._login_superuser()
        page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
        page.wait_for_selector(".user-edit-first-name")

        first_name = page.locator(".user-edit-first-name")
        first_name.fill("NewFirst")

        page.locator(".user-edit-save").click()
        page.wait_for_url(f"**/users/id/{self.target.public_id}")

        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, "NewFirst")

    def test_edit_page_updates_description(self) -> None:
        """Type into the rich-text editor; submit persists the description."""
        page = self._login_superuser()
        page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
        page.wait_for_selector(".ql-editor")

        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        quill_editor.type("Updated about text")

        page.locator(".user-edit-save").click()
        page.wait_for_url(f"**/users/id/{self.target.public_id}")

        self.target.refresh_from_db()
        self.assertIn("Updated about text", self.target.description)

    def test_edit_page_requires_superuser(self) -> None:
        """Anonymous viewer of the edit form gets a 404."""
        page = self.context.new_page()
        response = page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
        assert response is not None
        self.assertEqual(response.status, 404)


@tag("playwright")
class UserHistoryE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the superuser user-history page.

    Tests verify the history timeline renders after an edit, showing the
    "Edited" badge and the per-field diff. (User "created" history is not
    recorded yet, so the timeline is seeded by an explicit edit.)

    - test_history_page_shows_edit_diff: after an edit the timeline shows the first-name diff
    - test_history_page_requires_superuser: anonymous viewer gets 404
    """

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Before",
            last_name="Name",
            email="before@example.com",
        )

    def _login_superuser(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.superuser.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def test_history_page_shows_edit_diff(self) -> None:
        """After an edit, the history timeline shows the first-name diff."""
        self.target.update(
            first_name="After",
            last_name=self.target.last_name,
            email=self.target.email,
            description=self.target.description,
            has_public_profile=self.target.has_public_profile,
            is_active=self.target.is_active,
            is_staff=self.target.is_staff,
            is_superuser=self.target.is_superuser,
            user=self.superuser,
        )

        page = self._login_superuser()
        page.goto(f"{self.live_server_url}/users/history/{self.target.public_id}")
        page.wait_for_selector(".user-history-entry")

        self.assertTrue(page.locator("text=Edited").count() >= 1)
        self.assertTrue(page.locator(".user-history-old", has_text="Before").count() >= 1)
        self.assertTrue(page.locator(".user-history-new", has_text="After").count() >= 1)

    def test_history_page_requires_superuser(self) -> None:
        """Anonymous viewer of the history page gets a 404."""
        page = self.context.new_page()
        response = page.goto(f"{self.live_server_url}/users/history/{self.target.public_id}")
        assert response is not None
        self.assertEqual(response.status, 404)
