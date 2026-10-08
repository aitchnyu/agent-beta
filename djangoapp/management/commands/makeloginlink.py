from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import LOGIN_LINK_MIN_MINUTES, LoginKey, User


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
            default=LOGIN_LINK_MIN_MINUTES,
            help="Link lifetime in minutes "
            f"(default {LOGIN_LINK_MIN_MINUTES}; minimum {LOGIN_LINK_MIN_MINUTES}).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        email: str = options["email"]
        minutes: int = options["minutes"]
        # 0/negative/sub-hour values refuse instead of printing a link that
        # dies before the operator uses it.
        if minutes < LOGIN_LINK_MIN_MINUTES:
            msg = f"--minutes must be >= {LOGIN_LINK_MIN_MINUTES} (got {minutes})."
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
        # The FIRST configured origin (settings.BASE_URLS) is the base —
        # never an assumed scheme/host/port.
        url = f"{settings.BASE_URLS[0]}/login-for-test/{key}/"
        self.stdout.write(
            self.style.SUCCESS(
                f"One-time login for '{user.username}' (valid {minutes} min, single use):\n{url}"
            )
        )
