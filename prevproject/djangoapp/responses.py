"""Response schemas for API endpoints.

This module contains Pydantic response schemas to avoid circular imports
between models and views.

We will try to keep it synced with schemas.ts
"""

import datetime  # noqa: TC003 pydantic needs datetime at runtime in Python 3.14
import typing
from typing import Annotated, Any, Literal

from django.db.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
)
from django.db.models.fields.related import ForeignKey
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, PrivateAttr


class UserSchema(PydanticBaseModel):
    """Schema for user information in responses."""

    id: int
    title: str


class RowUpdateResponse(PydanticBaseModel):
    """Schema for row update information in responses."""

    id: str
    action: Literal["created_row", "updated_row", "commented"]
    created_at: datetime.datetime
    created_by: UserSchema | None
    column_values: list[Any] | None
    comment_content: str | None
    comment_deleted_at: datetime.datetime | None
    comment_deleted_by: UserSchema | None
    comment_edited_at: datetime.datetime | None


class RowUpdateListResponse(PydanticBaseModel):
    """Schema for list of row updates in responses."""

    can_create_comment: bool
    edit_comment_timeout: int | None
    delete_comment_timeout: int | None
    updates: list[RowUpdateResponse]


class NotificationItem(PydanticBaseModel):
    id: str
    viewname: str
    row_public_id: str
    row_update: dict[str, Any]


class NotificationListResponse(PydanticBaseModel):
    notifications: list[NotificationItem]
    viewname_counts: dict[str, int]
    total_count: int
    current_page: int
    total_pages: int


class DeleteNotificationsResponse(PydanticBaseModel):
    deleted_count: int


class CommentResponse(PydanticBaseModel):
    message: str
    comment_id: str


class DeleteRowResponse(PydanticBaseModel):
    message: str


class SearchRowItem(PydanticBaseModel):
    id: str
    title: str


class SearchRowsResponse(PydanticBaseModel):
    rows: list[SearchRowItem]


# ------------------ FieldSchema Pydantic Models ---------------------
# Schema definitions for field metadata sent to frontend.


class BaseFieldSchema(PydanticBaseModel):
    """Base class for all field schema types."""

    model_config = ConfigDict(
        populate_by_name=True, serialize_by_alias=True, validate_by_alias=True
    )

    name: str
    required: bool
    discriminator: str

    def to_th(self) -> ThSchema:
        return ThSchema(name=self.name)


class CharFieldSchema(BaseFieldSchema):
    discriminator: Literal["char"] = Field(default="char", alias="d")
    _field_type: type[CharField] = PrivateAttr(default=CharField)  # type: ignore[type-arg]
    required: bool
    max_length: int
    choices: list[dict[str, str]] | None
    default: str | None


class TextFieldSchema(BaseFieldSchema):
    discriminator: Literal["text"] = Field(default="text", alias="d")
    _field_type: type[CharField] = PrivateAttr(default=CharField)  # type: ignore[type-arg]
    required: bool
    length: int
    default: str | None


class IntegerFieldSchema(BaseFieldSchema):
    discriminator: Literal["integer"] = Field(default="integer", alias="d")
    _field_type: type[IntegerField] = PrivateAttr(default=IntegerField)  # type: ignore[type-arg]
    required: bool
    choices: list[dict[str, str]] | None
    default: int | None


class BooleanFieldSchema(BaseFieldSchema):
    discriminator: Literal["boolean"] = Field(default="boolean", alias="d")
    _field_type: type[BooleanField] = PrivateAttr(default=BooleanField)  # type: ignore[type-arg]
    required: bool
    default: bool | None = Field(default=None)


class DecimalFieldSchema(BaseFieldSchema):
    discriminator: Literal["decimal"] = Field(default="decimal", alias="d")
    _field_type: type[DecimalField] = PrivateAttr(default=DecimalField)  # type: ignore[type-arg]
    required: bool
    decimal_places: int
    default: str | None


class DateTimeFieldSchema(BaseFieldSchema):
    discriminator: Literal["datetime"] = Field(default="datetime", alias="d")
    _field_type: type[DateTimeField] = PrivateAttr(default=DateTimeField)  # type: ignore[type-arg]
    required: bool
    default: str | None


class FileFieldSchema(BaseFieldSchema):
    discriminator: Literal["file"] = Field(default="file", alias="d")
    required: bool
    default: str | None = None


class ForeignKeyFieldSchema(BaseFieldSchema):
    discriminator: Literal["foreignkey"] = Field(default="foreignkey", alias="d")
    _field_type: type[ForeignKey] = PrivateAttr(default=ForeignKey)  # type: ignore[type-arg]
    required: bool
    view_name: str
    default: dict[str, Any] | None = None


# Union type for all field schemas - used for proper serialization
FieldSchema = (
    CharFieldSchema
    | TextFieldSchema
    | IntegerFieldSchema
    | BooleanFieldSchema
    | DecimalFieldSchema
    | DateTimeFieldSchema
    | FileFieldSchema
    | ForeignKeyFieldSchema
)


# ------------------ InputSchema Pydantic Models ---------------------
# Schema definitions for input field components sent to frontend for form rendering.


class BaseInputSchema(PydanticBaseModel):
    model_config = ConfigDict(
        populate_by_name=True, serialize_by_alias=True, validate_by_alias=True
    )

    discriminator: str
    component: str
    name: str
    required: bool


class CharFieldInputSchema(BaseInputSchema):
    discriminator: Literal["char"] = Field(default="char", alias="d")
    component: str = "/components/inputs/CharFieldInput"
    max_length: int | None = None
    choices: list[dict[str, str]] | None = None
    default: str | None = None


class TextFieldInputSchema(BaseInputSchema):
    discriminator: Literal["text"] = Field(default="text", alias="d")
    component: str = "/components/inputs/TextFieldInput"
    length: int
    default: str | None = None


class IntegerFieldInputSchema(BaseInputSchema):
    discriminator: Literal["integer"] = Field(default="integer", alias="d")
    component: str = "/components/inputs/IntegerFieldInput"
    choices: list[dict[str, str]] | None = None
    default: int | None = None


class BooleanFieldInputSchema(BaseInputSchema):
    discriminator: Literal["boolean"] = Field(default="boolean", alias="d")
    component: str = "/components/inputs/BooleanFieldInput"
    default: bool | None = Field(default=None)


class DecimalFieldInputSchema(BaseInputSchema):
    discriminator: Literal["decimal"] = Field(default="decimal", alias="d")
    component: str = "/components/inputs/DecimalFieldInput"
    decimal_places: int
    default: str | None = None


class DateTimeFieldInputSchema(BaseInputSchema):
    discriminator: Literal["datetime"] = Field(default="datetime", alias="d")
    component: str = "/components/inputs/DateTimeFieldInput"
    default: str | None = None


class FileFieldInputSchema(BaseInputSchema):
    discriminator: Literal["file"] = Field(default="file", alias="d")
    component: str = "/components/inputs/FileFieldInput"
    default: dict[str, str] | None = None


class ForeignKeyFieldInputSchema(BaseInputSchema):
    discriminator: Literal["foreignkey"] = Field(default="foreignkey", alias="d")
    component: str = "/components/inputs/ForeignKeyFieldInput"
    view_name: str
    default: dict[str, Any] | None = None


InputSchema = (
    CharFieldInputSchema
    | TextFieldInputSchema
    | IntegerFieldInputSchema
    | BooleanFieldInputSchema
    | DecimalFieldInputSchema
    | DateTimeFieldInputSchema
    | FileFieldInputSchema
    | ForeignKeyFieldInputSchema
)


# ------------------ RowColumnValue Pydantic Models ---------------------
# Schema definitions for row update column values sent to the frontend.


# Wrapper classes for complex value types (choice fields, foreign keys)
class IntegerChoiceWrapper(PydanticBaseModel):
    """Wrapper for integer choice values with value and title."""

    value: int | None
    value_title: str | None = None


class CharChoiceWrapper(PydanticBaseModel):
    """Wrapper for char choice values with value and title."""

    value: str | None
    value_title: str | None = None


class ForeignKeyWrapper(PydanticBaseModel):
    """Wrapper for foreign key values with id, title, and url."""

    id: str
    title: str
    url: str


class BaseRowValueSchema(PydanticBaseModel):
    """Base class for all row update column value schema types."""

    model_config = ConfigDict(
        populate_by_name=True, serialize_by_alias=True, validate_by_alias=True
    )

    discriminator: str
    name: str


class RowUpdateBooleanValue(BaseRowValueSchema):
    """Boolean column value for row updates."""

    discriminator: typing.Literal["boolean"] = Field(default="boolean", alias="d")
    old_value: bool | None = None
    new_value: bool | None = None


class RowUpdateIntegerValue(BaseRowValueSchema):
    """Integer column value for row updates."""

    discriminator: typing.Literal["integer"] = Field(default="integer", alias="d")
    old_value: int | None = None
    new_value: int | None = None


class RowUpdateIntegerChoiceValue(BaseRowValueSchema):
    """Integer choice column value for row updates."""

    discriminator: typing.Literal["integer-choice"] = Field(default="integer-choice", alias="d")
    old_value: IntegerChoiceWrapper | None = None
    new_value: IntegerChoiceWrapper | None = None


class RowUpdateCharValue(BaseRowValueSchema):
    """Char column value for row updates."""

    discriminator: typing.Literal["char"] = Field(default="char", alias="d")
    old_value: str | None = None
    new_value: str | None = None


class RowUpdateCharChoiceValue(BaseRowValueSchema):
    """Char choice column value for row updates."""

    discriminator: typing.Literal["char_choice"] = Field(default="char_choice", alias="d")
    old_value: CharChoiceWrapper | None = None
    new_value: CharChoiceWrapper | None = None


class RowUpdateTextValue(BaseRowValueSchema):
    """Text column value for row updates."""

    discriminator: typing.Literal["text"] = Field(default="text", alias="d")
    old_value: str | None = None
    new_value: str | None = None


class RowUpdateDecimalValue(BaseRowValueSchema):
    """Decimal column value for row updates (serialized as string)."""

    discriminator: typing.Literal["decimal"] = Field(default="decimal", alias="d")
    old_value: str | None = None
    new_value: str | None = None


class RowUpdateForeignKeyValue(BaseRowValueSchema):
    """ForeignKey column value for row updates."""

    discriminator: typing.Literal["foreign_key"] = Field(default="foreign_key", alias="d")
    old_value: ForeignKeyWrapper | None = None
    new_value: ForeignKeyWrapper | None = None


class RowUpdateDatetimeValue(BaseRowValueSchema):
    """Datetime column value for row updates (serialized as ISO format string)."""

    discriminator: typing.Literal["datetime"] = Field(default="datetime", alias="d")
    old_value: str | None = None
    new_value: str | None = None


class RowUpdateFileValue(BaseRowValueSchema):
    """File column value for row updates (stores filename)."""

    discriminator: typing.Literal["file"] = Field(default="file", alias="d")
    old_value: str | None = None
    new_value: str | None = None


# Discriminated union for deserialization - uses discriminator field to determine concrete type
RowColumnValueSchema = Annotated[
    (
        RowUpdateBooleanValue
        | RowUpdateIntegerValue
        | RowUpdateIntegerChoiceValue
        | RowUpdateCharValue
        | RowUpdateCharChoiceValue
        | RowUpdateTextValue
        | RowUpdateDecimalValue
        | RowUpdateForeignKeyValue
        | RowUpdateDatetimeValue
        | RowUpdateFileValue
    ),
    Field(discriminator="discriminator"),
]


# ------------------ Th/Td Pydantic Models ---------------------
# Table header (Th) and table data cell (Td) schemas for rendering.


class ThSchema(PydanticBaseModel):
    name: str
    component: str = "/components/cells/Th"


class BaseContent(PydanticBaseModel):
    component: str
    value: Any

    @classmethod
    def initialize(cls, schema: BaseFieldSchema, raw_value: Any) -> BaseContent:  # noqa: ANN401
        msg = "Subclasses must implement initialize()"
        raise NotImplementedError(msg)

    def as_html(self) -> str:
        return str(self.value) if self.value is not None else "—"


class NullContent(BaseContent):
    component: str = "/components/cells/NullTd"
    value: None = None

    @classmethod
    def initialize(cls, _schema: BaseFieldSchema, _raw_value: Any) -> NullContent:  # noqa: ANN401
        return cls()

    def as_html(self) -> str:
        return "—"


class CharFieldContent(BaseContent):
    component: str = "/components/cells/CharFieldTd"
    value: str

    @classmethod
    def initialize(cls, schema: BaseFieldSchema, raw_value: Any) -> CharFieldContent:  # noqa: ANN401
        assert isinstance(raw_value, str), f"Expected str, got {type(raw_value).__name__}"
        choices = getattr(schema, "choices", None)
        if choices:
            for choice in choices:
                if str(choice.get("value")) == str(raw_value):
                    return cls(value=str(choice.get("label", raw_value)))
        return cls(value=raw_value)


class TextContent(BaseContent):
    component: str = "/components/cells/TextFieldTd"
    value: str

    @classmethod
    def initialize(cls, _schema: BaseFieldSchema, raw_value: Any) -> TextContent:  # noqa: ANN401
        assert isinstance(raw_value, str), f"Expected str, got {type(raw_value).__name__}"
        return cls(value=raw_value)


class TextHtmlContent(BaseContent):
    component: str = "/components/cells/TextFieldHtmlTd"
    value: str

    def as_html(self) -> str:
        return self.value


class IntegerFieldContent(BaseContent):
    component: str = "/components/cells/IntegerFieldTd"
    value: str | int

    @classmethod
    def initialize(cls, schema: BaseFieldSchema, raw_value: Any) -> IntegerFieldContent:  # noqa: ANN401
        assert isinstance(raw_value, int), f"Expected int, got {type(raw_value).__name__}"
        choices = getattr(schema, "choices", None)
        if choices:
            for choice in choices:
                if str(choice.get("value")) == str(raw_value):
                    return cls(value=choice.get("label", raw_value))
        return cls(value=raw_value)


class BooleanFieldContent(BaseContent):
    component: str = "/components/cells/BooleanFieldTd"
    value: bool

    @classmethod
    def initialize(cls, _schema: BaseFieldSchema, raw_value: Any) -> BooleanFieldContent:  # noqa: ANN401
        assert isinstance(raw_value, bool), f"Expected bool, got {type(raw_value).__name__}"
        return cls(value=raw_value)

    def as_html(self) -> str:
        return "Yes" if self.value else "No"


class DecimalFieldContent(BaseContent):
    component: str = "/components/cells/DecimalFieldTd"
    value: str

    @classmethod
    def initialize(cls, _schema: BaseFieldSchema, raw_value: Any) -> DecimalFieldContent:  # noqa: ANN401
        assert isinstance(raw_value, str), f"Expected str, got {type(raw_value).__name__}"
        return cls(value=raw_value)


class DateTimeFieldContent(BaseContent):
    component: str = "/components/cells/DateTimeFieldTd"
    value: str

    @classmethod
    def initialize(cls, _schema: BaseFieldSchema, raw_value: Any) -> DateTimeFieldContent:  # noqa: ANN401
        assert isinstance(raw_value, str), f"Expected str, got {type(raw_value).__name__}"
        return cls(value=raw_value)


class ForeignKeyContentValue(PydanticBaseModel):
    id: str
    title: str
    viewname: str


class FileFieldContent(BaseContent):
    component: str = "/components/cells/FileFieldTd"
    value: dict[str, str]

    @classmethod
    def initialize(cls, _schema: BaseFieldSchema, raw_value: Any) -> FileFieldContent:  # noqa: ANN401
        assert isinstance(raw_value, dict), f"Expected dict, got {type(raw_value).__name__}"
        return cls(value=raw_value)

    def as_html(self) -> str:
        return self.value.get("filename", "—")


class ForeignKeyFieldContent(BaseContent):
    component: str = "/components/cells/ForeignKeyFieldTd"
    value: ForeignKeyContentValue

    @classmethod
    def initialize(cls, schema: BaseFieldSchema, raw_value: Any) -> ForeignKeyFieldContent:  # noqa: ANN401
        assert isinstance(schema, ForeignKeyFieldSchema)
        assert isinstance(raw_value, dict), f"Expected dict, got {type(raw_value).__name__}"
        return cls(
            value=ForeignKeyContentValue(
                id=raw_value["id"],
                title=raw_value.get("text", ""),
                viewname=schema.view_name,
            )
        )

    def as_html(self) -> str:
        return self.value.title
