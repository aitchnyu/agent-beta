from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import User


class Command(BaseCommand):
    """Promote an existing user (found by email) to superuser + staff.

    Social-login users can't be made superuser at creation time; this grants the
    ``/admin`` authorization flags afterwards via ``User.update`` (so the change
    is audited in ``UserHistory``). Sets ``is_staff=True`` as well, because
    Django admin refuses to render for non-staff users even when ``is_superuser``
    is set.
    """

    help = "Promote an existing user (looked up by email) to superuser and staff."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "email",
            type=str,
            help="Email of the existing user to promote (matched case-insensitively).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        email: str = options["email"]
        # email__iexact so "User@x.com" matches "user@x.com". The User model does
        # not enforce a unique email, so guard against 0 / >1 matches explicitly.
        matches = User.objects.filter(email__iexact=email)
        if not matches.exists():
            msg = f"No user found with email '{email}'."
            raise CommandError(msg)
        if matches.count() > 1:
            msg = f"Multiple users share email '{email}'; dedupe accounts before promoting."
            raise CommandError(msg)
        user = matches.get()
        if user.is_superuser and user.is_staff:
            self.stdout.write(
                self.style.WARNING(f"User '{user.username}' is already a superuser; nothing to do.")
            )
            return
        # Route through User.update so the promotion is audited via UserHistory
        # (an "edited" entry with the is_staff/is_superuser diff). All other
        # fields are passed back unchanged. The CLI has no request user, so the
        # promoted user is recorded as its own actor.
        user.update(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            description=user.description,
            has_public_profile=user.has_public_profile,
            is_active=user.is_active,
            is_staff=True,
            is_superuser=True,
            user=user,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Promoted user '{user.username}' (public_id={user.public_id}) "
                "to superuser + staff."
            )
        )
