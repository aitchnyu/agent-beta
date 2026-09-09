from __future__ import annotations

from typing import Any

from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers import registry
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

# Fixed per-provider settings stored on the SocialApp row, overriding the
# provider class defaults. Keys are lowercase because allauth's OAuth2Provider
# reads app.settings.get("scope") / app.settings.get("auth_params") (see
# allauth/socialaccount/providers/oauth2/provider.py). Providers without an
# entry get {} — allauth's built-in provider defaults then apply. New
# provider = new entry.
PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "google": {
        "scope": ["profile", "email"],
        "auth_params": {"access_type": "online"},
    },
}


class Command(BaseCommand):
    """Create or update a social provider's SocialApp (credentials in the DB).

    Provider-agnostic upsert of the allauth ``SocialApp`` row: stores the
    provider's client credentials (plus its fixed scope/auth params when
    ``PROVIDER_DEFAULTS`` has an entry) linked to the current Site. The
    provider must be enabled in ``INSTALLED_APPS``. Idempotent: re-running
    updates the existing row instead of creating a duplicate.
    """

    help = "Create or update a social provider's SocialApp (client_id/secret in the DB)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "provider",
            type=str,
            help="Provider id (google, …) — must be enabled in INSTALLED_APPS.",
        )
        parser.add_argument(
            "client_id",
            type=str,
            help="OAuth client id.",
        )
        parser.add_argument(
            "secret",
            type=str,
            help="OAuth client secret.",
        )
        parser.add_argument(
            "--key",
            type=str,
            default="",
            help="OAuth consumer key (blank for OAuth2 providers).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        # Allauth's registry is populated from INSTALLED_APPS during app
        # loading; load() is idempotent. A provider id absent from it is
        # either a typo or a provider whose app is not installed — name the
        # enabled ids so both fail loudly.
        registry.load()
        provider_cls = registry.get_class(options["provider"])
        if provider_cls is None:
            enabled = ", ".join(sorted(registry.provider_map)) or "none"
            msg = (
                f"Unknown or not-enabled provider {options['provider']!r}. Providers "
                f"enabled in INSTALLED_APPS: {enabled}."
            )
            raise CommandError(msg)
        provider = options["provider"]
        # Display name = the provider's own ("Google"); single-site setup —
        # the app links to SITE_ID.
        name = provider_cls.name
        site_id = settings.SITE_ID

        # The default site exists after `migrate`; if it is missing we create a
        # bare row so the command works on a fresh DB without manual setup.
        site, _ = Site.objects.get_or_create(
            pk=site_id,
            defaults={"domain": "example.com", "name": "example.com"},
        )
        app_settings = PROVIDER_DEFAULTS.get(provider, {})
        with transaction.atomic():
            # Upsert on provider — re-running with rotated creds updates in
            # place instead of duplicating. sites.add is idempotent.
            app, created = SocialApp.objects.update_or_create(
                provider=provider,
                defaults={
                    "name": name,
                    "client_id": options["client_id"],
                    "secret": options["secret"],
                    "key": options["key"],
                    "settings": app_settings,
                },
            )
            app.sites.add(site)

        action = "Created" if created else "Updated"
        settings_desc = ", ".join(f"{k}={v}" for k, v in app_settings.items())
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {name} SocialApp (provider={app.provider}) "
                f"linked to site {site.id} ({site.domain}). "
                f"{settings_desc or 'provider-default settings'}."
            )
        )
