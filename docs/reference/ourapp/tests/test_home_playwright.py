"""E2e for the home page auth state + logout flow."""

from __future__ import annotations

from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class HomeAuthE2e(BasePlaywrightTestCase):
    """The landing page's auth state and logout flow, end-to-end.

    Drives a real browser through the signed-out / signed-in states and the full
    logout round-trip on the landing page (component ``ours/Home``).

    - test_anon_home_shows_signed_out, anon / shows signed-out + Google login link, no logout button
    - test_authenticated_home_shows_user, authed / shows display name + logout button, no login link
    - test_logout_flow_returns_to_signed_out, Sign out logs out and lands on signed-out home
    """

    def test_anon_home_shows_signed_out(self) -> None:
        """Anon / shows signed-out status and a Google login link, no logout button."""
        with self.anon_page() as page:
            page.goto(f"{self.live_server_url}/")
            page.wait_for_selector(".home-status-signed-out")
            self.assertEqual(page.locator(".home-login-link").count(), 1)
            self.assertEqual(page.locator(".home-logout-btn").count(), 0)

    def test_authenticated_home_shows_user(self) -> None:
        """Authed / shows the user's display name and a logout button, no login link."""
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".home-status-signed-in")
        self.assertEqual(page.text_content(".home-display-name"), self.user.display_name)
        self.assertEqual(page.locator(".home-logout-btn").count(), 1)
        self.assertEqual(page.locator(".home-login-link").count(), 0)

    def test_logout_flow_returns_to_signed_out(self) -> None:
        """Clicking Sign out logs out and lands back on the signed-out home."""
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".home-logout-btn")
        page.click(".home-logout-btn")
        # allauth logout POST redirects to LOGOUT_REDIRECT_URL ("/")
        page.wait_for_url(f"{self.live_server_url}/")
        page.wait_for_selector(".home-status-signed-out")
