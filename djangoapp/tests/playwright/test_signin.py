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
    the button reveals the configured provider as a link (the link itself
    is NOT followed — it would leave for Google's OAuth handshake). The
    dropdown's closing behaviour lives with the navbar e2e
    (test_navbar.py — NavbarE2e).

    - test_signin_dropdown_lists_provider, opening shows Google with its login URL
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
