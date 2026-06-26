"""Serializer functions for Django field types.

This module contains all serializer functions for converting Django field types
to various formats (schema, API, CRUD values, form deserialization).

The model_to_viewname callable is populated by add_views() in views.py.
"""

from __future__ import annotations

import datetime
import decimal
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields import (
    EmailField,
)
from django.utils import timezone

from djangoapp.responses import (
    BaseContent,
    BaseFieldSchema,
    BooleanFieldContent,
    BooleanFieldInputSchema,
    BooleanFieldSchema,
    CharChoiceWrapper,
    CharFieldContent,
    CharFieldInputSchema,
    CharFieldSchema,
    DateTimeFieldContent,
    DateTimeFieldInputSchema,
    DateTimeFieldSchema,
    DecimalFieldContent,
    DecimalFieldInputSchema,
    DecimalFieldSchema,
    FileFieldContent,
    FileFieldInputSchema,
    FileFieldSchema,
    ForeignKeyFieldContent,
    ForeignKeyFieldInputSchema,
    ForeignKeyFieldSchema,
    ForeignKeyWrapper,
    InputSchema,
    IntegerChoiceWrapper,
    IntegerFieldContent,
    IntegerFieldInputSchema,
    IntegerFieldSchema,
    NullContent,
    RowColumnValueSchema,
    RowUpdateBooleanValue,
    RowUpdateCharChoiceValue,
    RowUpdateCharValue,
    RowUpdateDatetimeValue,
    RowUpdateDecimalValue,
    RowUpdateFileValue,
    RowUpdateForeignKeyValue,
    RowUpdateIntegerChoiceValue,
    RowUpdateIntegerValue,
    RowUpdateTextValue,
    TextContent,
    TextFieldInputSchema,
    TextFieldSchema,
    TextHtmlContent,
)
from djangoapp.utils import sanitize_html, strip_html

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from djangoapp.models.base import _BaseModelMixin

# Type alias for Django field types
type DjangoField = models.Field

# Type alias for form deserializer functions
# Takes: (field, posted_value, files, existing_instance)
# Returns: parsed value, UNCHANGED sentinel, or raises ValidationError
FormDeserializer = Callable[
    [DjangoField, str | None, dict[str, "UploadedFile"], typing.Optional["_BaseModelMixin"]],
    typing.Any,
]


# ------------------ model_to_viewname Callable ---------------------
# This is populated by add_views() in views.py to avoid circular imports


def _model_to_viewname_not_initialized(model: type[_BaseModelMixin]) -> str:  # pragma: no cover
    """Default implementation that raises error if called before add_views()."""
    msg = "model_to_viewname not initialized. Call add_views() first."
    raise NotImplementedError(msg)


model_to_viewname: Callable[[type[_BaseModelMixin]], str] = _model_to_viewname_not_initialized


# ------------------ UNCHANGED Sentinel ---------------------
# Used for file fields to indicate the existing file should be kept


class _Unchanged:
    """Sentinel class to indicate a field should not be changed.

    Used for file fields when keeping existing file.
    """

    def __repr__(self) -> str:  # pragma: no cover
        return "UNCHANGED"


UNCHANGED = _Unchanged()


# ------------------ Helper Functions ---------------------


def _default_val(field: DjangoField) -> typing.Any:  # noqa: ANN401
    """Get the default value for a field.

    Args:
        field: The Django field to get default value from

    Returns:
        The default value, or None if field has no default

    """
    if not field.has_default():
        return None
    default_val = field.get_default()
    if callable(default_val):
        default_val = default_val()
    return default_val


def _get_choice_title(value: Any, field: DjangoField) -> str | None:  # noqa: ANN401
    """Look up the display title for a choice value.

    Args:
        value: The choice value to look up
        field: The Django field to get choices from

    Returns:
        The display title for the choice, or None if not found

    """
    if value is None:
        return None
    choices = field.choices
    if choices is None:
        return None
    min_choice_length = 2  # minimum length for choice tuple
    for choice in choices:
        if isinstance(choice, (list, tuple)) and len(choice) >= min_choice_length:
            choice_val, choice_label = choice[0], choice[1]
            if choice_val == value:
                return str(choice_label)
    return None


# ------------------ Schema Serializer Functions ---------------------
# These functions convert Django fields to FieldSchema pydantic models.
# They are module-level functions (not methods) to avoid circular imports
# with models.py and to allow easy access to the model_to_viewname callable.

# Type alias for JSON values
JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]


def _char_field_to_schema(field: DjangoField) -> CharFieldSchema:
    """Convert a CharField to a CharFieldSchema pydantic model."""
    assert isinstance(field, models.CharField)
    default_val = _default_val(field)

    return CharFieldSchema(
        name=field.name,
        required=not field.blank,
        max_length=getattr(field, "max_length", None) or 255,
        choices=[
            {"value": str(choice[0]), "label": str(choice[1])}
            for choice in getattr(field, "choices", [])
        ]
        if getattr(field, "choices", None)
        else None,
        default=str(default_val) if default_val is not None else None,
    )


def _text_field_to_schema(field: DjangoField) -> TextFieldSchema:
    """Convert a TextField to a TextFieldSchema pydantic model."""
    assert isinstance(field, models.TextField)
    default_val = _default_val(field)
    length = getattr(field, "max_length", None) or 1000  # arbitrary default

    return TextFieldSchema(
        name=field.name,
        required=not field.blank,
        length=length,
        default=str(default_val) if default_val is not None else None,
    )


def _integer_field_to_schema(field: DjangoField) -> IntegerFieldSchema:
    """Convert an IntegerField to an IntegerFieldSchema pydantic model."""
    assert isinstance(field, models.IntegerField)
    default_val = _default_val(field)

    return IntegerFieldSchema(
        name=field.name,
        required=not field.null,
        choices=[
            {"value": str(choice[0]), "label": str(choice[1])}
            for choice in getattr(field, "choices", [])
        ]
        if getattr(field, "choices", None)
        else None,
        default=int(default_val) if default_val is not None else None,
    )


def _boolean_field_to_schema(field: DjangoField) -> BooleanFieldSchema:
    """Convert a BooleanField to a BooleanFieldSchema pydantic model."""
    assert isinstance(field, models.BooleanField)
    default_val = _default_val(field)

    return BooleanFieldSchema(
        name=field.name,
        required=not field.null,
        default=bool(default_val) if default_val is not None else None,
    )


def _decimal_field_to_schema(field: DjangoField) -> DecimalFieldSchema:
    """Convert a DecimalField to a DecimalFieldSchema pydantic model."""
    assert isinstance(field, models.DecimalField)
    default_val = _default_val(field)

    return DecimalFieldSchema(
        name=field.name,
        required=not field.null,
        decimal_places=field.decimal_places,
        default=str(default_val) if default_val is not None else None,
    )


def _datetime_field_to_schema(field: DjangoField) -> DateTimeFieldSchema:
    """Convert a DateTimeField to a DateTimeFieldSchema pydantic model."""
    assert isinstance(field, models.DateTimeField)

    return DateTimeFieldSchema(
        name=field.name,
        required=not field.null,
        default=None,
    )


def _file_field_to_schema(field: DjangoField) -> FileFieldSchema:
    """Convert a FileField to a FileFieldSchema pydantic model."""
    assert isinstance(field, models.FileField)

    return FileFieldSchema(
        name=field.name,
        required=not field.null,
        default=None,
    )


def _foreignkey_field_to_schema(field: DjangoField) -> ForeignKeyFieldSchema:
    """Convert a ForeignKey field to a ForeignKeyFieldSchema pydantic model."""
    assert isinstance(field, models.ForeignKey)
    assert field.related_model is not None
    # Cast to _BaseModelMixin - all our models inherit from it
    related_model = cast(type["_BaseModelMixin"], field.related_model)

    return ForeignKeyFieldSchema(
        name=field.name,
        required=not field.null,
        view_name=model_to_viewname(related_model),
        default=None,
    )


SCHEMA_SERIALIZERS: dict[type[DjangoField], Callable[[DjangoField], BaseFieldSchema]] = {
    models.CharField: _char_field_to_schema,
    models.TextField: _text_field_to_schema,
    models.IntegerField: _integer_field_to_schema,
    models.BooleanField: _boolean_field_to_schema,
    models.DecimalField: _decimal_field_to_schema,
    models.DateTimeField: _datetime_field_to_schema,
    models.FileField: _file_field_to_schema,
    models.ForeignKey: _foreignkey_field_to_schema,
    EmailField: _char_field_to_schema,  # EmailField uses CharField schema
}


# ------------------ Row Value Serializer Functions ---------------------
# These functions convert Django field values to RowColumnValueSchema pydantic models.


def _rowupdate_value_char(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a CharField value to RowColumnValueSchema with old and new values."""
    if field.choices:
        old_title = _get_choice_title(old_value, field) if old_value is not None else None
        new_title = _get_choice_title(new_value, field) if new_value is not None else None
        return RowUpdateCharChoiceValue(
            name=field.name,
            old_value=CharChoiceWrapper(value=old_value, value_title=old_title)
            if old_value is not None
            else None,
            new_value=CharChoiceWrapper(value=new_value, value_title=new_title)
            if new_value is not None
            else None,
        )
    return RowUpdateCharValue(name=field.name, old_value=old_value, new_value=new_value)


def _rowupdate_value_text(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a TextField value to RowColumnValueSchema with old and new values."""
    return RowUpdateTextValue(name=field.name, old_value=old_value, new_value=new_value)


def _rowupdate_value_integer(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize an IntegerField value to RowColumnValueSchema with old and new values."""
    if field.choices:
        old_title = _get_choice_title(old_value, field) if old_value is not None else None
        new_title = _get_choice_title(new_value, field) if new_value is not None else None
        return RowUpdateIntegerChoiceValue(
            name=field.name,
            old_value=IntegerChoiceWrapper(value=old_value, value_title=old_title)
            if old_value is not None
            else None,
            new_value=IntegerChoiceWrapper(value=new_value, value_title=new_title)
            if new_value is not None
            else None,
        )
    return RowUpdateIntegerValue(name=field.name, old_value=old_value, new_value=new_value)


def _rowupdate_value_boolean(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a BooleanField value to RowColumnValueSchema with old and new values."""
    return RowUpdateBooleanValue(name=field.name, old_value=old_value, new_value=new_value)


def _rowupdate_value_decimal(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a DecimalField value to RowColumnValueSchema with old and new values."""
    old_str = str(old_value) if old_value is not None else None
    new_str = str(new_value) if new_value is not None else None
    return RowUpdateDecimalValue(name=field.name, old_value=old_str, new_value=new_str)


def _rowupdate_value_datetime(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a DateTimeField value to RowColumnValueSchema with old and new values."""

    def to_iso_string(val: Any) -> str | None:  # noqa: ANN401
        if val is None:
            return None
        if timezone.is_naive(val):
            val = timezone.make_aware(val)
        return timezone.localtime(val).strftime("%Y-%m-%dT%H:%M:%S")

    return RowUpdateDatetimeValue(
        name=field.name,
        old_value=to_iso_string(old_value),
        new_value=to_iso_string(new_value),
    )


def _rowupdate_value_file(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a FileField value to RowColumnValueSchema with old and new values."""
    old_name = old_value.name if old_value else None
    new_name = new_value.name if new_value else None
    return RowUpdateFileValue(name=field.name, old_value=old_name, new_value=new_name)


def _rowupdate_value_foreignkey(
    field: DjangoField,
    old_value: Any,  # noqa: ANN401
    new_value: Any,  # noqa: ANN401
) -> RowColumnValueSchema:
    """Serialize a ForeignKey value to RowColumnValueSchema with old and new values."""

    def to_fk_wrapper(val: Any) -> ForeignKeyWrapper | None:  # noqa: ANN401
        if val is None:
            return None
        assert isinstance(field, models.ForeignKey)
        related_model = field.remote_field.model
        if isinstance(related_model, type) and hasattr(related_model, "queryset_with_title"):
            annotated_obj = related_model.queryset_with_title().get(pk=val.pk)
            text = str(annotated_obj.annotated_text)
            viewname = model_to_viewname(related_model)  # type: ignore[arg-type] # related_model is a _BaseModelMixin subclass at this point
            url = f"/tables/{viewname}/id/{val.public_id}"
            return ForeignKeyWrapper(id=val.public_id, title=text, url=url)
        # pragma: no cover
        msg = "Untested scenario"
        raise ValueError(msg)

    return RowUpdateForeignKeyValue(
        name=field.name,
        old_value=to_fk_wrapper(old_value),
        new_value=to_fk_wrapper(new_value),
    )


# Type alias for row value serializer functions
RowUpdateValueSerializer = Callable[[DjangoField, Any, Any], RowColumnValueSchema]

# Dict mapping field types to row value serializer functions
ROWUPDATE_VALUE_SERIALIZERS: dict[type[DjangoField], RowUpdateValueSerializer] = {
    models.CharField: _rowupdate_value_char,
    models.TextField: _rowupdate_value_text,
    models.IntegerField: _rowupdate_value_integer,
    models.BooleanField: _rowupdate_value_boolean,
    models.DecimalField: _rowupdate_value_decimal,
    models.DateTimeField: _rowupdate_value_datetime,
    models.FileField: _rowupdate_value_file,
    models.ForeignKey: _rowupdate_value_foreignkey,
    EmailField: _rowupdate_value_char,  # EmailField uses CharField serializer
}


# ------------------ Form Deserializer Classes ---------------------
# These classes parse posted form values, validate them, and return parsed values.
# They use a common base class to share validation logic.


class BaseDeserializer:
    """Base class for form deserializers with common validation logic.

    Uses Template Method pattern - subclasses should override transform() and
    optionally validate_required() for customization.
    """

    def validate_not_blank(self, field: DjangoField, value: typing.Any) -> None:  # noqa: ANN401
        """Raise ValidationError if field blank=False and value is empty string.

        Only applies to text-based fields (CharField, TextField).
        """
        if hasattr(field, "blank") and field.blank is False and value == "":
            msg = "Value is required"
            raise ValidationError(msg)

    def transform(
        self,
        field: DjangoField,  # noqa: ARG002
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> typing.Any:  # noqa: ANN401
        """Transform raw value to Python type. Override in subclasses."""
        return raw_value  # pragma: no cover

    def validate_required(
        self,
        field: DjangoField,
        value: typing.Any,  # noqa: ANN401
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> None:
        """Validate that required fields have a value.

        Override in subclasses to customize required validation behavior.
        """
        if field.null is False and value is None:
            msg = "Value is required"
            raise ValidationError(msg)

    def run_validators(self, field: DjangoField, value: typing.Any) -> None:  # noqa: ANN401
        """Run field validators on the value."""
        if value is not None and value is not UNCHANGED:
            for validator in field.validators:
                validator(value)

    def __call__(
        self,
        field: DjangoField,
        posted_value: str | None,
        files: dict[str, UploadedFile],
        existing_instance: _BaseModelMixin | None,
    ) -> typing.Any:  # noqa: ANN401
        """Deserialize and validate a field from posted form value.

        Template method that orchestrates the validation pipeline.
        Subclasses should override hook methods, not this method.
        """
        raw_value = None if posted_value is None else posted_value.strip()
        value = self.transform(field, raw_value, files, existing_instance)
        self.validate_required(field, value, existing_instance)
        self.run_validators(field, value)
        return value


class CharFieldDeserializer(BaseDeserializer):
    """Deserializer for CharField fields."""

    def transform(
        self,
        field: DjangoField,
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> typing.Any:  # noqa: ANN401
        """Transform and validate CharField value."""
        self.validate_not_blank(field, raw_value)
        if (
            field.choices
            and raw_value is not None
            and raw_value not in [choice[0] for choice in field.choices]
        ):
            msg = "Invalid choice"
            raise ValidationError(msg)
        return raw_value


class TextFieldDeserializer(BaseDeserializer):
    """Deserializer for TextField fields."""

    def transform(
        self,
        field: DjangoField,
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> typing.Any:  # noqa: ANN401
        """Transform and validate TextField value, sanitizing HTML content."""
        if field.blank is False and raw_value == "":
            msg = "Value is required"
            raise ValidationError(msg)
        if raw_value is None:
            return None
        # Sanitize HTML content to allow only whitelisted tags and attributes
        return sanitize_html(raw_value)


class IntegerFieldDeserializer(BaseDeserializer):
    """Deserializer for IntegerField fields."""

    def transform(
        self,
        field: DjangoField,
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,
    ) -> typing.Any:  # noqa: ANN401
        """Transform string to integer and validate choices."""
        if raw_value == "" or raw_value is None:
            if field.null:
                return None
            # For updates, return UNCHANGED to keep existing value
            # For creates with default, return UNCHANGED to use default value
            if existing_instance is not None or field.has_default():
                return UNCHANGED
            return None
        try:
            value = int(raw_value)
        except ValueError:
            msg = f"Not a valid integer: {raw_value}"
            raise ValidationError(msg) from None
        if field.choices and value not in [choice[0] for choice in field.choices]:
            msg = "Invalid choice"
            raise ValidationError(msg)
        return value


class BooleanFieldDeserializer(BaseDeserializer):
    """Deserializer for BooleanField fields."""

    def transform(
        self,
        field: DjangoField,  # noqa: ARG002
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> bool:
        """Transform string to boolean. Boolean is never None - unchecked is False."""
        return str(raw_value).lower() in ("on", "true", "1", "yes")


class DecimalFieldDeserializer(BaseDeserializer):
    """Deserializer for DecimalField fields."""

    def transform(
        self,
        field: DjangoField,  # noqa: ARG002
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> typing.Any:  # noqa: ANN401
        """Transform string to Decimal."""
        if raw_value == "" or raw_value is None:
            return None
        try:
            return decimal.Decimal(raw_value)
        except decimal.InvalidOperation:
            msg = f"Not a valid decimal: {raw_value}"
            raise ValidationError(msg) from None


class DateTimeFieldDeserializer(BaseDeserializer):
    """Deserializer for DateTimeField fields."""

    def transform(
        self,
        field: DjangoField,  # noqa: ARG002
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> typing.Any:  # noqa: ANN401
        """Transform string to datetime. Accepts ISO format with seconds only."""
        if raw_value == "" or raw_value is None:
            return None
        try:
            return datetime.datetime.fromisoformat(raw_value.replace("T", " "))
        except ValueError:
            msg = f"Not a valid datetime: {raw_value}"
            raise ValidationError(msg) from None


class FileFieldDeserializer(BaseDeserializer):
    """Deserializer for FileField fields."""

    def transform(
        self,
        field: DjangoField,
        raw_value: str | None,
        files: dict[str, UploadedFile],
        existing_instance: _BaseModelMixin | None,
    ) -> UploadedFile | None | typing.Any:  # noqa: ANN401
        """Handle file upload, keep existing, or remove."""
        if field.name in files:
            # New file uploaded - replace
            return files[field.name]
        if existing_instance and raw_value == getattr(existing_instance, field.name).name:
            # Keep existing file - don't change
            return UNCHANGED
        # No file uploaded and not keeping existing - remove
        return None


class ForeignKeyFieldDeserializer(BaseDeserializer):
    """Deserializer for ForeignKey fields."""

    def transform(
        self,
        field: DjangoField,
        raw_value: str | None,
        files: dict[str, UploadedFile],  # noqa: ARG002
        existing_instance: _BaseModelMixin | None,  # noqa: ARG002
    ) -> typing.Any:  # noqa: ANN401
        """Transform string to FK model instance."""
        if raw_value == "" or raw_value is None:
            if not field.null:
                msg = f"{field.verbose_name} is required."
                raise ValidationError(msg)
            return None
        related_model = field.related_model
        try:
            return related_model.get_by_public_id(  # type: ignore[union-attr]
                related_model._default_manager.all(),  # type: ignore[union-attr] # noqa: SLF001
                raw_value,
            )
        except ValueError, related_model.DoesNotExist:  # type: ignore[union-attr]
            msg = f"Invalid {related_model.__name__} ID: {raw_value}"  # type: ignore[union-attr]
            raise ValidationError(msg) from None


# Dict mapping field types to form deserializer callables
FORM_DESERIALIZERS: dict[type[DjangoField], FormDeserializer] = {
    models.CharField: CharFieldDeserializer(),
    models.TextField: TextFieldDeserializer(),
    models.IntegerField: IntegerFieldDeserializer(),
    models.BooleanField: BooleanFieldDeserializer(),
    models.DecimalField: DecimalFieldDeserializer(),
    models.DateTimeField: DateTimeFieldDeserializer(),
    models.FileField: FileFieldDeserializer(),
    models.ForeignKey: ForeignKeyFieldDeserializer(),
    EmailField: CharFieldDeserializer(),  # EmailField uses CharField deserializer
}


# ------------------ ValueWrapper Classes ---------------------
# Each wrapper holds a field definition, its raw Python value, and optionally
# pre-fetched FK title data.  Three output methods cover every consumer:
# - as_json()  -> JSONValue   — API serialization (replaces JSON_VALUE_SERIALIZERS)
# - as_td()    -> BaseContent  — table cell rendering (replaces field_value_to_td)
# - as_input() -> InputSchema  — form input with value
#   (replaces field_schema_to_input + field_values)


@dataclass(frozen=True)
class ForeignKeyTitleData:
    public_id: str
    title: str


type FkTitlesMap = dict[str, dict[int, ForeignKeyTitleData]]


@dataclass
class BaseValueWrapper:
    field: DjangoField
    value: Any
    instance: _BaseModelMixin
    context: str = "list"

    def _schema(self) -> BaseFieldSchema:
        return SCHEMA_SERIALIZERS[type(self.field)](self.field)

    def as_json(self) -> JSONValue:
        msg = "Subclasses must implement as_json()"
        raise NotImplementedError(msg)

    def as_td(self) -> BaseContent:
        msg = "Subclasses must implement as_td()"
        raise NotImplementedError(msg)

    def as_input(self) -> InputSchema:
        msg = "Subclasses must implement as_input()"
        raise NotImplementedError(msg)


@dataclass
class CharValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        return self.value if self.value is not None else None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, CharFieldSchema)
        return CharFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, CharFieldSchema)
        return CharFieldInputSchema(
            name=schema.name,
            required=schema.required,
            max_length=schema.max_length,
            choices=schema.choices,
            default=self.value if self.value is not None else schema.default,
        )


@dataclass
class TextValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        return self.value if self.value is not None else None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        assert isinstance(json_val, str)
        if self.context == "details":
            return TextHtmlContent(value=sanitize_html(json_val))
        plain = strip_html(json_val)
        max_len = 200
        truncated = (plain[:max_len] + "…") if len(plain) > max_len else plain
        return TextContent(value=truncated)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, TextFieldSchema)
        return TextFieldInputSchema(
            name=schema.name,
            required=schema.required,
            length=schema.length,
            default=self.value if self.value is not None else schema.default,
        )


@dataclass
class IntegerValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        return self.value if self.value is not None else None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, IntegerFieldSchema)
        return IntegerFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, IntegerFieldSchema)
        return IntegerFieldInputSchema(
            name=schema.name,
            required=schema.required,
            choices=schema.choices,
            default=self.value if self.value is not None else schema.default,
        )


@dataclass
class BooleanValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        return self.value if self.value is not None else None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, BooleanFieldSchema)
        return BooleanFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, BooleanFieldSchema)
        return BooleanFieldInputSchema(
            name=schema.name,
            required=schema.required,
            default=self.value if self.value is not None else schema.default,
        )


@dataclass
class DecimalValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        return str(self.value) if self.value is not None else None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, DecimalFieldSchema)
        return DecimalFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, DecimalFieldSchema)
        serialized = str(self.value) if self.value is not None else None
        return DecimalFieldInputSchema(
            name=schema.name,
            required=schema.required,
            decimal_places=schema.decimal_places,
            default=serialized if serialized is not None else schema.default,
        )


@dataclass
class DateTimeValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        value = self.value
        if value:
            if timezone.is_naive(value):
                value = timezone.make_aware(value)
            return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")
        return None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, DateTimeFieldSchema)
        return DateTimeFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, DateTimeFieldSchema)
        serialized = typing.cast(str | None, self.as_json())
        return DateTimeFieldInputSchema(
            name=schema.name,
            required=schema.required,
            default=serialized if serialized is not None else schema.default,
        )


@dataclass
class FileValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        value = self.value
        if value:
            viewname = model_to_viewname(type(self.instance))
            row_id = self.instance.public_id
            download_url = f"/tables/{viewname}/download-file/{row_id}/{self.field.name}"
            return {"filename": value.name, "download_url": download_url}
        return None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, FileFieldSchema)
        return FileFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, FileFieldSchema)
        json_val = typing.cast(dict[str, str] | None, self.as_json())
        return FileFieldInputSchema(
            name=schema.name,
            required=schema.required,
            default=json_val,
        )


@dataclass
class ForeignKeyValueWrapper(BaseValueWrapper):
    def as_json(self) -> JSONValue:
        fk_id = getattr(self.instance, f"{self.field.name}_id", None)
        if fk_id is None:
            return None

        fk_titles = getattr(self.instance, "_fk_titles", None)
        assert fk_titles is not None, "Annotation was not done"
        field_titles = fk_titles.get(self.field.name)
        if field_titles:
            title_data = field_titles.get(fk_id)
            if title_data:
                return {"id": title_data.public_id, "text": title_data.title}
        return None

    def as_td(self) -> BaseContent:
        json_val = self.as_json()
        if json_val is None:
            return NullContent()
        schema = self._schema()
        assert isinstance(schema, ForeignKeyFieldSchema)
        return ForeignKeyFieldContent.initialize(schema, json_val)

    def as_input(self) -> InputSchema:
        schema = self._schema()
        assert isinstance(schema, ForeignKeyFieldSchema)
        json_val = typing.cast(dict[str, Any] | None, self.as_json())
        return ForeignKeyFieldInputSchema(
            name=schema.name,
            required=schema.required,
            view_name=schema.view_name,
            default=json_val,
        )


VALUE_WRAPPER_TYPES: dict[type[DjangoField], type[BaseValueWrapper]] = {
    models.CharField: CharValueWrapper,
    models.TextField: TextValueWrapper,
    models.IntegerField: IntegerValueWrapper,
    models.BooleanField: BooleanValueWrapper,
    models.DecimalField: DecimalValueWrapper,
    models.DateTimeField: DateTimeValueWrapper,
    models.FileField: FileValueWrapper,
    models.ForeignKey: ForeignKeyValueWrapper,
    EmailField: CharValueWrapper,
}
