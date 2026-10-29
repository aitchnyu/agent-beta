from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import User


class Command(BaseCommand):
    """Create a user by first/last name + email, optionally a superuser.

    Every creation is audited as a ``UserHistory`` "created" entry; with
    ``--superuser`` the entry carries the staff + superuser flags.
    """

    help = "Create a user: createuser <first> <last> <email> [--superuser]."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("first_name", type=str, help="First name.")
        parser.add_argument("last_name", type=str, help="Last name.")
        parser.add_argument("email", type=str, help="Email (also the login identity).")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Also grant is_staff + is_superuser (audited in UserHistory).",
        )
        parser.add_argument(
            "--if-absent",
            action="store_true",
            help="Skip silently when the email already exists (no audit entry).",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        superuser: bool = options["superuser"]
        email: str = options["email"]
        if options["if_absent"] and User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"{email} already exists — skipped")
            return
        try:
            user = User.create_by_email(
                email=email,
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
                f"login link: ./run djangomanage makeloginlink {user.email}"
            )
        )
