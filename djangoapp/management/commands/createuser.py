from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import User


class Command(BaseCommand):
    """Create a user by email, optionally with names and superuser flags.

    Every creation is audited as a ``UserHistory`` "created" entry; with
    ``--superuser`` the entry carries the staff + superuser flags.
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
        superuser: bool = options["superuser"]
        try:
            user = User.create_by_email(
                email=options["email"],
                first_name=options["first_name"],
                last_name=options["last_name"],
                is_staff=superuser,
                is_superuser=superuser,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        flags = " + superuser/staff" if superuser else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Created user '{user.username}' ({user.email}){flags}. "
                "Sign in via: manage.py makeloginlink " + user.email
            )
        )
