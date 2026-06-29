"""Dynamic-model generation and schema operations for application tables.

Each ``ApplicationTable`` is materialised as a real Django model class
(subclassing ``BaseTable``) whose ``db_table`` is
``zz_<physical_name>``, where ``physical_name`` is the table's immutable
creation-time identifier (``<tablename><unix-seconds>``). Collection and
table display-name renames therefore never touch the physical table.
Table creation, column add/remove and table deletion all go through
``connection.schema_editor()`` (Baserow-style), so the underlying Postgres
table is altered in place without Django migrations.

All of this state lives on a single :class:`DynamicModelRegistry` instance
(``dynamic_models``). It owns the model cache and is the **only** way to
retrieve a generated model (``dynamic_models.get_model``). Every operation
that changes a model's field set (create table, add/remove columns,
delete table) calls :meth:`DynamicModelRegistry.reset` so the next
``get_model`` rebuilds from the live columns. Display-name renames never
reset (the cache key, ``physical_name``, is immutable).
"""

from __future__ import annotations

import contextlib
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import connection, models, transaction
from django.db.models.base import ModelBase
from django.db.utils import ProgrammingError

from djangoapp.models.applications import (
    Application,
    ApplicationCollection,
    ApplicationTable,
    ApplicationTableColumn,
    BaseTable,
    ColumnType,
)
from djangoapp.models.base import User

if TYPE_CHECKING:
    from collections.abc import Callable


class TableNotFoundError(Exception):
    """Raised when no Application/ApplicationTable matches the given names."""


def dynamic_db_table(physical_name: str) -> str:
    """Physical Postgres table name for a table's immutable physical_name."""
    return f"zz_{physical_name}"


def _dynamic_class_name(physical_name: str) -> str:
    """Python class name for the generated model: ``<Physicalname>DynamicModel``.

    Capitalises the first character of the immutable ``physical_name`` and
    appends ``DynamicModel``. Keys on ``physical_name`` (not on display
    names) so collection/table renames never change the generated class
    name. Note this is not full PascalCase/camel-casing — ``physical_name``
    is ``<letters><digits>``, so only the leading letter is uppercased.
    """
    return physical_name[:1].upper() + physical_name[1:] + "DynamicModel"


def _char_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.CharField(
        max_length=col.text_max_length,
        default=col.text_default,
        blank=True,
        choices=[(c, c) for c in col.char_choices] or None,
        validators=[
            MinLengthValidator(col.text_min_length),
            MaxLengthValidator(col.text_max_length),
        ],
    )


def _text_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.TextField(
        default=col.text_default,
        blank=True,
        validators=[
            MinLengthValidator(col.text_min_length),
            MaxLengthValidator(col.text_max_length),
        ],
    )


def _integer_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.IntegerField(default=col.int_default, null=col.nullable, blank=col.nullable)


def _boolean_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.BooleanField(default=col.boolean_default)


def _decimal_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.DecimalField(
        max_digits=col.decimal_max_digits,
        decimal_places=col.decimal_places,
        default=col.decimal_default,
        null=col.nullable,
        blank=col.nullable,
    )


def _datetime_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.DateTimeField(null=col.nullable, blank=col.nullable)


def _user_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    return models.ForeignKey(
        User,
        null=col.nullable,
        blank=col.nullable,
        on_delete=models.RESTRICT,
        related_name="+",
    )


# Dispatch table keeps _column_field to a single return statement.
_COLUMN_FIELD_BUILDERS: dict[str, Callable[[ApplicationTableColumn], models.Field[Any, Any]]] = {
    ColumnType.CHAR: _char_field,
    ColumnType.TEXT: _text_field,
    ColumnType.INTEGER: _integer_field,
    ColumnType.BOOLEAN: _boolean_field,
    ColumnType.DECIMAL: _decimal_field,
    ColumnType.DATETIME: _datetime_field,
    ColumnType.USER: _user_field,
}


def _column_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    """Build the Django field that realises a single column definition."""
    builder = _COLUMN_FIELD_BUILDERS.get(col.type)
    if builder is None:
        msg = f"Unknown column type: {col.type}"
        raise ValueError(msg)
    return builder(col)


class DynamicModelRegistry:
    """Owns the dynamic-model cache and is the sole retrieval point.

    Generated model classes are cached by the table's immutable
    ``physical_name`` and registered in Django's app registry; column
    mutations invalidate both so the next :meth:`get_model` rebuilds from
    live columns. Collection/table display-name renames never touch the
    cache (the key is immutable).
    """

    def __init__(self) -> None:
        self._cache: dict[str, type[BaseTable]] = {}

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_model(self, physical_name: str) -> type[BaseTable]:
        """Return the dynamic model for a table, building+caching it once.

        The single entry point for retrieving a generated model. Keyed on the
        table's immutable ``physical_name``. Raises ``TableNotFoundError`` if
        no such table exists.
        """
        cached = self._cache.get(physical_name)
        if cached is not None:
            return cached
        class_name = _dynamic_class_name(physical_name)
        existing = self._existing_registered(class_name)
        if existing is not None:
            # A registration survived a reset (e.g. after a column mutation);
            # reuse it instead of rebuilding to avoid a re-registration error.
            self._cache[physical_name] = existing  # type: ignore[assignment] # registry holds concrete models
            return existing  # type: ignore[return-value]
        model = self._build_model_class(physical_name)
        self._cache[physical_name] = model
        return model

    # ------------------------------------------------------------------
    # Build / registry plumbing
    # ------------------------------------------------------------------

    def _existing_registered(
        self, class_name: str
    ) -> type[models.Model] | None:  # registry-owned lookup, self unused
        return apps.all_models["djangoapp"].get(class_name.lower())

    def _build_model_class(
        self,
        physical_name: str,  # registry plumbing, self unused
    ) -> type[BaseTable]:
        """Construct and register a fresh dynamic model for the given table.

        Always reads the current column set from the DB, so callers get a
        class whose fields match the live table.
        """
        try:
            table = ApplicationTable.objects.get(physical_name=physical_name)
        except ApplicationTable.DoesNotExist as exc:
            msg = f"No table with physical_name '{physical_name}'."
            raise TableNotFoundError(msg) from exc
        columns = list(table.columns.all())
        attrs: dict[str, Any] = {}
        for col in columns:
            attrs[col.name] = _column_field(col)

        class Meta:
            db_table = dynamic_db_table(physical_name)
            app_label = "djangoapp"

        attrs["Meta"] = Meta
        attrs["__module__"] = "djangoapp.models.dynamic"

        class_name = _dynamic_class_name(physical_name)
        model = ModelBase(class_name, (BaseTable,), attrs)
        return cast("type[BaseTable]", model)

    def reset(self) -> None:
        """Clear the cache and unregister every dynamic model.

        Called after any *field-set-changing* schema mutation (create table,
        add/remove columns, delete table) and between tests. It is
        intentionally broad — wipe everything and let the next
        ``get_model`` rebuild from the live DB — because correctness is
        simpler and safer than surgically invalidating one model, and the
        rebuild cost is acceptable here. Display-name renames do **not**
        call this (the cache key ``physical_name`` is immutable, so a
        renamed table's cached class stays valid).

        TestCase wraps each test in a transaction, so physical tables are
        rolled back, but the in-memory model registrations survive across
        tests and would collide on the next build; reset returns the
        registry to a clean slate.
        """
        self._cache.clear()
        # Sweep every dynamic registration (class names end in "DynamicModel").
        registry = apps.all_models["djangoapp"]
        for model_name in [n for n in list(registry) if n.endswith("dynamicmodel")]:
            registry.pop(model_name, None)

    # ------------------------------------------------------------------
    # DB resolvers (stateless)
    # ------------------------------------------------------------------

    def _resolve_collection(
        self,
        appcollection: str,  # registry-owned lookup, self unused
    ) -> ApplicationCollection:
        try:
            return ApplicationCollection.objects.get(name=appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No application collection '{appcollection}'."
            raise TableNotFoundError(msg) from exc

    def _resolve_application(self, appcollection: str, app: str) -> Application:
        collection = self._resolve_collection(appcollection)
        try:
            return Application.objects.get(application_collection=collection, name=app)
        except Application.DoesNotExist as exc:
            msg = f"No application '{app}' in collection '{appcollection}'."
            raise TableNotFoundError(msg) from exc

    def _get_application_table_for(
        self,
        application: Application,
        table_name: str,  # registry-owned lookup, self unused
    ) -> ApplicationTable:
        try:
            return ApplicationTable.objects.get(application=application, name=table_name)
        except ApplicationTable.DoesNotExist as exc:
            msg = f"No table '{table_name}' in application '{application.name}'."
            raise TableNotFoundError(msg) from exc

    # ------------------------------------------------------------------
    # Schema operations
    # ------------------------------------------------------------------

    def create_application_table(
        self,
        appcollection: str,
        app: str,
        name: str,
        columns: list[dict[str, Any]],
    ) -> ApplicationTable:
        """Create an ApplicationTable plus its physical table in one transaction."""
        with transaction.atomic():
            application = self._resolve_application(appcollection, app)
            table = ApplicationTable(
                application=application,
                name=name,
                physical_name=ApplicationTable.make_physical_name(name),
                column_order=[c["name"] for c in columns],
            )
            # full_clean runs ApplicationTable.clean(), which enforces the
            # collection-scoped display-name uniqueness before any column rows
            # or DDL are created.
            table.full_clean()
            table.save()
            for spec in columns:
                _create_column_row(table, spec)

            # Build the model and create the physical table before caching:
            # the DB rows and DDL are rolled back by the atomic block on
            # failure, but the in-memory registration is not, so a
            # create_model failure must reset the registry.
            model = self._build_model_class(table.physical_name)
            try:
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(model)
            except Exception:
                self.reset()
                raise
            self._cache[table.physical_name] = model
            return table

    def add_application_table_columns(
        self,
        appcollection: str,
        app: str,
        table: str,
        columns: list[dict[str, Any]],
    ) -> list[ApplicationTableColumn]:
        """Add columns to an existing table (DDL ALTER TABLE ADD COLUMN)."""
        with transaction.atomic():
            application = self._resolve_application(appcollection, app)
            app_table = self._get_application_table_for(application, table)
            model = self.get_model(app_table.physical_name)
            created: list[ApplicationTableColumn] = []
            with connection.schema_editor() as schema_editor:
                for spec in columns:
                    col = _create_column_row(app_table, spec)
                    field = _column_field(col)
                    # The field is not yet attached to a model, so set its DB
                    # column/attribute name before the schema editor reads it.
                    field.set_attributes_from_name(col.name)
                    schema_editor.add_field(model, field)
                    created.append(col)
            app_table.column_order = list(app_table.column_order) + [c["name"] for c in columns]
            # Only column_order changed; restrict the UPDATE to that column.
            app_table.save(update_fields=["column_order"])
            self.reset()
            return created

    def delete_application_table_columns(
        self,
        appcollection: str,
        app: str,
        table: str,
        columns: list[str],
    ) -> ApplicationTable:
        """Remove columns from a table (DDL ALTER TABLE DROP COLUMN)."""
        with transaction.atomic():
            application = self._resolve_application(appcollection, app)
            app_table = self._get_application_table_for(application, table)
            model = self.get_model(app_table.physical_name)
            with connection.schema_editor() as schema_editor:
                for col_name in columns:
                    try:
                        col = app_table.columns.get(name=col_name)
                    except ApplicationTableColumn.DoesNotExist as exc:
                        msg = f"Column '{col_name}' not found on table '{table}'."
                        raise ValidationError(msg) from exc
                    field = cast(
                        "models.Field[Any, Any]",
                        # only _meta exposes the dynamic model's fields
                        model._meta.get_field(col_name),  # noqa: SLF001
                    )
                    schema_editor.remove_field(model, field)
                    col.delete()
            app_table.column_order = [c for c in app_table.column_order if c not in columns]
            # Only column_order changed; restrict the UPDATE to that column.
            app_table.save(update_fields=["column_order"])
            self.reset()
            return app_table

    def delete_application_table(self, appcollection: str, app: str, table: str) -> None:
        """Drop the physical table and delete its definition rows."""
        with transaction.atomic():
            application = self._resolve_application(appcollection, app)
            app_table = self._get_application_table_for(application, table)
            cached = self._cache.pop(app_table.physical_name, None)
            model = cached or self._build_model_class(app_table.physical_name)
            # Table already absent (e.g. partial state); tolerate the
            # ProgrammingError so cleanup can finish and the definition rows
            # are removed.
            with (
                connection.schema_editor() as schema_editor,
                contextlib.suppress(ProgrammingError),
            ):
                schema_editor.delete_model(model)
            self.reset()
            # Columns reference the table via a RESTRICT FK; drop them first so
            # the table definition row can be deleted.
            ApplicationTableColumn.objects.filter(application_table=app_table).delete()
            app_table.delete()

    def rename_application_collection(
        self, collection: ApplicationCollection, new_name: str
    ) -> None:
        """Rename a collection's display name (no physical-table changes).

        Physical tables are keyed by the immutable ``physical_name`` and named
        ``zz_<physical_name>``, which does not include the collection name, so
        renaming the collection is a plain row update — no DDL, no registry
        reset.
        """
        with transaction.atomic():
            collection.name = new_name
            collection.full_clean()
            collection.save()

    def rename_application_table(
        self, app_table: ApplicationTable, new_name: str
    ) -> ApplicationTable:
        """Rename a table's display name (no physical-table changes).

        The physical table is keyed by the immutable ``physical_name``, so a
        display-name rename is a plain row update — no DDL, no registry reset.
        """
        with transaction.atomic():
            app_table.name = new_name
            app_table.full_clean()
            app_table.save()
            return app_table


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _create_column_row(table: ApplicationTable, spec: dict[str, Any]) -> ApplicationTableColumn:
    """Validate a column spec and persist an ApplicationTableColumn row."""
    name = spec.get("name", "")
    col_type = spec.get("type", "")
    if col_type not in {t.value for t in ColumnType}:
        msg = f"Unknown column type '{col_type}'."
        raise ValidationError({"type": msg})
    is_textish = col_type in {ColumnType.CHAR, ColumnType.TEXT}
    decimal_default: Decimal | None = None
    if col_type == ColumnType.DECIMAL and spec.get("default") is not None:
        decimal_default = Decimal(str(spec["default"]))
    col = ApplicationTableColumn(
        application_table=table,
        name=name,
        type=col_type,
        char_choices=spec.get("choices", []) or [],
        text_default=spec.get("default", "") if is_textish else "",
        text_min_length=int(spec.get("min_length", 0)) if is_textish else 0,
        text_max_length=int(spec.get("max_length", 1000)) if is_textish else 1000,
        nullable=bool(spec.get("nullable", False)),
        int_default=spec.get("default") if col_type == ColumnType.INTEGER else None,
        boolean_default=bool(spec.get("default", False))
        if col_type == ColumnType.BOOLEAN
        else False,
        decimal_default=decimal_default,
        decimal_max_digits=int(spec.get("max_digits", 10))
        if col_type == ColumnType.DECIMAL
        else 10,
        decimal_places=int(spec.get("decimal_places", 2)) if col_type == ColumnType.DECIMAL else 2,
    )
    col.full_clean()
    col.save()
    return col


# The single registry instance; the only way to retrieve dynamic models.
dynamic_models = DynamicModelRegistry()
