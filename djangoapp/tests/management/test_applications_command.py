from __future__ import annotations

import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from djangoapp.models import Application, ApplicationCollection, ApplicationTable
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
    """End-to-end behaviour of the ``applications`` management command.

    Drives every subcommand through ``call_command`` and asserts on both
    the printed output and the resulting model state.

    - test_collection_create_rename_list, collection create+rename+list round-trips
    - test_delete_collection_refuses_when_not_empty, non-empty collection deletion rejected
    - test_application_create_rename_delete, app create+rename+delete lifecycle
    - test_create_table_builds_columns_and_physical_table, table create issues DDL + columns
    - test_add_and_delete_columns_via_command, add/delete column subcommands mutate the table
    - test_describe_application_table, describe prints table/columns, omits physical_name/db_table
    - test_delete_application_table, table delete removes physical table and definition
    - test_invalid_json_returns_nonzero, malformed JSON exits non-zero with a message
    """

    def _seed_collection_and_app(self) -> None:
        run("create_application_collection", "--name", "inv")
        run("create_application", "--appcollection", "inv", "--name", "orders")

    def setUp(self) -> None:
        super().setUp()
        # DDL lives inside the per-test transaction (rolled back), but the
        # in-memory dynamic-model registrations survive across tests and
        # would trigger a re-registration warning; reset between tests.
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    # -- collection ----------------------------------------------------

    def test_collection_create_rename_list(self) -> None:
        """Collection create+rename+list round-trips via the command."""
        code, out = run("create_application_collection", "--name", "Inv1")
        self.assertEqual(code, 0)
        self.assertIn("Created collection", out)
        code, _ = run("rename_application_collection", "--old-name", "Inv1", "--new-name", "Inv2")
        self.assertEqual(code, 0)
        self.assertTrue(ApplicationCollection.objects.filter(name="Inv2").exists())
        code, out = run("list_application_collections")
        self.assertEqual(code, 0)
        self.assertIn("Inv2", out)

    def test_delete_collection_refuses_when_not_empty(self) -> None:
        """Non-empty collection deletion is rejected with a non-zero exit."""
        self._seed_collection_and_app()
        code, out = run("delete_application_collection", "--name", "inv")
        self.assertNotEqual(code, 0)
        self.assertIn("not empty", out)
        self.assertTrue(ApplicationCollection.objects.filter(name="inv").exists())

    # -- application ---------------------------------------------------

    def test_application_create_rename_delete(self) -> None:
        """App create+rename (same collection)+delete lifecycle."""
        self._seed_collection_and_app()
        # rename within the same collection (cross-collection move is forbidden)
        code, out = run(
            "rename_application",
            "--old-appcollection",
            "inv",
            "--old-name",
            "orders",
            "--new-appcollection",
            "inv",
            "--new-name",
            "orders2",
        )
        self.assertEqual(code, 0, out)
        app = Application.objects.get(name="orders2")
        self.assertEqual(app.name, "orders2")
        self.assertEqual(app.application_collection.name, "inv")
        # list
        code, out = run("list_application_collection", "--name", "inv")
        self.assertIn("orders2", out)
        # delete
        code, _ = run("delete_application", "--appcollection", "inv", "--name", "orders2")
        self.assertEqual(code, 0)
        self.assertFalse(Application.objects.filter(name="orders2").exists())

    # -- tables --------------------------------------------------------

    def test_create_table_builds_columns_and_physical_table(self) -> None:
        """Table create issues DDL and persists column definitions."""
        self._seed_collection_and_app()
        payload = {
            "appcollection": "inv",
            "app": "orders",
            "name": "items",
            "columns": [
                {"name": "code", "type": "char", "max_length": 10},
                {"name": "qty", "type": "integer", "default": 1, "nullable": True},
            ],
        }
        code, out = run("create_application_table", "--json-payload", json.dumps(payload))
        self.assertEqual(code, 0)
        table = ApplicationTable.objects.get(name="items")
        self.assertEqual(table.column_order, ["code", "qty"])
        self.assertEqual(table.columns.count(), 2)
        # Physical name is <name><seconds><n>; db_table prefix is zz_items.
        self.assertTrue(table.physical_name.startswith("items"))
        self.assertIn(f"zz_{table.physical_name}", out)

    def test_add_and_delete_columns_via_command(self) -> None:
        """add/delete column subcommands mutate the table and column_order."""
        self._seed_collection_and_app()
        run(
            "create_application_table",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "name": "items",
                    "columns": [{"name": "code", "type": "char", "max_length": 10}],
                }
            ),
        )
        code, _ = run(
            "add_application_table_columns",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "table": "items",
                    "columns": [{"name": "qty", "type": "integer", "default": 0}],
                }
            ),
        )
        self.assertEqual(code, 0)
        table = ApplicationTable.objects.get(name="items")
        self.assertIn("qty", table.column_order)
        self.assertTrue(table.columns.filter(name="qty").exists())

        code, _ = run(
            "delete_application_table_columns",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "table": "items",
                    "columns": ["code"],
                }
            ),
        )
        self.assertEqual(code, 0)
        table.refresh_from_db()
        self.assertNotIn("code", table.column_order)
        self.assertFalse(table.columns.filter(name="code").exists())

    def test_describe_application_table(self) -> None:
        """Describe prints the table name, column_order, and columns.

        Internal physical_name/db_table are deliberately not printed
        (agents address tables by display name), so the assert confirms
        their absence.
        """
        self._seed_collection_and_app()
        run(
            "create_application_table",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "name": "items",
                    "columns": [{"name": "code", "type": "char"}],
                }
            ),
        )
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
        table = ApplicationTable.objects.get(name="items")
        # Internal physical naming must not leak to the agent-facing output.
        self.assertNotIn(table.physical_name, out)
        self.assertNotIn("db_table:", out)

    def test_delete_application_table(self) -> None:
        """Table delete removes the physical table and definition rows."""
        self._seed_collection_and_app()
        run(
            "create_application_table",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "name": "items",
                    "columns": [{"name": "code", "type": "char"}],
                }
            ),
        )
        code, _ = run(
            "delete_application_table",
            "--appcollection",
            "inv",
            "--app",
            "orders",
            "--name",
            "items",
        )
        self.assertEqual(code, 0)
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())

    def test_rename_application_table(self) -> None:
        """Table rename changes only the display name (physical table intact, zero DDL)."""
        self._seed_collection_and_app()
        run(
            "create_application_table",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "name": "items",
                    "columns": [{"name": "code", "type": "char"}],
                }
            ),
        )
        before = ApplicationTable.objects.get(name="items")
        code, out = run(
            "rename_application_table",
            "--appcollection",
            "inv",
            "--app",
            "orders",
            "--name",
            "items",
            "--new-name",
            "items2",
        )
        self.assertEqual(code, 0, out)
        after = ApplicationTable.objects.get(name="items2")
        self.assertEqual(after.pk, before.pk)
        self.assertEqual(after.physical_name, before.physical_name)  # immutable

    def test_invalid_json_returns_nonzero(self) -> None:
        """Malformed JSON exits non-zero with a printed message."""
        self._seed_collection_and_app()
        code, out = run("create_application_table", "--json-payload", "{not json}")
        self.assertNotEqual(code, 0)
        self.assertIn("Invalid JSON", out)


class ApplicationsValidationTests(TestCase):
    """Schema-driven validation for the ``applications`` command.

    Covers the cross-field and DB-clash rules enforced by the Pydantic
    schemas, which the happy-path tests above do not exercise.

    - test_rename_collection_same_name_rejected, old_name == new_name rejected
    - test_create_collection_duplicate_rejected, duplicate name rejected
    - test_create_application_clash_rejected, duplicate app within collection rejected
    - test_rename_application_noop_rejected, identical target rejected
    - test_rename_application_move_rejected, cross-collection move rejected
    - test_leading_digit_name_rejected, names must start with a letter
    - test_create_table_duplicate_column_rejected, duplicate column names in payload rejected
    - test_boolean_column_has_no_length_fields, boolean spec carries only default
    - test_unknown_column_type_rejected, invalid type exits non-zero
    - test_add_existing_column_rejected, adding an existing column rejected
    - test_delete_missing_column_rejected, deleting a non-existent column rejected
    """

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _seed(self) -> None:
        run("create_application_collection", "--name", "inv")
        run("create_application", "--appcollection", "inv", "--name", "orders")

    def test_rename_collection_same_name_rejected(self) -> None:
        """old_name == new_name is rejected (no-op rename)."""
        run("create_application_collection", "--name", "C1")
        code, out = run("rename_application_collection", "--old-name", "C1", "--new-name", "C1")
        self.assertNotEqual(code, 0)
        self.assertIn("differ", out)

    def test_create_collection_duplicate_rejected(self) -> None:
        """Duplicate collection name is rejected."""
        run("create_application_collection", "--name", "dup")
        code, out = run("create_application_collection", "--name", "dup")
        self.assertNotEqual(code, 0)
        self.assertIn("already exists", out)

    def test_create_application_clash_rejected(self) -> None:
        """Duplicate application name within a collection is rejected."""
        self._seed()
        code, out = run("create_application", "--appcollection", "inv", "--name", "orders")
        self.assertNotEqual(code, 0)
        self.assertIn("already exists", out)

    def test_rename_application_noop_rejected(self) -> None:
        """Renaming an app to the same name in the same collection is rejected."""
        self._seed()
        code, out = run(
            "rename_application",
            "--old-appcollection",
            "inv",
            "--old-name",
            "orders",
            "--new-appcollection",
            "inv",
            "--new-name",
            "orders",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("differ", out)

    def test_rename_application_move_rejected(self) -> None:
        """Moving an app to a different collection is rejected."""
        self._seed()
        run("create_application_collection", "--name", "inv2")
        code, out = run(
            "rename_application",
            "--old-appcollection",
            "inv",
            "--old-name",
            "orders",
            "--new-appcollection",
            "inv2",
            "--new-name",
            "orders2",
        )
        self.assertNotEqual(code, 0)
        self.assertIn("not supported", out)
        # The app must still belong to the original collection.
        self.assertEqual(Application.objects.get(name="orders").application_collection.name, "inv")

    def test_leading_digit_name_rejected(self) -> None:
        """Names starting with a digit are rejected (must start with a letter)."""
        run("create_application_collection", "--name", "inv")
        code, out = run("create_application", "--appcollection", "inv", "--name", "2orders")
        self.assertNotEqual(code, 0)
        self.assertIn("start with a letter", out)
        self.assertFalse(Application.objects.filter(name="2orders").exists())

    def test_create_table_duplicate_column_rejected(self) -> None:
        """Duplicate column names within a create payload are rejected."""
        self._seed()
        payload = {
            "appcollection": "inv",
            "app": "orders",
            "name": "items",
            "columns": [
                {"name": "code", "type": "char"},
                {"name": "code", "type": "char"},
            ],
        }
        code, out = run("create_application_table", "--json-payload", json.dumps(payload))
        self.assertNotEqual(code, 0)
        self.assertIn("Duplicate", out)

    def test_boolean_column_has_no_length_fields(self) -> None:
        """A boolean column accepts only default; extra fields are rejected."""
        self._seed()
        payload = {
            "appcollection": "inv",
            "app": "orders",
            "name": "items",
            "columns": [{"name": "active", "type": "boolean", "default": True, "min_length": 3}],
        }
        code, out = run("create_application_table", "--json-payload", json.dumps(payload))
        self.assertNotEqual(code, 0)
        self.assertIn("extra", out.lower())

    def test_unknown_column_type_rejected(self) -> None:
        """An invalid column type is rejected by the discriminated union."""
        self._seed()
        payload = {
            "appcollection": "inv",
            "app": "orders",
            "name": "items",
            "columns": [{"name": "x", "type": "bogus"}],
        }
        code, _out = run("create_application_table", "--json-payload", json.dumps(payload))
        self.assertNotEqual(code, 0)

    def test_add_existing_column_rejected(self) -> None:
        """Adding a column that already exists is rejected."""
        self._seed()
        run(
            "create_application_table",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "name": "items",
                    "columns": [{"name": "code", "type": "char"}],
                }
            ),
        )
        code, out = run(
            "add_application_table_columns",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "table": "items",
                    "columns": [{"name": "code", "type": "text"}],
                }
            ),
        )
        self.assertNotEqual(code, 0)
        self.assertIn("already exist", out)

    def test_delete_missing_column_rejected(self) -> None:
        """Deleting a column that does not exist is rejected."""
        self._seed()
        run(
            "create_application_table",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "name": "items",
                    "columns": [{"name": "code", "type": "char"}],
                }
            ),
        )
        code, out = run(
            "delete_application_table_columns",
            "--json-payload",
            json.dumps(
                {
                    "appcollection": "inv",
                    "app": "orders",
                    "table": "items",
                    "columns": ["nope"],
                }
            ),
        )
        self.assertNotEqual(code, 0)
        self.assertIn("not found", out)
