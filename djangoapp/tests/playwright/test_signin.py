"""Playwright E2E for the anonymous navbar Sign-in dropdown."""

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from playwright.sync_api import expect

from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class SignInDropdownTests(BasePlaywrightTestCase):
    """The navbar's single Sign-in button drops the provider links down.

    Shared ``login_providers`` drives the menu (see SharedPropsMiddleware);
    these tests pin the interactive half the backend tests can't: opening
    the button reveals the configured provider as a link, and clicking
    anywhere outside folds the menu away (the link itself is NOT followed —
    it would leave for Google's OAuth handshake).

    - test_signin_dropdown_lists_provider, opening shows Google with its login URL
    - test_signin_dropdown_closes_on_outside_click, a click elsewhere folds the menu
    """

    def setUp(self) -> None:
        super().setUp()
        app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="client-abc",
            secret="secret",
        )
        app.sites.add(Site.objects.get(pk=settings.SITE_ID))

    def test_signin_dropdown_lists_provider(self) -> None:
        """Opening the dropdown shows the configured provider as a link."""
        with self.anon_page() as page:
            page.goto(f"{self.live_server_url}/")
            page.locator(".layout-signin summary").click()
            link = page.locator(".layout-signin-link")
            expect(link).to_be_visible()
            expect(link).to_have_attribute("href", "/accounts/google/login/")
            expect(link).to_have_text("Google")

    def test_signin_dropdown_closes_on_outside_click(self) -> None:
        """Clicking outside the open dropdown folds it away."""
        with self.anon_page() as page:
            page.goto(f"{self.live_server_url}/")
            page.locator(".layout-signin summary").click()
            page.locator(".layout-signin-menu").wait_for(state="visible")
            # Home's signed-out notice sits well clear of the navbar dropdown.
            page.get_by_text("You are not signed in.").click()
            page.locator(".layout-signin-menu").wait_for(state="hidden")
