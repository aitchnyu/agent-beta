from io import StringIO

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase


class AddGoogleOAuthCommandTests(TestCase):
    """``addgoogleoauth`` stores the Google SocialApp in the database.

    Verifies the command replaces the old ``SOCIALACCOUNT_PROVIDERS`` block by
    writing one ``SocialApp(provider="google")`` linked to SITE_ID, with the
    scope/auth params that allauth's OAuth2Provider reads, and that re-running
    updates in place instead of duplicating.

    - test_creates_socialapp_with_credentials_and_settings, first run writes creds/settings + site
    - test_settings_use_lowercase_keys, settings keys are scope/auth_params (lowercase)
    - test_rerun_updates_in_place, second run with new creds updates the single row, no duplicate
    - test_creates_site_if_missing, missing SITE_ID site row is created so a fresh DB works
    """

    def test_creates_socialapp_with_credentials_and_settings(self) -> None:
        """First run writes provider/client_id/secret/key/settings + site link."""
        call_command(
            "addgoogleoauth",
            "client-abc.apps.googleusercontent.com",
            "GOCSPX-secret",
            stdout=StringIO(),
        )
        app = SocialApp.objects.get(provider="google")
        self.assertEqual(app.client_id, "client-abc.apps.googleusercontent.com")
        self.assertEqual(app.secret, "GOCSPX-secret")
        self.assertEqual(app.key, "")
        self.assertEqual(app.name, "Google")
        self.assertEqual(
            app.settings, {"scope": ["profile", "email"], "auth_params": {"access_type": "online"}}
        )
        self.assertEqual(list(app.sites.values_list("id", flat=True)), [settings.SITE_ID])

    def test_settings_use_lowercase_keys(self) -> None:
        """Settings keys are scope/auth_params (the keys allauth reads)."""
        call_command("addgoogleoauth", "c", "s", stdout=StringIO())
        app = SocialApp.objects.get(provider="google")
        # OAuth2Provider.get_scope/get_auth_params read lowercase keys; the
        # uppercase SOCIALACCOUNT_PROVIDERS keys must not leak through.
        self.assertIn("scope", app.settings)
        self.assertIn("auth_params", app.settings)
        self.assertNotIn("SCOPE", app.settings)
        self.assertNotIn("AUTH_PARAMS", app.settings)

    def test_rerun_updates_in_place(self) -> None:
        """Second run with new creds updates the single row, no duplicate."""
        call_command("addgoogleoauth", "old-client", "old-secret", stdout=StringIO())
        call_command(
            "addgoogleoauth",
            "new-client",
            "new-secret",
            "--key",
            "k1",
            stdout=StringIO(),
        )
        self.assertEqual(SocialApp.objects.filter(provider="google").count(), 1)
        app = SocialApp.objects.get(provider="google")
        self.assertEqual(app.client_id, "new-client")
        self.assertEqual(app.secret, "new-secret")
        self.assertEqual(app.key, "k1")

    def test_creates_site_if_missing(self) -> None:
        """Missing SITE_ID site row is created so a fresh DB works."""
        Site.objects.filter(pk=settings.SITE_ID).delete()
        call_command("addgoogleoauth", "c", "s", stdout=StringIO())
        self.assertTrue(Site.objects.filter(pk=settings.SITE_ID).exists())
