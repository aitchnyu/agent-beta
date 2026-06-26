from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand

from djangoapp.models.app import FirstStuff
from djangoapp.models.base import User

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = "Create 200 FirstStuff rows for a specific user"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Email address of the user to create rows for",
        )

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN401, ARG002 # Django fixes *args/**options; values are Any
        user = User.objects.get(email=options["email"])

        # Create 200 FirstStuff rows
        created_count = 0
        for i in range(200):
            FirstStuff.objects.create(
                char_field="aaa",
                text_field="bbb",
                integer_field=i,
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {created_count} FirstStuff rows for user {user.email}",
            ),
        )
