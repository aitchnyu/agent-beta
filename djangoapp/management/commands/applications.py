"""``applications`` management command: read-only listing/describe.

A single command with argparse subparsers. Mutation of collections, apps
and tables lives on ``dynamic_models`` (see ``djangoapp/models/dynamic.py``);
this command only lists collections, lists an app's contents, and describes
a table's columns.

Renaming an application, table, or collection only changes its display
name: physical tables are keyed by the immutable ``physical_name``
(``zz_<physical_name>``), which omits the collection/app/table name
entirely, so renames never trigger DDL.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management.base import BaseCommand, CommandParser
from django.db import IntegrityError

from djangoapp.management.commands.applications_schemas import (
    DescribeApplicationTableSchema,
    ListApplicationCollectionSchema,
)
from djangoapp.models import ApplicationCollection


def _format_django_error(exc: DjangoValidationError | Exception) -> str:
    if isinstance(exc, DjangoValidationError):
        # messages covers both dict-style and list-style ValidationErrors
        # without touching message_dict (which raises for non-dict errors).
        return "; ".join(exc.messages)
    return str(exc)


class Command(BaseCommand):
    """List application collections, apps, and describe tables."""

    help = "List application collections/apps and describe tables (read-only)."

    SUBCOMMANDS: ClassVar[list[str]] = [
        "list_application_collections",
        "list_application_collection",
        "describe_application_table",
    ]

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest="subcommand", required=True)

        sub.add_parser("list_application_collections")

        p = sub.add_parser("list_application_collection")
        p.add_argument("--name", required=True)

        p = sub.add_parser("describe_application_table")
        p.add_argument("--appcollection", required=True)
        p.add_argument("--app", required=True)
        p.add_argument("--name", required=True)

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # options is untyped Django command flags
        # Django's BaseCommand.execute() writes handle()'s return value to
        # stdout, so we must NOT return an int; SystemExit(1) is the clean
        # way to signal a non-zero exit without Django's CommandError prefix.
        sub: str | None = options.get("subcommand")
        handler = getattr(self, f"_handle_{sub}", None) if sub else None
        if handler is None:
            self.stdout.write(self.style.ERROR("No subcommand supplied."))
            raise SystemExit(1)
        try:
            handler(options)
        except (DjangoValidationError, IntegrityError, ValueError) as exc:
            # IntegrityError is the last line of defense for the DB unique
            # constraints; surface it as a clean non-zero exit rather than a
            # traceback.
            self.stdout.write(self.style.ERROR(_format_django_error(exc)))
            raise SystemExit(1) from exc

    # ------------------------------------------------------------------
    # Read handlers
    # ------------------------------------------------------------------

    def _handle_list_application_collections(self, _options: dict[str, Any]) -> None:
        for collection in ApplicationCollection.objects.all().order_by("name"):
            self.stdout.write(collection.name)

    def _handle_list_application_collection(self, options: dict[str, Any]) -> None:
        payload = ListApplicationCollectionSchema(name=options["name"])
        for app in payload.collection.applications.all().order_by("name"):
            self.stdout.write(app.name)

    def _handle_describe_application_table(self, options: dict[str, Any]) -> None:
        payload = DescribeApplicationTableSchema(
            appcollection=options["appcollection"],
            app=options["app"],
            name=options["name"],
        )
        table = payload.application_table
        self.stdout.write(f"table: {table.name}")
        self.stdout.write(f"column_order: {json.dumps(table.column_order)}")
        for col in table.columns.all().order_by("name"):
            self.stdout.write(f"  - {col.name}: {col.type}")
