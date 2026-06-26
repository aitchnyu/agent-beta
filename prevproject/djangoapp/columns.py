"""Self-contained column descriptors for FooView.

Each kind carries its own behavior: how to render a form input (``to_input``,
shaped to match the frontend InputSchema zod schema), how to render a display
cell (``to_td``), and how to parse a posted form value (``parse``). Nothing is
imported from serializers.py or models/base.py.

``editable`` ("always" | "createonly" | "never") drives create/update form
visibility: create -> always|createonly; update -> always; never -> display only.

The to_input/to_td/parse signatures are uniform across kinds; a kind that does
not use an argument names it with a leading underscore (``_field`` etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.dateparse import parse_datetime

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

Editable = Literal["always", "createonly", "never"]
OPERATIONS = Literal["create", "update", "list", "details"]

# Sentinel: a posted file field indicating "leave the existing file as-is".
UNCHANGED = object()

type Field = "models.Field[Any, Any]"
type Files = "dict[str, UploadedFile]"


def _str(value: object) -> str | None:
    return str(value) if value is not None else None


def _int(value: object) -> int | None:
    return int(cast(Any, value)) if value is not None else None


def _bool(value: object) -> bool | None:
    return bool(value) if value is not None else None


def _choices(field: Field) -> list[dict[str, str]] | None:
    raw = getattr(field, "choices", None)
    if not raw:
        return None
    return [{"value": str(c[0]), "label": str(c[1])} for c in raw]


class Column:
    """Base column descriptor with editable behavior + (de)serialization hooks."""

    input_component: str = ""
    # Frontend InputSchema discriminator for this column kind.
    discriminator: str = ""

    def __init__(self, editable: Editable = "always") -> None:
        if editable not in ("always", "createonly", "never"):
            msg = f"editable must be 'always' | 'createonly' | 'never', got {editable!r}"
            raise ValueError(msg)
        self.editable = editable

    def is_editable(self, operation: OPERATIONS) -> bool:
        if operation == "create":
            return self.editable in ("always", "createonly")
        if operation == "update":
            return self.editable == "always"
        return False

    def accepts(self, field: Field) -> None:
        """Validate the Django field type matches this column kind (override)."""

    def _input_base(self, field: Field, *, required: bool, default: object) -> dict[str, object]:
        """Return common InputSchema fields; kinds add type-specific keys."""
        return {
            "d": self.discriminator,
            "component": self.input_component,
            "name": field.name,
            "required": required,
            "default": default,
        }

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        """Form input descriptor for the frontend (override per kind)."""
        return self._input_base(
            field, required=not getattr(field, "null", False), default=_str(value)
        )

    def to_td(self, _field: Field, value: object) -> object:
        """Display value for a cell."""
        return "" if value is None else str(value)

    def parse(self, _field: Field, raw: str, _files: Files) -> object:
        """Parse a posted value into a Python value for the model field."""
        return raw


@dataclass
class ResolvedColumn:
    """A model field paired with its Column descriptor.

    The type a FooView iterates over: it carries the Django field plus the
    Column that encodes its (de)serialization, so the view doesn't look the
    Column up by name on each access.
    """

    field: Field
    column: Column

    @property
    def name(self) -> str:
        return self.field.name

    def to_input(self, value: object) -> dict[str, object]:
        return self.column.to_input(self.field, value)

    def to_td(self, value: object) -> object:
        return self.column.to_td(self.field, value)

    def parse(self, raw: str, files: Files) -> object:
        return self.column.parse(self.field, raw, files)


class Charfield(Column):
    input_component = "/components/inputs/CharFieldInput"
    discriminator = "char"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.CharField):
            msg = f"{type(self).__name__} expects CharField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        return {
            **self._input_base(field, required=not field.blank, default=_str(value)),
            "max_length": getattr(field, "max_length", None) or 255,
            "choices": _choices(field),
        }


class CharChoicefield(Charfield):
    def accepts(self, field: Field) -> None:
        super().accepts(field)
        if not getattr(field, "choices", None):
            msg = f"{type(self).__name__} expects a CharField with choices, got none"
            raise TypeError(msg)


class Textfield(Column):
    input_component = "/components/inputs/TextFieldInput"
    discriminator = "text"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.TextField):
            msg = f"{type(self).__name__} expects TextField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        return {
            **self._input_base(field, required=not field.blank, default=_str(value)),
            "length": getattr(field, "max_length", None) or 1000,
        }


class Integerfield(Column):
    input_component = "/components/inputs/IntegerFieldInput"
    discriminator = "integer"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.IntegerField):
            msg = f"{type(self).__name__} expects IntegerField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_td(self, _field: Field, value: object) -> object:
        return value

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        return {
            **self._input_base(field, required=not field.null, default=_int(value)),
            "choices": _choices(field),
        }

    def parse(self, field: Field, raw: str, _files: Files) -> object:
        try:
            return int(raw)
        except ValueError:
            msg = f"{field.name}: {raw!r} is not a valid integer"
            raise ValidationError(msg) from None


class Booleanfield(Column):
    input_component = "/components/inputs/BooleanFieldInput"
    discriminator = "boolean"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.BooleanField):
            msg = f"{type(self).__name__} expects BooleanField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_td(self, _field: Field, value: object) -> object:
        return bool(value)

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        return self._input_base(field, required=not field.null, default=_bool(value))

    def parse(self, _field: Field, raw: str, _files: Files) -> object:
        return raw in ("on", "true", "True", "1")


class Decimalfield(Column):
    input_component = "/components/inputs/DecimalFieldInput"
    discriminator = "decimal"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.DecimalField):
            msg = f"{type(self).__name__} expects DecimalField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        return {
            **self._input_base(field, required=not field.null, default=_str(value)),
            "decimal_places": getattr(field, "decimal_places", 0),
        }

    def to_td(self, _field: Field, value: object) -> object:
        return str(value) if value is not None else None

    def parse(self, field: Field, raw: str, _files: Files) -> object:
        try:
            return Decimal(raw)
        except InvalidOperation:
            msg = f"{field.name}: {raw!r} is not a valid decimal"
            raise ValidationError(msg) from None


class Datetimefield(Column):
    input_component = "/components/inputs/DateTimeFieldInput"
    discriminator = "datetime"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.DateTimeField):
            msg = f"{type(self).__name__} expects DateTimeField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_td(self, _field: Field, value: object) -> object:
        return value.isoformat() if isinstance(value, datetime) else value

    def to_input(self, field: Field, value: object) -> dict[str, object]:
        # datetime-local inputs default to step=60 (minute granularity), so the
        # value must omit seconds or it trips stepMismatch + required validation.
        default = value.strftime("%Y-%m-%dT%H:%M") if isinstance(value, datetime) else None
        return self._input_base(field, required=not field.null, default=default)

    def parse(self, field: Field, raw: str, _files: Files) -> object:
        parsed = parse_datetime(raw)
        if parsed is None:
            msg = f"{field.name}: {raw!r} is not a valid datetime"
            raise ValidationError(msg) from None
        return parsed


class Filefield(Column):
    input_component = "/components/inputs/FileFieldInput"
    discriminator = "file"

    def accepts(self, field: Field) -> None:
        if not isinstance(field, models.FileField):
            msg = f"{type(self).__name__} expects FileField, got {type(field).__name__}"
            raise TypeError(msg)

    def to_td(self, _field: Field, value: object) -> object:
        if not value:
            return None
        try:
            return {"name": getattr(value, "name", ""), "url": getattr(value, "url", "")}
        except Exception:  # noqa: BLE001 # value may be missing from storage
            return None

    def to_input(self, field: Field, _value: object) -> dict[str, object]:
        return self._input_base(field, required=not field.null, default=None)

    def parse(self, field: Field, _raw: str, files: Files) -> object:
        uploaded = files.get(field.name)
        if uploaded is not None:
            return uploaded
        return UNCHANGED


class Reffield(Column):
    """Foreign-key column. Deferred -- FooView skips Reffield columns for now."""

    input_component = "/components/inputs/ForeignKeyFieldInput"
    discriminator = "foreignkey"
