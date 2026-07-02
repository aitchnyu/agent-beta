from __future__ import annotations

import json
from io import StringIO
from typing import ClassVar

from django.core.management import call_command
from django.test import TestCase

from djangoapp.models import (
    Application,
    ApplicationCollection,
    ApplicationTable,
)
from djangoapp.models.dynamic import dynamic_models


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
    three read subcommands, seeded via the registry/ORM directly.

    - test_list_application_collections, every collection name printed one per line, sorted
    - test_list_application_collection, apps under the collection printed one per line, sorted
    - test_list_application_collection_missing, unknown collection exits non-zero
    - test_describe_application_table, prints table + columns, omits physical_name/db_table
    - test_describe_application_table_missing, unknown table exits non-zero
    - test_leading_digit_name_rejected, names must start with a letter
    """

    collection: ClassVar[ApplicationCollection]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.collection = ApplicationCollection.objects.create(name="inv")
        cls.app = cls.collection.applications.create(name="orders")

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
            "inv",
            "orders",
            name,
            [{"name": "code", "type": "char"}],
        )

    # -- list_application_collections ---------------------------------

    def test_list_application_collections(self) -> None:
        """Every collection name printed one per line, sorted."""
        ApplicationCollection.objects.create(name="aaa")
        code, out = run("list_application_collections")
        self.assertEqual(code, 0)
        # Output is sorted by name; "aaa" precedes "inv".
        lines = [ln for ln in out.splitlines() if ln]
        self.assertEqual(lines, ["aaa", "inv"])

    # -- list_application_collection ----------------------------------

    def test_list_application_collection(self) -> None:
        """Apps under the collection printed one per line, sorted."""
        self.collection.applications.create(name="billing")
        code, out = run("list_application_collection", "--name", "inv")
        self.assertEqual(code, 0)
        lines = [ln for ln in out.splitlines() if ln]
        self.assertEqual(lines, ["billing", "orders"])

    def test_list_application_collection_missing(self) -> None:
        """Unknown collection exits non-zero."""
        code, out = run("list_application_collection", "--name", "nope")
        self.assertNotEqual(code, 0)
        self.assertIn("No collection", out)

    def test_leading_digit_name_rejected(self) -> None:
        """Names must start with a letter."""
        code, out = run("list_application_collection", "--name", "2bad")
        self.assertNotEqual(code, 0)
        self.assertIn("start with a letter", out)

    # -- describe_application_table -----------------------------------

    def test_describe_application_table(self) -> None:
        """Prints table + columns, omits physical_name/db_table."""
        table = self._create_table()
        code, out = run(
            "describe_application_table",
            "--appcollection",
            "inv",
            "--app",
            "orders",
            "--name",
            "items",
        )
        self.assertEqual(code, 0)
        self.assertIn("table: items", out)
        self.assertIn("code: char", out)
        self.assertIn(f"column_order: {json.dumps(['code'])}", out)
        # Internal physical naming must not leak to the agent-facing output.
        self.assertNotIn(table.physical_name, out)
        self.assertNotIn("db_table:", out)

    def test_describe_application_table_missing(self) -> None:
        """Unknown table exits non-zero."""
        code, out = run(
            "describe_application_table",
            "--appcollection",
            "inv",
            "--app",
            "orders",
            "--name",
            "nope",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("No table", out)
        self.assertFalse(ApplicationTable.objects.filter(name="nope").exists())
        self.assertTrue(Application.objects.filter(name="orders").exists())
