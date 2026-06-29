"""Pydantic schemas for the ``applications`` management command.

Every subcommand validates its inputs against one of these schemas. The
schemas enforce format (alphanumeric names, valid column types),
cross-field rules (old != new, duplicate column names) and DB-dependent
rules (existence, name clashes) via ``model_validator``. Resolved
model instances are stashed in ``PrivateAttr`` fields and exposed via
read-only properties, so the command handlers reuse them without
re-querying.

Column specs are a discriminated union: each column type carries only
its own fields (a boolean column has no ``min_length``/``max_digits``, a
datetime carries only ``nullable``).

Each long rule-set is split into several small ``@model_validator(mode="after")``
methods that run in source order: resolve first, then enforce each check in
turn. ``mode="after"`` is explicit on every validator because pydantic 2.13
requires the ``mode`` argument (a bare ``@model_validator`` raises
``TypeError`` at runtime). A failed validation surfaces as a printed,
non-zero-exit error (never a traceback), since the command is meant to be
driven by agents.
"""

from decimal import (
    Decimal,  # noqa: TC003 # pydantic resolves Decimal at model build time, not just for typing
)
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationInfo,
    field_validator,
    model_validator,
)

from djangoapp.models import (
    Application,
    ApplicationCollection,
    ApplicationTable,
)


def _must_be_alphanumeric_name(value: str, field_name: str) -> str:
    """All user-facing names must start with a letter, then letters/digits only.

    Shared by collection/app/table names and column names: a leading digit
    is rejected to match the model-level validator, and excluding the
    underscore keeps user names out of the underscore-prefixed built-in
    column namespace (_public_id, _created_by, ...).
    """
    if not value or not value[0].isalpha() or not value.isalnum():
        msg = f"'{field_name}' must start with a letter and contain only letters and digits."
        raise ValueError(msg)
    return value


# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------


class CreateApplicationCollectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _must_be_alphanumeric_name(v, "name")

    @model_validator(mode="after")
    def _reject_name_clash(self) -> CreateApplicationCollectionSchema:
        """Reject if a collection with this name already exists."""
        if ApplicationCollection.objects.filter(name=self.name).exists():
            msg = f"A collection named '{self.name}' already exists."
            raise ValueError(msg)
        return self


class RenameApplicationCollectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_name: str = Field(min_length=1, max_length=100)
    new_name: str = Field(min_length=1, max_length=100)
    _collection: ApplicationCollection = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @field_validator("old_name", "new_name")
    @classmethod
    def _check_names(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @property
    def collection(self) -> ApplicationCollection:
        return self._collection

    @model_validator(mode="after")
    def _reject_noop(self) -> RenameApplicationCollectionSchema:
        """Reject a no-op rename (old name == new name).

        Exact match, mirroring the app/table rename checks: names are
        case-sensitive everywhere else, so ``Foo`` -> ``foo`` is a real
        rename and is allowed.
        """
        if self.old_name == self.new_name:
            msg = "new_name must differ from old_name."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _resolve_collection(self) -> RenameApplicationCollectionSchema:
        """Look up the existing collection by old name."""
        try:
            self._collection = ApplicationCollection.objects.get(name=self.old_name)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.old_name}'."
            raise ValueError(msg) from exc
        return self

    @model_validator(mode="after")
    def _reject_new_name_clash(self) -> RenameApplicationCollectionSchema:
        """Reject if another collection already uses the new name."""
        clash = (
            ApplicationCollection.objects.exclude(pk=self._collection.pk)
            .filter(name=self.new_name)
            .exists()
        )
        if clash:
            msg = f"A collection named '{self.new_name}' already exists."
            raise ValueError(msg)
        return self


class DeleteApplicationCollectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    _collection: ApplicationCollection = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def collection(self) -> ApplicationCollection:
        return self._collection

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _must_be_alphanumeric_name(v, "name")

    @model_validator(mode="after")
    def _resolve_collection(self) -> DeleteApplicationCollectionSchema:
        try:
            self._collection = ApplicationCollection.objects.get(name=self.name)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.name}'."
            raise ValueError(msg) from exc
        return self


class ListApplicationCollectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    _collection: ApplicationCollection = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def collection(self) -> ApplicationCollection:
        return self._collection

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _must_be_alphanumeric_name(v, "name")

    @model_validator(mode="after")
    def _resolve_collection(self) -> ListApplicationCollectionSchema:
        try:
            self._collection = ApplicationCollection.objects.get(name=self.name)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.name}'."
            raise ValueError(msg) from exc
        return self


# ---------------------------------------------------------------------------
# Application schemas
# ---------------------------------------------------------------------------


class CreateApplicationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appcollection: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    desc: str = ""
    _collection: ApplicationCollection = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def collection(self) -> ApplicationCollection:
        return self._collection

    @field_validator("appcollection", "name")
    @classmethod
    def _check_alnum(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @model_validator(mode="after")
    def _resolve_collection(self) -> CreateApplicationSchema:
        """Look up the parent collection by name."""
        try:
            self._collection = ApplicationCollection.objects.get(name=self.appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        return self

    @model_validator(mode="after")
    def _reject_app_name_clash(self) -> CreateApplicationSchema:
        """Reject if an app with this name already exists in the collection."""
        clash = Application.objects.filter(
            application_collection=self._collection,
            name=self.name,
        ).exists()
        if clash:
            msg = f"An application named '{self.name}' already exists in collection '{self.appcollection}'."  # noqa: E501 let user-facing message stay on one line
            raise ValueError(msg)
        return self


class RenameApplicationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_appcollection: str = Field(min_length=1, max_length=100)
    old_name: str = Field(min_length=1, max_length=100)
    new_appcollection: str = Field(min_length=1, max_length=100)
    new_name: str = Field(min_length=1, max_length=100)
    _application: Application = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator
    _new_collection: ApplicationCollection = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def application(self) -> Application:
        return self._application

    @property
    def new_collection(self) -> ApplicationCollection:
        return self._new_collection

    @field_validator("old_appcollection", "old_name", "new_appcollection", "new_name")
    @classmethod
    def _check_alnum(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @model_validator(mode="after")
    def _resolve_source_app(self) -> RenameApplicationSchema:
        """Look up the source collection and the app within it."""
        try:
            old_collection = ApplicationCollection.objects.get(name=self.old_appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.old_appcollection}'."
            raise ValueError(msg) from exc
        try:
            self._application = Application.objects.get(
                application_collection=old_collection,
                name=self.old_name,
            )
        except Application.DoesNotExist as exc:
            msg = f"No application '{self.old_name}' in collection '{self.old_appcollection}'."
            raise ValueError(msg) from exc
        return self

    @model_validator(mode="after")
    def _resolve_new_collection(self) -> RenameApplicationSchema:
        """Look up the destination collection by name."""
        try:
            self._new_collection = ApplicationCollection.objects.get(name=self.new_appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.new_appcollection}'."
            raise ValueError(msg) from exc
        return self

    @model_validator(mode="after")
    def _reject_collection_move(self) -> RenameApplicationSchema:
        """Forbid moving an app between collections.

        Moving an app (and its tables) to a different collection is not a
        supported feature: an app's name is its identity and is unique only
        within its collection, so a move would break name-as-identity in
        URLs and across tables.
        """
        if self._application.application_collection != self._new_collection:
            msg = (
                "Moving an application to a different collection is not supported; "
                "an application's name is scoped to its collection."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_noop(self) -> RenameApplicationSchema:
        """Reject a no-op rename (same name)."""
        if self.new_name == self.old_name:
            msg = "new_name must differ from old_name."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_destination_clash(self) -> RenameApplicationSchema:
        """Reject if another app in the collection already has the new name."""
        clash = (
            Application.objects.exclude(pk=self._application.pk)
            .filter(application_collection=self._new_collection, name=self.new_name)
            .exists()
        )
        if clash:
            msg = (
                f"An application named '{self.new_name}' already exists "
                f"in collection '{self.new_appcollection}'."
            )
            raise ValueError(msg)
        return self


class DeleteApplicationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appcollection: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    _application: Application = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def application(self) -> Application:
        return self._application

    @field_validator("appcollection", "name")
    @classmethod
    def _check_alnum(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @model_validator(mode="after")
    def _resolve_app(self) -> DeleteApplicationSchema:
        """Look up the collection and the app within it."""
        try:
            collection = ApplicationCollection.objects.get(name=self.appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        try:
            self._application = Application.objects.get(
                application_collection=collection,
                name=self.name,
            )
        except Application.DoesNotExist as exc:
            msg = f"No application '{self.name}' in collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        return self


# ---------------------------------------------------------------------------
# Column specs (discriminated union: each type carries only its own fields)
# ---------------------------------------------------------------------------


class _ColumnBase(BaseModel):
    """Shared shape for every column spec: an alphanumeric user column name.

    Subclasses pin ``type`` to a single literal and add only the fields
    relevant to that column kind, so a boolean column has no
    ``min_length``/``max_digits`` and a datetime has only ``nullable``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return _must_be_alphanumeric_name(v, "name")


class CharColumnSpec(_ColumnBase):
    """char: a short string, optional enumerated choices, length bounds."""

    type: Literal["char"] = "char"
    default: str = ""
    choices: list[str] = Field(default_factory=list)
    min_length: int = 0
    max_length: int = 1000

    @model_validator(mode="after")
    def _max_gte_min(self) -> CharColumnSpec:
        if self.max_length < self.min_length:
            msg = "max_length cannot be less than min_length."
            raise ValueError(msg)
        return self


class TextColumnSpec(_ColumnBase):
    """text: a long string with length bounds (no DB max length)."""

    type: Literal["text"] = "text"
    default: str = ""
    min_length: int = 0
    max_length: int = 1000

    @model_validator(mode="after")
    def _max_gte_min(self) -> TextColumnSpec:
        if self.max_length < self.min_length:
            msg = "max_length cannot be less than min_length."
            raise ValueError(msg)
        return self


class IntegerColumnSpec(_ColumnBase):
    """integer: a whole number with a default and optional nullability."""

    type: Literal["integer"] = "integer"
    default: int = 0
    nullable: bool = False


class BooleanColumnSpec(_ColumnBase):
    """boolean: a true/false flag with a default."""

    type: Literal["boolean"] = "boolean"
    default: bool = False


class DecimalColumnSpec(_ColumnBase):
    """decimal: a fixed-precision number with digits/places and nullability."""

    type: Literal["decimal"] = "decimal"
    default: Decimal | None = None
    nullable: bool = False
    max_digits: int = 10
    decimal_places: int = 2

    @model_validator(mode="after")
    def _places_le_digits(self) -> DecimalColumnSpec:
        if self.decimal_places > self.max_digits:
            msg = "decimal_places cannot exceed max_digits."
            raise ValueError(msg)
        return self


class DatetimeColumnSpec(_ColumnBase):
    """datetime: a timestamp; no default, optionally nullable."""

    type: Literal["datetime"] = "datetime"
    nullable: bool = False


class UserColumnSpec(_ColumnBase):
    """user: a ForeignKey to the project User; optionally nullable."""

    type: Literal["user"] = "user"
    nullable: bool = False


# Discriminated union: pydantic picks the right subclass from ``type``.
ColumnSpec = Annotated[
    CharColumnSpec
    | TextColumnSpec
    | IntegerColumnSpec
    | BooleanColumnSpec
    | DecimalColumnSpec
    | DatetimeColumnSpec
    | UserColumnSpec,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Table schemas
# ---------------------------------------------------------------------------


class CreateApplicationTableSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appcollection: str
    app: str
    name: str
    columns: list[ColumnSpec]
    _application: Application = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def application(self) -> Application:
        return self._application

    @field_validator("appcollection", "app", "name")
    @classmethod
    def _check_alnum(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @model_validator(mode="after")
    def _resolve_parent_application(self) -> CreateApplicationTableSchema:
        """Look up the parent collection and the app within it."""
        try:
            collection = ApplicationCollection.objects.get(name=self.appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        try:
            self._application = Application.objects.get(
                application_collection=collection,
                name=self.app,
            )
        except Application.DoesNotExist as exc:
            msg = f"No application '{self.app}' in collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        return self

    @model_validator(mode="after")
    def _reject_table_name_clash(self) -> CreateApplicationTableSchema:
        """Reject a collection-scoped table name clash (physical name omits app)."""
        clash = ApplicationTable.objects.filter(
            application__application_collection=self._application.application_collection,
            name=self.name,
        ).exists()
        if clash:
            msg = (
                f"A table named '{self.name}' already exists in collection '{self.appcollection}'."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_invalid_columns(self) -> CreateApplicationTableSchema:
        """Reject an empty column list and duplicate column names."""
        if not self.columns:
            msg = "A table requires at least one column."
            raise ValueError(msg)
        names = [c.name for c in self.columns]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            msg = f"Duplicate column name(s) in payload: {sorted(dupes)}."
            raise ValueError(msg)
        return self


class _TableTargetSchema(BaseModel):
    """Shared base resolving appcollection/app/table to live rows."""

    model_config = ConfigDict(extra="forbid")

    appcollection: str
    app: str
    table: str
    _application: Application = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator
    _application_table: ApplicationTable = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def application(self) -> Application:
        return self._application

    @property
    def application_table(self) -> ApplicationTable:
        return self._application_table

    @field_validator("appcollection", "app", "table")
    @classmethod
    def _check_alnum(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @model_validator(mode="after")
    def _resolve_table(self) -> _TableTargetSchema:
        """Resolve the collection, app and table rows named by the request."""
        try:
            collection = ApplicationCollection.objects.get(name=self.appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        try:
            self._application = Application.objects.get(
                application_collection=collection,
                name=self.app,
            )
        except Application.DoesNotExist as exc:
            msg = f"No application '{self.app}' in collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        try:
            self._application_table = ApplicationTable.objects.get(
                application=self._application,
                name=self.table,
            )
        except ApplicationTable.DoesNotExist as exc:
            msg = f"No table '{self.table}' in application '{self.app}'."
            raise ValueError(msg) from exc
        return self


class AddApplicationTableColumnsSchema(_TableTargetSchema):
    columns: list[ColumnSpec]

    @model_validator(mode="after")
    def _reject_empty_columns(self) -> AddApplicationTableColumnsSchema:
        """Reject an empty column list."""
        if not self.columns:
            msg = "At least one column is required."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_duplicate_columns_in_payload(self) -> AddApplicationTableColumnsSchema:
        """Reject duplicate column names within the payload."""
        names = [c.name for c in self.columns]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            msg = f"Duplicate column name(s) in payload: {sorted(dupes)}."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_existing_columns(self) -> AddApplicationTableColumnsSchema:
        """Reject any new name that already exists on the table."""
        existing = {c.name for c in self._application_table.columns.all()}
        clashes = sorted({c.name for c in self.columns if c.name in existing})
        if clashes:
            msg = f"Column(s) already exist on table '{self.table}': {clashes}."
            raise ValueError(msg)
        return self


class DeleteApplicationTableColumnsSchema(_TableTargetSchema):
    columns: list[str]

    @field_validator("columns")
    @classmethod
    def _non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            msg = "At least one column is required."
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _columns_exist(self) -> DeleteApplicationTableColumnsSchema:
        """Reject columns not present on the table (table resolved by base)."""
        existing = {c.name for c in self._application_table.columns.all()}
        missing = sorted({c for c in self.columns if c not in existing})
        if missing:
            msg = f"Column(s) not found on table '{self.table}': {missing}."
            raise ValueError(msg)
        return self


class _TableLookupSchema(BaseModel):
    """Shared base for describe/delete_application_table (no columns field)."""

    model_config = ConfigDict(extra="forbid")

    appcollection: str
    app: str
    name: str
    _application_table: ApplicationTable = PrivateAttr(default=None)  # type: ignore[assignment] # set by validator

    @property
    def application_table(self) -> ApplicationTable:
        return self._application_table

    @field_validator("appcollection", "app", "name")
    @classmethod
    def _check_alnum(cls, v: str, info: ValidationInfo[object]) -> str:
        return _must_be_alphanumeric_name(v, info.field_name or "value")

    @model_validator(mode="after")
    def _resolve_table(self) -> _TableLookupSchema:
        """Resolve the collection, app and table rows named by the request."""
        try:
            collection = ApplicationCollection.objects.get(name=self.appcollection)
        except ApplicationCollection.DoesNotExist as exc:
            msg = f"No collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        try:
            application = Application.objects.get(
                application_collection=collection,
                name=self.app,
            )
        except Application.DoesNotExist as exc:
            msg = f"No application '{self.app}' in collection '{self.appcollection}'."
            raise ValueError(msg) from exc
        try:
            self._application_table = ApplicationTable.objects.get(
                application=application,
                name=self.name,
            )
        except ApplicationTable.DoesNotExist as exc:
            msg = f"No table '{self.name}' in application '{self.app}'."
            raise ValueError(msg) from exc
        return self


class DescribeApplicationTableSchema(_TableLookupSchema):
    pass


class DeleteApplicationTableSchema(_TableLookupSchema):
    pass


class RenameApplicationTableSchema(_TableLookupSchema):
    new_name: str = Field(min_length=1, max_length=100)

    @field_validator("new_name")
    @classmethod
    def _check_new_name(cls, v: str) -> str:
        return _must_be_alphanumeric_name(v, "new_name")

    @model_validator(mode="after")
    def _reject_noop(self) -> RenameApplicationTableSchema:
        """Reject a no-op rename (same name)."""
        if self.new_name == self.name:
            msg = "new_name must differ from the current name."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_name_clash(self) -> RenameApplicationTableSchema:
        """Reject if another table in the collection already has the new name."""
        collection = self._application_table.collection
        clash = (
            ApplicationTable.objects.exclude(pk=self._application_table.pk)
            .filter(application__application_collection=collection, name=self.new_name)
            .exists()
        )
        if clash:
            msg = (
                f"A table named '{self.new_name}' already exists in collection '{collection.name}'."
            )
            raise ValueError(msg)
        return self


__all__ = [
    "AddApplicationTableColumnsSchema",
    "BooleanColumnSpec",
    "CharColumnSpec",
    "ColumnSpec",
    "CreateApplicationCollectionSchema",
    "CreateApplicationSchema",
    "CreateApplicationTableSchema",
    "DatetimeColumnSpec",
    "DecimalColumnSpec",
    "DeleteApplicationCollectionSchema",
    "DeleteApplicationSchema",
    "DeleteApplicationTableColumnsSchema",
    "DeleteApplicationTableSchema",
    "DescribeApplicationTableSchema",
    "IntegerColumnSpec",
    "ListApplicationCollectionSchema",
    "RenameApplicationCollectionSchema",
    "RenameApplicationSchema",
    "RenameApplicationTableSchema",
    "TextColumnSpec",
    "UserColumnSpec",
]
