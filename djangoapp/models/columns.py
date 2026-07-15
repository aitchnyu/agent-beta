"""Typed column declarations for application tables.

Column objects are the only way to declare a table's columns (the old
``{"name", "type", ...}`` dict spec is gone). Each class takes a positional
``name`` and keyword-only type-specific options, validates them in
``__post_init__``, and knows how to render itself into the
``ApplicationTableColumn`` field set via :meth:`Column.row`.

The registry (``dynamic_models``) consumes these via :func:`row`; it never
touches a raw dict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar

from djangoapp.models.applications import COLUMN_NAME_RE, ColumnType


@dataclass(frozen=True)
class Column:
    """Base column declaration.

    ``name`` is positional; ``nullable`` is keyword-only. Subclasses add
    type-specific keyword-only options. Validate in ``__post_init__`` so a
    malformed column raises before it reaches the registry.
    """

    name: str
    nullable: bool = field(default=False, kw_only=True)

    # Set by each subclass; read by the registry to build the right field.
    column_type: ClassVar[ColumnType]

    def __post_init__(self) -> None:
        """Validate the name and run subclass validation before construction."""
        if not re.fullmatch(COLUMN_NAME_RE, self.name):
            msg = (
                f"Column name '{self.name}' must start with a letter and "
                "contain only letters and digits."
            )
            raise ValueError(msg)
        self._validate()

    def _validate(self) -> None:
        """Validate subclass-specific options (override as needed)."""

    def row(self) -> dict[str, Any]:
        """Render this column into the ``ApplicationTableColumn`` field set.

        Base provides the common + zeroed fields; subclasses override
        :meth:`_row_extra` to set the fields their type cares about.
        """
        data: dict[str, Any] = {
            "name": self.name,
            "type": self.column_type.value,
            "char_choices": [],
            "text_default": "",
            "text_min_length": 0,
            "text_max_length": 1000,
            "nullable": self.nullable,
            "int_default": None,
            "boolean_default": False,
            "decimal_default": None,
            "decimal_max_digits": 10,
            "decimal_places": 2,
        }
        data.update(self._row_extra())
        return data

    def _row_extra(self) -> dict[str, Any]:
        """Type-specific overrides on top of the base row."""
        return {}


@dataclass(frozen=True)
class CharColumn(Column):
    """A fixed-length string column (``max_length`` required)."""

    max_length: int = field(kw_only=True)
    default: str = field(default="", kw_only=True)
    min_length: int = field(default=0, kw_only=True)
    choices: list[str] = field(default_factory=list, kw_only=True)
    column_type: ClassVar[ColumnType] = ColumnType.CHAR

    def _validate(self) -> None:
        if self.max_length < 1:
            msg = f"CharColumn '{self.name}': max_length must be >= 1."
            raise ValueError(msg)
        if self.min_length > self.max_length:
            msg = (
                f"CharColumn '{self.name}': min_length ({self.min_length}) "
                f"cannot exceed max_length ({self.max_length})."
            )
            raise ValueError(msg)

    def _row_extra(self) -> dict[str, Any]:
        return {
            "char_choices": list(self.choices),
            "text_default": self.default,
            "text_min_length": self.min_length,
            "text_max_length": self.max_length,
        }


@dataclass(frozen=True)
class TextColumn(Column):
    """An unbounded text column."""

    default: str = field(default="", kw_only=True)
    min_length: int = field(default=0, kw_only=True)
    max_length: int = field(default=1000, kw_only=True)
    column_type: ClassVar[ColumnType] = ColumnType.TEXT

    def _validate(self) -> None:
        if self.max_length < 1:
            msg = f"TextColumn '{self.name}': max_length must be >= 1."
            raise ValueError(msg)
        if self.min_length > self.max_length:
            msg = (
                f"TextColumn '{self.name}': min_length ({self.min_length}) "
                f"cannot exceed max_length ({self.max_length})."
            )
            raise ValueError(msg)

    def _row_extra(self) -> dict[str, Any]:
        return {
            "text_default": self.default,
            "text_min_length": self.min_length,
            "text_max_length": self.max_length,
        }


@dataclass(frozen=True)
class IntegerColumn(Column):
    """An integer column."""

    default: int | None = field(default=None, kw_only=True)
    column_type: ClassVar[ColumnType] = ColumnType.INTEGER

    def _validate(self) -> None:
        if self.default is not None and not isinstance(self.default, int):
            msg = f"IntegerColumn '{self.name}': default must be an int."
            raise TypeError(msg)

    def _row_extra(self) -> dict[str, Any]:
        return {"int_default": self.default}


@dataclass(frozen=True)
class BooleanColumn(Column):
    """A boolean column."""

    default: bool = field(default=False, kw_only=True)
    column_type: ClassVar[ColumnType] = ColumnType.BOOLEAN

    def _row_extra(self) -> dict[str, Any]:
        return {"boolean_default": self.default}


@dataclass(frozen=True)
class DecimalColumn(Column):
    """A fixed-precision decimal column (``max_digits``/``decimal_places`` required)."""

    max_digits: int = field(kw_only=True)
    decimal_places: int = field(kw_only=True)
    default: Decimal | str | int | None = field(default=None, kw_only=True)
    column_type: ClassVar[ColumnType] = ColumnType.DECIMAL

    def _validate(self) -> None:
        if self.max_digits < 1:
            msg = f"DecimalColumn '{self.name}': max_digits must be >= 1."
            raise ValueError(msg)
        if self.decimal_places < 0:
            msg = f"DecimalColumn '{self.name}': decimal_places must be >= 0."
            raise ValueError(msg)
        if self.decimal_places > self.max_digits:
            msg = (
                f"DecimalColumn '{self.name}': decimal_places ({self.decimal_places}) "
                f"cannot exceed max_digits ({self.max_digits})."
            )
            raise ValueError(msg)

    def _row_extra(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "decimal_max_digits": self.max_digits,
            "decimal_places": self.decimal_places,
        }
        if self.default is not None:
            data["decimal_default"] = Decimal(str(self.default))
        return data


@dataclass(frozen=True)
class DateTimeColumn(Column):
    """A datetime column (no default; ``nullable`` only)."""

    column_type: ClassVar[ColumnType] = ColumnType.DATETIME


@dataclass(frozen=True)
class UserColumn(Column):
    """A ForeignKey column to the project ``User`` (``nullable`` only)."""

    column_type: ClassVar[ColumnType] = ColumnType.USER


@dataclass(frozen=True)
class ForeignKeyColumn(Column):
    """A ForeignKey column to another application table.

    ``target`` is a ``(collection, app, table)`` triple naming the referenced
    ``ApplicationTable``. It is resolved to the target row at column-creation
    time (by the registry, not here — this class stays DB-free), and the dynamic
    field references the target by its immutable ``physical_name``, so renaming
    a collection/app/table display name never breaks the link. Self-reference
    (``target`` naming the column's own table) is allowed (e.g. a tree parent).
    """

    target: tuple[str, str, str] = field(kw_only=True)
    column_type: ClassVar[ColumnType] = ColumnType.FOREIGN_KEY

    def _validate(self) -> None:
        if (
            not isinstance(self.target, tuple) or len(self.target) != 3  # noqa: PLR2004 # (collection, app, table) triple arity
        ):
            msg = (
                f"ForeignKeyColumn '{self.name}': target must be a (collection, app, table) triple."
            )
            raise ValueError(msg)


_ALL_COLUMNS: dict[ColumnType, type[Column]] = {
    ColumnType.CHAR: CharColumn,
    ColumnType.TEXT: TextColumn,
    ColumnType.INTEGER: IntegerColumn,
    ColumnType.BOOLEAN: BooleanColumn,
    ColumnType.DECIMAL: DecimalColumn,
    ColumnType.DATETIME: DateTimeColumn,
    ColumnType.USER: UserColumn,
    ColumnType.FOREIGN_KEY: ForeignKeyColumn,
}


def column_class_for(column_type: ColumnType) -> type[Column]:
    """Return the :class:`Column` subclass for a ``ColumnType``."""
    try:
        return _ALL_COLUMNS[column_type]
    except KeyError as exc:  # pragma: no cover - exhaustive dispatch
        msg = f"No Column class for type {column_type!r}."
        raise KeyError(msg) from exc


__all__ = [
    "BooleanColumn",
    "CharColumn",
    "Column",
    "DateTimeColumn",
    "DecimalColumn",
    "ForeignKeyColumn",
    "IntegerColumn",
    "TextColumn",
    "UserColumn",
    "column_class_for",
]
