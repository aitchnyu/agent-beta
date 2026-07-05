from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar, cast
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from djangoapp.models import (
    Application,
    ApplicationCollection,
    ApplicationTable,
    ApplicationTableColumn,
    User,
)
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    Column,
    DateTimeColumn,
    DecimalColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)
from djangoapp.models.dynamic import (
    TableNotFoundError,
    dynamic_db_table,
    dynamic_models,
)


class _RollbackError(Exception):
    """Sentinel raised inside a savepoint to force it to roll back."""


def _all_column_types() -> list[Column]:
    """One Column per ColumnType, minimal fields."""
    return [
        CharColumn("code", max_length=10),
        TextColumn("note"),
        IntegerColumn("qty", default=1, nullable=True),
        BooleanColumn("active", default=True),
        DecimalColumn("price", max_digits=8, decimal_places=2, default="1.50"),
        DateTimeColumn("due", nullable=True),
        UserColumn("owner", nullable=True),
    ]


class DynamicTableTestCase(TestCase):
    """Shared fixture (inv/orders), registry reset, and physical-DB helpers.

    Subclasses cover a single module's behaviour; this base owns the only
    copy of the cursor helpers so they cannot drift.

    - setUpTestData, seeds the inv collection + orders app once per class
    - setUp, resets the in-memory dynamic-model registry before each test
    - tearDown, resets the registry again (registrations survive the per-test rollback)
    """

    collection: ClassVar[ApplicationCollection]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.collection = ApplicationCollection.objects.create(name="inv")
        cls.app = cls.collection.applications.create(
            name="orders",
        )

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()


class DynamicSchemaTests(DynamicTableTestCase):
    """Physical-table lifecycle for application tables via schema_editor (positive).

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
    - test_add_application_table_columns_all_types, every type materialises a column (user as _id)
    - test_delete_columns_removes_definition_and_physical, gone from definition + physical table
    """

    def _columns_spec(self) -> list[Column]:
        return [
            CharColumn("code", default="X", max_length=10),
            IntegerColumn("qty", default=1, nullable=True),
            DecimalColumn("price", max_digits=8, decimal_places=2, default="1.50"),
            BooleanColumn("active", default=True),
            TextColumn("note"),
            DateTimeColumn("due", nullable=True),
        ]

    def _make_items(self) -> ApplicationTable:
        return dynamic_models.create_application_table(
            collection="inv", application="orders", table="items", columns=self._columns_spec()
        )

    def test_create_table_creates_physical_table_and_model(self) -> None:
        """CREATE TABLE issued, model registered, column_order set, physical_name set."""
        table = self._make_items()
        self.assertTrue(table.does_physical_table_exist())
        db_table = dynamic_db_table(table.physical_name)
        model = dynamic_models.get_model(table.physical_name)
        self.assertEqual(model._meta.db_table, db_table)
        # physical_name is <name><seconds><n>, i.e. starts with the table name.
        self.assertTrue(table.physical_name.startswith("items"))
        self.assertEqual(table.column_order, ["code", "qty", "price", "active", "note", "due"])

    def test_create_table_with_all_column_types(self) -> None:
        """Every column type maps to a real column in the physical table."""
        table = self._make_items()
        cols = set(table.physical_columns())
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
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("region", max_length=5)],
        )
        self.assertIn("region", table.physical_columns())
        table.refresh_from_db()
        self.assertEqual(table.column_order[-1], "region")

    def test_delete_columns_alters_table_and_order(self) -> None:
        """ALTER TABLE DROP COLUMN removes the column and trims column_order."""
        table = self._make_items()
        dynamic_models.delete_application_table_columns(
            collection="inv", application="orders", table="items", names=["note", "due"]
        )
        cols = table.physical_columns()
        self.assertNotIn("note", cols)
        self.assertNotIn("due", cols)
        table.refresh_from_db()
        self.assertNotIn("note", table.column_order)
        self.assertNotIn("due", table.column_order)

    def test_delete_table_drops_physical_table(self) -> None:
        """DROP TABLE removes the physical table and all definition rows."""
        table = self._make_items()
        self.assertTrue(table.does_physical_table_exist())
        dynamic_models.delete_application_table(
            collection="inv", application="orders", table="items"
        )
        self.assertFalse(table.does_physical_table_exist())
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())
        self.assertFalse(
            ApplicationTableColumn.objects.filter(application_table__name="items").exists()
        )

    def test_dynamic_model_supports_row_roundtrip(self) -> None:
        """Generated model can insert and read back a row through ORM."""
        table = self._make_items()
        # The dynamic model is a runtime-built concrete model; cast lets the
        # test exercise its manager/fields without per-access type: ignores.
        model = cast(Any, table.as_model())
        obj = model.objects.create(code="A1", qty=3, price=Decimal("2.00"), active=True, note="hi")
        refreshed = model.objects.get(_public_id=obj._public_id)
        self.assertEqual(refreshed.code, "A1")
        self.assertEqual(refreshed.qty, 3)

    def test_duplicate_table_in_collection_rejected(self) -> None:
        """Collection-scoped name clash is rejected before DDL runs."""
        self._make_items()
        # A second app in the same collection must not be able to reuse the name.
        other = self.collection.applications.create(
            name="other",
        )
        with self.assertRaises(ValidationError):
            dynamic_models.create_application_table(
                collection="inv",
                application="other",
                table="items",
                columns=[CharColumn("a", max_length=10)],
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
        self.assertTrue(table.does_physical_table_exist())

    def test_rename_collection_keeps_physical_name(self) -> None:
        """Renaming a collection changes no physical table (keyed by physical_name)."""
        table = self._make_items()
        dynamic_models.rename_application_collection(self.collection, "inv2")
        table.refresh_from_db()
        self.assertEqual(self.collection.name, "inv2")
        self.assertTrue(table.does_physical_table_exist())  # physical table intact
        # The dynamic model still resolves and counts rows.
        model = cast(Any, table.as_model())
        self.assertEqual(model.objects.count(), 0)

    def test_resolve_missing_table_raises(self) -> None:
        """TableNotFoundError surfaces for an unknown physical name."""
        with self.assertRaises(TableNotFoundError):
            dynamic_models.get_model("nope1231")

    def test_add_application_table_columns_all_types(self) -> None:
        """Every column type materialises a column; user columns land as `<name>_id` FKs."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("seed", max_length=10)],
        )
        dynamic_models.add_application_table_columns(
            collection="inv", application="orders", table="items", columns=_all_column_types()
        )
        table.refresh_from_db()
        for name in [c.name for c in _all_column_types()]:
            self.assertIn(name, table.column_order)
            self.assertTrue(table.columns.filter(name=name).exists())
        cols = set(table.physical_columns())
        for spec in _all_column_types():
            # user columns materialise as a FK column ("<name>_id").
            expected = f"{spec.name}_id" if spec.column_type.value == "user" else spec.name
            self.assertIn(expected, cols)

    def test_delete_columns_removes_definition_and_physical(self) -> None:
        """Columns gone from both the ApplicationTableColumn rows and the physical table."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10), IntegerColumn("qty")],
        )
        dynamic_models.delete_application_table_columns(
            collection="inv", application="orders", table="items", names=["qty"]
        )
        table.refresh_from_db()
        self.assertEqual(table.column_order, ["code"])
        self.assertFalse(table.columns.filter(name="qty").exists())
        self.assertNotIn("qty", table.physical_columns())


class TransactionalDDLRollbackTests(DynamicTableTestCase):
    """schema_editor ops issued inside a savepoint roll back on Postgres.

    Each test runs a DDL mutation inside ``transaction.atomic()`` and raises
    to roll the savepoint back, then asserts the *physical* DB reverted —
    not just the ORM rows. This pins transactional DDL, the property every
    schema mutation in the module relies on.

    - test_create_table_rolled_back, CREATE TABLE + definition rows gone after rollback
    - test_add_columns_rolled_back, ALTER TABLE ADD COLUMN reverted, columns absent
    - test_delete_columns_rolled_back, ALTER TABLE DROP COLUMN reverted, columns restored
    - test_delete_table_rolled_back, DROP TABLE reverted, physical table still exists
    - test_delete_application_cascade_rolled_back, cascade drop reverted, tables intact
    """

    def test_create_table_rolled_back(self) -> None:
        """CREATE TABLE + definition rows gone after rollback."""
        with self.assertRaises(_RollbackError), transaction.atomic():
            table = dynamic_models.create_application_table(
                collection="inv",
                application="orders",
                table="items",
                columns=[CharColumn("code", max_length=10)],
            )
            self.assertTrue(table.does_physical_table_exist())
            raise _RollbackError
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())

    def test_add_columns_rolled_back(self) -> None:
        """ALTER TABLE ADD COLUMN reverted, columns absent."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        before = table.physical_columns()
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.add_application_table_columns(
                collection="inv",
                application="orders",
                table="items",
                columns=[IntegerColumn("qty")],
            )
            raise _RollbackError
        table.refresh_from_db()
        self.assertNotIn("qty", table.column_order)
        self.assertFalse(table.columns.filter(name="qty").exists())
        self.assertEqual(table.physical_columns(), before)

    def test_delete_columns_rolled_back(self) -> None:
        """ALTER TABLE DROP COLUMN reverted, columns restored."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10), IntegerColumn("qty")],
        )
        before = table.physical_columns()
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.delete_application_table_columns(
                collection="inv", application="orders", table="items", names=["qty"]
            )
            raise _RollbackError
        table.refresh_from_db()
        self.assertIn("qty", table.column_order)
        self.assertTrue(table.columns.filter(name="qty").exists())
        self.assertEqual(table.physical_columns(), before)

    def test_delete_table_rolled_back(self) -> None:
        """DROP TABLE reverted, physical table still exists."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.delete_application_table(
                collection="inv", application="orders", table="items"
            )
            raise _RollbackError
        self.assertTrue(ApplicationTable.objects.filter(name="items").exists())
        self.assertTrue(table.does_physical_table_exist())

    def test_delete_application_cascade_rolled_back(self) -> None:
        """Cascade drop reverted, tables + physical tables intact."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.delete_application(self.app)
            raise _RollbackError
        self.assertTrue(Application.objects.filter(name="orders").exists())
        self.assertTrue(ApplicationTable.objects.filter(name="items").exists())
        self.assertTrue(table.does_physical_table_exist())


class GraphLifecycleTests(DynamicTableTestCase):
    """Collection/application create/rename/delete via the registry.

    Positive behaviour plus the cascade-drop guarantee and the
    cascade-failure safety net (the real reason each method wraps its
    work in ``transaction.atomic()``).

    - test_create_application_collection, collection carries the name and is queryable
    - test_rename_application_collection, name updated, no physical change
    - test_delete_application_collection_empty, no row remains for an app-less collection
    - test_delete_application_collection_non_empty_refused, non-empty raises and untouched
    - test_create_application, app created under the right collection
    - test_rename_application, old name gone / new name set within its collection (no DDL)
    - test_delete_application_no_tables, no Application row remains after delete
    - test_delete_application_cascades_tables, child physical tables dropped
    - test_delete_application_mid_cascade_failure, failure rolls back the whole graph
    """

    def test_create_application_collection(self) -> None:
        """Returned collection carries the name and is queryable by it."""
        collection = dynamic_models.create_application_collection("inventory")
        self.assertEqual(collection.name, "inventory")
        self.assertTrue(ApplicationCollection.objects.filter(name="inventory").exists())

    def test_rename_application_collection(self) -> None:
        """Name updated, no physical change."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        dynamic_models.rename_application_collection(self.collection, "inventory")
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.name, "inventory")
        # Display-name rename must not touch the physical table.
        self.assertTrue(table.does_physical_table_exist())

    def test_delete_application_collection_empty(self) -> None:
        """An app-less collection has no row after delete."""
        empty = dynamic_models.create_application_collection("ephemeral")
        dynamic_models.delete_application_collection(empty)
        self.assertFalse(ApplicationCollection.objects.filter(name="ephemeral").exists())

    def test_delete_application_collection_non_empty_refused(self) -> None:
        """non-empty raises and untouched."""
        with self.assertRaises(ValidationError):
            dynamic_models.delete_application_collection(self.collection)
        self.assertTrue(ApplicationCollection.objects.filter(name="inv").exists())
        self.assertTrue(Application.objects.filter(name="orders").exists())

    def test_create_application(self) -> None:
        """App created under the right collection."""
        app = dynamic_models.create_application(
            collection="inv", name="billing", description="bills"
        )
        self.assertEqual(app.name, "billing")
        self.assertEqual(app.application_collection, self.collection)
        self.assertEqual(Application.get_by_names("inv", "billing").description, "bills")

    def test_rename_application(self) -> None:
        """Old app name is gone and the new one is set, within its own collection (no DDL)."""
        dynamic_models.rename_application(collection="inv", old_name="orders", new_name="orders2")
        self.assertTrue(Application.objects.filter(name="orders2").exists())
        self.assertFalse(Application.objects.filter(name="orders").exists())

    def test_delete_application_no_tables(self) -> None:
        """No Application row remains for the app after delete."""
        app = dynamic_models.create_application(collection="inv", name="ephemeral")
        dynamic_models.delete_application(app)
        self.assertFalse(Application.objects.filter(name="ephemeral").exists())

    def test_delete_application_cascades_tables(self) -> None:
        """Child physical tables dropped."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        dynamic_models.delete_application(self.app)
        self.assertFalse(Application.objects.filter(name="orders").exists())
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())
        self.assertFalse(table.does_physical_table_exist())

    def test_delete_application_mid_cascade_failure(self) -> None:
        """Failure rolls back the whole graph (no half-deleted state)."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        # The cascade calls the instance-based _drop_application_table, so
        # patch that to force a mid-cascade failure.
        with (
            patch.object(
                dynamic_models,
                "_drop_application_table",
                side_effect=RuntimeError("boom"),
            ),
            self.assertRaises(RuntimeError),
        ):
            dynamic_models.delete_application(self.app)
        # The atomic block must roll back: app + table + physical table intact.
        self.assertTrue(Application.objects.filter(name="orders").exists())
        self.assertTrue(ApplicationTable.objects.filter(name="items").exists())
        self.assertTrue(table.does_physical_table_exist())


class RowLifecycleTests(DynamicTableTestCase):
    """CRUD on rows via the fetched dynamic model.

    - test_inserted_row_is_readable, created row matches the values via the model manager
    - test_saved_changes_persist_on_update, re-fetched row reflects the mutated field
    - test_deleted_row_is_absent_from_queryset, pk-filter returns empty after delete
    """

    user: ClassVar[User]
    table: ApplicationTable

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(username="owner")

    def setUp(self) -> None:
        super().setUp()
        self.table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10), UserColumn("owner", nullable=True)],
        )

    def test_inserted_row_is_readable(self) -> None:
        """Fetched row matches the created values via the generated model's manager."""
        # The dynamic model is a runtime-built concrete model; cast lets the
        # test exercise its manager/fields without per-access type: ignores.
        model = cast(Any, self.table.as_model())
        row = model.objects.create(code="A1", owner=self.user)
        fetched = model.objects.get(pk=row.pk)
        self.assertEqual(fetched.code, "A1")
        self.assertEqual(fetched.owner_id, self.user.id)

    def test_saved_changes_persist_on_update(self) -> None:
        """A re-fetched row reflects the mutated field after save (not a stale read)."""
        model = cast(Any, self.table.as_model())
        row = model.objects.create(code="A1")
        row.code = "B2"
        row.save()
        self.assertEqual(model.objects.get(pk=row.pk).code, "B2")

    def test_deleted_row_is_absent_from_queryset(self) -> None:
        """A pk-filter for the deleted row returns empty (delete is a real DB remove)."""
        model = cast(Any, self.table.as_model())
        row = model.objects.create(code="A1")
        row.delete()
        self.assertFalse(model.objects.filter(pk=row.pk).exists())
