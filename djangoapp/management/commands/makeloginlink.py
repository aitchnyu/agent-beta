from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import LoginKey, User


class Command(BaseCommand):
    """Print a one-time login URL for an existing user (looked up by email).

    The test VM cannot complete Google OAuth (its ``.local`` hostname isn't
    registrable), so this is how the operator signs in there: it issues a
    ``/login-for-test/<key>/`` URL that logs the user in exactly once
    before it expires. Only the SHA-256 of the key is stored server-side, so
    the printed line is the only place the raw key exists.
    """

    help = "Print a one-time login URL for an existing user (looked up by email)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "email",
            type=str,
            help="Email of the existing user (matched case-insensitively).",
        )
        parser.add_argument(
            "--minutes",
            type=int,
            default=15,
            help="Link lifetime in minutes (default 15).",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default=None,
            help="Origin to prefix the path with (default: derived from DEBUG/ALLOWED_HOSTS).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        email: str = options["email"]
        minutes: int = options["minutes"]
        base_url: str | None = options["base_url"]
        # 0/negative would issue an already-dead link and print it as success.
        if minutes <= 0:
            msg = f"--minutes must be > 0 (got {minutes})."
            raise CommandError(msg)
        # email__iexact so "User@x.com" matches "user@x.com". The User model does
        # not enforce a unique email, so guard against 0 / >1 matches explicitly.
        matches = User.objects.filter(email__iexact=email)
        if not matches.exists():
            msg = f"No user found with email '{email}'."
            raise CommandError(msg)
        if matches.count() > 1:
            msg = f"Multiple users share email '{email}'; dedupe accounts first."
            raise CommandError(msg)
        user = matches.get()
        key, _expires_at = LoginKey.issue(user, minutes=minutes)
        # Outside DEBUG the app is always behind the HTTPS proxy at its first
        # allowed host; in dev the runserver port is the only reachable origin.
        if base_url is None:
            base_url = (
                "http://127.0.0.1:8000"
                if settings.DEBUG
                else f"https://{settings.ALLOWED_HOSTS[0]}"
            )
        url = f"{base_url}/login-for-test/{key}/"
        self.stdout.write(
            self.style.SUCCESS(
                f"One-time login for '{user.username}' (valid {minutes} min, single use):\n{url}"
            )
        )
