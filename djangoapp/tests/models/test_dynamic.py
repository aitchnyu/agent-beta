from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar, cast
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.test import TestCase

from djangoapp.models import (
    Application,
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
    ForeignKeyColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)
from djangoapp.models.dynamic import (
    TableNotFoundError,
    dynamic_db_table,
    dynamic_models,
)

_APP = "OrdersData"


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
    """Shared fixture (OrdersData), registry reset, and physical-DB helpers.

    Subclasses cover a single module's behaviour; this base owns the only
    copy of the cursor helpers so they cannot drift.

    - setUpTestData, seeds the OrdersData app once per class
    - setUp, resets the in-memory dynamic-model registry before each test
    - tearDown, resets the registry again (registrations survive the per-test rollback)
    """

    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.app = Application.objects.create(name=_APP)

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
    - test_duplicate_table_in_app_rejected, app-scoped name clash rejected
    - test_rename_table_keeps_physical_name, table rename leaves physical_name/db_table unchanged
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
            application=_APP, table="items", columns=self._columns_spec()
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
            application=_APP,
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
            application=_APP, table="items", names=["note", "due"]
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
        dynamic_models.delete_application_table(application=_APP, table="items")
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

    def test_duplicate_table_in_app_rejected(self) -> None:
        """App-scoped name clash is rejected before DDL runs."""
        self._make_items()
        with self.assertRaises(ValidationError):
            dynamic_models.create_application_table(
                application=_APP,
                table="items",
                columns=[CharColumn("a", max_length=10)],
            )

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

    def test_resolve_missing_table_raises(self) -> None:
        """TableNotFoundError surfaces for an unknown physical name."""
        with self.assertRaises(TableNotFoundError):
            dynamic_models.get_model("nope1231")

    def test_add_application_table_columns_all_types(self) -> None:
        """Every column type materialises a column; user columns land as `<name>_id` FKs."""
        table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[CharColumn("seed", max_length=10)],
        )
        dynamic_models.add_application_table_columns(
            application=_APP, table="items", columns=_all_column_types()
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
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=10), IntegerColumn("qty")],
        )
        dynamic_models.delete_application_table_columns(
            application=_APP, table="items", names=["qty"]
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
                application=_APP,
                table="items",
                columns=[CharColumn("code", max_length=10)],
            )
            self.assertTrue(table.does_physical_table_exist())
            raise _RollbackError
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())

    def test_add_columns_rolled_back(self) -> None:
        """ALTER TABLE ADD COLUMN reverted, columns absent."""
        table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        before = table.physical_columns()
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.add_application_table_columns(
                application=_APP,
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
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=10), IntegerColumn("qty")],
        )
        before = table.physical_columns()
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.delete_application_table_columns(
                application=_APP, table="items", names=["qty"]
            )
            raise _RollbackError
        table.refresh_from_db()
        self.assertIn("qty", table.column_order)
        self.assertTrue(table.columns.filter(name="qty").exists())
        self.assertEqual(table.physical_columns(), before)

    def test_delete_table_rolled_back(self) -> None:
        """DROP TABLE reverted, physical table still exists."""
        table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.delete_application_table(application=_APP, table="items")
            raise _RollbackError
        self.assertTrue(ApplicationTable.objects.filter(name="items").exists())
        self.assertTrue(table.does_physical_table_exist())

    def test_delete_application_cascade_rolled_back(self) -> None:
        """Cascade drop reverted, tables + physical tables intact."""
        table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        with self.assertRaises(_RollbackError), transaction.atomic():
            dynamic_models.delete_application(self.app)
            raise _RollbackError
        self.assertTrue(Application.objects.filter(name=_APP).exists())
        self.assertTrue(ApplicationTable.objects.filter(name="items").exists())
        self.assertTrue(table.does_physical_table_exist())


class GraphLifecycleTests(DynamicTableTestCase):
    """Application create/rename/delete via the registry.

    Positive behaviour plus the cascade-drop guarantee and the
    cascade-failure safety net (the real reason each method wraps its
    work in ``transaction.atomic()``).

    - test_create_application, app created and queryable
    - test_rename_application, old name gone / new name set (no DDL)
    - test_delete_application_no_tables, no Application row remains after delete
    - test_delete_application_cascades_tables, child physical tables dropped
    - test_delete_application_mid_cascade_failure, failure rolls back the whole graph
    """

    def test_create_application(self) -> None:
        """App created and queryable."""
        app = dynamic_models.create_application(name="BillingData", description="bills")
        self.assertEqual(app.name, "BillingData")
        self.assertEqual(Application.objects.get(name="BillingData").description, "bills")

    def test_rename_application(self) -> None:
        """Old app name is gone and the new one is set (no DDL)."""
        dynamic_models.rename_application(old_name=_APP, new_name="OrdersData2")
        self.assertTrue(Application.objects.filter(name="OrdersData2").exists())
        self.assertFalse(Application.objects.filter(name=_APP).exists())

    def test_delete_application_no_tables(self) -> None:
        """No Application row remains for the app after delete."""
        app = dynamic_models.create_application(name="EphemeralApp")
        dynamic_models.delete_application(app)
        self.assertFalse(Application.objects.filter(name="EphemeralApp").exists())

    def test_delete_application_cascades_tables(self) -> None:
        """Child physical tables dropped."""
        table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        dynamic_models.delete_application(self.app)
        self.assertFalse(Application.objects.filter(name=_APP).exists())
        self.assertFalse(ApplicationTable.objects.filter(name="items").exists())
        self.assertFalse(table.does_physical_table_exist())

    def test_delete_application_mid_cascade_failure(self) -> None:
        """Failure rolls back the whole graph (no half-deleted state)."""
        table = dynamic_models.create_application_table(
            application=_APP,
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
        self.assertTrue(Application.objects.filter(name=_APP).exists())
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
            application=_APP,
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


class ForeignKeyColumnTests(DynamicTableTestCase):
    """Foreign-key columns between tables + the table-graph invariants.

    A ``ForeignKeyColumn`` points one table at another via a
    ``(app, table)`` target; the dynamic field is a Django
    ``ForeignKey(on_delete=RESTRICT)`` referencing the target's immutable
    physical table. Cycles are rejected, referenced tables can't be dropped,
    and multi-table apps are created in dependency order.

    - test_fk_column_creates_physical_reference, FK lands as <name>_id + a ForeignKey field
    - test_fk_column_blocks_deleting_referenced_row, deleting a referenced row raises (RESTRICT)
    - test_self_referential_fk_builds, a table referencing itself builds and round-trips a parent
    - test_forward_reference_topo_ordered, a referencer declared before its target still installs
    - test_add_fk_column_to_existing_target, adds a FK to an existing table
    - test_cycle_rejected_on_create, mutually-referencing tables rejected with a readable cycle
    - test_cycle_rejected_on_add_column, an FK that closes a cycle is rejected with a cycle message
    - test_drop_referenced_table_refused, dropping a referenced table raises; referencer drops fine
    - test_delete_application_with_internal_fk, an app whose tables cross-reference deletes cleanly
    """

    def _table(self, app: str, name: str) -> ApplicationTable:
        """Fetch an ApplicationTable row by app + table name."""
        return ApplicationTable.objects.get(
            application__name=app,
            name=name,
        )

    def test_fk_column_creates_physical_reference(self) -> None:
        """Cross-table FK materialises as a ``<name>_id`` column and a ForeignKey field."""
        dynamic_models.create_application(
            name="FkTargetApp",
            tables={
                "target": [CharColumn("code", max_length=10)],
                "ref": [ForeignKeyColumn("link", target=("FkTargetApp", "target"))],
            },
        )
        ref = self._table("FkTargetApp", "ref")
        self.assertIn("link_id", ref.physical_columns())
        model = cast(Any, ref.as_model())
        self.assertIsInstance(model._meta.get_field("link"), models.ForeignKey)
        # The FK stores the target row's pk; setting it via the ORM round-trips.
        target_model = cast(Any, self._table("FkTargetApp", "target").as_model())
        target = target_model.objects.create(code="A")
        created = cast(Any, model.objects.create(link=target))
        self.assertEqual(cast(Any, created.link_id), target.pk)

    def test_fk_column_blocks_deleting_referenced_row(self) -> None:
        """Deleting a row another row points at raises (on_delete=RESTRICT backstop)."""
        dynamic_models.create_application(
            name="RestrictApp",
            tables={
                "target": [CharColumn("code", max_length=10)],
                "ref": [ForeignKeyColumn("link", target=("RestrictApp", "target"))],
            },
        )
        target_model = cast(Any, self._table("RestrictApp", "target").as_model())
        ref_model = cast(Any, self._table("RestrictApp", "ref").as_model())
        target = target_model.objects.create(code="A")
        ref_model.objects.create(link=target)
        with self.assertRaises(models.RestrictedError):
            target.delete()

    def test_self_referential_fk_builds(self) -> None:
        """A table referencing itself builds (to='self') and round-trips a parent row."""
        dynamic_models.create_application(
            name="TreeAppDemo",
            tables={
                "nodes": [
                    CharColumn("name", max_length=10),
                    ForeignKeyColumn("parent", target=("TreeAppDemo", "nodes"), nullable=True),
                ]
            },
        )
        model = cast(Any, self._table("TreeAppDemo", "nodes").as_model())
        root = model.objects.create(name="root", parent=None)
        child = model.objects.create(name="child", parent=root)
        fetched = model.objects.get(pk=child.pk)
        self.assertEqual(cast(Any, fetched.parent_id), root.pk)

    def test_forward_reference_topo_ordered(self) -> None:
        """A referencer declared before its target installs (target created first)."""
        dynamic_models.create_application(
            name="FwdRefTest",
            tables={
                # "ref" is declared first but depends on "target"; topo order
                # must create "target" before "ref"'s create_model runs.
                "ref": [ForeignKeyColumn("link", target=("FwdRefTest", "target"), nullable=True)],
                "target": [CharColumn("code", max_length=10)],
            },
        )
        ref = self._table("FwdRefTest", "ref")
        self.assertIn("link_id", ref.physical_columns())

    def test_add_fk_column_to_existing_target(self) -> None:
        """add_application_table_columns adds a FK to an already-existing target table."""
        dynamic_models.create_application(
            name="AddColumnApp",
            tables={"target": [CharColumn("code", max_length=10)]},
        )
        # A second table created standalone, then given a FK to "target".
        dynamic_models.create_application_table(
            application="AddColumnApp",
            table="ref",
            columns=[CharColumn("note", max_length=10)],
        )
        dynamic_models.add_application_table_columns(
            application="AddColumnApp",
            table="ref",
            columns=[ForeignKeyColumn("link", target=("AddColumnApp", "target"), nullable=True)],
        )
        self.assertIn("link_id", self._table("AddColumnApp", "ref").physical_columns())

    def test_cycle_rejected_on_create(self) -> None:
        """Two tables that reference each other are rejected with a readable cycle path."""
        with self.assertRaises(ValidationError) as ctx:
            dynamic_models.create_application(
                name="CycleAppOne",
                tables={
                    "alpha": [ForeignKeyColumn("b", target=("CycleAppOne", "beta"))],
                    "beta": [ForeignKeyColumn("a", target=("CycleAppOne", "alpha"))],
                },
            )
        self.assertIn("foreign-key cycle", "; ".join(ctx.exception.messages))
        self.assertIn("alpha", "; ".join(ctx.exception.messages))

    def test_cycle_rejected_on_add_column(self) -> None:
        """An FK added via add_columns that closes a cycle is rejected with a cycle message."""
        dynamic_models.create_application(
            name="CycleAppTwo",
            tables={
                "alpha": [CharColumn("code", max_length=5)],
                "beta": [ForeignKeyColumn("a", target=("CycleAppTwo", "alpha"))],
            },
        )
        with self.assertRaises(ValidationError) as ctx:
            dynamic_models.add_application_table_columns(
                application="CycleAppTwo",
                table="alpha",
                columns=[ForeignKeyColumn("back", target=("CycleAppTwo", "beta"))],
            )
        self.assertIn("foreign-key cycle", "; ".join(ctx.exception.messages))

    def test_drop_referenced_table_refused(self) -> None:
        """Dropping a referenced table raises; the referencer drops fine."""
        dynamic_models.create_application(
            name="DropAppDemo",
            tables={
                "target": [CharColumn("code", max_length=5)],
                "ref": [ForeignKeyColumn("link", target=("DropAppDemo", "target"))],
            },
        )
        with self.assertRaises(ValidationError):
            dynamic_models.delete_application_table(application="DropAppDemo", table="target")
        # The referencer (nothing references it) drops cleanly, and then so does
        # the now-unreferenced target.
        dynamic_models.delete_application_table(application="DropAppDemo", table="ref")
        dynamic_models.delete_application_table(application="DropAppDemo", table="target")

    def test_delete_application_with_internal_fk(self) -> None:
        """An app whose own tables cross-reference deletes cleanly (internal refs ignored)."""
        app = dynamic_models.create_application(
            name="DeleteAppOne",
            tables={
                "target": [CharColumn("code", max_length=5)],
                "ref": [ForeignKeyColumn("link", target=("DeleteAppOne", "target"))],
            },
        )
        dynamic_models.delete_application(app)
        self.assertFalse(Application.objects.filter(pk=app.pk).exists())
        self.assertFalse(ApplicationTable.objects.filter(application__name="DeleteAppOne").exists())
