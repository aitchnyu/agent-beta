from __future__ import annotations

import math
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from djangoapp.models import User


class Command(BaseCommand):
    """List users — first, last, email, staff, superuser — paginated."""

    help = (
        "List users (first, last, email, staff, superuser); --page N; "
        "--exclude <regex> omits users whose email matches."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--page", type=int, default=1, help="1-based page number.")
        parser.add_argument(
            "--exclude", default="", help="Omit users whose email matches this regex."
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        page: int = options["page"]
        page_size = 100
        if page < 1:
            msg = "--page is 1-based"
            raise CommandError(msg)

        users = User.objects.order_by("email")
        if options["exclude"]:
            users = users.exclude(email__regex=options["exclude"])
        total = users.count()
        pages = max(1, math.ceil(total / page_size))
        if page > pages:
            msg = f"page {page} is past the last page ({pages})"
            raise CommandError(msg)

        rows = list(
            users.values("first_name", "last_name", "email", "is_staff", "is_superuser")[
                (page - 1) * page_size : page * page_size
            ]
        )

        display = [
            {
                "first": row["first_name"],
                "last": row["last_name"],
                "email": row["email"],
                "staff": "yes" if row["is_staff"] else "-",
                "super": "yes" if row["is_superuser"] else "-",
            }
            for row in rows
        ]
        columns = ("first", "last", "email", "staff", "super")
        widths = {
            key: max(len(key), *(len(str(row[key])) for row in display)) if display else len(key)
            for key in columns
        }
        header = "  ".join(f"{key:<{widths[key]}}" for key in columns).rstrip()
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for row in display:
            self.stdout.write("  ".join(f"{row[key]:<{widths[key]}}" for key in columns).rstrip())
        self.stdout.write(self.style.SUCCESS(f"page {page}/{pages} · {total} users"))
