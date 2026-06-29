"""``applications`` management command: agent-driven app/table management.

A single command with argparse subparsers. Every subcommand parses its
inputs through Pydantic schemas (where JSON is involved), runs inside an
atomic transaction, prints a success message + relevant info on exit 0,
or prints a styled error and exits non-zero on bad input.

Renaming an application, table, or collection only changes its display
name: physical tables are keyed by the immutable ``physical_name``
(``zz_<physical_name>``), which omits the collection/app/table name
entirely, so renames never trigger DDL.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, TypeVar

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management.base import BaseCommand, CommandParser
from django.db import IntegrityError, transaction
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from djangoapp.management.commands.applications_schemas import (
    AddApplicationTableColumnsSchema,
    CreateApplicationCollectionSchema,
    CreateApplicationSchema,
    CreateApplicationTableSchema,
    DeleteApplicationCollectionSchema,
    DeleteApplicationSchema,
    DeleteApplicationTableColumnsSchema,
    DeleteApplicationTableSchema,
    DescribeApplicationTableSchema,
    ListApplicationCollectionSchema,
    RenameApplicationCollectionSchema,
    RenameApplicationSchema,
    RenameApplicationTableSchema,
)
from djangoapp.models import (
    Application,
    ApplicationCollection,
)
from djangoapp.models.dynamic import (
    TableNotFoundError,
    dynamic_db_table,
    dynamic_models,
)

# Bound for _parse_json's generic schema argument (a concrete BaseModel).
T = TypeVar("T", bound=BaseModel)


def _format_pydantic_error(exc: PydanticValidationError) -> str:
    """Render a Pydantic ValidationError as a concise multi-line message."""
    lines = ["Invalid input:"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


def _format_django_error(exc: DjangoValidationError | Exception) -> str:
    if isinstance(exc, DjangoValidationError):
        # messages covers both dict-style and list-style ValidationErrors
        # without touching message_dict (which raises for non-dict errors).
        return "; ".join(exc.messages)
    return str(exc)


class Command(BaseCommand):
    """Manage application collections, applications and their tables."""

    help = "Create/rename/delete application collections, applications, and tables."

    SUBCOMMANDS: ClassVar[list[str]] = [
        "create_application_collection",
        "rename_application_collection",
        "delete_application_collection",
        "list_application_collections",
        "list_application_collection",
        "create_application",
        "rename_application",
        "delete_application",
        "create_application_table",
        "add_application_table_columns",
        "delete_application_table_columns",
        "describe_application_table",
        "rename_application_table",
        "delete_application_table",
    ]

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest="subcommand", required=True)

        p = sub.add_parser("create_application_collection")
        p.add_argument("--name", required=True)

        p = sub.add_parser("rename_application_collection")
        p.add_argument("--old-name", dest="old_name", required=True)
        p.add_argument("--new-name", dest="new_name", required=True)

        p = sub.add_parser("delete_application_collection")
        p.add_argument("--name", required=True)

        sub.add_parser("list_application_collections")

        p = sub.add_parser("list_application_collection")
        p.add_argument("--name", required=True)

        p = sub.add_parser("create_application")
        p.add_argument("--appcollection", required=True)
        p.add_argument("--name", required=True)
        p.add_argument("--desc", default="")

        p = sub.add_parser("rename_application")
        p.add_argument("--old-appcollection", dest="old_appcollection", required=True)
        p.add_argument("--old-name", dest="old_name", required=True)
        p.add_argument("--new-appcollection", dest="new_appcollection", required=True)
        p.add_argument("--new-name", dest="new_name", required=True)

        p = sub.add_parser("delete_application")
        p.add_argument("--appcollection", required=True)
        p.add_argument("--name", required=True)

        p = sub.add_parser("create_application_table")

        p.add_argument("--json-payload", dest="json_payload", required=True)

        p = sub.add_parser("add_application_table_columns")
        p.add_argument("--json-payload", dest="json_payload", required=True)

        p = sub.add_parser("delete_application_table_columns")
        p.add_argument("--json-payload", dest="json_payload", required=True)

        p = sub.add_parser("describe_application_table")
        p.add_argument("--appcollection", required=True)
        p.add_argument("--app", required=True)
        p.add_argument("--name", required=True)

        p = sub.add_parser("rename_application_table")
        p.add_argument("--appcollection", required=True)
        p.add_argument("--app", required=True)
        p.add_argument("--name", required=True)
        p.add_argument("--new-name", dest="new_name", required=True)

        p = sub.add_parser("delete_application_table")
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
        except (
            PydanticValidationError,
            DjangoValidationError,
            TableNotFoundError,
            ValueError,
            IntegrityError,
        ) as exc:
            # IntegrityError is the last line of defense for the DB unique
            # constraints (collection/app/table names, physical_name); a
            # concurrent create can slip past the schema-level pre-checks,
            # so surface it as a clean non-zero exit rather than a traceback.
            if isinstance(exc, PydanticValidationError):
                self.stdout.write(self.style.ERROR(_format_pydantic_error(exc)))
            else:
                self.stdout.write(self.style.ERROR(_format_django_error(exc)))
            raise SystemExit(1) from exc

    # ------------------------------------------------------------------
    # Collection handlers
    # ------------------------------------------------------------------

    def _handle_create_application_collection(self, options: dict[str, Any]) -> None:
        payload = CreateApplicationCollectionSchema(name=options["name"])
        with transaction.atomic():
            collection = ApplicationCollection.objects.create(name=payload.name)
        self.stdout.write(self.style.SUCCESS(f"Created collection '{collection.name}'."))

    def _handle_rename_application_collection(self, options: dict[str, Any]) -> None:
        payload = RenameApplicationCollectionSchema(
            old_name=options["old_name"],
            new_name=options["new_name"],
        )
        # Display-name only: physical_name omits the collection, so the
        # rename is a plain row update — no DDL, no registry reset.
        collection = payload.collection
        dynamic_models.rename_application_collection(collection, payload.new_name)
        self.stdout.write(self.style.SUCCESS(f"Renamed collection to '{collection.name}'."))

    def _handle_delete_application_collection(self, options: dict[str, Any]) -> None:
        payload = DeleteApplicationCollectionSchema(name=options["name"])
        with transaction.atomic():
            collection = payload.collection
            if collection.applications.exists():
                msg = (
                    f"Collection '{payload.name}' is not empty "
                    f"({collection.applications.count()} application(s))."
                )
                raise DjangoValidationError(msg)
            collection.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted collection '{payload.name}'."))

    def _handle_list_application_collections(self, _options: dict[str, Any]) -> None:
        for collection in ApplicationCollection.objects.all().order_by("name"):
            self.stdout.write(collection.name)

    def _handle_list_application_collection(self, options: dict[str, Any]) -> None:
        payload = ListApplicationCollectionSchema(name=options["name"])
        for app in payload.collection.applications.all().order_by("name"):
            self.stdout.write(app.name)

    # ------------------------------------------------------------------
    # Application handlers
    # ------------------------------------------------------------------

    def _handle_create_application(self, options: dict[str, Any]) -> None:
        payload = CreateApplicationSchema(
            appcollection=options["appcollection"],
            name=options["name"],
            desc=options["desc"],
        )
        with transaction.atomic():
            app = Application.objects.create(
                application_collection=payload.collection,
                name=payload.name,
                description=payload.desc,
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created application '{app.name}' in collection '{payload.collection.name}'."
            )
        )

    def _handle_rename_application(self, options: dict[str, Any]) -> None:
        payload = RenameApplicationSchema(
            old_appcollection=options["old_appcollection"],
            old_name=options["old_name"],
            new_appcollection=options["new_appcollection"],
            new_name=options["new_name"],
        )
        with transaction.atomic():
            app = payload.application
            app.name = payload.new_name
            app.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Renamed application to '{app.name}' "
                f"in collection '{payload.new_collection.name}'."
            )
        )

    def _handle_delete_application(self, options: dict[str, Any]) -> None:
        payload = DeleteApplicationSchema(
            appcollection=options["appcollection"],
            name=options["name"],
        )
        with transaction.atomic():
            app = payload.application
            if app.tables.exists():
                msg = f"Application '{payload.name}' is not empty ({app.tables.count()} table(s))."
                raise DjangoValidationError(msg)
            app.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted application '{payload.name}'."))

    # ------------------------------------------------------------------
    # Table handlers
    # ------------------------------------------------------------------

    def _handle_create_application_table(self, options: dict[str, Any]) -> None:
        payload = self._parse_json(options["json_payload"], CreateApplicationTableSchema)
        table = dynamic_models.create_application_table(
            appcollection=payload.appcollection,
            app=payload.app,
            name=payload.name,
            columns=[c.model_dump(exclude_none=True) for c in payload.columns],
        )
        db_table = dynamic_db_table(table.physical_name)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created table '{table.name}' with "
                f"{len(payload.columns)} column(s); db_table={db_table}."
            )
        )

    def _handle_add_application_table_columns(self, options: dict[str, Any]) -> None:
        payload = self._parse_json(options["json_payload"], AddApplicationTableColumnsSchema)
        created = dynamic_models.add_application_table_columns(
            appcollection=payload.appcollection,
            app=payload.app,
            table=payload.table,
            columns=[c.model_dump(exclude_none=True) for c in payload.columns],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Added {len(created)} column(s) to table '{payload.table}'.")
        )

    def _handle_delete_application_table_columns(self, options: dict[str, Any]) -> None:
        payload = self._parse_json(options["json_payload"], DeleteApplicationTableColumnsSchema)
        dynamic_models.delete_application_table_columns(
            appcollection=payload.appcollection,
            app=payload.app,
            table=payload.table,
            columns=payload.columns,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {len(payload.columns)} column(s) from table '{payload.table}'."
            )
        )

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

    def _handle_rename_application_table(self, options: dict[str, Any]) -> None:
        payload = RenameApplicationTableSchema(
            appcollection=options["appcollection"],
            app=options["app"],
            name=options["name"],
            new_name=options["new_name"],
        )
        # Display-name only: physical_name is immutable, so no DDL/reset.
        app_table = dynamic_models.rename_application_table(
            payload.application_table, payload.new_name
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Renamed table to '{app_table.name}' "
                f"(physical_name {app_table.physical_name} unchanged)."
            )
        )

    def _handle_delete_application_table(self, options: dict[str, Any]) -> None:
        payload = DeleteApplicationTableSchema(
            appcollection=options["appcollection"],
            app=options["app"],
            name=options["name"],
        )
        dynamic_models.delete_application_table(
            appcollection=payload.appcollection,
            app=payload.app,
            table=payload.name,
        )
        self.stdout.write(self.style.SUCCESS(f"Deleted table '{payload.name}'."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_json(self, raw: str, schema: type[T]) -> T:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON: {exc}"
            raise ValueError(msg) from exc
        return schema.model_validate(data)
