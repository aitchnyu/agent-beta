from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import User


class Command(BaseCommand):
    """Create a user by email, optionally with names and superuser flags.

     ``--superuser`` grants staff + superuser at creation (audited via ``UserHistory`` like every user write)
    """

    help = "Create a user by email (optionally --first-name/--last-name/--superuser)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", type=str, help="Email (also the login identity).")
        parser.add_argument("--first-name", type=str, default="", help="First name.")
        parser.add_argument("--last-name", type=str, default="", help="Last name.")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Also grant is_staff + is_superuser (audited in UserHistory).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        email: str = options["email"]
        first_name: str = options["first_name"]
        last_name: str = options["last_name"]
        superuser: bool = options["superuser"]
        # The User model does not enforce unique emails — refuse a second
        # account for the same address (iexact) instead of silently doubling.
        if User.objects.filter(email__iexact=email).exists():
            msg = f"A user with email '{email}' already exists."
            raise CommandError(msg)
        # Username derives from the email local part (unique-ified by
        # create_user if needed); names pass through as given.
        username = email.rsplit("@", 1)[0]
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        if superuser:
            # Route through User.update so the grant is audited via
            # UserHistory (the CLI has no request user, so the new user is
            # recorded as its own actor).
            user.update(
                first_name=first_name,
                last_name=last_name,
                email=email,
                description=user.description,
                has_public_profile=user.has_public_profile,
                is_active=user.is_active,
                is_staff=True,
                is_superuser=True,
                user=user,
            )
        flags = " + superuser/staff" if superuser else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Created user '{user.username}' ({email}){flags}. "
                "Sign in via: manage.py makeloginlink " + email
            )
        )
