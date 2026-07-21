from __future__ import annotations

import json
from io import StringIO
from typing import ClassVar

from django.core.management import call_command
from django.test import TestCase

from djangoapp.models import (
    Application,
    ApplicationTable,
)
from djangoapp.models.columns import CharColumn, ForeignKeyColumn, IntegerColumn
from djangoapp.models.dynamic import dynamic_models

_APP = "OrdersData"


def run(subcommand: str, *args: str) -> tuple[int, str]:
    """Invoke the applications command and return (exit_code, stdout).

    Catches SystemExit so callers see a plain (code, output) tuple: the
    command raises SystemExit(1) on bad input (Django treats handle()'s
    return value as stdout text, so an int return cannot carry the code).
    """
    out = StringIO()
    try:
        call_command("applications", subcommand, *args, stdout=out, stderr=out)
    except SystemExit as exc:
        return int(exc.code or 1), out.getvalue()
    return 0, out.getvalue()


class ApplicationsCommandTests(TestCase):
    """Read-only ``applications`` command subcommands.

    Mutation lives on ``dynamic_models`` now; these tests only cover the
    read subcommands, seeded via the registry/ORM directly.

    - test_list_applications, every app name printed one per line, sorted
    - test_describe_application_table, prints table + columns, omits physical_name/db_table
    - test_describe_application_table_missing, unknown table exits non-zero
    """

    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.app = Application.objects.create(name=_APP)

    def setUp(self) -> None:
        super().setUp()
        # DDL lives inside the per-test transaction (rolled back), but the
        # in-memory dynamic-model registrations survive across tests and
        # would trigger a re-registration warning; reset between tests.
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _create_table(self, name: str = "items") -> ApplicationTable:
        return dynamic_models.create_application_table(
            application=_APP,
            table=name,
            columns=[CharColumn("code", max_length=10), IntegerColumn("qty")],
        )

    # -- list_applications --------------------------------------------

    def test_list_applications(self) -> None:
        """Every app name printed one per line, sorted."""
        Application.objects.create(name="ApplesData")  # precedes OrdersData sorted
        code, out = run("list_applications")
        self.assertEqual(code, 0)
        lines = [ln for ln in out.splitlines() if ln]
        self.assertEqual(lines, ["ApplesData", _APP])

    # -- describe_application_table -----------------------------------

    def test_describe_application_table(self) -> None:
        """Prints table + columns, omits physical_name/db_table."""
        table = self._create_table()
        code, out = run(
            "describe_application_table",
            "--app",
            _APP,
            "--name",
            "items",
        )
        self.assertEqual(code, 0)
        self.assertIn("table: items", out)
        self.assertIn("code: char", out)
        self.assertIn(f"column_order: {json.dumps(['code', 'qty'])}", out)
        # Internal physical naming must not leak to the agent-facing output.
        self.assertNotIn(table.physical_name, out)
        self.assertNotIn("db_table:", out)

    def test_describe_application_table_missing(self) -> None:
        """Unknown table exits non-zero."""
        code, out = run(
            "describe_application_table",
            "--app",
            _APP,
            "--name",
            "nope",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("No table", out)
        self.assertFalse(ApplicationTable.objects.filter(name="nope").exists())
        self.assertTrue(Application.objects.filter(name=_APP).exists())


class ExportFkGraphTests(TestCase):
    """``applications export_fk_graph`` renders tables + FK edges.

    Tables are nodes (label ``app:table`` — ``:`` is Mermaid-id-safe, so it
    doubles as the node id and text); each foreign-key column is an edge
    source -> target labelled with the column name. DOT is the default;
    ``--format mermaid`` emits a Mermaid graph. The whole graph is emitted
    (no scoping).

    - test_dot_default_emits_nodes_and_edge, default format is DOT with nodes + a labelled edge
    - test_mermaid_format_emits_graph, --format mermaid emits a renderable Mermaid graph
    - test_all_tables_emitted, every table across apps appears as a node
    """

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        # GraphAppOne: beta references alpha.
        dynamic_models.create_application(
            name="GraphAppOne",
            tables={
                "alpha": [CharColumn("code", max_length=5)],
                "beta": [ForeignKeyColumn("link", target=("GraphAppOne", "alpha"), nullable=True)],
            },
        )

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def test_dot_default_emits_nodes_and_edge(self) -> None:
        """Default format is DOT: nodes for tables, a labelled edge for the FK."""
        code, out = run("export_fk_graph")
        self.assertEqual(code, 0)
        self.assertIn("digraph fk {", out)
        self.assertIn('"GraphAppOne:alpha" [label="alpha"];', out)
        self.assertIn('"GraphAppOne:beta" [label="beta"];', out)
        self.assertIn('"GraphAppOne:beta" -> "GraphAppOne:alpha" [label="link"];', out)

    def test_mermaid_format_emits_graph(self) -> None:
        """--format mermaid emits a graph: the ':'-label is the id and the text."""
        code, out = run("export_fk_graph", "--format", "mermaid")
        self.assertEqual(code, 0)
        self.assertIn("graph LR", out)
        self.assertIn('GraphAppOne:alpha["GraphAppOne:alpha"]', out)
        self.assertIn("GraphAppOne:beta -->|link| GraphAppOne:alpha", out)

    def test_all_tables_emitted(self) -> None:
        """Every table across apps appears as a node (the graph is unscoped)."""
        dynamic_models.create_application(
            name="PlainAppOne",
            tables={"solo": [CharColumn("code", max_length=5)]},
        )
        code, out = run("export_fk_graph")
        self.assertEqual(code, 0)
        self.assertIn('"PlainAppOne:solo"', out)
        self.assertIn('"GraphAppOne:alpha"', out)
