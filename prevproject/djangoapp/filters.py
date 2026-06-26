"""Filter classes for table views."""

import datetime  # noqa: TC003 pydantic needs datetime at runtime in Python 3.14
import decimal
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Any, Literal

from dateutil.relativedelta import relativedelta
from django.db.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
)
from django.db.models.fields.related import ForeignKey
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from djangoapp.models.base import RowUpdate

if TYPE_CHECKING:
    from django.db.models import QuerySet


class FilterABC(BaseModel, ABC):
    """Abstract base class for all filters."""

    model_config = ConfigDict(
        populate_by_name=True, serialize_by_alias=True, validate_by_alias=True
    )

    @abstractmethod
    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        """Apply the filter to a queryset."""


class BooleanValueFilter(FilterABC):
    """Filter for boolean fields."""

    discriminator: Literal["bv"] = Field(default="bv", alias="d")
    _field_type: type[BooleanField] = PrivateAttr(default=BooleanField)  # type: ignore[type-arg]  # Private attribute for field type
    value: bool

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        return qs.filter(**{column_name: self.value})


class IntegerComparisonFilter(FilterABC):
    """Filter for integer fields with comparison operators."""

    discriminator: Literal["icomp"] = Field(default="icomp", alias="d")
    _field_type: type[IntegerField] = PrivateAttr(default=IntegerField)  # type: ignore[type-arg]  # Private attribute for field type
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne", "inc", "ex"] = Field(alias="op")
    number_1: int
    number_2: int | None = None

    def validate_filter(self) -> None:
        """Validate the filter parameters.

        For inc/ex operators, ensures number_2 is not None and swaps values if
        number_2 < number_1.
        """
        if self.operator in ("inc", "ex"):
            if self.number_2 is None:
                msg = f"{self.operator} operator requires both number_1 and number_2"
                raise ValueError(msg)

            # Swap if number_2 is less than number_1 to ensure valid range
            if self.number_2 < self.number_1:
                self.number_1, self.number_2 = self.number_2, self.number_1

    def apply(
        self, qs: QuerySet[Any], column_name: str
    ) -> QuerySet[Any]:  # too many return statements: 7 > 6, but no early returns now
        # Validate the filter before applying
        self.validate_filter()

        col = column_name
        op = self.operator
        if op == "eq":
            qs = qs.filter(**{col: self.number_1})
        elif op in ("gt", "gte", "lt", "lte"):
            qs = qs.filter(**{f"{col}__{op}": self.number_1})
        elif op == "ne":
            qs = qs.exclude(**{col: self.number_1})
        elif op == "inc":
            # For inc/ex, number_2 should never be None based on validation
            qs = qs.filter(**{f"{col}__gte": self.number_1, f"{col}__lte": self.number_2})
        elif op == "ex":
            # For inc/ex, number_2 should never be None based on validation
            qs = qs.exclude(**{f"{col}__gte": self.number_1, f"{col}__lte": self.number_2})
        return qs


class IntegerChoiceFilter(FilterABC):
    """Filter for integer fields with choice selection."""

    discriminator: Literal["ich"] = Field(default="ich", alias="d")
    _field_type: type[IntegerField] = PrivateAttr(default=IntegerField)  # type: ignore[type-arg]  # Private attribute for field type
    mode: Literal["any", "none"]
    options: list[int]

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        col = column_name
        if self.mode == "any":
            return qs.filter(**{f"{col}__in": self.options})
        if self.mode == "none":
            return qs.exclude(**{f"{col}__in": self.options})
        return qs


class NullFilter(FilterABC):
    """Base class for null filters."""

    value: bool

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        return qs.filter(**{f"{column_name}__isnull": self.value})


class IntegerNullFilter(NullFilter):
    """Filter for integer fields checking null values."""

    discriminator: Literal["null"] = Field(default="null", alias="d")
    _field_type: type[IntegerField] = PrivateAttr(default=IntegerField)  # type: ignore[type-arg]  # Private attribute for field type


class CharChoiceFilter(FilterABC):
    """Filter for char fields with choice selection."""

    discriminator: Literal["cc"] = Field(default="cc", alias="d")
    _field_type: type[CharField] = PrivateAttr(default=CharField)  # type: ignore[type-arg]  # Private attribute for field type
    mode: Literal["any", "none"]
    options: list[str]

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        col = column_name
        if self.mode == "any":
            return qs.filter(**{f"{col}__in": self.options})
        if self.mode == "none":
            return qs.exclude(**{f"{col}__in": self.options})
        return qs


class CharTextFilter(FilterABC):
    """Filter for char fields with text search."""

    discriminator: Literal["ct"] = Field(default="ct", alias="d")
    _field_type: type[CharField] = PrivateAttr(default=CharField)  # type: ignore[type-arg]  # Private attribute for field type
    text: str

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        return qs.filter(**{f"{column_name}__icontains": self.text})


class CharBlankFilter(FilterABC):
    """Filter for char fields checking blank values."""

    discriminator: Literal["cb"] = Field(default="cb", alias="d")
    _field_type: type[CharField] = PrivateAttr(default=CharField)  # type: ignore[type-arg]  # Private attribute for field type
    value: bool  # true for blank, false for not blank

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        if self.value:
            return qs.filter(**{f"{column_name}__exact": ""})
        return qs.exclude(**{f"{column_name}__exact": ""})


class DecimalComparisonFilter(FilterABC):
    """Filter for decimal fields with comparison operators."""

    discriminator: Literal["dcomp"] = Field(default="dcomp", alias="d")
    _field_type: type[DecimalField] = PrivateAttr(default=DecimalField)  # type: ignore[type-arg]  # Private attribute for field type
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne", "inc", "ex"] = Field(alias="op")
    number_1: str  # Decimal as string to preserve precision
    number_2: str  # For inc/ex, this should never be None

    def validate_filter(self) -> None:
        """Validate the filter parameters.

        For inc/ex operators, ensures number_2 is not None and swaps values if
        number_2 < number_1.
        """
        if self.operator in ("inc", "ex"):
            if not self.number_2:
                msg = f"{self.operator} operator requires both number_1 and number_2"
                raise ValueError(msg)

            # Convert string decimals to Decimal objects for comparison
            dec1 = decimal.Decimal(self.number_1)
            dec2 = decimal.Decimal(self.number_2)

            # Swap if number_2 is less than number_1 to ensure valid range
            if dec2 < dec1:
                self.number_1, self.number_2 = self.number_2, self.number_1

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        # Validate the filter before applying
        self.validate_filter()

        col = column_name
        op = self.operator

        # Convert string decimals to Decimal objects
        dec1 = decimal.Decimal(self.number_1)

        if op == "eq":
            qs = qs.filter(**{col: dec1})
        elif op in ("gt", "gte", "lt", "lte"):
            qs = qs.filter(**{f"{col}__{op}": dec1})
        elif op == "ne":
            qs = qs.exclude(**{col: dec1})
        elif op == "inc":
            # For inc/ex, number_2 should never be None based on validation
            dec2 = decimal.Decimal(self.number_2)
            qs = qs.filter(**{f"{col}__gte": dec1, f"{col}__lte": dec2})
        elif op == "ex":
            # For inc/ex, number_2 should never be None based on validation
            dec2 = decimal.Decimal(self.number_2)
            qs = qs.exclude(**{f"{col}__gte": dec1, f"{col}__lte": dec2})
        return qs


class DatetimeComparisonFilter(FilterABC):
    """Filter for datetime fields with comparison operators."""

    discriminator: Literal["dtcomp"] = Field(default="dtcomp", alias="d")
    _field_type: type[DateTimeField] = PrivateAttr(default=DateTimeField)  # type: ignore[type-arg]  # Private attribute for field type
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne", "inc", "ex"] = Field(alias="op")
    datetime_1: str  # ISO format datetime string
    datetime_2: str  # For inc/ex, this should never be None

    def validate_filter(self) -> None:
        """Validate the filter parameters.

        For inc/ex operators, ensures datetime_2 is not None and swaps values if
        datetime_2 < datetime_1.
        """
        if self.operator in ("inc", "ex"):
            if not self.datetime_2:
                msg = f"{self.operator} operator requires both datetime_1 and datetime_2"
                raise ValueError(msg)

            # Parse datetimes for comparison
            dt1 = parse_datetime(self.datetime_1)
            dt2 = parse_datetime(self.datetime_2)

            # Swap if datetime_2 is less than datetime_1 to ensure valid range
            if dt2 and dt1 and dt2 < dt1:
                self.datetime_1, self.datetime_2 = self.datetime_2, self.datetime_1

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        # Validate the filter before applying
        self.validate_filter()

        col = column_name
        op = self.operator

        # Parse ISO format datetime strings
        dt1 = parse_datetime(self.datetime_1)
        dt2 = parse_datetime(self.datetime_2)

        if op == "eq":
            qs = qs.filter(**{col: dt1})
        elif op in ("gt", "gte", "lt", "lte"):
            qs = qs.filter(**{f"{col}__{op}": dt1})
        elif op == "ne":
            qs = qs.exclude(**{col: dt1})
        elif op == "inc":
            # Include range: datetime between datetime_1 and datetime_2 (inclusive)
            qs = qs.filter(**{f"{col}__gte": dt1, f"{col}__lte": dt2})
        elif op == "ex":
            # Exclude range: datetime NOT between datetime_1 and datetime_2 (inclusive)
            qs = qs.exclude(**{f"{col}__gte": dt1, f"{col}__lte": dt2})
        return qs


class DecimalNullFilter(NullFilter):
    """Filter for decimal fields checking null values."""

    discriminator: Literal["dnull"] = Field(default="dnull", alias="d")
    _field_type: type[DecimalField] = PrivateAttr(default=DecimalField)  # type: ignore[type-arg]  # Private attribute for field type


class DatetimeRelativeFilter(FilterABC):
    """Filter for datetime fields with relative time ranges."""

    discriminator: Literal["dtrel"] = Field(default="dtrel", alias="d")
    _field_type: type[DateTimeField] = PrivateAttr(default=DateTimeField)  # type: ignore[type-arg]  # Private attribute for field type
    direction: Literal["past", "next"]  # past or next
    unit: Literal["hours", "days", "months", "years"]  # time unit
    quantity: int  # number of units

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        # Use timezone.now() for server time
        now = timezone.now()

        # Calculate relativedelta first, then add/subtract depending on direction
        if self.unit == "hours":
            delta = relativedelta(hours=self.quantity)
        elif self.unit == "days":
            delta = relativedelta(days=self.quantity)
        elif self.unit == "months":
            delta = relativedelta(months=self.quantity)
        elif self.unit == "years":  # years
            delta = relativedelta(years=self.quantity)
        else:
            raise ValueError

        if self.direction == "past":
            # Calculate datetime in the past
            target_time = now - delta
            return qs.filter(**{f"{column_name}__gte": target_time, f"{column_name}__lte": now})
        target_time = now + delta
        return qs.filter(**{f"{column_name}__gte": now, f"{column_name}__lte": target_time})


class DatetimeNullFilter(NullFilter):
    """Filter for datetime fields checking null values."""

    discriminator: Literal["dtnull"] = Field(default="dtnull", alias="d")
    _field_type: type[DateTimeField] = PrivateAttr(default=DateTimeField)  # type: ignore[type-arg]  # Private attribute for field type


class ForeignKeyChoiceFilter(FilterABC):
    """Filter for foreign key fields with choice selection."""

    discriminator: Literal["fk"] = Field(default="fk", alias="d")
    _field_type: type[ForeignKey] = PrivateAttr(default=ForeignKey)  # type: ignore[type-arg]  # Private attribute for field type
    mode: Literal["any", "none"]
    options: list[str]

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:
        related_model = qs.model._meta.get_field(column_name).related_model  # noqa: SLF001
        lookup = f"{column_name}__{related_model.public_id_field}__in"
        if self.mode == "any":
            return qs.filter(**{lookup: self.options})
        if self.mode == "none":
            return qs.exclude(**{lookup: self.options})
        return qs


class ForeignKeyNullFilter(NullFilter):
    """Filter for foreign key fields checking null values."""

    discriminator: Literal["fknull"] = Field(default="fknull", alias="d")
    _field_type: type[ForeignKey] = PrivateAttr(default=ForeignKey)  # type: ignore[type-arg]  # Private attribute for field type


class RowUpdateFilter(FilterABC):
    """Filter rows based on associated RowUpdate entries.

    This filter uses a subquery to find rows that have matching RowUpdate entries.
    It's a special filter that doesn't operate on a specific column, but on the
    row's audit history.

    Attributes:
        user_ids: List of user IDs to filter by (created_by)
        actions: Action type to filter by ("created_row", "updated_row", "commented")
        date_from: Start datetime for date range filter
        date_to: End datetime for date range filter

    """

    user_ids: list[str] | None = None
    actions: list[Literal["created_row", "updated_row", "commented"]] | None = None
    date_from: datetime.datetime | None = None
    date_to: datetime.datetime | None = None

    def apply(self, qs: QuerySet[Any], column_name: str) -> QuerySet[Any]:  # noqa: ARG002 # column_name required by FilterABC interface but not used for row-level filtering
        """Apply the filter using a subquery on RowUpdate.

        Since RowUpdate has no direct FK relationship to the model, we use
        a subquery to find distinct (modelname, row_pk) pairs that match
        the filter criteria.

        """
        model_class = qs.model

        # Use manager methods for cleaner querying
        # Start with filter_model, then chain filter_user_and_actions and filter_dates
        row_updates = RowUpdate.objects.filter_model(model_class)
        row_updates = row_updates.filter_user_and_actions(
            user_ids=self.user_ids,
            actions=self.actions,
        )
        row_updates = row_updates.filter_dates(
            start=self.date_from,
            end=self.date_to,
        )

        # Get distinct row_pk values that have matching RowUpdates
        # This is processed by the database only - the subquery is executed as part of the
        # main query, not eagerly loaded into Python. Django's ORM will translate this into
        # a SQL subquery, making it efficient even for large datasets.
        matching_row_pks = row_updates.values_list("row_pk", flat=True).distinct()

        return qs.filter(pk__in=matching_row_pks)


# Union type for all filter types using discriminator
UnionFilter = Annotated[
    BooleanValueFilter
    | IntegerComparisonFilter
    | IntegerChoiceFilter
    | IntegerNullFilter
    | CharChoiceFilter
    | CharTextFilter
    | CharBlankFilter
    | DecimalComparisonFilter
    | DatetimeComparisonFilter
    | DecimalNullFilter
    | DatetimeNullFilter
    | DatetimeRelativeFilter
    | ForeignKeyChoiceFilter
    | ForeignKeyNullFilter,
    Field(discriminator="discriminator"),
]
