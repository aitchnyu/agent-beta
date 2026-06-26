# ------------------ Our test models, must be last part of this model ---------------------
from __future__ import annotations

import typing
import uuid
from decimal import Decimal
from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import F, Value

if typing.TYPE_CHECKING:
    from django_stubs_ext import WithAnnotations

from django.db.models.functions import Coalesce, Concat, NullIf, Trim
from django.utils import timezone

from djangoapp.models.base import (
    AnnotatedTextDict,
    BaseModel,
    CommentPermissionContext,
    FooModel,
    NotifyContext,
    ResolveColumnsContext,
    ResolveRowsContext,
    SaveContext,
    SearchContext,
    User,
    UserWithPublicId,
    _BaseModelMixin,
    _default_integer_callable,
    search,
)
from djangoapp.models.public_ids import (
    generate_sequence_id,
    public_id_django_validator,
    validate_public_id_format,
)

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class Ref(BaseModel):
    title_annotation = F("char_field")
    char_field = models.CharField(max_length=10)

    def save_stuff(self, context: SaveContext[typing.Self]) -> None:  # pragma: no cover
        # if self.char_field == "11":
        #     raise ValidationError({"char_field": "value is 11", "_top": "Oops, something is 11"})
        super().save_stuff(context)


class FirstStuff(BaseModel):
    char_field = models.CharField(max_length=10, default="foo")
    text_field = models.TextField(default="bar", blank=True)
    integer_field = models.IntegerField(default=1)
    nullable_integer_field = models.IntegerField(default=10, null=True)
    boolean_field = models.BooleanField(default=True)
    decimal_field = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    datetime_field = models.DateTimeField(default=timezone.now)
    char_choice_field = models.CharField(
        max_length=10,
        choices=[("opt1", "Option 1"), ("opt2", "Option 2"), ("opt3", "Option 3")],
        default="opt2",
    )
    int_choice_field = models.IntegerField(
        choices=[(1, "One"), (2, "Two"), (3, "Three")], default=1
    )
    ref_fk = models.ForeignKey(Ref, null=True, on_delete=models.RESTRICT)
    user_fk = models.ForeignKey("ProxyUser", null=True, on_delete=models.RESTRICT)
    file_field = models.FileField(upload_to="uploads/", null=True, blank=True)

    def save_stuff(self, context: SaveContext[typing.Self]) -> None:
        # self.integer_field = 1
        # raise ValidationError({"integer_field": "haha", 'char_field': 'meow', "_top": 'xyz'})
        super().save_stuff(context)

    @search("user_fk")
    @classmethod
    def search_user_fk(cls, context: SearchContext[ProxyUser]) -> models.QuerySet[ProxyUser]:
        """Filter ProxyUser by is_active status."""
        return context.queryset.filter(is_active=True)

    def notify_users(self, context: NotifyContext) -> Sequence[UserWithPublicId]:  # noqa: ARG002 # method override, context required by signature
        return list(User.objects.all())


class NotifyingFirstStuff(FirstStuff):
    class Meta:
        proxy = True
        app_label = "djangoapp"

    def notify_users(self, context: NotifyContext) -> Sequence[UserWithPublicId]:  # noqa: ARG002 returns all users regardless of context
        return list(User.objects.all())


class MoreStuff(BaseModel):
    char_field = models.CharField(max_length=10, default="char")
    text_field = models.TextField(default="text")


class AbstractIntegerModel(BaseModel):
    int1 = models.IntegerField(default=1)
    int2 = models.IntegerField(default=2)
    int3 = models.IntegerField(default=3)

    class Meta:
        abstract = True


class IncludeFirstTwo(AbstractIntegerModel):
    include_columns = ("int1", "int2")


class PreventEditDeleteModel(BaseModel):
    """Test model for prevent_edit and prevent_delete via resolve_rows."""

    name = models.CharField(max_length=100)
    prevent_edit = models.BooleanField(default=False)
    prevent_delete = models.BooleanField(default=False)

    @classmethod
    def resolve_rows(cls, context: ResolveRowsContext) -> models.QuerySet[typing.Self]:
        qs = context.query
        if context.operation == "update":
            return qs.filter(prevent_edit=False)
        if context.operation == "delete":
            return qs.filter(prevent_delete=False)
        return qs


class ConditionalRowUpdatePermissionModel(BaseModel):
    """Test model for testing row update permission overrides.

    Used by RowUpdatePlaywrightTests to test permission-based access control:
    - test_authenticated_user_can_see_column_values: Tests authenticated users
      can see column values
    - test_none_mode_returns_404_on_row_updates_endpoint: Tests none mode 404
    - test_cannot_add_comment_when_permission_not_full: Tests comment restrictions

    Permission levels based on name:
    - Name starts with "No Permission": Denies all comment operations
    - Name starts with "Redacted": Denies all comment operations
    - Other names: Default behavior (authenticated users get full access)
    """

    name = models.CharField(max_length=100)

    def row_update_access_timeout(
        self,
        context: CommentPermissionContext[typing.Self],
    ) -> int:  # pragma: no cover
        # Get the row name from self since this is an instance method
        row_name = self.name if self else ""

        # "No Permission" mode: deny all comment operations
        if row_name.startswith("No Permission"):
            return 0

        # "Redacted" mode: deny all comment operations
        if row_name.startswith("Redacted"):
            return 0

        # Default: allow authenticated users for all comment operations
        if context.user is None:
            return 0
        return 86400  # 24 hours


class TestFileUploadModel(BaseModel):
    nullable_integer_field = models.IntegerField(default=10, null=True)
    file_field = models.FileField(upload_to="uploads/", null=True)


class BooleanFieldModel(BaseModel):
    """Test model for boolean field filtering."""

    boolean_field = models.BooleanField(default=False)


class IntegerFieldModel(BaseModel):
    """Test model for integer field filtering."""

    integer_field = models.IntegerField(default=0)
    optional_integer_field = models.IntegerField(default=0, null=True, blank=True)

    # Choice fields
    STATUS_CHOICES: ClassVar[list[tuple[int, str]]] = [
        (1, "Active"),
        (2, "Inactive"),
        (3, "Pending"),
    ]
    integer_choice_field = models.IntegerField(choices=STATUS_CHOICES, default=1)
    optional_integer_choice_field = models.IntegerField(
        choices=STATUS_CHOICES, default=1, null=True, blank=True
    )


class DecimalFieldModel(BaseModel):
    """Test model for decimal field filtering."""

    decimal_field = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    optional_decimal_field = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, null=True, blank=True
    )


class CharFieldModel(BaseModel):
    """Test model for character field filtering."""

    char_field = models.CharField(max_length=100, default="")
    text_field = models.TextField(default="")

    # Choice fields
    STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("pending", "Pending"),
    ]
    char_choice_field = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    optional_char_choice_field = models.CharField(  # noqa: DJ001
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        null=True,
        blank=True,
    )


class DatetimeFieldModel(BaseModel):
    """Test model for datetime field filtering."""

    datetime_field = models.DateTimeField(default=timezone.now)
    optional_datetime_field = models.DateTimeField(default=timezone.now, null=True, blank=True)
    date_field = models.DateField(default=timezone.now)


class CategoryModel(BaseModel):
    """Category model for foreign key relationships."""

    title_annotation = F("name")
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self) -> str:  # pragma: no cover
        """Return string representation of CategoryModel."""
        return self.name


class ForeignKeyModel(BaseModel):
    """Test model for foreign key field filtering."""

    category_field = models.ForeignKey(
        CategoryModel, on_delete=models.CASCADE, related_name="items"
    )
    optional_category_field = models.ForeignKey(
        CategoryModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="optional_items",
    )

    name = models.CharField(max_length=100, default="")


class SearchForFkTargetModel(BaseModel):
    """Target model for SearchForFkDestinationModel FK columns."""

    title_annotation = F("name")
    name = models.CharField(max_length=100)


class SearchForFkDestinationModel(BaseModel):
    """Model with two FK columns to SearchForFkTargetModel for testing @search decorator.

    Has one FK with @search decorator and one without, to test both code paths.
    """

    fk_with_search = models.ForeignKey(
        SearchForFkTargetModel,
        null=True,
        on_delete=models.RESTRICT,
        related_name="destinations_with_search",
    )
    fk_without_search = models.ForeignKey(
        SearchForFkTargetModel,
        null=True,
        on_delete=models.RESTRICT,
        related_name="destinations_without_search",
    )

    @search("fk_with_search")
    @classmethod
    def search_fk_with_search(
        cls, context: SearchContext[SearchForFkTargetModel]
    ) -> models.QuerySet[SearchForFkTargetModel]:
        """Search by name containing search text, ignoring base queryset."""
        # Do a fresh search instead of filtering context.queryset
        # because base search_text returns empty for non-numeric text
        return SearchForFkTargetModel.objects.filter(name__icontains=context.search_text).annotate(
            text=SearchForFkTargetModel.title_annotation
        )


class ProxyUser(User, _BaseModelMixin):
    """Proxy model for User that allows editing specific fields via table views."""

    # The tables machinery (get_by_public_id etc.) reads public_id_field to
    # resolve rows; User itself no longer declares it (assume "public_id"),
    # so the proxy pins it here.
    public_id_field: ClassVar[str] = "public_id"

    # Use Coalesce to fall back to username when first_name and last_name are empty
    # This prevents returning just " " for users with no name set
    title_annotation = Coalesce(
        # Try trimmed concatenated name first
        NullIf(
            Trim(Concat("first_name", Value(" "), "last_name")),
            Value(""),
        ),
        # Fall back to username
        "username",
        output_field=models.CharField(),
    )

    class Meta:
        proxy = True

    # Only allow editing these fields via table views
    include_columns: ClassVar[tuple[str, ...]] = (
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    @classmethod
    def search_text(
        cls, text: str
    ) -> models.QuerySet[WithAnnotations[typing.Self, AnnotatedTextDict]]:
        """Search users by ID, username, first_name, or last_name.

        When text is numeric, returns union of ID match (on top) and text matches
        (in alphabetical order by title_annotation).
        """
        if not text:
            return cls.objects.none()

        # Build text search filter
        text_filter = (
            models.Q(username__icontains=text)
            | models.Q(first_name__icontains=text)
            | models.Q(last_name__icontains=text)
        )

        if text.isnumeric():
            # Annotate with ordering: 0 for ID match, 1 for text matches
            # This ensures ID match appears first, then text matches alphabetically
            return (  # type: ignore[no-any-return] # Django manager on proxy model
                cls.objects.filter(models.Q(id=int(text)) | text_filter)
                .annotate(
                    annotated_text=cls.title_annotation,
                    sort_order=models.Case(
                        models.When(id=int(text), then=models.Value(0)),
                        default=models.Value(1),
                        output_field=models.IntegerField(),
                    ),
                )
                .order_by("sort_order", "first_name", "last_name")
            )

        # Non-numeric: just text matches in alphabetical order
        return cls.queryset_with_title().filter(text_filter).order_by("first_name", "last_name")

    @classmethod
    def resolve_columns(cls, context: ResolveColumnsContext) -> Sequence[str] | None:
        if context.operation == "create":
            return None
        columns = super().resolve_columns(context)
        if columns is None:
            return None
        if context.operation == "list":
            return [c for c in columns if c not in ("first_name", "last_name")]
        if context.operation == "update":
            return [c for c in columns if c != "username"]
        return columns


class SerializerTestModel(BaseModel):
    """Model for testing serializer functions. Fields ordered by type.

    This model is used exclusively for testing the serializer functions in
    serializers.py. Each field type is represented to ensure full coverage.
    """

    # CharField variants
    char_field = models.CharField(max_length=100, blank=True)
    char_choice_field = models.CharField(
        max_length=10,
        choices=[("a", "Option A"), ("b", "Option B")],
        blank=True,
    )
    char_with_default = models.CharField(max_length=50, default="default_value")

    # TextField
    text_field = models.TextField(blank=True)
    # TextField with validator for testing validator coverage
    text_with_validator = models.TextField(
        blank=True,
        validators=[MinLengthValidator(10)],
    )

    # IntegerField variants
    integer_field = models.IntegerField(null=True, blank=True)
    integer_choice_field = models.IntegerField(
        choices=[(1, "One"), (2, "Two")],
        null=True,
        blank=True,
    )
    integer_with_default = models.IntegerField(default=42)
    integer_with_callable_default = models.IntegerField(default=_default_integer_callable)

    # BooleanField
    boolean_field = models.BooleanField(default=False)

    # DecimalField
    decimal_field = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # DateTimeField
    datetime_field = models.DateTimeField(null=True, blank=True)

    # FileField
    file_field = models.FileField(upload_to="uploads/", null=True, blank=True)

    # ForeignKey (self-referential for simplicity)
    fk_field = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="related_items",
    )

    class Meta:
        app_label = "djangoapp"


class SlotDemoModel(BaseModel):
    """Demo model for testing custom ListPageSchema subclasses and list_rows overrides.

    Tests per-view schema extension (``SlotDemoListPageSchema.diff``),
    computed annotation columns (``int1 - int2`` as ``diff``), conditional
    column visibility, and frontend diff filter UI (None / Any positive / integer).
    """

    title_annotation = F("title")
    title = models.CharField(max_length=100, default="")
    int1 = models.IntegerField(default=0)
    int2 = models.IntegerField(default=0)


class PublicIdUuid7TestModel(BaseModel):
    """Test model with auto-generated UUID7 public ID.

    Validates that a model using ``public_id_field = "uuid_id"`` correctly
    generates, stores, and exposes a UUID7-based public ID via the base
    ``save_stuff`` auto-generation. No ``save_stuff`` override or field
    ``default=`` is needed — the ``public_id_generator`` (inherited from
    ``BaseModel``) handles it. Smoke tests verify ``id`` is excluded from
    ``include_columns``, and unit tests confirm creation and update flows.
    """

    public_id_field: ClassVar[str] = "uuid_id"
    uuid_id = models.CharField(max_length=36, unique=True, editable=False)
    title_annotation = F("name")
    name = models.CharField(max_length=100, default="")

    include_columns: ClassVar[tuple[str, ...]] = ("name",)


class PublicIdUuid7TestModel2(BaseModel):
    """Test model with editable slug-based public ID.

    The slug is auto-generated as UUID7 on creation via the base
    ``save_stuff`` auto-generation (no field ``default=`` needed).
    Users can edit it to custom values like ``john-smith``. The
    ``save_stuff`` override validates the slug format on updates using
    ``validate_public_id_format``. Playwright tests verify the URL changes
    after editing and that old URLs return 404.
    """

    public_id_field: ClassVar[str] = "slug"
    slug = models.CharField(
        max_length=100,
        unique=True,
        validators=[public_id_django_validator],
    )
    title_annotation = F("slug")
    name = models.CharField(max_length=100, default="")

    include_columns: ClassVar[tuple[str, ...]] = ("slug", "name")

    @classmethod
    def resolve_columns(cls, context: ResolveColumnsContext) -> Sequence[str] | None:
        columns = super().resolve_columns(context)
        if columns is None:
            return None
        if context.operation == "create":
            return tuple(c for c in columns if c != "slug")
        return columns

    def save_stuff(self, context: SaveContext[typing.Self]) -> None:
        if context.existing_row is not None:
            try:
                validate_public_id_format(self.slug)
            except ValueError as e:
                raise ValidationError({"slug": str(e)}) from e
        super().save_stuff(context)


class PublicIdSequenceTestModel1(BaseModel):
    """Test model with daily sequential public ID (e.g. ``2026-04-30-1``).

    Overrides ``public_id_generator`` to use ``generate_sequence_id("%Y-%m-%d-ID")``,
    so the base ``save_stuff`` auto-generates the ID on creation. No
    ``save_stuff`` override or field ``default=`` is needed.
    """

    public_id_field: ClassVar[str] = "seq_id"
    public_id_generator: ClassVar[Callable[[], Any]] = generate_sequence_id("%Y-%m-%d-ID")
    seq_id = models.CharField(max_length=100, unique=True, editable=False)
    title_annotation = F("name")
    name = models.CharField(max_length=100, default="")

    include_columns: ClassVar[tuple[str, ...]] = ("name",)


class PublicIdSequenceTestModel2(BaseModel):
    """Test model with monthly sequential public ID (e.g. ``2026-04-1``).

    Same as ``PublicIdSequenceTestModel1`` but with ``"%Y-%m-ID"`` format,
    so the counter resets monthly.
    """

    public_id_field: ClassVar[str] = "seq_id"
    public_id_generator: ClassVar[Callable[[], Any]] = generate_sequence_id("%Y-%m-ID")
    seq_id = models.CharField(max_length=100, unique=True, editable=False)
    title_annotation = F("name")
    name = models.CharField(max_length=100, default="")

    include_columns: ClassVar[tuple[str, ...]] = ("name",)


class PublicIdUuid7TestModel3(BaseModel):
    public_id_field: ClassVar[str] = "uuid_id"
    public_id_generator: ClassVar[Callable[[], Any]] = uuid.uuid4
    uuid_id = models.UUIDField(unique=True, editable=False)
    title_annotation = F("name")
    name = models.CharField(max_length=100, default="")

    include_columns: ClassVar[tuple[str, ...]] = ("name",)


class AllColumns(FooModel):
    """Example FooModel exercising every non-ref column kind."""

    char_field = models.CharField(max_length=10, default="foo")
    char_choice_field = models.CharField(
        max_length=10,
        choices=[("opt1", "Option 1"), ("opt2", "Option 2"), ("opt3", "Option 3")],
        default="opt2",
    )
    text_field = models.TextField(default="bar", blank=True)
    integer_field = models.IntegerField(default=1)
    boolean_field = models.BooleanField(default=True)
    decimal_field = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    datetime_field = models.DateTimeField(default=timezone.now)
    file_field = models.FileField(upload_to="uploads/", null=True, blank=True)

    class Meta:
        app_label = "djangoapp"
