"""Dynamic-model generation and schema operations for application tables.

Each ``ApplicationTable`` is materialised as a real Django model class
(subclassing ``BaseTable``) whose ``db_table`` is
``zz_<physical_name>``, where ``physical_name`` is the table's immutable
creation-time identifier (``<tablename><unix-seconds>``). Table display-name
renames therefore never touch the physical table.
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
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

import networkx as nx
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import connection, models, transaction
from django.db.models.base import ModelBase
from django.db.utils import ProgrammingError

from djangoapp.apps.dynamic_module import clear_app_caches
from djangoapp.models.applications import (
    Application,
    ApplicationTable,
    ApplicationTableColumn,
    BaseTable,
    ColumnType,
)
from djangoapp.models.base import User
from djangoapp.models.columns import Column, ForeignKeyColumn

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class TableNotFoundError(Exception):
    """Raised when no Application/ApplicationTable matches the given names."""


def _synced[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Decorate a public registry method to sync caches to the apps generation per call.

    ``setup`` (any process) bumps ``AppsGeneration`` on install; each call here
    checks the live value and, on a change, resets this registry's model cache
    and the app-module loader's cache — so a running worker serves the latest
    installed app without a restart. ``reset`` is intentionally NOT decorated
    (it is called by the sync itself). Signature-preserving via PEP 695 generics.
    """

    @wraps(fn)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        clear_app_caches()
        return fn(*args, **kwargs)

    return _wrapper


def dynamic_db_table(physical_name: str) -> str:
    """Physical Postgres table name for a table's immutable physical_name."""
    return f"zz_{physical_name}"


def _dynamic_class_name(physical_name: str) -> str:
    """Python class name for the generated model: ``<Physicalname>DynamicModel``.

    Capitalises the first character of the immutable ``physical_name`` and
    appends ``DynamicModel``. Keys on ``physical_name`` (not on display
    names) so table renames never change the generated class
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


def _foreign_key_field(col: ApplicationTableColumn) -> models.Field[Any, Any]:
    # Self-reference (a table pointing at itself, e.g. a tree parent) must use
    # the lazy "self" string: resolving the target through get_model *during*
    # this very model's build would recurse without end. The table graph is
    # acyclic (enforced at create/add-column time), so any *other* target is
    # already built + registered and safe to resolve by physical_name.
    assert (
        col.fk_target_table is not None
    )  # foreign_key columns always set a target (clean() enforces it)
    if col.fk_target_table_id == col.application_table_id:
        to: type[BaseTable] | str = "self"
    else:
        to = dynamic_models.get_model(col.fk_target_table.physical_name)
    return models.ForeignKey(
        to,
        null=col.nullable,
        blank=col.nullable,
        on_delete=models.RESTRICT,
        # related_name="+" disables reverse accessors so several FK columns can
        # target the same table without clashing on an auto-generated name.
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
    ColumnType.FOREIGN_KEY: _foreign_key_field,
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
    live columns. Table display-name renames never touch the
    cache (the key is immutable).
    """

    def __init__(self) -> None:
        self._cache: dict[str, type[BaseTable]] = {}

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @_synced
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
    # Column creation
    # ------------------------------------------------------------------

    def _create_column(self, table: ApplicationTable, col: Column) -> ApplicationTableColumn:
        """Validate a column declaration and persist an ApplicationTableColumn.

        The :class:`Column` already validated itself in ``__post_init__``; this
        builds the row from :meth:`Column.row` and runs ``full_clean`` so the
        model-level cross-field invariants hold. For a foreign-key column the
        ``(app, table)`` target is resolved to its row here (the only
        relation): a forward reference inside one ``create_application`` resolves
        because targets are created first (topological order), while a cross-app
        target must already exist — else ``DoesNotExist``.
        """
        row = col.row()
        if isinstance(col, ForeignKeyColumn):
            ta, tt = col.target
            row["fk_target_table"] = Application.objects.get(name=ta).get_table(tt)
        obj = ApplicationTableColumn(application_table=table, **row)
        obj.full_clean()
        obj.save()
        return obj

    def _assert_add_columns_acyclic(
        self, app_table: ApplicationTable, columns: list[Column]
    ) -> None:
        """Reject new FK columns that would close a foreign-key cycle.

        Starts from the live table graph (by ``app/table`` label) and
        adds the edges this add would introduce; a cycle is reported by label.
        """
        graph = DependencyGraph.from_db()
        src_label = _table_label(app_table)
        for col in columns:
            if isinstance(col, ForeignKeyColumn):
                ta, tt = col.target
                target = Application.objects.get(name=ta).get_table(tt)
                # A self-reference adds no cross-table edge (and is allowed).
                if target.pk != app_table.pk:
                    graph.add_edge(src_label, _table_label(target))
        graph.assert_acyclic()

    # ------------------------------------------------------------------
    # Application lifecycle
    # ------------------------------------------------------------------
    #
    # Co-located with the table methods below, so DynamicModelRegistry is
    # the single place for all application-graph mutation. Create/rename are
    # thin (full_clean + save); ``delete_application`` cascades its
    # tables (dropping each physical table). The ``on_delete=RESTRICT``
    # FKs are only a DB backstop — the registry always deletes children
    # first.

    @_synced
    def create_application(
        self,
        *,
        name: str,
        description: str = "",
        tables: dict[str, list[Column]] | None = None,
    ) -> Application:
        """Create an application, optionally with inline tables, in one transaction.

        ``tables`` maps each table's display name to
        its Column list; each is created via :meth:`_create_application_table`
        (which also builds the physical table). Tables are created in
        dependency order (a table's foreign-key targets first) so a target's
        physical table + registered model exist before a referencer's
        create_model runs; a foreign-key cycle is rejected up front.
        """
        with transaction.atomic():
            application = Application(
                name=name,
                description=description,
            )
            application.full_clean()
            application.save()
            declared = tables or {}
            # Build the new-table graph once: the cycle check and the creation
            # order both read it (edges run table -> target, so a target is
            # created before its referencer). Only edges among the new tables
            # matter, so nodes are their names (see from_application_tables).
            graph = DependencyGraph.from_application_tables(name, declared)
            graph.assert_acyclic()
            for table_name in graph.topological_order():
                self._create_application_table(application, table_name, declared[table_name])
            return application

    @_synced
    def rename_application(self, *, old_name: str, new_name: str) -> Application:
        """Rename an application (display-name only).

        Physical tables are keyed by the immutable ``physical_name`` which
        omits the app, so no DDL and no registry reset.
        """
        with transaction.atomic():
            application = Application.objects.get(name=old_name)
            application.name = new_name
            application.full_clean()
            application.save()
            return application

    @_synced
    def delete_application(self, application: Application) -> None:
        """Delete an application and cascade-drop every table it owns.

        Each child table is removed via ``_drop_application_table`` (which
        drops its physical table and definition rows), then the app row is
        deleted. Wrapped in one transaction so a mid-cascade failure leaves
        the whole graph intact — nothing half-deleted, no orphaned table.
        Uses the child ``ApplicationTable`` instances directly instead of
        re-resolving them by name, so the cascade does no per-table DB
        lookups and ignores any unsaved display-name change on the app.
        """
        with transaction.atomic():
            tables = list(application.tables.all())
            # Tables in this app may reference each other; capture their pks
            # once here and pass as ``also_dropping`` so the per-table guard
            # ignores references among siblings (they are being dropped
            # together) instead of blocking the cascade. Pks (not the table
            # objects) because ``_drop_application_table`` nulls each table's
            # pk on delete, so a later iteration's filter could not reuse them.
            also_dropping = {t.pk for t in tables}
            for table in tables:
                self._drop_application_table(table, also_dropping=also_dropping)
            application.delete()

    # ------------------------------------------------------------------
    # Schema operations
    # ------------------------------------------------------------------

    def _create_application_table(
        self,
        application: Application,
        name: str,
        columns: list[Column],
    ) -> ApplicationTable:
        """Build a table + its physical table for an already-resolved application.

        Shared by :meth:`create_application` (inline tables) and
        :meth:`create_application_table` (standalone). Assumes the caller
        wraps the work in a transaction.
        """
        table = ApplicationTable(
            application=application,
            name=name,
            physical_name=ApplicationTable.make_physical_name(name),
            column_order=[c.name for c in columns],
        )
        # full_clean runs ApplicationTable.clean(), which enforces the
        # app-scoped display-name uniqueness before any column rows
        # or DDL are created.
        table.full_clean()
        table.save()
        for col in columns:
            self._create_column(table, col)

        # Build the model and create the physical table before caching:
        # the DB rows and DDL are rolled back by the caller's atomic block
        # on failure, but the in-memory registration is not, so a
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

    @_synced
    def create_application_table(
        self,
        *,
        application: str,
        table: str,
        columns: list[Column],
    ) -> ApplicationTable:
        """Resolve (app, table) names, then create the table + physical table."""
        with transaction.atomic():
            application_row = Application.objects.get(name=application)
            return self._create_application_table(application_row, table, columns)

    @_synced
    def add_application_table_columns(
        self,
        *,
        application: str,
        table: str,
        columns: list[Column],
    ) -> list[ApplicationTableColumn]:
        """Add columns to an existing table (DDL ALTER TABLE ADD COLUMN).

        A foreign-key column that would close a cycle is rejected before any
        DDL.
        """
        with transaction.atomic():
            application_row = Application.objects.get(name=application)
            app_table = application_row.get_table(table)
            self._assert_add_columns_acyclic(app_table, columns)
            model = self.get_model(app_table.physical_name)
            created: list[ApplicationTableColumn] = []
            with connection.schema_editor() as schema_editor:
                for col in columns:
                    col_row = self._create_column(app_table, col)
                    field = _column_field(col_row)
                    # The field is not yet attached to a model, so set its DB
                    # column/attribute name before the schema editor reads it.
                    field.set_attributes_from_name(col_row.name)
                    schema_editor.add_field(model, field)
                    created.append(col_row)
            app_table.column_order = list(app_table.column_order) + [c.name for c in columns]
            # Only column_order changed; restrict the UPDATE to that column.
            app_table.save(update_fields=["column_order"])
            self.reset()
            return created

    @_synced
    def delete_application_table_columns(
        self,
        *,
        application: str,
        table: str,
        names: list[str],
    ) -> ApplicationTable:
        """Remove columns from a table (DDL ALTER TABLE DROP COLUMN)."""
        with transaction.atomic():
            application_row = Application.objects.get(name=application)
            app_table = application_row.get_table(table)
            model = self.get_model(app_table.physical_name)
            with connection.schema_editor() as schema_editor:
                for col_name in names:
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
            app_table.column_order = [c for c in app_table.column_order if c not in names]
            # Only column_order changed; restrict the UPDATE to that column.
            app_table.save(update_fields=["column_order"])
            self.reset()
            return app_table

    def _drop_application_table(
        self,
        app_table: ApplicationTable,
        *,
        also_dropping: Iterable[int] | None = None,
    ) -> None:
        """Drop a table's physical table and delete its definition rows.

        Instance-based: takes the ``ApplicationTable`` directly so callers
        that already hold it (e.g. ``delete_application``'s cascade) pay no
        name-resolution queries.

        Refuses to drop a table still referenced by a foreign-key column on
        *another* table (breaking it would dangle the FK). ``also_dropping``
        is the set of table pks dropped in the same operation (e.g. an app's
        own tables during ``delete_application``); references from those
        tables are ignored so a whole-app cascade isn't falsely blocked.
        """
        with transaction.atomic():
            # A surviving column on another table pointing here would dangle.
            refs = ApplicationTableColumn.objects.filter(fk_target_table=app_table).exclude(
                application_table=app_table
            )
            if also_dropping:
                refs = refs.exclude(application_table__pk__in=also_dropping)
            ref = refs.select_related("application_table__application").first()
            if ref is not None:
                src = ref.application_table
                msg = (
                    f"Cannot drop {_table_label(app_table)}: column "
                    f"'{_table_label(src)}.{ref.name}' references it. "
                    "Remove that column (or its table) first."
                )
                raise ValidationError(msg)
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

    @_synced
    def delete_application_table(self, *, application: str, table: str) -> None:
        """Resolve (app, table) names to a row, then drop it."""
        with transaction.atomic():
            application_row = Application.objects.get(name=application)
            app_table = application_row.get_table(table)
            self._drop_application_table(app_table)

    @_synced
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


def _table_label(table: ApplicationTable) -> str:
    """``app/table`` label for a table (used in graph errors/export)."""
    return f"{table.application.name}/{table.name}"


class DependencyGraph:
    """Mutable foreign-key dependency graph with cycle/order queries.

    Wraps an ``nx.DiGraph`` so every ``networkx`` touch — construction,
    ``find_cycle`` and ``topological_sort`` — lives in one place. Nodes are
    plain strings: the live graph (:meth:`from_db`) keys them by
    ``app/table`` label, while the new-table graph
    (:meth:`from_application_tables`) keys them by table name — the set is
    scoped to one app, so bare names are unique there and the new tables need no
    pk. Edges run ``source -> target`` (source depends on target); self-loops
    are never added (a self-reference is allowed and carries no cross-table
    dependency).

    :meth:`cycle` returns the raw node path; :meth:`assert_acyclic` formats it
    into the ``foreign-key cycle: A -> B -> A`` error — label-agnostic, since the
    path is whatever labels the graph was built from.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph[str] = nx.DiGraph()

    @staticmethod
    def from_db() -> DependencyGraph:
        """Live graph of every installed FK column (nodes = app/table labels)."""
        graph = DependencyGraph()
        columns = ApplicationTableColumn.objects.filter(
            type=ColumnType.FOREIGN_KEY, fk_target_table__isnull=False
        ).select_related(
            "application_table__application",
            "fk_target_table__application",
        )
        for col in columns:
            target = col.fk_target_table
            # fk_target_table is nullable on the model; the filter makes it
            # non-null, but this guard keeps the type and label lookup safe. A
            # self-reference is allowed and adds no cross-table edge.
            if target is None:
                continue
            src = _table_label(col.application_table)
            dst = _table_label(target)
            if src == dst:
                continue
            graph.add_edge(src, dst)
        return graph

    @staticmethod
    def from_application_tables(
        app: str,
        tables: dict[str, list[Column]],
    ) -> DependencyGraph:
        """FK dependency graph among the new tables of one ``create_application``.

        Nodes are the new table names; an edge ``table -> target`` means
        ``table`` foreign-keys ``target`` (so target must be created first).
        Only in-set edges are added: a create-time cycle can only run among
        these tables, since an existing table cannot reference a not-yet-created
        one. Self-references are allowed and omitted. Built from the declared
        ``Column`` specs (not the live DB): the new tables have no pk yet, so
        nodes are their names — sufficient as the set is one app.
        """
        graph = DependencyGraph()
        graph.add_nodes(tables)
        for table_name, cols in tables.items():
            for col in cols:
                if isinstance(col, ForeignKeyColumn):
                    ta, tt = col.target
                    if ta == app and tt != table_name and tt in tables:
                        graph.add_edge(table_name, tt)
        return graph

    def add_nodes(self, nodes: Iterable[str]) -> None:
        self._graph.add_nodes_from(nodes)

    def add_edge(self, src: str, dst: str) -> None:
        self._graph.add_edge(src, dst)

    def cycle(self) -> list[str] | None:
        """One cycle's nodes as a closed path (e.g. [A, B, A]), or None."""
        try:
            edges = nx.find_cycle(self._graph)
        except nx.NetworkXNoCycle:
            return None
        nodes = [src for src, _dst in edges]
        nodes.append(edges[0][0])
        return nodes

    def assert_acyclic(self) -> None:
        """Raise a ValidationError naming one cycle if the graph has one.

        Edges run ``source -> target`` (depends-on), so a cycle means a set of
        tables mutually depend on each other and can neither be created nor
        ordered. Label-agnostic: the cycle path is the raw nodes, formatted
        whatever labels the graph was built from.
        """
        cycle = self.cycle()
        if cycle is not None:
            raise ValidationError("foreign-key cycle: " + " -> ".join(cycle))

    def topological_order(self) -> list[str]:
        """Targets-first order; only valid once :meth:`cycle` returns None.

        Edges run ``source -> target`` (depends-on), so the reversed graph's
        ``topological_sort`` yields each target before its referencers.
        """
        return list(nx.topological_sort(self._graph.reverse()))


# The single registry instance; the only way to retrieve dynamic models.
dynamic_models = DynamicModelRegistry()
