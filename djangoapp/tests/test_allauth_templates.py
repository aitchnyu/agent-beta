from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.staticfiles import finders

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase


class AllauthPageTests(BaseTestCase):
    """The server-rendered allauth pages: layout override, provider list, CSP.

    The project overrides ``allauth/layouts/base.html`` (via TEMPLATES DIRS —
    DIRS beat app dirs, which is what makes the override win over allauth's
    own copy despite INSTALLED_APPS order) and ``allauth/elements/provider.
    html``. These tests pin that wiring and that the provider list is
    DB-driven (only the configured SocialApp appears).

    - test_login_page_renders_layout_override, /accounts/login/ carries override marker + CSS link
    - test_login_page_lists_configured_providers, the seeded provider renders by name + login URL
    - test_logout_page_renders_confirm, GET /accounts/logout/ renders the confirm in the override
    - test_csp_form_action_lists_enabled_providers, CSP carries enabled providers' domains only
    """

    def setUp(self) -> None:
        super().setUp()
        site = Site.objects.get(pk=settings.SITE_ID)
        app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="client-abc",
            secret="secret",
        )
        app.sites.add(site)

    def test_login_page_renders_layout_override(self) -> None:
        """``/accounts/login/`` carries the override marker + stylesheet link."""
        resp = self.client.get("/accounts/login/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        # The marker exists only in djangoapp/templates/allauth/layouts/base.html
        # — if this fails, the DIRS override is not winning over allauth's own.
        self.assertIn("data-allauth-layout", body)
        self.assertIn("/static/allauth/allauth.css", body)
        # The stylesheet itself must actually ship: regression test
        self.assertTrue(finders.find("allauth/allauth.css"))

    def test_login_page_lists_configured_providers(self) -> None:
        """The seeded provider renders by name with its login URL."""
        resp = self.client.get("/accounts/login/")
        body = resp.content.decode()
        # Name and URL come from the SocialApp row, not template hardcoding
        # (provider_login_url appends ?process=login).
        self.assertIn("Google", body)
        self.assertIn('href="/accounts/google/login/', body)
        # A provider without a SocialApp row never appears.
        self.assertNotIn("GitHub", body)

    def test_logout_page_renders_confirm(self) -> None:
        """GET /accounts/logout/ renders the confirm page inside the override."""
        user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(user)
        resp = self.client.get("/accounts/logout/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data-allauth-layout", resp.content.decode())

    def test_csp_form_action_lists_enabled_providers(self) -> None:
        """Response CSP carries enabled providers' authorize domains only."""
        resp = self.client.get("/accounts/login/")
        csp = resp.headers["Content-Security-Policy"]
        # form-action carries the enabled provider's authorize domain (google,
        # hardcoded in settings.py — see docs/social-providers.md) and no others.
        self.assertIn("https://accounts.google.com", csp)
        self.assertNotIn("github.com", csp)
        self.assertNotIn("appleid.apple.com", csp)
