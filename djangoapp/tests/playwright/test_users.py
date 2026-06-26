from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from django.test import override_settings

from djangoapp.models import User
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase

if TYPE_CHECKING:
    from playwright.sync_api import Page


class HomeAuthE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the Home auth state and logout flow.

    Drives a real browser through the signed-out / signed-in states and
    the full logout round-trip on the foundation Home page.

    - test_anon_home_shows_signed_out, anon / shows signed-out + Google login link, no logout button
    - test_authenticated_home_shows_user, authed / shows display name + logout button, no login link
    - test_logout_flow_returns_to_signed_out, Sign out logs out and lands on signed-out home
    """

    def test_anon_home_shows_signed_out(self) -> None:
        """Anon / shows signed-out status and a Google login link, no logout button."""
        with self.anon_page() as page:
            page.goto(f"{self.live_server_url}/")
            page.wait_for_selector(".home-status-signed-out")
            assert page.locator(".home-login-link").count() == 1
            assert page.locator(".home-logout-btn").count() == 0

    def test_authenticated_home_shows_user(self) -> None:
        """Authed / shows the user's display name and a logout button, no login link."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".home-status-signed-in")
        assert page.text_content(".home-display-name") == self.user.display_name
        assert page.locator(".home-logout-btn").count() == 1
        assert page.locator(".home-login-link").count() == 0

    def test_logout_flow_returns_to_signed_out(self) -> None:
        """Clicking Sign out logs out and lands back on the signed-out home."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".home-logout-btn")
        page.click(".home-logout-btn")
        # allauth logout POST redirects to LOGOUT_REDIRECT_URL ("/")
        page.wait_for_url(f"{self.live_server_url}/")
        page.wait_for_selector(".home-status-signed-out")


class LoginForTestGateE2eTestCase(BasePlaywrightTestCase):
    """The test login bypass must be disabled outside DEBUG.

    - test_login_for_test_forbidden_when_not_debug, with DEBUG off the login-for-test URL is 404
    """

    @override_settings(DEBUG=False)
    def test_login_for_test_forbidden_when_not_debug(self) -> None:
        """With DEBUG off the login-for-test URL is 404."""
        with self.anon_page() as page:
            response = page.request.get(
                f"{self.live_server_url}/login-for-test/{self.user.pk}",
            )
            assert response.status == HTTPStatus.NOT_FOUND


class UserEditE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the superuser user-edit page.

    Verifies the edit form loads for a superuser, a field change is saved
    via POST, the page redirects to the profile, and the DB reflects the
    edit (which also records a UserHistory entry).

    - test_edit_page_saves_first_name, change first name, submit, redirect, DB updated
    - test_edit_page_updates_description, type into the rich-text editor, submit, DB updated
    - test_edit_page_requires_superuser, anonymous viewer gets 404 on the edit form
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

        page.locator(".user-edit-first-name").fill("NewFirst")
        page.locator(".user-edit-save").click()
        page.wait_for_url(f"**/users/id/{self.target.public_id}")

        self.target.refresh_from_db()
        assert self.target.first_name == "NewFirst"

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
        assert "Updated about text" in self.target.description

    def test_edit_page_requires_superuser(self) -> None:
        """Anonymous viewer of the edit form gets a 404."""
        page = self.context.new_page()
        response = page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
        assert response is not None
        assert response.status == HTTPStatus.NOT_FOUND
        page.close()


class UserHistoryE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the superuser user-history page.

    Verifies the history timeline renders after an edit, showing the
    "Edited" badge and the per-field diff. (User "created" history is not
    recorded yet, so the timeline is seeded by an explicit edit.)

    - test_history_page_shows_edit_diff, after an edit the timeline shows the first-name diff
    - test_history_page_requires_superuser, anonymous viewer gets 404
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

        assert page.locator("text=Edited").count() >= 1
        assert page.locator(".user-history-old", has_text="Before").count() >= 1
        assert page.locator(".user-history-new", has_text="After").count() >= 1

    def test_history_page_requires_superuser(self) -> None:
        """Anonymous viewer of the history page gets a 404."""
        page = self.context.new_page()
        response = page.goto(f"{self.live_server_url}/users/history/{self.target.public_id}")
        assert response is not None
        assert response.status == HTTPStatus.NOT_FOUND
        page.close()
