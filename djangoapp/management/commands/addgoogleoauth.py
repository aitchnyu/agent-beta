from __future__ import annotations

from typing import Any

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

# Reproduces the original SOCIALACCOUNT_PROVIDERS["google"] SCOPE/AUTH_PARAMS.
# Keys are lowercase because allauth's OAuth2Provider reads
# app.settings.get("scope") / app.settings.get("auth_params") (see
# allauth/socialaccount/providers/oauth2/provider.py).
GOOGLE_SETTINGS: dict[str, Any] = {
    "scope": ["profile", "email"],
    "auth_params": {"access_type": "online"},
}


class Command(BaseCommand):
    """Create or update the Google OAuth SocialApp.

    Stores the Google client credentials and the fixed scope/auth params in the
    database (a ``SocialApp`` row linked to the current Site), replacing the old
    ``SOCIALACCOUNT_PROVIDERS`` settings block. Idempotent: re-running updates the
    existing app in place instead of creating a duplicate.
    """

    help = "Create or update the Google OAuth SocialApp (client_id/secret in the DB)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "client_id",
            type=str,
            help="Google OAuth client id (xxxxx.apps.googleusercontent.com).",
        )
        parser.add_argument(
            "secret",
            type=str,
            help="Google OAuth client secret (GOCSPX-...).",
        )
        parser.add_argument(
            "--key",
            type=str,
            default="",
            help="OAuth consumer key (blank for Google OAuth2).",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="Google",
            help="Display name for the SocialApp row.",
        )
        parser.add_argument(
            "--site",
            type=int,
            default=settings.SITE_ID,
            help="Site id to link the app to (defaults to SITE_ID).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        client_id: str = options["client_id"]
        secret: str = options["secret"]
        key: str = options["key"]
        name: str = options["name"]
        site_id: int = options["site"]

        site = self._get_site(site_id)
        with transaction.atomic():
            app, created = SocialApp.objects.get_or_create(
                provider="google",
                defaults={
                    "name": name,
                    "client_id": client_id,
                    "secret": secret,
                    "key": key,
                    "settings": GOOGLE_SETTINGS,
                },
            )
            if not created:
                # Update an existing app so re-running with rotated creds just works.
                app.name = name
                app.client_id = client_id
                app.secret = secret
                app.key = key
                app.settings = GOOGLE_SETTINGS
                app.save()
            app.sites.add(site)

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} Google SocialApp (provider={app.provider}) "
                f"linked to site {site.id} ({site.domain}). "
                f"scope={GOOGLE_SETTINGS['scope']}, "
                f"auth_params={GOOGLE_SETTINGS['auth_params']}."
            )
        )

    def _get_site(self, site_id: int) -> Site:
        """Return the Site to link the app to.

        The default site exists after `migrate`; if it is missing we create a
        bare row so the command is usable on a fresh DB without manual setup.
        """
        site, _ = Site.objects.get_or_create(
            pk=site_id,
            defaults={"domain": "example.com", "name": "example.com"},
        )
        return site
