from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar, cast

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase

from djangoapp.models import (
    Application,
    ApplicationCollection,
    ApplicationTable,
    ApplicationTableColumn,
)
from djangoapp.models.dynamic import (
    TableNotFoundError,
    dynamic_db_table,
    dynamic_models,
)


class DynamicSchemaTests(TestCase):
    """Physical-table lifecycle for application tables via schema_editor.

    Verifies create/add/delete of tables and columns really alters the
    Postgres table, that column_order tracks the changes, that the generated
    dynamic model can query its rows, and that renames never touch the
    physical table (names are immutable).

    - test_create_table_creates_physical_table_and_model, CREATE TABLE + model fields present
    - test_create_table_with_all_column_types, every column type maps to a usable field
    - test_add_columns_alters_table_and_order, ALTER TABLE ADD COLUMN + column_order append
    - test_delete_columns_alters_table_and_order, ALTER TABLE DROP COLUMN + column_order trim
    - test_delete_table_drops_physical_table, DROP TABLE + definition rows removed
    - test_dynamic_model_supports_row_roundtrip, generated model can insert/read a row
    - test_duplicate_table_in_collection_rejected, collection-scoped name clash rejected
    - test_rename_table_keeps_physical_name, table rename leaves physical_name/db_table unchanged
    - test_rename_collection_keeps_physical_name, collection rename leaves physical tables intact
    - test_resolve_missing_table_raises, TableNotFoundError for an unknown physical name
    """

    collection: ClassVar[ApplicationCollection]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.collection = ApplicationCollection.objects.create(name="inv")
        cls.app = cls.collection.applications.create(name="orders")

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _columns_spec(self) -> list[dict[str, object]]:
        return [
            {"name": "code", "type": "char", "default": "X", "max_length": 10},
            {"name": "qty", "type": "integer", "default": 1, "nullable": True},
            {
                "name": "price",
                "type": "decimal",
                "default": "1.50",
                "max_digits": 8,
                "decimal_places": 2,
            },
            {"name": "active", "type": "boolean", "default": True},
            {"name": "note", "type": "text"},
            {"name": "due", "type": "datetime", "nullable": True},
        ]

    def _table_exists(self, db_table: str) -> bool:
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [db_table])
            return cur.fetchone()[0] is not None

    def _table_columns(self, db_table: str) -> list[str]:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                [db_table],
            )
            return [r[0] for r in cur.fetchall()]

    def _make_items(self) -> ApplicationTable:
        return dynamic_models.create_application_table(
            "inv", "orders", "items", self._columns_spec()
        )

    def test_create_table_creates_physical_table_and_model(self) -> None:
        """CREATE TABLE issued, model registered, column_order set, physical_name set."""
        table = self._make_items()
        db_table = dynamic_db_table(table.physical_name)
        self.assertTrue(self._table_exists(db_table))
        model = dynamic_models.get_model(table.physical_name)
        self.assertEqual(model._meta.db_table, db_table)
        # physical_name is <name><seconds><n>, i.e. starts with the table name.
        self.assertTrue(table.physical_name.startswith("items"))
        self.assertEqual(table.column_order, ["code", "qty", "price", "active", "note", "due"])

    def test_create_table_with_all_column_types(self) -> None:
        """Every column type maps to a real column in the physical table."""
        table = self._make_items()
        cols = set(self._table_columns(dynamic_db_table(table.physical_name)))
        # Built-in underscore-prefixed columns plus user columns.
        for user_col in [
            "code",
            "qty",
            "price",
            "active",
            "note",
            "due",
            "_public_id",
            "_created_by_id",
            "_created_at",
            "_edited_at",
        ]:
            with self.subTest(col=user_col):
                self.assertIn(user_col, cols)

    def test_add_columns_alters_table_and_order(self) -> None:
        """ALTER TABLE ADD COLUMN adds the column and appends to column_order."""
        table = self._make_items()
        dynamic_models.add_application_table_columns(
            "inv", "orders", "items", [{"name": "region", "type": "char", "max_length": 5}]
        )
        cols = self._table_columns(dynamic_db_table(table.physical_name))
        self.assertIn("region", cols)
        table.refresh_from_db()
        self.assertEqual(table.column_order[-1], "region")

    def test_delete_columns_alters_table_and_order(self) -> None:
        """ALTER TABLE DROP COLUMN removes the column and trims column_order."""
        table = self._make_items()
        dynamic_models.delete_application_table_columns("inv", "orders", "items", ["note", "due"])
        cols = self._table_columns(dynamic_db_table(table.physical_name))
        self.assertNotIn("note", cols)
        self.assertNotIn("due", cols)
        table.refresh_from_db()
        self.assertNotIn("note", table.column_order)
        self.assertNotIn("due", table.column_order)

    def test_delete_table_drops_physical_table(self) -> None:
        """DROP TABLE removes the physical table and all definition rows."""
        table = self._make_items()
        db_table = dynamic_db_table(table.physical_name)
        self.assertTrue(self._table_exists(db_table))
        dynamic_models.delete_application_table("inv", "orders", "items")
        self.assertFalse(self._table_exists(db_table))
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())
        self.assertFalse(
            ApplicationTableColumn.objects.filter(application_table__name="items").exists()
        )

    def test_dynamic_model_supports_row_roundtrip(self) -> None:
        """Generated model can insert and read back a row through ORM."""
        table = self._make_items()
        # The dynamic model is a runtime-built concrete model; cast lets the
        # test exercise its manager/fields without per-access type: ignores.
        model = cast(Any, dynamic_models.get_model(table.physical_name))
        obj = model.objects.create(code="A1", qty=3, price=Decimal("2.00"), active=True, note="hi")
        refreshed = model.objects.get(_public_id=obj._public_id)
        self.assertEqual(refreshed.code, "A1")
        self.assertEqual(refreshed.qty, 3)

    def test_duplicate_table_in_collection_rejected(self) -> None:
        """Collection-scoped name clash is rejected before DDL runs."""
        self._make_items()
        # A second app in the same collection must not be able to reuse the name.
        other = self.collection.applications.create(name="other")
        with self.assertRaises(ValidationError):
            dynamic_models.create_application_table(
                "inv", "other", "items", [{"name": "a", "type": "char"}]
            )
        self.assertFalse(other.tables.filter(name="items").exists())

    def test_rename_table_keeps_physical_name(self) -> None:
        """Renaming a table changes only the display name; physical table is untouched."""
        table = self._make_items()
        db_table = dynamic_db_table(table.physical_name)
        dynamic_models.rename_application_table(table, "items2")
        table.refresh_from_db()
        self.assertEqual(table.name, "items2")
        self.assertTrue(table.physical_name.startswith("items"))  # unchanged prefix
        self.assertEqual(dynamic_db_table(table.physical_name), db_table)  # physical table intact
        self.assertTrue(self._table_exists(db_table))

    def test_rename_collection_keeps_physical_name(self) -> None:
        """Renaming a collection changes no physical table (keyed by physical_name)."""
        table = self._make_items()
        db_table = dynamic_db_table(table.physical_name)
        dynamic_models.rename_application_collection(self.collection, "inv2")
        table.refresh_from_db()
        self.assertEqual(self.collection.name, "inv2")
        self.assertTrue(self._table_exists(db_table))  # physical table intact
        # The dynamic model still resolves and counts rows.
        model = cast(Any, dynamic_models.get_model(table.physical_name))
        self.assertEqual(model.objects.count(), 0)

    def test_resolve_missing_table_raises(self) -> None:
        """TableNotFoundError surfaces for an unknown physical name."""
        with self.assertRaises(TableNotFoundError):
            dynamic_models.get_model("nope1231")
