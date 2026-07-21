"""``applications`` management command: read-only listing/describe.

A single command with argparse subparsers. Mutation of apps and tables lives
on ``dynamic_models`` (see ``djangoapp/models/dynamic.py``); this command only
lists apps and describes a table's columns.

Renaming an application or table only changes its display name: physical
tables are keyed by the immutable ``physical_name``
(``zz_<physical_name>``), which omits the app/table name entirely, so
renames never trigger DDL.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management.base import BaseCommand, CommandParser
from django.db import IntegrityError

from djangoapp.management.commands.applications_schemas import DescribeApplicationTableSchema
from djangoapp.models import Application, ApplicationTable, ApplicationTableColumn
from djangoapp.models.applications import ColumnType


def _format_django_error(exc: DjangoValidationError | Exception) -> str:
    if isinstance(exc, DjangoValidationError):
        # messages covers both dict-style and list-style ValidationErrors
        # without touching message_dict (which raises for non-dict errors).
        return "; ".join(exc.messages)
    return str(exc)


class Command(BaseCommand):
    """List apps and describe tables."""

    help = "List apps and describe tables (read-only)."

    SUBCOMMANDS: ClassVar[list[str]] = [
        "list_applications",
        "describe_application_table",
        "export_fk_graph",
    ]

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest="subcommand", required=True)

        sub.add_parser("list_applications")

        p = sub.add_parser("describe_application_table")
        p.add_argument("--app", required=True)
        p.add_argument("--name", required=True)

        p = sub.add_parser("export_fk_graph")
        p.add_argument(
            "--format",
            choices=["dot", "mermaid"],
            default="dot",
            help="Graph format (default: dot).",
        )

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

    def _handle_list_applications(self, _options: dict[str, Any]) -> None:
        for app in Application.objects.all().order_by("name"):
            self.stdout.write(app.name)

    def _handle_describe_application_table(self, options: dict[str, Any]) -> None:
        payload = DescribeApplicationTableSchema(
            app=options["app"],
            name=options["name"],
        )
        table = payload.application_table
        self.stdout.write(f"table: {table.name}")
        self.stdout.write(f"column_order: {json.dumps(table.column_order)}")
        for col in table.columns.all().order_by("name"):
            self.stdout.write(f"  - {col.name}: {col.type}")

    def _handle_export_fk_graph(self, options: dict[str, Any]) -> None:
        def label(table: ApplicationTable) -> str:
            """``app:table``; ``:`` is Mermaid-id-safe, so it doubles as id and text."""
            return f"{table.application.name}:{table.name}"

        # Every table is a node; every foreign-key column is a labelled edge
        # source -> target. Emits the whole graph (no scoping), so isolated
        # tables (no FK in or out) appear as nodes too.
        tables = list(
            ApplicationTable.objects.select_related("application").order_by(
                "application__name", "name"
            )
        )
        # Labels are unique per table (application+name is unique), so a single
        # comprehension needs no dedup. Both endpoints of every edge are
        # ApplicationTable rows already in this list, so the edge loop below only
        # reads their labels — no registration there.
        node_labels = [label(t) for t in tables]

        edges: list[tuple[str, str, str]] = []
        fk_columns = (
            ApplicationTableColumn.objects.filter(type=ColumnType.FOREIGN_KEY)
            .select_related(
                "application_table__application",
                "fk_target_table__application",
            )
            .order_by("application_table__name", "name")
        )
        for column in fk_columns:
            target = column.fk_target_table
            # clean() forces a target for every foreign_key column, so an
            # orphaned column is impossible in a correctly-created app.
            assert target is not None
            edges.append((label(column.application_table), label(target), column.name))

        emit = _emit_mermaid if options["format"] == "mermaid" else _emit_graphviz
        self.stdout.write(emit(node_labels, edges))


def _emit_graphviz(nodes: list[str], edges: list[tuple[str, str, str]]) -> str:
    """Render nodes + FK edges as a Graphviz DOT digraph.

    Each node's id is the full ``app:table`` label, but its visible text is just
    the table name (the segment after the last ``:``) — the unique ids keep
    same-named tables across apps distinct, while the boxes stay short.
    """
    lines = ["digraph fk {"]
    lines.extend(f'  "{label}" [label="{label.rsplit(":", 1)[-1]}"];' for label in nodes)
    lines.extend(
        f'  "{source}" -> "{destination}" [label="{column_name}"];'
        for source, destination, column_name in edges
    )
    lines.append("}")
    return "\n".join(lines)


def _emit_mermaid(nodes: list[str], edges: list[tuple[str, str, str]]) -> str:
    """Render nodes + FK edges as a Mermaid graph (renders in GitHub/VS Code).

    Unlike DOT, the full ``app:table`` label is both the node id and its
    displayed text, so same-named tables across apps stay distinct in both (DOT
    collapses them to the bare table name). ``graph LR`` is left-to-right.
    """
    lines = ["graph LR"]
    lines.extend(f'  {label}["{label}"]' for label in nodes)
    lines.extend(
        f"  {source} -->|{column_name}| {destination}" for source, destination, column_name in edges
    )
    return "\n".join(lines)
