from __future__ import annotations

import datetime as datetime_module  # needed at runtime for pydantic ArticleSnapshot
import secrets
import typing
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import (
    date as date_type,  # needed at runtime for pydantic ArticleSnapshot
)
from datetime import (
    datetime as datetime_type,
)
from typing import Any, ClassVar, Literal, TypedDict, TypeVar, cast

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Prefetch, Sum
from django.http import Http404
from django.utils import timezone
from django.utils.text import slugify
from pydantic import BaseModel as PydanticBaseModel
from pydantic import TypeAdapter

from djangoapp.models.public_ids import generate_sequence_id, public_id_django_validator
from djangoapp.responses import BaseFieldSchema, RowColumnValueSchema, RowUpdateResponse, UserSchema
from djangoapp.serializers import (
    FORM_DESERIALIZERS,
    ROWUPDATE_VALUE_SERIALIZERS,
    SCHEMA_SERIALIZERS,
    UNCHANGED,
    VALUE_WRAPPER_TYPES,
    BaseValueWrapper,
    FkTitlesMap,
    ForeignKeyTitleData,
)

if typing.TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django_stubs_ext import WithAnnotations

# Constants for permission checks
ONE_HOUR_IN_SECONDS = 3600

ModelType = TypeVar("ModelType", bound="_BaseModelMixin")


class AnnotatedTextDict(TypedDict):
    annotated_text: str | int


ROW_OPERATIONS = Literal["create", "read", "update", "delete"]
# Extended operations for column resolution - includes list/details separately
COLUMN_OPERATIONS = Literal["create", "list", "details", "update", "delete"]

# Comment operations for permission checking
COMMENT_OPERATIONS = Literal["create_comment", "update_comment", "delete_comment"]

# Type alias for user parameters across dataclasses and methods.
# At runtime this is our custom ``User`` (``AbstractUser`` +
# ``_BaseModelMixin``), so it natively has ``.public_id``.  It does
# NOT carry ``.annotated_text`` / ``.name`` / ``.url`` unless the
# queryset it came from was annotated; callers needing those must
# fetch via an annotated queryset (or ``ProxyUser``).  The alias
# exists purely for readability, signalling "this is a user that
# participates in the tables permission system".
type UserWithPublicId = User


@dataclass
class ResolveRowsContext:
    user: UserWithPublicId | None
    query: models.QuerySet[typing.Any]
    operation: ROW_OPERATIONS


@dataclass
class ResolveColumnsContext:
    user: UserWithPublicId | None
    operation: COLUMN_OPERATIONS
    columns: tuple[str, ...]
    maybe_row: typing.Any | None = None  # Provided for details/update/delete


@dataclass
class SaveContext[T: "_BaseModelMixin"]:
    user: UserWithPublicId | None
    existing_row: T | None


def _default_integer_callable() -> int:
    return 99


@dataclass
class CommentPermissionContext[BM: "_BaseModelMixin"]:
    """Context for checking permission to perform comment operations on a row.

    Attributes:
        user: The authenticated user making the request
        operation: One of "create_comment", "update_comment", or "delete_comment"
        row: The model instance the comment belongs to (for update/delete operations)

    """

    user: UserWithPublicId | None
    operation: COMMENT_OPERATIONS
    row: BM | None = None


@dataclass
class RowUpdateRedactContext[BM: "_BaseModelMixin"]:
    """Context for determining which columns to redact in row updates.

    Attributes:
        user: The authenticated user making the request
        row_updates: List of RowUpdate objects to potentially redact
        row: The model instance being viewed

    """

    user: UserWithPublicId | None
    row_updates: Sequence[RowUpdate]
    row: BM


class CollectedProblems:
    def __init__(self) -> None:
        self.fields: dict[str, str] = {}
        self.top_level: str | None = None
        self.title: str | None = None

    def has_failed(self) -> bool:
        return len(self.fields) > 0 or self.top_level is not None or self.title is not None


type DjangoField = models.Field


class BaseTableQuerySet[T: "_BaseModelMixin"](models.QuerySet[T, T]):
    pass


class BaseManager[T: "_BaseModelMixin"](models.Manager[T]):
    pass
    # def paginate(self, per_page: int, page_number: int) -> Page:
    #     paginator = Paginator(self, per_page, orphans=5)
    #     return paginator.get_page(page_number)
    #
    # def search_by_title_or_id(self, term: str) -> list[ModelType]:
    #     id_match = []
    #     if term.isnumeric():
    #         maybe_id_match = self.filter(id=int(term)).first()
    #         if maybe_id_match:
    #             id_match = [maybe_id_match]
    #     lex_matches = []
    #     if self.model().has_title:
    #         lex_matches = list(self.filter(_maybe_title__icontains=term).order_by("-id")[:20])
    #     return id_match + lex_matches


@dataclass
class SearchContext[T: "_BaseModelMixin"]:
    """Context passed to @search decorated methods.

    Attributes:
        user: The authenticated user making the request
        queryset: The queryset to refine (already annotated with text from search_text)
        search_text: The search string entered by the user

    """

    user: UserWithPublicId | None
    queryset: models.QuerySet[T]
    search_text: str


# TODO in future Mypy, ensure T,T,T instead of Any,Any,Any
# Type alias for search methods - requires (cls, context) signature
type _SearchMethod = Callable[[type[Any], SearchContext[Any]], models.QuerySet[Any]]

# TODO in a later mypy version, ensure its classmethod
# Union type for decorator input - accepts classmethod or plain function with (cls, context) sig
type _DecoratorInput = (
    "classmethod[Any, Any, models.QuerySet[Any]]"
    | Callable[[type[Any], SearchContext[Any]], models.QuerySet[Any]]
)


class SearchProxy:
    """Wrapper that makes a search method behave like a classmethod."""

    func: _SearchMethod
    column_name: str

    def __init__(self, func: _DecoratorInput, column_name: str) -> None:
        # At runtime, func is a classmethod descriptor; extract underlying function.
        # Typecheck is forced to be lenient, we should catch this at runtime.
        assert isinstance(func, classmethod)
        self.func = func.__func__
        self.column_name = column_name
        self.__name__ = self.func.__name__

    def __call__(self, context: SearchContext[Any]) -> models.QuerySet[Any]:
        """Call the search method with context."""
        model_class = context.queryset.model
        return self.func(model_class, context)


def search(
    column_name: str,
) -> Callable[[_DecoratorInput], SearchProxy]:
    """Define a search method for a FK column.

    Usage:
        @search("fk_column_name")
        @classmethod
        def any_method_name(cls, context: SearchContext[RelatedModel]) -> QuerySet[RelatedModel]:
            # context.queryset is the base queryset from search_text (already annotated)
            # context.search_text is the search string
            # context.user is the current user
            return context.queryset.filter(some_condition)

    The decorated function MUST be a classmethod.
    """

    def decorator(func: _DecoratorInput) -> SearchProxy:
        # Ensure func is a classmethod (either already wrapped or auto-wrap if sig matches)
        if not isinstance(func, classmethod):  # pragma: no cover
            msg = "@search should work on classmethod only"
            raise TypeError(msg)
        return SearchProxy(func, column_name)

    return decorator


class _BaseModelMixin(models.Model):
    include_columns: ClassVar[tuple[str, ...]] = ()

    public_id_field: ClassVar[str] = "id"
    public_id_generator: ClassVar[Callable[[], Any]] = lambda: str(uuid.uuid7())

    title_annotation: ClassVar[
        models.F | models.Value | models.functions.Concat | models.functions.Coalesce
    ] = F("id")

    _fk_titles: FkTitlesMap | None
    # Populated by annotate_fk_titles() for batch FK title resolution.

    annotated_text: str | int
    # TODO django-stubs WithAnnotations return type doesn't propagate through
    # QuerySet iteration/get/filter, so this class attribute is needed
    # for mypy to resolve .annotated_text at call sites.
    # CAUTION: this is a type-only declaration — accessing .annotated_text
    # on an instance whose queryset was NOT annotated will raise
    # AttributeError at runtime. Every access must go through
    # queryset_with_title() or .annotate(annotated_text=...).

    class Meta:
        abstract = True

    @property
    def public_id(self) -> str:
        maybe_value = getattr(self, self.public_id_field)
        assert maybe_value is not None
        return str(maybe_value)

    @classmethod
    def has_custom_public_id(cls) -> bool:
        return cls.public_id_field != "id"

    @classmethod
    def get_by_public_id(
        cls, queryset: models.QuerySet[typing.Self], public_id: str
    ) -> typing.Self:
        """Look up a row by its public ID field.

        For models using the default integer ``id``, coerces the string to int.
        For models with a custom ``public_id_field``, filters by string directly.

        Raises:
            models.ObjectDoesNotExist: if no row matches.

        """
        field = cls.public_id_field
        lookup_value: str | int = public_id
        if not cls.has_custom_public_id():
            lookup_value = int(public_id)
        return queryset.get(**{field: lookup_value})

    @classmethod
    def get_by_public_id_or_404(
        cls, queryset: models.QuerySet[typing.Self], public_id: str
    ) -> typing.Self:
        """Raise Http404 instead of DoesNotExist, otherwise identical to ``get_by_public_id``."""
        try:
            return cls.get_by_public_id(queryset, public_id)
        except cls.DoesNotExist:
            raise Http404 from None

    @classmethod
    def filter_by_public_ids(
        cls, queryset: models.QuerySet[typing.Any], ids: list[str]
    ) -> models.QuerySet[typing.Any]:
        """Filter a queryset by a list of public ID values.

        For models using the default integer ``id`` field, coerces strings
        to int and returns an empty queryset if coercion fails.
        For models with a custom ``public_id_field`` (CharField-based),
        filters directly by string values.
        """
        if not cls.has_custom_public_id():
            return queryset.filter(pk__in=[int(i) for i in ids])
        return queryset.filter(**{cls.public_id_field + "__in": ids})

    @classmethod
    def queryset_with_title(
        cls,
    ) -> models.QuerySet[WithAnnotations[typing.Self, AnnotatedTextDict]]:
        """Return queryset annotated with `text` field using class's title_annotation."""
        return cls.objects.all().annotate(annotated_text=cls.title_annotation)  # type: ignore[attr-defined, no-any-return] # Django manager on abstract model

    @classmethod
    def modelname(cls) -> str:
        """Get the model name for RowUpdate logging.

        For proxy models, returns the concrete parent's label.
        For regular models, returns the model's own label.
        """
        meta = cls._meta
        if meta.proxy:
            # For proxy models, get the concrete parent model's label
            for parent in meta.parents:
                if not parent._meta.proxy:  # noqa: SLF001
                    return parent._meta.label  # noqa: SLF001
            # Fallback to own label if no concrete parent found
            msg = "Untested scenario"  # pragma: no cover
            raise ValueError(msg)  # pragma: no cover
            return meta.label
        return meta.label

    @classmethod
    def search_text(
        cls, text: str
    ) -> models.QuerySet[WithAnnotations[typing.Self, AnnotatedTextDict]]:
        """Return annotated queryset for search.

        For numeric text, matches by exact public_id_field value.
        For non-numeric text on models with custom public_id_field (CharField-based),
        matches by prefix (startswith).
        Subclasses can override for custom text search behavior.
        """
        if cls.has_custom_public_id():
            return cls.queryset_with_title().filter(**{cls.public_id_field + "__startswith": text})
        if text.isnumeric():
            return cls.queryset_with_title().filter(**{cls.public_id_field: int(text)})
        return cls.objects.none()  # type: ignore[attr-defined, no-any-return] # Django manager on abstract model

    @classmethod
    def get_search_method(cls, column_name: str) -> SearchProxy | None:
        """Get the search method for a column name by iterating class attributes."""
        for _attr_name, proxy in cls._get_search_proxies():
            if proxy.column_name == column_name:
                return proxy
        return None

    @classmethod
    def search_for_fk_column(
        cls,
        column_name: str,
        user: UserWithPublicId | None,
        search_text: str,
    ) -> models.QuerySet[Any]:
        """Search for FK column values by combining search_text and maybe @search method."""
        field = cls._meta.get_field(column_name)
        related_model = field.related_model
        assert related_model is not None

        # Start with base search_text results (already annotated with text)
        assert issubclass(related_model, _BaseModelMixin)  # type: ignore[arg-type] # related_model type is complex
        queryset = related_model.search_text(search_text)  # type: ignore[union-attr] # related_model is _BaseModelMixin subclass

        # Check for @search decorated method on this model
        search_method = cls.get_search_method(column_name)
        if search_method:
            context = SearchContext(
                user=user,
                queryset=queryset,
                search_text=search_text,
            )
            queryset = search_method(context)

        return queryset  # type: ignore[no-any-return] # queryset type varies by model

    @classmethod
    def _get_search_proxies(cls) -> list[tuple[str, SearchProxy]]:
        """Collect all SearchProxy instances defined on this class.

        Returns list of (attr_name, SearchProxy) tuples.
        """
        return [
            (attr_name, getattr(cls, attr_name))
            for attr_name in dir(cls)
            if isinstance(getattr(cls, attr_name, None), SearchProxy)
        ]

    @classmethod
    def _validate_search_proxies(cls) -> None:
        """Validate SearchProxy configurations in smoke_tests.

        Verifies that:
        - Each @search decorator's column_name matches an actual FK column
        - The related model is a BaseModel descendant
        """
        for attr_name, proxy in cls._get_search_proxies():
            column_name = proxy.column_name
            # Check that the column exists on this model
            try:
                field = cls._meta.get_field(column_name)
            except Exception as e:
                msg = (
                    f"SearchProxy '{attr_name}' references column "
                    f"'{column_name}' which does not exist on {cls.__name__}"
                )
                raise TypeError(msg) from e

            # Check that the column is a ForeignKey
            if not isinstance(field, models.ForeignKey):
                msg = (
                    f"SearchProxy '{attr_name}' references column "
                    f"'{column_name}' which is not a ForeignKey on {cls.__name__}"
                )
                raise TypeError(msg)

            # Check that the related model is a BaseModel descendant
            related_model = field.related_model
            # related_model can be a string for lazy FK references
            if isinstance(related_model, str):
                msg = (
                    f"SearchProxy '{attr_name}' references column "
                    f"'{column_name}' with lazy FK reference '{related_model}' "
                    f"- use direct class reference instead"
                )
                raise TypeError(msg)
            if not issubclass(related_model, _BaseModelMixin):
                msg = (
                    f"SearchProxy '{attr_name}' references column "
                    f"'{column_name}' whose related model "
                    f"'{related_model.__name__}' is not a _BaseModelMixin descendant"
                )
                raise TypeError(msg)

    @classmethod
    def _validate_include_columns(cls) -> None:
        """Validate include_columns configuration in smoke_tests.

        Verifies that:
        - include_columns only references valid field names
        - include_columns has no duplicate entries
        - include_columns does not contain 'id' when has_custom_public_id()
        """
        if not cls.include_columns:
            return

        if cls.has_custom_public_id() and "id" in cls.include_columns:
            msg = (
                f"include_columns on {cls.__name__} contains 'id' but "
                f"public_id_field is '{cls.public_id_field}'. "
                f"Internal 'id' must not be exposed to the client."
            )
            raise TypeError(msg)

        # Get all valid field names for this model (use _meta.fields directly for validation,
        # not raw_resolve_columns which requires view-specific supported_handlers)
        valid_field_names = {f.name for f in cls._meta.fields}

        # Check for invalid column names
        for column_name in cls.include_columns:
            if column_name not in valid_field_names:
                msg = (
                    f"include_columns references '{column_name}' "
                    f"which does not exist on {cls.__name__}. "
                    f"Valid fields: {sorted(valid_field_names)}"
                )
                raise TypeError(msg)

        # Check for duplicate column names
        seen = set()
        for column_name in cls.include_columns:
            if column_name in seen:
                msg = f"include_columns has duplicate column '{column_name}' on {cls.__name__}"
                raise TypeError(msg)
            seen.add(column_name)

    @classmethod
    def _validate_public_id_field(cls) -> None:
        if cls.public_id_field == "id":
            return

        try:
            field = cls._meta.get_field(cls.public_id_field)
        except Exception as e:
            msg = f"public_id_field '{cls.public_id_field}' does not exist on {cls.__name__}"
            raise TypeError(msg) from e

        if not isinstance(field, models.Field):
            msg = f"public_id_field '{cls.public_id_field}' on {cls.__name__} is not a model field"
            raise TypeError(msg)

        if not getattr(field, "unique", False):
            msg = f"public_id_field '{cls.public_id_field}' on {cls.__name__} must be unique"
            raise TypeError(msg)

        if getattr(field, "null", False):
            msg = f"public_id_field '{cls.public_id_field}' on {cls.__name__} must not be nullable"
            raise TypeError(msg)

        if getattr(field, "null", False):
            msg = f"public_id_field '{cls.public_id_field}' on {cls.__name__} must not be nullable"
            raise TypeError(msg)

        if getattr(field, "null", True) is not False and getattr(field, "blank", True) is not False:
            has_nullable = getattr(field, "null", False)
            if has_nullable:
                msg = (
                    f"public_id_field '{cls.public_id_field}' on {cls.__name__} "
                    f"must not be nullable"
                )
                raise TypeError(msg)

    @classmethod
    def smoke_tests(cls) -> None:
        """Validate model configuration.

        Call this when registering a model with the views to catch config errors.
        Raises TypeError if validation fails.

        Runs validation methods:
        - _validate_search_proxies: Validates @search decorator configurations
        - _validate_include_columns: Validates include_columns field references
        - _validate_public_id_field: Validates public_id_field configuration
        """
        cls._validate_search_proxies()
        cls._validate_include_columns()
        cls._validate_public_id_field()

    @classmethod
    def raw_resolve_columns(cls) -> dict[str, DjangoField]:
        fields = [f for f in cls._meta.fields if f.__class__ in SCHEMA_SERIALIZERS]
        if cls.include_columns:
            # Return fields in the order specified in include_columns
            field_map = {f.name: f for f in fields}
            return {name: field_map[name] for name in cls.include_columns if name in field_map}
        return {f.name: f for f in fields}

    @classmethod
    def columns_schemas(
        cls,
        columns: Sequence[DjangoField],
    ) -> dict[str, BaseFieldSchema]:
        """Generate schemas for given columns using serializer functions from serializers.py.

        Args:
            columns: List of Django fields to generate schemas for

        Returns:
            Dict of FieldSchema pydantic models keyed by field name

        """
        result: dict[str, BaseFieldSchema] = {}

        for field in columns:
            serializer = SCHEMA_SERIALIZERS[type(field)]
            schema = serializer(field)
            result[schema.name] = schema

        return result

    def value_wrappers(
        self,
        columns: Sequence[DjangoField],
        context: str = "list",
    ) -> dict[str, BaseValueWrapper]:
        """Create ValueWrapper instances for each column.

        Args:
            columns: List of Django fields to wrap
            context: Rendering context - 'list', 'details', or 'input'

        Returns:
            Dict mapping field names to ValueWrapper instances

        """
        result: dict[str, BaseValueWrapper] = {}
        for field in columns:
            wrapper_cls = VALUE_WRAPPER_TYPES[type(field)]
            if isinstance(field, models.ForeignKey):
                raw_value = None
            else:
                raw_value = getattr(self, field.name)
            result[field.name] = wrapper_cls(
                field=field,
                value=raw_value,
                instance=self,
                context=context,
            )
        return result

    def feed_values(
        self,
        post: dict[str, str],
        files: dict[str, UploadedFile],
        columns: Sequence[DjangoField],
        existing_instance: _BaseModelMixin | None = None,
    ) -> CollectedProblems:
        """Parse and validate form values, setting them on self.

        This method handles:
        1. File fields with keep/replace/remove logic
        2. Regular fields using form deserializers from serializers.py

        Args:
            post: Dict of posted form values
            files: Dict of uploaded files
            columns: List of Django fields to process
            existing_instance: For updates, the existing model instance

        Returns:
            CollectedProblems with any validation errors

        """
        collected_problems = CollectedProblems()

        # Determine which fields are present in the request (POST or files)
        present_fields = set(post.keys()) | set(files.keys())

        for column in columns:
            if column.name not in present_fields:
                if isinstance(column, models.ForeignKey) and not column.null:
                    collected_problems.fields[column.name] = f"{column.verbose_name} is required."
                continue

            try:
                posted_value = post.get(column.name, "")
                deserializer = FORM_DESERIALIZERS[type(column)]
                result = deserializer(column, posted_value, files, existing_instance)

                # Handle file deletion marking for file fields
                if (
                    isinstance(column, models.FileField)
                    and result is not UNCHANGED
                    and existing_instance
                    and isinstance(existing_instance, _BaseModelMixin)
                ):
                    old_file = getattr(existing_instance, column.name)
                    if old_file:
                        existing_instance.mark_column_file_for_deletion(old_file)

                # UNCHANGED was introduced for file fields
                if result is not UNCHANGED:
                    setattr(self, column.name, result)

            except ValidationError as e:
                collected_problems.fields[column.name] = ".".join(e.messages)

        return collected_problems

    @classmethod
    def resolve_columns(
        cls,
        context: ResolveColumnsContext,
    ) -> Sequence[str] | None:
        """Resolve which columns are accessible for a given operation.

        Override this method to control column visibility based on user,
        operation, or row. Return None to deny access (404 error).

        Yes, its called for delete, in which case context.columns don't mean anything.
        Row is non-empty for details, update and delete operations.

        Base implementation returns context.columns unchanged.

        Example: prevent delete for certain rows
            if context.operation == "delete":
                # assert context.maybe_row # to satisfy typecheckers
                if context.maybe_row.prevent_delete:
                    return None
            return context.columns

        Example: different columns for list vs details
            if context.operation == "list":
                return ("id", "name")  # summary columns
            return context.columns  # all columns for details
        """
        return context.columns

    @classmethod
    def fields_or_404(
        cls,
        user: UserWithPublicId | None,
        operation: COLUMN_OPERATIONS,
        maybe_row: typing.Any | None = None,  # Row can be any model instance  # noqa: ANN401
    ) -> list[DjangoField]:
        """Resolve columns and return DjangoField objects, raising Http404 if access denied.

        Convenience method that combines raw_resolve_columns, resolve_columns,
        and conversion back to DjangoField objects.

        Args:
            user: The authenticated user
            operation: The operation being performed
            maybe_row: The row for details/update/delete operations

        Returns:
            List of DjangoField objects

        Raises:
            Http404: If resolve_columns returns None (access denied)

        """
        all_columns = cls.raw_resolve_columns()
        all_column_names = tuple(all_columns.keys())

        resolved_columns = cls.resolve_columns(
            ResolveColumnsContext(
                user=user, operation=operation, columns=all_column_names, maybe_row=maybe_row
            )
        )
        if resolved_columns is None:
            raise Http404

        if len(resolved_columns) == 0:
            msg = f"{cls.__name__}.resolve_columns is not allowed to be an empty sequence"
            raise ValueError(msg)

        return [all_columns[name] for name in resolved_columns if name in all_columns]

    def save_stuff(self, context: SaveContext[typing.Self]) -> None:
        """Save the row with validation.

        Override to add validation logic before saving or modify values.
        Raise ValidationError to prevent save and show errors.

        The ValidationError can include:
        - Field-specific errors: {"field_name": "error message"}
        - Top-level error: {"_top": "overall form error"}
        - Both together: {"field_name": "error", "_top": "overall error"}

        Example:
            if self.char_field == "11":
                raise ValidationError({
                    "char_field": "value is 11",
                    "_top": "Oops, your submission is invalid"
                })
            super().save_stuff(context)

        """
        self.save()
        row_update = self._create_row_update(context)

        actor = context.user
        if actor is not None:
            if context.existing_row is None:
                notify_context: NotifyContext = CreateRowNotifyContext(user=actor)
            else:
                notify_context = UpdateRowNotifyContext(user=actor)
            self._create_notifications(row_update, notify_context)

    def _create_row_update(self, context: SaveContext[typing.Self]) -> RowUpdate:
        """Create a RowUpdate entry after successful save."""
        assert self.pk is not None  # for type checker - already asserted in save_stuff

        action = "created_row" if context.existing_row is None else "updated_row"

        all_fields = [
            f
            for f in type(self).raw_resolve_columns().values()
            if type(f) in ROWUPDATE_VALUE_SERIALIZERS
        ]

        if action == "updated_row":
            changed_fields = []
            for field in all_fields:
                current_value = getattr(self, field.name)
                old_value = getattr(context.existing_row, field.name)
                if current_value != old_value:
                    changed_fields.append(field)
            fields_to_serialize = changed_fields
        else:
            fields_to_serialize = list(all_fields)

        old_values: dict[str, typing.Any] = {}
        if context.existing_row is not None:
            for field in fields_to_serialize:
                old_values[field.name] = getattr(context.existing_row, field.name)

        column_values = self.serialize_to_row_values(
            fields_to_serialize,
            old_values=old_values or None,
        )

        row_update = RowUpdate(
            action=action,
            created_by=context.user,
            modelname=self.modelname(),
            row_pk=self.pk,
            row_public_id=self.public_id,
        )
        row_update.values = column_values
        row_update.save()
        return row_update

    def notify_users(self, context: NotifyContext) -> Sequence[UserWithPublicId]:  # noqa: ARG002
        """Return users who should be notified about a row event.

        Override this method in subclasses to return the list of users
        who should receive a notification. The context parameter carries
        the event type (create_row, update_row, create_comment, update_comment)
        and the user who triggered the action.

        The actor (context.user) is automatically excluded from recipients
        by _create_notifications, so it is safe to include them here.

        Returns:
            Sequence of User objects to notify. Empty list by default.

        """
        return []

    def _create_notifications(self, row_update: RowUpdate, context: NotifyContext) -> None:
        users = self.notify_users(context)
        recipients = [u for u in users if u.pk != context.user.pk]
        if not recipients:
            return
        RowUpdateUserNotification.objects.bulk_create(
            [
                RowUpdateUserNotification(
                    modelname=self.modelname(),
                    row_pk=self.pk,
                    row_public_id=self.public_id,
                    user=u,
                    content=self.row_update_response(u, row_update).model_dump(mode="json"),
                )
                for u in recipients
            ],
        )

    @classmethod
    def default_query(cls) -> models.QuerySet[typing.Self]:
        return cls.objects.order_by("-id")  # type: ignore[attr-defined, no-any-return] # objects defined on subclasses

    @classmethod
    def resolve_rows(
        cls,
        context: ResolveRowsContext,
    ) -> models.QuerySet[typing.Self]:
        """Resolve the queryset for a given operation.

        Override this method to filter rows based on user or operation.
        Return a filtered queryset to restrict access.
        Base implementation returns context.query unchanged.

        Note: The operation for list/details is "read" (not "list"/"details" like resolve_columns).
        For column-level control with distinct list/details operations, use resolve_columns.

        Example: prevent delete for certain rows
            if context.operation == "delete":
                return context.query.filter(prevent_delete=False)
            return context.query
        """
        return context.query  # pragma: no cover

    @classmethod
    def list_rows(cls, user: UserWithPublicId | None) -> models.QuerySet[typing.Self]:
        return cls.resolve_rows(
            ResolveRowsContext(query=cls.default_query(), user=user, operation="read"),
        )

    @classmethod
    def get_row_for_user_and_operation(
        cls, row_id: str, user: UserWithPublicId | None, operation: ROW_OPERATIONS
    ) -> typing.Self:
        """Get a row by public ID, restricted to rows the user can access.

        Raises:
            DoesNotExist: if the row doesn't exist or the user lacks access.

        """
        query = cls.resolve_rows(
            ResolveRowsContext(query=cls.default_query(), user=user, operation=operation),
        )
        return cls.get_by_public_id(query, row_id)

    def row_update_access_timeout(
        self,
        context: CommentPermissionContext[typing.Self],  # noqa: ARG002
    ) -> int:
        """Return timeout in seconds for the given comment operation.

        Default implementation returns 86400 (24 hours) for all operations.
        Override this method to customize permission logic.

        For create_comment operation: Any positive integer allows comment creation.
        For update_comment operation: User must be comment author within timeout.
        For delete_comment operation: Any user can delete within timeout (no author check).

        Args:
            context: CommentPermissionContext containing user and operation info.

        Returns:
            int: Timeout in seconds (operation allowed within this window)
                 0 or negative: Operation not allowed

        """
        return ONE_HOUR_IN_SECONDS * 24

    def can_create_comment(self, user: UserWithPublicId | None) -> bool:
        """Check if user can create a comment on this row."""
        if user is None:
            return False
        context = CommentPermissionContext[_BaseModelMixin](
            user=user, operation="create_comment", row=self
        )
        return self.row_update_access_timeout(context) > 0

    def update_timeout(self, user: UserWithPublicId | None) -> int:
        """Get timeout in seconds for update_comment operation.

        Args:
            user: The user attempting to update a comment

        Returns:
            Timeout in seconds (positive if allowed, 0 or negative if not allowed)

        """
        context = CommentPermissionContext[_BaseModelMixin](
            user=user, operation="update_comment", row=self
        )
        return self.row_update_access_timeout(context)

    def delete_timeout(self, user: UserWithPublicId | None) -> int:
        """Get timeout in seconds for delete_comment operation.

        Args:
            user: The user attempting to delete a comment

        Returns:
            Timeout in seconds (positive if allowed, 0 or negative if not allowed)

        """
        context = CommentPermissionContext[_BaseModelMixin](
            user=user, operation="delete_comment", row=self
        )
        return self.row_update_access_timeout(context)

    def get_rowupdate_for_update(
        self, user: UserWithPublicId | None, row_update_id: int
    ) -> RowUpdate | None:
        """Get RowUpdate for update operation if user has permission.

        Returns RowUpdate if:
        - row_update_access_timeout returns a positive integer for update_comment
        - The comment was created within the timeout window
        - The user is the comment author
        - The row_update belongs to this model instance (modelname and row_pk match)

        Returns None if any condition fails.

        """
        try:
            row_update = RowUpdate.objects.filter_model(type(self)).get(
                pk=row_update_id,
                row_pk=self.pk,
            )
        except RowUpdate.DoesNotExist:
            return None

        timeout = self.update_timeout(user)
        if timeout <= 0:
            return None
        # Check if user is the comment author
        if row_update.created_by != user:
            return None
        # Check if within timeout window
        time_diff: datetime_module.timedelta = timezone.now() - row_update.created_at
        if time_diff.total_seconds() > timeout:
            return None
        return row_update

    def get_rowupdate_for_delete(
        self, user: UserWithPublicId | None, row_update_id: int
    ) -> RowUpdate | None:
        """Get RowUpdate for delete operation if allowed.

        Returns RowUpdate if:
        - row_update_access_timeout returns a positive integer for delete_comment
        - The comment was created within the timeout window
        - No user check for delete (anyone can delete within timeout)
        - The row_update belongs to this model instance (modelname and row_pk match)

        Returns None if any condition fails.

        """
        try:
            row_update = RowUpdate.objects.filter_model(type(self)).get(
                pk=row_update_id,
                row_pk=self.pk,
            )
        except RowUpdate.DoesNotExist:
            return None

        timeout = self.delete_timeout(user)
        if timeout <= 0:
            return None
        # Check if within timeout window (no user check for delete)
        time_diff: datetime_module.timedelta = timezone.now() - row_update.created_at
        if time_diff.total_seconds() > timeout:
            return None
        return row_update

    def create_comment(self, user: UserWithPublicId, content: str) -> RowUpdate:
        """Create a comment on this row.

        Args:
            user: The user creating the comment
            content: The comment content

        Returns:
            The created RowUpdate instance

        """
        modelname = self.modelname()
        row_update = RowUpdate(
            action="commented",
            created_by=user,
            modelname=modelname,
            row_pk=self.pk,
            row_public_id=self.public_id,
            comment_content=content,
        )
        row_update.save()
        self._create_notifications(
            row_update, CreateCommentNotifyContext(user=user, comment=row_update)
        )
        return row_update

    def update_comment(
        self, user: UserWithPublicId, row_update: RowUpdate, new_content: str
    ) -> RowUpdate:
        verified_update = self.get_rowupdate_for_update(user, row_update.pk)
        if not verified_update:
            msg = "Not allowed to update this comment"
            raise Http404(msg)
        verified_update.edit_comment(new_content)
        self._create_notifications(
            verified_update, UpdateCommentNotifyContext(user=user, comment=verified_update)
        )
        return verified_update

    def _build_row_update_response(
        self,
        row_update: RowUpdate,
        user: UserWithPublicId | None,
    ) -> RowUpdateResponse:
        redact_context = RowUpdateRedactContext[typing.Self](
            user=user,
            row_updates=[row_update],
            row=self,  # type: ignore[arg-type] # Self vs BaseModel type mismatch
        )
        redaction_map = self.redact_row_updates(
            redact_context  # type: ignore[arg-type] # Self vs BaseModel type mismatch
        )
        redaction_value = redaction_map[row_update.pk]

        user_ids: set[int] = set()
        if row_update.created_by_id is not None:
            user_ids.add(row_update.created_by_id)
        if row_update.comment_deleted_by_id is not None:
            user_ids.add(row_update.comment_deleted_by_id)

        user_map: dict[int, tuple[int, str]] = {}
        if user_ids:
            from djangoapp.models.app import (  # noqa: PLC0415 # avoid circular import at module level
                ProxyUser,
            )

            users_with_title = ProxyUser.queryset_with_title().filter(pk__in=user_ids)
            user_map = {u.pk: (u.pk, str(u.annotated_text)) for u in users_with_title}

        def user_schema_from_id(user_id: int | None) -> UserSchema | None:
            if user_id is None or user_id not in user_map:
                return None
            pk, title = user_map[user_id]
            return UserSchema(id=pk, title=title)

        created_by: UserSchema | None = None
        column_values: list[Any] | None = None
        comment_content: str | None = None
        comment_deleted_at: datetime_module.datetime | None = None
        comment_deleted_by: UserSchema | None = None
        comment_edited_at: datetime_module.datetime | None = None

        if redaction_value == "datetime_only":
            pass
        elif redaction_value == "datetime_user":
            created_by = user_schema_from_id(row_update.created_by_id)
        elif isinstance(redaction_value, list):
            all_values = row_update.values or []
            column_values = (
                [v for v in all_values if v.name in redaction_value] if all_values else None
            )
            created_by = user_schema_from_id(row_update.created_by_id)
            comment_edited_at = row_update.comment_edited_at
            comment_deleted_at = row_update.comment_deleted_at
            comment_deleted_by = user_schema_from_id(row_update.comment_deleted_by_id)
            comment_content = row_update.comment_content

        return RowUpdateResponse(
            id=str(row_update.id),
            action=row_update.action,  # type: ignore[arg-type]
            created_at=row_update.created_at,
            created_by=created_by,
            column_values=column_values,
            comment_content=comment_content,
            comment_deleted_at=comment_deleted_at,
            comment_deleted_by=comment_deleted_by,
            comment_edited_at=comment_edited_at,
        )

    def row_update_response(
        self, user: UserWithPublicId, row_update: RowUpdate
    ) -> RowUpdateResponse:
        return self._build_row_update_response(row_update, user)

    def rowupdates(self, user: UserWithPublicId | None = None) -> list[RowUpdateResponse]:
        row_updates = list(
            RowUpdate.objects.filter_model(type(self))
            .filter(row_pk=self.pk)
            .order_by("-created_at")
        )
        return [self._build_row_update_response(ru, user) for ru in row_updates]

    def serialize_to_row_values(
        self,
        fields: Sequence[DjangoField],
        old_values: dict[str, typing.Any] | None = None,
    ) -> list[RowColumnValueSchema] | None:
        """Serialize model instance field values to RowColumnValueSchema schemas.

        Args:
            fields: List of Django fields to serialize
            old_values: Dict mapping field names to old values (for updates)

        Returns:
            List of RowColumnValueSchema pydantic models, or None if no values serialized

        """
        result: list[RowColumnValueSchema] = []

        for field in fields:
            new_value = getattr(self, field.name)
            old_value = old_values.get(field.name) if old_values else None
            serializer = ROWUPDATE_VALUE_SERIALIZERS[type(field)]
            column_value = serializer(field, old_value, new_value)
            result.append(column_value)

        return result or None

    def redact_row_updates(
        self, context: RowUpdateRedactContext[typing.Self]
    ) -> dict[int, list[str] | Literal["datetime_only", "datetime_user"]]:
        """Determine which columns are visible for each row update.

        Default implementation: show all recorded columns.
        Override to implement custom redaction logic.

        Args:
            context: RowUpdateRedactContext with user, row_updates, and row

        Returns:
            Dict mapping row_update.id to either:
            - list[str]: column names that are visible (full access)
            - "datetime_only": only show timestamp, no user or column values
            - "datetime_user": show timestamp and created user, no column values

        """
        out: dict[int, list[str] | Literal["datetime_only", "datetime_user"]] = {}
        for row_update in context.row_updates:
            out[row_update.pk] = row_update.recorded_columns()
        return out

    def mark_files_for_deletion(self) -> None:
        """Mark all file fields on this instance for deletion (FileMarkedForDeletion records)."""
        fields = [
            f
            for f in self.__class__.raw_resolve_columns().values()
            if isinstance(f, models.FileField)
        ]
        for field in fields:
            file_value = getattr(self, field.name)
            if file_value and file_value.name:
                FileMarkedForDeletion.objects.create(file=file_value)

    def mark_column_file_for_deletion(self, field_instance: models.FileField) -> None:
        """Mark the given field instance's file for deletion (FileMarkedForDeletion record)."""
        if field_instance and field_instance.name:
            FileMarkedForDeletion.objects.create(file=field_instance)

    def delete_safely(self) -> tuple[int, dict[str, int]]:
        fields = [
            f
            for f in self.__class__.raw_resolve_columns().values()
            if isinstance(f, models.FileField)
        ]
        for field in fields:
            file_value = getattr(self, field.name)
            if file_value and file_value.name:
                FileMarkedForDeletion.objects.create(file=file_value)
        return self.delete()


class BaseModel(_BaseModelMixin):
    id = models.BigAutoField(primary_key=True)

    objects = BaseManager.from_queryset(BaseTableQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        cls = type(self)
        if cls.has_custom_public_id() and self.pk is None:
            field_name = cls.public_id_field
            if not getattr(self, field_name):
                setattr(self, field_name, cls.public_id_generator())
        super().save(*args, **kwargs)

    @staticmethod
    def generate_uuid7_id() -> str:
        return str(uuid.uuid7())


class UserManager(DjangoUserManager):  # type: ignore[type-arg] # parametrised implicitly via self.model = User
    """Manager for the custom ``User`` model.

    Subclasses Django's ``UserManager`` so ``create_user`` /
    ``create_superuser`` (and allauth) keep working unchanged. It does
    not carry the tables queryset methods (``queryset_with_title``,
    ``search_text``, ...); those live on ``ProxyUser`` via
    ``BaseManager``. ``public_id`` auto-generates from the field's
    ``default=BaseModel.generate_uuid7_id``, not via ``BaseModel.save``.
    """

    use_in_migrations = True


class User(AbstractUser, BaseModel):
    """Project-wide custom user model (``AUTH_USER_MODEL``).

    Carries a URL-safe UUID7 ``public_id`` (used in all public URLs and
    API responses), an optional rich-text ``description`` shown only when
    ``has_public_profile`` is set, and a ``search_users`` trigram search.
    Concrete tables/views must never send the integer ``pk`` to clients.
    """

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=BaseModel.generate_uuid7_id,
    )

    description = models.TextField(blank=True, default="")
    has_public_profile = models.BooleanField(default=False)

    objects = UserManager()  # type: ignore[assignment, misc] # custom user manager replaces BaseModel's BaseManager (create_user/superuser + allauth)

    class Meta:
        db_table = "auth_user"
        # GIN trigram indexes back User.search_users (pg_trgm similarity).
        indexes: ClassVar[list[models.Index]] = [
            GinIndex(
                fields=["first_name"],
                opclasses=["gin_trgm_ops"],
                name="user_first_name_trgm_idx",
            ),
            GinIndex(
                fields=["last_name"],
                opclasses=["gin_trgm_ops"],
                name="user_last_name_trgm_idx",
            ),
            GinIndex(
                fields=["username"],
                opclasses=["gin_trgm_ops"],
                name="user_username_trgm_idx",
            ),
        ]

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    @classmethod
    def search_users(cls, q: str) -> models.QuerySet[typing.Self]:
        """Return users ranked by trigram similarity across name fields.

        Matches ``first_name``, ``last_name`` and ``username`` using
        ``pg_trgm`` ``TrigramSimilarity`` and orders by best match.
        An empty query returns all users ordered by username so callers
        can still slice a top-N without special-casing empty input.
        """
        cleaned = q.strip()
        if not cleaned:
            return cast(
                "models.QuerySet[typing.Self]",
                cls.objects.all().order_by("username"),
            )
        return cast(
            "models.QuerySet[typing.Self]",
            cls.objects.annotate(
                similarity=(
                    TrigramSimilarity("first_name", cleaned)
                    + TrigramSimilarity("last_name", cleaned)
                    + TrigramSimilarity("username", cleaned)
                ),
            )
            .filter(similarity__gt=0.1)
            .order_by("-similarity", "username"),
        )

    def snapshot(self) -> UserSnapshot:
        return UserSnapshot(
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            description=self.description,
            has_public_profile=self.has_public_profile,
            is_active=self.is_active,
            is_staff=self.is_staff,
            is_superuser=self.is_superuser,
        )

    def update(  # noqa: PLR0913 # 8 params: all needed for user update
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        description: str,
        has_public_profile: bool,
        is_active: bool,
        is_staff: bool,
        is_superuser: bool,
        user: User,
    ) -> None:
        old_snapshot = self.snapshot()
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.description = description
        self.has_public_profile = has_public_profile
        self.is_active = is_active
        self.is_staff = is_staff
        self.is_superuser = is_superuser
        self.save()
        new_snapshot = self.snapshot()
        # Only record an edited entry when something actually changed; a
        # no-op submit must not create empty history noise.
        if any(v is not None for v in old_snapshot.difference(new_snapshot).model_dump().values()):
            UserHistory.record_edited(self, user, old_snapshot, new_snapshot)


class FileMarkedForDeletion(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField()


def annotate_fk_titles(
    columns: Sequence[DjangoField],
    rows: Sequence[_BaseModelMixin],
) -> None:
    """Batch-fetch FK titles and embed them on each row instance.

    Populates ``_fk_titles`` on each row so ForeignKeyValueWrapper can
    look up titles without additional queries.

    Args:
        columns: List of Django fields (only ForeignKey fields are processed)
        rows: Model instances to annotate

    """
    fk_titles: FkTitlesMap = {}

    for field in columns:
        if not isinstance(field, models.ForeignKey):
            continue

        fk_ids: set[int] = set()
        for row in rows:
            fk_id = getattr(row, f"{field.name}_id", None)
            if fk_id is not None:
                fk_ids.add(fk_id)

        if not fk_ids:
            continue

        field_titles: dict[int, ForeignKeyTitleData] = {}
        assert field.related_model is not None
        related_model = cast(type["_BaseModelMixin"], field.related_model)
        for obj in related_model.queryset_with_title().filter(pk__in=fk_ids):
            field_titles[obj.pk] = ForeignKeyTitleData(
                public_id=obj.public_id,
                title=str(obj.annotated_text),
            )
        fk_titles[field.name] = field_titles

    for row in rows:
        row._fk_titles = fk_titles  # setting annotated FK data on instance  # noqa: SLF001


class RowUpdateQuerySet(models.QuerySet["RowUpdate"]):
    """Custom QuerySet with chainable filter methods for RowUpdate."""

    def filter_model(self, model_class: type[_BaseModelMixin]) -> RowUpdateQuerySet:
        modelname = model_class.modelname()
        return self.filter(modelname=modelname)

    def filter_user_and_actions(
        self,
        user_ids: list[str] | None = None,
        actions: list[Literal["created_row", "updated_row", "commented"]] | None = None,
    ) -> RowUpdateQuerySet:
        """Filter RowUpdates by user IDs and/or action types.

        Args:
            user_ids: List of user public IDs to filter by (None = no filter)
            actions: Action types to filter by (None = all actions)

        Returns:
            Self for chaining

        """
        qs = self
        if user_ids:
            from djangoapp.models.app import (  # noqa: PLC0415 # avoid circular import at module level
                ProxyUser,
            )

            resolved_pks = ProxyUser.filter_by_public_ids(
                ProxyUser._default_manager.all(),  # noqa: SLF001
                user_ids,
            ).values_list("pk", flat=True)
            qs = qs.filter(created_by_id__in=resolved_pks)
        if actions:
            qs = qs.filter(action__in=actions)
        return qs

    def filter_dates(
        self,
        start: datetime_module.datetime | None = None,
        end: datetime_module.datetime | None = None,
    ) -> RowUpdateQuerySet:
        qs = self
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)
        return qs


class RowUpdateManager(models.Manager["RowUpdate"]):
    """Custom manager for RowUpdate model with chainable queryset methods."""


# TypeAdapter for validating list of column values
_list_column_values_validator: TypeAdapter[list[RowColumnValueSchema]] = TypeAdapter(
    list[RowColumnValueSchema]
)


class RowUpdate(models.Model):
    """Stores audit trail for create/update/comment actions on BaseModel instances."""

    ACTION_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("created_row", "Created Row"),
        ("updated_row", "Updated Row"),
        ("commented", "Commented"),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    # TODO use generic user model
    # We disabled related_name using + since ProxyUser (then defined at line 1507) had this problem:
    # djangoapp/models.py:1507: error: Couldn't resolve related manager 'rowupdate_set' for relation 'djangoapp.models.RowUpdate.created_by'.  [django-manager-missing]  # noqa: E501, W505 let comments exceed line width
    # djangoapp/models.py:1507: error: Couldn't resolve related manager 'deleted_row_updates' for relation 'djangoapp.models.RowUpdate.comment_deleted_by'.  [django-manager-missing]  # noqa: E501, W505 let comments exceed line width
    #
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    _values = models.JSONField(
        default=list, null=True, blank=True
    )  # Stores list of column value dicts as JSON

    # We are avoiding GenericForeignKey since rows can be `(djangoapp.FirstStuff, 123)`
    # instead of `(5, 123)` where we have to lookup `5` is `djangoapp.FirstStuff`
    # in content type table.
    # Also Generic Foreign Key has only cascade deletes but we want to keep updates
    #  for deleted rows.
    modelname = models.CharField(
        max_length=255
    )  # Fully qualified model name (e.g., "djangoapp.FirstStuff")
    row_pk = models.IntegerField()  # Primary key of the related model instance
    row_public_id = models.CharField(max_length=255, default="")

    comment_content = models.TextField(blank=True, default="", max_length=1000)
    comment_deleted_at = models.DateTimeField(null=True, blank=True)

    # Track edits and deletions
    comment_edited_at = models.DateTimeField(null=True, blank=True)
    comment_deleted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )

    objects: RowUpdateQuerySet = RowUpdateManager.from_queryset(RowUpdateQuerySet)()  # type: ignore[assignment]

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["modelname", "row_pk"]),
            models.Index(fields=["modelname", "row_public_id"]),
            models.Index(fields=["created_at"]),
        ]
        ordering: ClassVar[list[str]] = ["-created_at"]

    def edit_comment(self, new_content: str) -> None:
        """Edit comment content and track edit timestamp.

        Args:
            new_content: The new comment content

        """
        self.comment_content = new_content
        self.comment_edited_at = timezone.now()
        self.save()

    def delete_comment(self, user: UserWithPublicId) -> None:
        """Soft delete the comment by setting deleted_at and clearing content.

        Args:
            user: The user deleting the comment

        """
        self.comment_deleted_at = timezone.now()
        self.comment_content = ""
        self.comment_deleted_by = user
        self.save()

    def recorded_columns(self) -> list[str]:
        """Get list of column names from .values.

        Returns empty list if no values are stored.
        """
        if not self._values:
            return []
        return [v.get("name", "") for v in self._values if v.get("name")]

    @property
    def values(self) -> list[RowColumnValueSchema] | None:
        """Deserialize JSON to list of column value schemas.

        Returns None if _values is empty. The returned list contains
        validated RowColumnValueSchema instances (one of the union types).
        """
        if not self._values:
            return None
        # Use TypeAdapter to validate the entire list at once
        return _list_column_values_validator.validate_python(self._values)

    @values.setter
    def values(self, value: list[RowColumnValueSchema] | None) -> None:
        """Serialize list of column value schemas to JSON.

        Stores as a plain list of dicts in _values field (no version wrapper).
        """
        if value is None:
            self._values = None
        else:
            self._values = _list_column_values_validator.dump_python(value)


type NotifyOperation = Literal["create_row", "update_row", "create_comment", "update_comment"]


@dataclass
class CreateRowNotifyContext:
    user: UserWithPublicId
    type: Literal["create_row"] = "create_row"


@dataclass
class UpdateRowNotifyContext:
    user: UserWithPublicId
    type: Literal["update_row"] = "update_row"


@dataclass
class CreateCommentNotifyContext:
    user: UserWithPublicId
    comment: RowUpdate
    type: Literal["create_comment"] = "create_comment"


@dataclass
class UpdateCommentNotifyContext:
    user: UserWithPublicId
    comment: RowUpdate
    type: Literal["update_comment"] = "update_comment"


type NotifyContext = (
    CreateRowNotifyContext
    | UpdateRowNotifyContext
    | CreateCommentNotifyContext
    | UpdateCommentNotifyContext
)


class RowUpdateUserNotification(models.Model):
    modelname = models.CharField(max_length=255)
    row_pk = models.IntegerField()
    row_public_id = models.CharField(max_length=255, default="")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    datetime = models.DateTimeField(auto_now_add=True)
    content = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["modelname", "row_pk"]),
        ]


class ArticleNotification(models.Model):
    article_public_id = models.CharField(max_length=255)
    comment_public_id = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    datetime = models.DateTimeField(auto_now_add=True)
    content = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["user", "-id"])]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["comment_public_id", "user"],
                name="uniq_article_notif_per_comment_user",
            ),
        ]


def _extract_article_image_ids(html: str, public_id: str) -> list[str]:
    """Extract image UUIDs from HTML content for a given article public_id.

    Parses <img> tags and collects the UUID portion after the
    ``download-image/{public_id}/`` marker in each ``src`` attribute.

    Returns:
        List of UUID strings found in image sources.

    """
    from html.parser import HTMLParser  # noqa: PLC0415 # used in inner class

    marker = f"download-image/{public_id}/"
    ids: list[str] = []

    class _Parser(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "img":
                for attr_name, attr_value in attrs:
                    if attr_name == "src" and attr_value and marker in attr_value:
                        ids.append(attr_value.split(marker, 1)[1])

    _Parser().feed(html)
    return ids


def _generate_article_public_id(title: str) -> str:
    """Generate a public ID for an article from its title.

    Example: ``_generate_article_public_id("Hello World")``
    might return ``"20260606-hello-world-a3f9k2"``.
    """
    date_str = timezone.now().strftime("%Y%m%d")
    slug = slugify(title)[:50] if title else "untitled"
    random_suffix = "".join(
        secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6)
    )
    return f"{date_str}-{slug}-{random_suffix}"


class ArticleTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7)

    def __str__(self) -> str:
        """Return the model's name."""
        return self.name

    @classmethod
    def get_or_404(cls, name: str) -> ArticleTag:
        """Get a tag by name or raise Http404."""
        try:
            return cls.objects.get(name=name)
        except cls.DoesNotExist:
            msg = "Tag not found"
            raise Http404(msg) from None

    @classmethod
    def create(cls, name: str, color: str) -> ArticleTag:
        """Create and return a new tag after validation.

        Raises ``ValidationError`` if a tag with the same name already exists
        (via ``full_clean()`` unique constraint check).
        """
        tag = cls(name=name, color=color)
        tag.full_clean()
        tag.save()
        return tag

    def update(self, name: str, color: str) -> None:
        """Update tag name and color after validation.

        Raises ``ValidationError`` from ``full_clean()`` if fields are invalid.
        """
        self.name = name
        self.color = color
        self.full_clean()
        self.save()


class MediaImageItem(PydanticBaseModel):
    uuid_id: str
    size: int
    image_url: str


class MediaSummary(PydanticBaseModel):
    total_bytes: int
    quota_bytes: int
    images: list[MediaImageItem]


class Article(models.Model):
    title = models.CharField(max_length=255)
    public_id = models.CharField(
        max_length=255,
        unique=True,
        editable=True,
        validators=[public_id_django_validator],
    )
    content = models.TextField(max_length=50000, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    is_commenting_enabled = models.BooleanField(default=True)
    tags = models.ManyToManyField(ArticleTag, blank=True)
    subscribers = models.ManyToManyField(User, related_name="+", blank=True)
    author = models.ForeignKey(User, on_delete=models.RESTRICT, related_name="articles")
    first_image = models.UUIDField(null=True, blank=True)

    CONTENT_IMAGES_TOTAL_BYTES: ClassVar[int] = 50 * 1024 * 1024
    # Late-bound resolvers registered by the app (see @article_editors /
    # @article_participants in views.articles). Stored as ClassVar callables so
    # model methods can test editorship/participation without importing views
    # (avoids a circular import).
    _editors_fn: ClassVar[Callable[[], models.QuerySet[User]] | None] = None
    _participants_fn: ClassVar[Callable[[], models.QuerySet[User]] | None] = None

    def __str__(self) -> str:
        """Return the model's title."""
        return self.title

    def save(self, **kwargs: Any) -> None:  # noqa: ANN401
        is_new = self.pk is None
        if is_new and not self.public_id:
            self.public_id = _generate_article_public_id(self.title)
        super().save(**kwargs)
        self.update_first_image()
        self.cleanup_orphaned_images()

    @classmethod
    def set_editors(cls, fn: Callable[[], models.QuerySet[User]]) -> None:
        cls._editors_fn = fn

    @classmethod
    def set_participants(cls, fn: Callable[[], models.QuerySet[User]]) -> None:
        cls._participants_fn = fn

    @classmethod
    def editors(cls) -> models.QuerySet[User]:
        if cls._editors_fn is None:
            msg = "article editors resolver not registered (use @article_editors)"
            raise NotImplementedError(msg)
        return cls._editors_fn()

    @classmethod
    def participants(cls) -> models.QuerySet[User]:
        if cls._participants_fn is None:
            msg = "article participants resolver not registered (use @article_participants)"
            raise NotImplementedError(msg)
        return cls._participants_fn()

    @classmethod
    def is_editor(cls, user: User) -> bool:
        if not user.is_authenticated:
            return False
        return cls.editors().filter(pk=user.pk).exists()

    @classmethod
    def is_participant(cls, user: User) -> bool:
        if not user.is_authenticated:
            return False
        return cls.participants().filter(pk=user.pk).exists()

    @classmethod
    def is_author(cls, user: User, article: Article) -> bool:
        return article.author_id == user.pk

    @classmethod
    def can_be_edited_by(cls, user: User, article: Article) -> bool:
        return cls.is_editor(user) or cls.is_author(user, article)

    @classmethod
    def get_or_404(cls, public_id: str) -> Article:
        """Get an article by public_id or raise Http404."""
        try:
            return cls.objects.get(public_id=public_id)
        except cls.DoesNotExist:
            msg = "Article not found"
            raise Http404(msg) from None

    @classmethod
    def get_or_404_with_annotations(cls, public_id: str) -> Article:
        try:
            return cls.objects.prefetch_related(
                "tags",
                Prefetch("author", queryset=User.objects.all()),
            ).get(public_id=public_id)
        except cls.DoesNotExist:
            msg = "Article not found"
            raise Http404(msg) from None

    @staticmethod
    def user_profile(user: User) -> UserProfile:
        return UserProfile(
            id=user.pk,
            public_id=user.public_id,
            title=user.display_name,
        )

    @staticmethod
    def comment_notification_content(
        article: Article, comment: ArticleComment, actor: User
    ) -> dict[str, Any]:
        profile = Article.user_profile(actor)
        return {
            "action": "commented",
            "article": {"public_id": article.public_id, "title": article.title},
            "comment": {"public_id": str(comment.public_id), "content": comment.content},
            "commenter": {"id": profile.id, "title": profile.title},
        }

    @classmethod
    def create(  # noqa: PLR0913 # 8 params: all needed for article creation
        cls,
        *,
        title: str,
        public_id: str = "",
        content: str = "",
        published: bool = False,
        tag_names: list[str] | None = None,
        author_id: int | None = None,
        is_commenting_enabled: bool = True,
        user: User,
    ) -> Article:
        published_at = timezone.now() if published else None
        article = cls(
            title=title,
            public_id=public_id or "",
            content=content,
            published_at=published_at,
            author_id=author_id or user.pk,
            is_commenting_enabled=is_commenting_enabled,
        )
        if not article.public_id:
            article.public_id = _generate_article_public_id(article.title)
        article.full_clean()
        article.save()

        article.tags.set(ArticleTag.objects.filter(name__in=(tag_names or [])))

        snapshot = article.snapshot()
        ArticleHistory.record_created(article, user, snapshot)

        return article

    def snapshot(self) -> ArticleSnapshot:
        return ArticleSnapshot(
            title=self.title,
            public_id=self.public_id,
            content=self.content,
            tags=[ArticleHistoryTagItem(name=t.name, color=t.color) for t in self.tags.all()],
            author=Article.user_profile(self.author),
            published_date=self.published_at or None,
        )

    def update(  # noqa: PLR0913 # 8 params: all needed for article update
        self,
        *,
        title: str,
        public_id: str = "",
        content: str = "",
        published: bool,
        tag_names: list[str] | None = None,
        author_id: int | None = None,
        is_commenting_enabled: bool = True,
        user: User,
    ) -> None:
        old_snapshot = self.snapshot()

        self.title = title
        if public_id:
            self.public_id = public_id
        self.content = content
        if published and self.published_at is None:
            self.published_at = timezone.now()
        elif not published:
            self.published_at = None

        if author_id is not None:
            self.author_id = author_id

        self.is_commenting_enabled = is_commenting_enabled
        self.save()

        self.tags.set(ArticleTag.objects.filter(name__in=(tag_names or [])))

        new_snapshot = self.snapshot()
        ArticleHistory.record_edited(self, user, old_snapshot, new_snapshot)

    def media_summary(self, path_prefix: str) -> MediaSummary:
        images = list(ArticleImage.objects.filter(article_id=self.pk))
        total = sum(img.size for img in images)
        return MediaSummary(
            total_bytes=total,
            quota_bytes=Article.CONTENT_IMAGES_TOTAL_BYTES,
            images=[
                MediaImageItem(
                    uuid_id=str(img.uuid_id),
                    size=img.size,
                    image_url=f"{path_prefix}/api/download-image/{self.public_id}/{img.uuid_id}",
                )
                for img in images
            ],
        )

    def existing_image_bytes(self) -> int:
        return int(
            ArticleImage.objects.filter(article_id=self.pk).aggregate(total=Sum("size"))["total"]
            or 0
        )

    def image_quota_exceeded(self, image_size: int) -> bool:
        return self.existing_image_bytes() + image_size > Article.CONTENT_IMAGES_TOTAL_BYTES

    def update_first_image(self) -> None:
        if self.pk and self.content and self.public_id:
            ids = _extract_article_image_ids(self.content, self.public_id)
            self.first_image = uuid.UUID(ids[0]) if ids else None
        else:
            self.first_image = None
        Article.objects.filter(pk=self.pk).update(first_image=self.first_image)

    def cleanup_orphaned_images(self) -> None:
        if not self.content or not self.pk or not self.public_id:
            return
        referenced_ids = _extract_article_image_ids(self.content, self.public_id)
        orphaned = ArticleImage.objects.filter(article_id=self.pk).exclude(
            uuid_id__in=referenced_ids
        )
        for img in orphaned:
            img.delete_safely()

    def delete(self, user: User | None = None, **kwargs: Any) -> tuple[int, dict[str, int]]:  # type: ignore[override]  # noqa: ANN401
        ArticleHistory.record_deleted(self, user)
        for img in ArticleImage.objects.filter(article_id=self.pk):
            img.delete_safely()
        return super().delete(**kwargs)


class ArticleImage(models.Model):
    uuid_id = models.UUIDField(
        unique=True, editable=False, default=uuid.uuid7, help_text="Public id for the image"
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.RESTRICT,
        db_index=True,
    )
    image = models.FileField(
        upload_to="uploads/article_images/",
    )
    size = models.PositiveBigIntegerField(
        default=0, help_text="Size of the uploaded image in bytes"
    )

    def save(self, **kwargs: Any) -> None:  # noqa: ANN401
        assert self.image, "ArticleImage must have an image file"
        self.size = self.image.size
        super().save(**kwargs)

    def delete_safely(self) -> tuple[int, dict[str, int]]:
        self.mark_image_for_deletion()
        return super().delete()

    def mark_image_for_deletion(self) -> None:
        if self.image and self.image.name:
            FileMarkedForDeletion.objects.create(file=self.image)


class ArticleHistoryTagItem(PydanticBaseModel):
    name: str
    color: str


class UserProfile(PydanticBaseModel):
    id: int
    public_id: str
    title: str


class StringChange(PydanticBaseModel):
    old: str
    new: str


class NullableDateChange(PydanticBaseModel):
    old: datetime_type | None
    new: datetime_type | None


class TagListChange(PydanticBaseModel):
    old: list[ArticleHistoryTagItem]
    new: list[ArticleHistoryTagItem]


class AuthorChange(PydanticBaseModel):
    old: UserProfile
    new: UserProfile


class ArticleHistoryContent(PydanticBaseModel):
    title: StringChange | None = None
    public_id: StringChange | None = None
    content: StringChange | None = None
    tags: TagListChange | None = None
    author: AuthorChange | None = None
    published_date: NullableDateChange | None = None


class ArticleSnapshot(PydanticBaseModel):
    title: str
    public_id: str
    content: str
    tags: list[ArticleHistoryTagItem]
    author: UserProfile
    published_date: datetime_type | None

    def as_new(self) -> ArticleHistoryContent:
        return ArticleHistoryContent(
            title=StringChange(old=self.title, new=self.title),
            public_id=StringChange(old=self.public_id, new=self.public_id),
            content=StringChange(old=self.content, new=self.content),
            tags=TagListChange(old=self.tags, new=self.tags),
            author=AuthorChange(old=self.author, new=self.author),
            published_date=NullableDateChange(
                old=self.published_date,
                new=self.published_date,
            ),
        )

    def difference(self, other: ArticleSnapshot) -> ArticleHistoryContent:
        changes: dict[str, Any] = {}
        if self.title != other.title:
            changes["title"] = StringChange(old=self.title, new=other.title)
        if self.public_id != other.public_id:
            changes["public_id"] = StringChange(old=self.public_id, new=other.public_id)
        if self.content != other.content:
            changes["content"] = StringChange(old=self.content, new=other.content)
        if self.tags != other.tags:
            changes["tags"] = TagListChange(old=self.tags, new=other.tags)
        if self.author != other.author:
            changes["author"] = AuthorChange(old=self.author, new=other.author)
        if self.published_date != other.published_date:
            changes["published_date"] = NullableDateChange(
                old=self.published_date,
                new=other.published_date,
            )
        return ArticleHistoryContent(**changes)


# `from __future__ import annotations` makes all annotations strings, so pydantic
# cannot resolve `date_type | None` at class-definition time. This rebuild call
# supplies the namespace so pydantic can evaluate those string annotations.
ArticleSnapshot.model_rebuild(
    _types_namespace={
        "date_type": date_type,
        "datetime_type": datetime_type,
        "datetime_module": datetime_module,
        "datetime": datetime_module,
        "UserProfile": UserProfile,
        "NullableDateChange": NullableDateChange,
        "AuthorChange": AuthorChange,
    }
)


class ArticleHistoryEntryItem(PydanticBaseModel):
    id: int
    action: Literal["created", "edited", "deleted"]
    time: str
    changes: ArticleHistoryContent


class ArticleHistory(models.Model):
    ACTION_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("created", "Created"),
        ("edited", "Edited"),
        ("deleted", "Deleted"),
    ]

    article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_entries",
    )
    article_public_id_copy = models.CharField(max_length=255, default="")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    time = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    _changes = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["article"]),
            models.Index(fields=["time"]),
        ]
        ordering: ClassVar[list[str]] = ["-time"]

    def to_article_history_entry_item(self) -> ArticleHistoryEntryItem:
        content = (
            ArticleHistoryContent.model_validate(self._changes)
            if self._changes
            else ArticleHistoryContent()
        )
        return ArticleHistoryEntryItem(
            id=self.pk,
            action=cast(Literal["created", "edited", "deleted"], self.action),
            time=self.time.isoformat(),
            changes=content,
        )

    @classmethod
    def record_created(
        cls,
        article: Article,
        user: User | None,
        snapshot: ArticleSnapshot,
    ) -> ArticleHistory:
        return cls.objects.create(
            article=article,
            article_public_id_copy=article.public_id,
            user=user,
            action="created",
            _changes=snapshot.as_new().model_dump(mode="json"),
        )

    @classmethod
    def record_edited(
        cls,
        article: Article,
        user: User | None,
        old_snapshot: ArticleSnapshot,
        new_snapshot: ArticleSnapshot,
    ) -> ArticleHistory:
        diff = old_snapshot.difference(new_snapshot)
        return cls.objects.create(
            article=article,
            article_public_id_copy=article.public_id,
            user=user,
            action="edited",
            _changes=diff.model_dump(mode="json"),
        )

    @classmethod
    def record_deleted(
        cls,
        article: Article,
        user: User | None,
    ) -> ArticleHistory:
        return cls.objects.create(
            article=article,
            article_public_id_copy=article.public_id,
            user=user,
            action="deleted",
            _changes={},
        )


class BoolChange(PydanticBaseModel):
    old: bool
    new: bool


class UserHistoryContent(PydanticBaseModel):
    first_name: StringChange | None = None
    last_name: StringChange | None = None
    email: StringChange | None = None
    description: StringChange | None = None
    has_public_profile: BoolChange | None = None
    is_active: BoolChange | None = None
    is_staff: BoolChange | None = None
    is_superuser: BoolChange | None = None


class UserSnapshot(PydanticBaseModel):
    first_name: str
    last_name: str
    email: str
    description: str
    has_public_profile: bool
    is_active: bool
    is_staff: bool
    is_superuser: bool

    def as_new(self) -> UserHistoryContent:
        return UserHistoryContent(
            first_name=StringChange(old=self.first_name, new=self.first_name),
            last_name=StringChange(old=self.last_name, new=self.last_name),
            email=StringChange(old=self.email, new=self.email),
            description=StringChange(old=self.description, new=self.description),
            has_public_profile=BoolChange(
                old=self.has_public_profile,
                new=self.has_public_profile,
            ),
            is_active=BoolChange(old=self.is_active, new=self.is_active),
            is_staff=BoolChange(old=self.is_staff, new=self.is_staff),
            is_superuser=BoolChange(
                old=self.is_superuser,
                new=self.is_superuser,
            ),
        )

    def difference(self, other: UserSnapshot) -> UserHistoryContent:
        changes: dict[str, Any] = {}
        if self.first_name != other.first_name:
            changes["first_name"] = StringChange(old=self.first_name, new=other.first_name)
        if self.last_name != other.last_name:
            changes["last_name"] = StringChange(old=self.last_name, new=other.last_name)
        if self.email != other.email:
            changes["email"] = StringChange(old=self.email, new=other.email)
        if self.description != other.description:
            changes["description"] = StringChange(old=self.description, new=other.description)
        if self.has_public_profile != other.has_public_profile:
            changes["has_public_profile"] = BoolChange(
                old=self.has_public_profile,
                new=other.has_public_profile,
            )
        if self.is_active != other.is_active:
            changes["is_active"] = BoolChange(old=self.is_active, new=other.is_active)
        if self.is_staff != other.is_staff:
            changes["is_staff"] = BoolChange(old=self.is_staff, new=other.is_staff)
        if self.is_superuser != other.is_superuser:
            changes["is_superuser"] = BoolChange(
                old=self.is_superuser,
                new=other.is_superuser,
            )
        return UserHistoryContent(**changes)


class UserHistoryEntryItem(PydanticBaseModel):
    id: int
    action: Literal["created", "edited", "deleted"]
    time: str
    changes: UserHistoryContent


class UserHistory(models.Model):
    ACTION_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("created", "Created"),
        ("edited", "Edited"),
        ("deleted", "Deleted"),
    ]

    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_entries",
    )
    target_user_public_id_copy = models.CharField(max_length=36, default="")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    time = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    _changes = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["target_user"]),
            models.Index(fields=["time"]),
        ]
        ordering: ClassVar[list[str]] = ["-time"]

    def to_user_history_entry_item(self) -> UserHistoryEntryItem:
        content = (
            UserHistoryContent.model_validate(self._changes)
            if self._changes
            else UserHistoryContent()
        )
        return UserHistoryEntryItem(
            id=self.pk,
            action=cast(Literal["created", "edited", "deleted"], self.action),
            time=self.time.isoformat(),
            changes=content,
        )

    @classmethod
    def record_created(
        cls,
        target_user: User,
        user: User | None,
        snapshot: UserSnapshot,
    ) -> UserHistory:
        return cls.objects.create(
            target_user=target_user,
            target_user_public_id_copy=target_user.public_id,
            user=user,
            action="created",
            _changes=snapshot.as_new().model_dump(mode="json"),
        )

    @classmethod
    def record_edited(
        cls,
        target_user: User,
        user: User | None,
        old_snapshot: UserSnapshot,
        new_snapshot: UserSnapshot,
    ) -> UserHistory:
        diff = old_snapshot.difference(new_snapshot)
        return cls.objects.create(
            target_user=target_user,
            target_user_public_id_copy=target_user.public_id,
            user=user,
            action="edited",
            _changes=diff.model_dump(mode="json"),
        )

    @classmethod
    def record_deleted(
        cls,
        target_user: User,
        user: User | None,
    ) -> UserHistory:
        return cls.objects.create(
            target_user=target_user,
            target_user_public_id_copy=target_user.public_id,
            user=user,
            action="deleted",
            _changes={},
        )


class ArticleCommentItem(PydanticBaseModel):
    public_id: str
    content: str
    commented_by: UserProfile
    commented_at: datetime_type
    updated_at: datetime_type | None = None
    is_deleted: Literal[False] = False


class DeletedArticleCommentItem(PydanticBaseModel):
    public_id: str
    commented_by: UserProfile
    commented_at: datetime_type
    is_deleted: Literal[True] = True


class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField(max_length=1000)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    commented_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    commented_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, blank=True, related_name="+"
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["article"]),
            models.Index(fields=["commented_at"]),
        ]
        ordering: ClassVar[list[str]] = ["-commented_at"]

    def soft_delete(self, user: User) -> None:
        self.deleted_at = timezone.now()
        self.deleted_by_id = user.pk
        self.content = ""
        self.save()

    def can_update_comment(self, user: User) -> bool:
        if self.deleted_at is not None:
            return False
        if self.commented_by_id != user.pk:
            return False
        elapsed = (timezone.now() - self.commented_at).total_seconds()
        return elapsed <= ONE_HOUR_IN_SECONDS

    def update_content(self, user: User, new_content: str, *, check: bool = True) -> None:
        if check and not self.can_update_comment(user):
            msg = "Cannot update comment"
            raise ValueError(msg)
        self.content = new_content
        self.updated_at = timezone.now()
        self.save()

    def can_soft_delete_comment(self, user: User, article: Article) -> bool:
        if self.commented_by_id == user.pk:
            return True
        if article.author_id == user.pk:
            return True
        return article.is_editor(user)

    @classmethod
    def for_article(cls, article: Article) -> list[ArticleCommentItem | DeletedArticleCommentItem]:
        comments = list(cls.objects.filter(article=article))
        user_ids = {c.commented_by_id for c in comments if c.commented_by_id}
        if user_ids:
            user_map = dict(User.objects.in_bulk(user_ids))
        else:
            user_map = {}
        items: list[ArticleCommentItem | DeletedArticleCommentItem] = []
        for c in comments:
            commenter = user_map.get(c.commented_by_id) if c.commented_by_id else None
            commented_by = (
                Article.user_profile(commenter)
                if commenter is not None
                else UserProfile(id=0, public_id="", title="[deleted]")
            )
            if c.deleted_at is not None:
                items.append(
                    DeletedArticleCommentItem(
                        public_id=str(c.public_id),
                        commented_by=commented_by,
                        commented_at=c.commented_at,
                    )
                )
            else:
                items.append(
                    ArticleCommentItem(
                        public_id=str(c.public_id),
                        content=c.content,
                        commented_by=commented_by,
                        commented_at=c.commented_at,
                        updated_at=c.updated_at,
                    )
                )
        return items


class FooModel(models.Model):
    """Concrete base for the Foo CRUD system (multi-table inheritance).

    A plain concrete model (NOT a BaseModel). It owns only created_at, a
    sequence-based public_id, and the minimum helpers (generate-on-save,
    fetch-by-public-id). Column serialization/editability live on the FooView
    + columns module.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    public_id = models.CharField(max_length=100, unique=True, editable=False)

    public_id_generator: typing.ClassVar[typing.Callable[[], str]] = generate_sequence_id(
        "%Y-%m-%d-ID"
    )

    class Meta:
        app_label = "djangoapp"

    def __str__(self) -> str:
        """Human label used as the list/details title."""
        return f"{type(self).__name__}({self.public_id})"

    def save(self, *args: object, **kwargs: object) -> None:
        # Generate the public id only on first save -- minimising sequence
        # gaps on rolled-back inserts (validate_unique runs before this).
        if self.pk is None and not self.public_id:
            self.public_id = type(self).public_id_generator()
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def get_by_public_id_or_404(cls, public_id: str) -> typing.Self:
        try:
            return cls.objects.get(public_id=public_id)
        except cls.DoesNotExist:
            msg = f"{cls.__name__} {public_id!r} not found"
            raise Http404(msg) from None
