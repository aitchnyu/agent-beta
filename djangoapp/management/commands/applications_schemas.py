"""Pydantic schemas for the ``applications`` management command (read-only).

The command exposes only listing/describe subcommands; mutation moved onto
``dynamic_models``. These schemas validate the read inputs (alphanumeric
names) and resolve them to live model rows, stashing the resolved instance
in a ``PrivateAttr`` exposed via a read-only property so the handler reuses
it without re-querying.

Each long rule-set is split into small ``@model_validator(mode="after")``
methods that run in source order. ``mode="after"`` is explicit on every
validator because pydantic 2.13 requires the ``mode`` argument (a bare
``@model_validator`` raises ``TypeError`` at runtime).
"""

from __future__ import annotations

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

    Excluding the underscore keeps user names out of the underscore-prefixed
    built-in column namespace (_public_id, _created_by, ...).
    """
    if not value or not value[0].isalpha() or not value.isalnum():
        msg = f"'{field_name}' must start with a letter and contain only letters and digits."
        raise ValueError(msg)
    return value


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


class DescribeApplicationTableSchema(BaseModel):
    """Resolve appcollection/app/table name args to a live ApplicationTable row."""

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
    def _resolve_table(self) -> DescribeApplicationTableSchema:
        """Resolve the app and table rows named by the request."""
        try:
            application = Application.get_by_names(self.appcollection, self.app)
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


__all__ = [
    "DescribeApplicationTableSchema",
    "ListApplicationCollectionSchema",
]
