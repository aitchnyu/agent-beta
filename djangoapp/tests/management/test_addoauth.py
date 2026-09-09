from io import StringIO

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command

from djangoapp.tests._base import BaseTestCase


class AddOAuthCommandTests(BaseTestCase):
    """``addoauth`` stores any enabled provider's SocialApp in the database.

    Verifies the provider-agnostic upsert: credentials + the fixed
    scope/auth params land on one ``SocialApp`` row linked to SITE_ID,
    re-running updates in place, and provider ids not enabled in
    INSTALLED_APPS are rejected with the enabled ids named.

    - test_creates_socialapp_with_google_defaults, addoauth google writes creds + defaults + link
    - test_rerun_updates_in_place, second run with new creds updates the single row, no duplicate
    - test_unknown_provider_rejected, not-enabled provider id errors naming the enabled ids
    - test_creates_site_if_missing, missing SITE_ID site row is created so a fresh DB works
    """

    def test_creates_socialapp_with_google_defaults(self) -> None:
        """First run writes provider/client_id/secret/name/settings + site link."""
        call_command("addoauth", "google", "client-abc", "GOCSPX-s", stdout=StringIO())
        app = SocialApp.objects.get(provider="google")
        self.assertEqual(app.client_id, "client-abc")
        self.assertEqual(app.secret, "GOCSPX-s")
        self.assertEqual(app.key, "")
        # Display name = the provider class's own ("Google").
        self.assertEqual(app.name, "Google")
        self.assertEqual(
            app.settings, {"scope": ["profile", "email"], "auth_params": {"access_type": "online"}}
        )
        self.assertEqual(list(app.sites.values_list("id", flat=True)), [settings.SITE_ID])

    def test_rerun_updates_in_place(self) -> None:
        """Second run with new creds updates the single row, no duplicate."""
        call_command("addoauth", "google", "old-client", "old-secret", stdout=StringIO())
        call_command(
            "addoauth",
            "google",
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

    def test_unknown_provider_rejected(self) -> None:
        """A provider not enabled in INSTALLED_APPS raises, naming the enabled ids."""
        with self.assertRaises(CommandError) as ctx:
            call_command("addoauth", "github", "c", "s", stdout=StringIO())
        self.assertIn("github", str(ctx.exception))
        # The error names the enabled ids so typos and missing INSTALLED_APPS
        # entries are distinguishable at a glance.
        self.assertIn("google", str(ctx.exception))
        self.assertFalse(SocialApp.objects.filter(provider="github").exists())

    def test_creates_site_if_missing(self) -> None:
        """Missing SITE_ID site row is created so a fresh DB works."""
        Site.objects.filter(pk=settings.SITE_ID).delete()
        call_command("addoauth", "google", "c", "s", stdout=StringIO())
        self.assertTrue(Site.objects.filter(pk=settings.SITE_ID).exists())
