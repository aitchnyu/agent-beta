"""Superuser-only models-management pages.

Lists the concrete ``BaseModel`` subclasses defined in the ``ourapp`` app (each
with its class docstring) and browse their rows. Replaces the old app/table
management views: there are no ``Application``/``ApplicationTable`` rows any
more — models are real Django models discovered from the app registry, routed
by class ``__name__``.

Mounted under ``/manage`` (separate from any app URL so a model name can never
collide with a path literal). Every route requires a superuser; anyone else
gets a 404.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

from django.apps import apps
from django.core.paginator import Paginator
from django.db import models
from django.http import Http404, HttpRequest, HttpResponse
from inertia import InertiaResponse
from ninja import (
    NinjaAPI,
    Query,
    Router,
)
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, field_validator

from djangoapp.models import BaseModel, UserProfile
from djangoapp.models.base import User
from djangoapp.views import require_superuser

if TYPE_CHECKING:
    from datetime import datetime


class FieldKind(StrEnum):
    """Client-facing kind for a model field, used by the frontend to render a cell.

    ``user`` is a ForeignKey to the project
    ``User`` (cell = a pk-free profile, linked to the profile page); every other
    ForeignKey is ``foreign_key`` (cell = the referenced row, linked via its
    ``get_absolute_url()``).
    """

    CHAR = "char"
    TEXT = "text"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DECIMAL = "decimal"
    DATETIME = "datetime"
    USER = "user"
    FOREIGN_KEY = "foreign_key"


class ModelItem(PydanticBaseModel):
    name: str
    docstring: str
    row_count: int


class ModelListProps(PydanticBaseModel):
    models: list[ModelItem]


class ColumnDef(PydanticBaseModel):
    name: str
    type: FieldKind
    has_choices: bool


class FkValue(PydanticBaseModel):
    """A foreign-key cell: the referenced row, linked via get_absolute_url()."""

    public_id: str
    url: str
    title: str


class RowItem(PydanticBaseModel):
    public_id: str
    # Cell values keyed by column name. The frontend looks up each column's
    # kind via ``columns`` to render; ``user`` cells are a {public_id, title}
    # profile (pk-free), ``foreign_key`` cells are an FkValue, decimal/datetime
    # cells are strings, others are raw.
    values: dict[str, Any]
    created_by: UserProfile | None
    created_at: str
    edited_at: str


class RowListPagination(PydanticBaseModel):
    page: int
    total_pages: int
    total_count: int


class RowListFilters(PydanticBaseModel):
    # Fixed page sizes (matches the frontend's PER_PAGE_OPTIONS); any other
    # value is rejected by Ninja with 422 rather than silently clamped. Declared
    # as int + an after-validator (not Literal[25,50,100]) because query params
    # arrive as strings and pydantic will not coerce "25" against an int Literal,
    # which would 422 every pagination link.
    per_page: int = 25
    page: int = Field(default=1, ge=1)
    # str (not Literal) so an unknown sort falls back to the default instead
    # of producing a 422; the view clamps to one of _ALLOWED_SORTS.
    sort: str = "created_at"

    @field_validator("per_page", mode="after")
    @classmethod
    def _fixed_per_page(cls, v: int) -> int:
        allowed = {25, 50, 100}
        if v not in allowed:
            msg = f"per_page must be one of {sorted(allowed)}."
            raise ValueError(msg)
        return v


class ModelRowsProps(PydanticBaseModel):
    model_name: str
    columns: list[ColumnDef]
    rows: list[RowItem]
    pagination: RowListPagination
    filters: RowListFilters


class RowDetailProps(PydanticBaseModel):
    model_name: str
    public_id: str
    columns: list[ColumnDef]
    values: dict[str, Any]
    created_by: UserProfile | None
    created_at: str
    edited_at: str


# Only the BaseModel built-in timestamps are sortable (newest first).
_ALLOWED_SORTS = {"created_at", "edited_at"}

manage_router = Router()


def _ourapp_models() -> list[type[BaseModel]]:
    """Concrete BaseModel subclasses declared in the ourapp app, by name.

    Uses the Django app registry (not import scanning) so only installed,
    migrated models appear, in a stable alphabetical order.
    """
    cfg = apps.get_app_config("ourapp")
    models_list = [m for m in cfg.get_models() if issubclass(m, BaseModel)]
    return sorted(models_list, key=lambda m: m.__name__)


def _model_or_404(model_name: str) -> type[BaseModel]:
    """Resolve a URL segment to a ourapp model class, 404 on any miss."""
    for model_cls in _ourapp_models():
        if model_cls.__name__ == model_name:
            return model_cls
    raise Http404


def _user_fields(model_cls: type[BaseModel]) -> list[models.Field[Any, Any]]:
    """Return a model's own columns (its declared fields).

    BaseModel's built-ins are underscore-prefixed (``_public_id`` etc.) and the
    auto ``id`` pk is the primary key — both excluded so only the fields the
    model declares for itself show as columns.
    """
    return [
        f
        for f in model_cls._meta.fields  # noqa: SLF001 # _meta.fields is the stable field list
        if not f.name.startswith("_") and not f.primary_key
    ]


# Django field class -> client-facing kind, in isinstance order (subclass-aware:
# TextField before CharField; IntegerField last so its subclasses resolve first).
# ForeignKeys are handled in _field_kind (their kind depends on the related model).
_FIELD_KIND_BY_CLASS: list[tuple[type[models.Field[Any, Any]], FieldKind]] = [
    (models.TextField, FieldKind.TEXT),
    (models.CharField, FieldKind.CHAR),
    (models.BooleanField, FieldKind.BOOLEAN),
    (models.DecimalField, FieldKind.DECIMAL),
    (models.DateTimeField, FieldKind.DATETIME),
    (models.IntegerField, FieldKind.INTEGER),
]


def _field_kind(field: models.Field[Any, Any]) -> FieldKind:
    """Map a Django field to its client-facing kind.

    Subclasses resolve to their base (EmailField/SlugField -> char,
    PositiveIntegerField -> integer). A ForeignKey to the project ``User`` is
    ``user``; any other ForeignKey is ``foreign_key``. Unmapped scalars
    (e.g. FloatField) render as their string form via ``char``.
    """
    if isinstance(field, models.ForeignKey):
        return FieldKind.USER if field.related_model is User else FieldKind.FOREIGN_KEY
    for cls, kind in _FIELD_KIND_BY_CLASS:
        if isinstance(field, cls):
            return kind
    return FieldKind.CHAR


def _column_def(field: models.Field[Any, Any]) -> ColumnDef:
    return ColumnDef(
        name=field.name,
        type=_field_kind(field),
        has_choices=bool(getattr(field, "choices", None)),
    )


def _user_profile(user: User | None) -> UserProfile | None:
    """Build a pk-free profile for a row's _created_by, or None."""
    if user is None:
        return None
    return UserProfile(public_id=user.public_id, title=user.display_name)


def _fk_value(related: BaseModel | None) -> FkValue | None:
    """Build the linked cell for a foreign-key column, or None when unset.

    Only ``BaseModel`` targets are linked (via ``get_absolute_url``); a foreign
    key to anything else (not ``User``, not a ``BaseModel``) has no management
    URL, so it renders as unset rather than raising — and ``str()`` is never
    called on it, so no pk can leak via a default ``Model.__str__``.
    """
    if related is None or not isinstance(related, BaseModel):
        return None
    return FkValue(public_id=related._public_id, url=related.get_absolute_url(), title=str(related))  # noqa: SLF001 # BaseModel built-in column; __str__ is pk-free


def _cell_value(kind: FieldKind, instance: BaseModel, field_name: str) -> object:
    """Return the client-facing value for one cell.

    ``user`` cells become a pk-free profile (or None); ``foreign_key`` cells
    become an :class:`FkValue` (or None); decimal/datetime cells are serialised
    to strings (precision- and JSON-safe); every other kind passes through
    as-is for the frontend to cast by column type.
    """
    if kind in {FieldKind.CHAR, FieldKind.TEXT, FieldKind.BOOLEAN, FieldKind.INTEGER}:
        value = getattr(instance, field_name)
        # Coerce anything not JSON-safe to a string. Char/Text/Integer/Boolean
        # are primitives; this only affects fields that fell through to char
        # (FloatField/DateField/UUIDField/DurationField/BinaryField), avoiding a
        # 500 on the non-serialisable ones (timedelta/bytes).
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)
    if kind == FieldKind.DECIMAL:
        raw = getattr(instance, field_name)
        return str(raw) if raw is not None else None
    if kind == FieldKind.DATETIME:
        raw = getattr(instance, field_name)
        return cast("datetime", raw).isoformat() if raw is not None else None
    if kind == FieldKind.USER:
        return _user_profile(cast("User | None", getattr(instance, field_name)))
    if kind == FieldKind.FOREIGN_KEY:
        return _fk_value(cast("BaseModel | None", getattr(instance, field_name)))
    msg = f"Unknown field kind: {kind}"
    raise ValueError(msg)


def _row_item(
    fields_with_kind: list[tuple[models.Field[Any, Any], FieldKind]],
    instance: BaseModel,
) -> RowItem:
    """Build the pk-free serialised view of one row (shared by list + detail)."""
    return RowItem(
        public_id=instance._public_id,  # noqa: SLF001 # BaseModel built-in column
        values={f.name: _cell_value(kind, instance, f.name) for f, kind in fields_with_kind},
        created_by=_user_profile(instance._created_by),  # noqa: SLF001 # BaseModel built-in column
        created_at=instance._created_at.isoformat(),  # noqa: SLF001 # BaseModel built-in column
        edited_at=instance._edited_at.isoformat(),  # noqa: SLF001 # BaseModel built-in column
    )


def _fields_with_kind(model_cls: type[BaseModel]) -> list[tuple[models.Field[Any, Any], FieldKind]]:
    """Pair each user field with its kind (computed once, reused per row)."""
    return [(f, _field_kind(f)) for f in _user_fields(model_cls)]


def _select_related_fields(
    fields_with_kind: list[tuple[models.Field[Any, Any], FieldKind]],
) -> list[str]:
    """FK field names to select_related (avoids an N+1 per cell)."""
    return [
        f.name for f, kind in fields_with_kind if kind in {FieldKind.USER, FieldKind.FOREIGN_KEY}
    ]


@manage_router.get("/models", response=None)
def models_page(request: HttpRequest) -> HttpResponse:
    """List every ourapp model with its docstring and live row count."""
    require_superuser(request)
    items = [
        ModelItem(
            name=m.__name__,
            docstring=(m.__doc__ or "").strip(),
            row_count=cast("Any", m).objects.count(),
        )
        for m in _ourapp_models()
    ]
    props = ModelListProps(models=items)
    return InertiaResponse(request, "ModelList", {"props": props.model_dump()})


@manage_router.get("/models/{model_name}/list", response=None)
def model_rows_page(
    request: HttpRequest,
    model_name: str,
    filters: Query[RowListFilters],
) -> HttpResponse:
    """List rows of a model, paginated and sorted newest-first (built-ins only)."""
    require_superuser(request)
    model_cls = _model_or_404(model_name)
    fields_with_kind = _fields_with_kind(model_cls)

    sort = filters.sort if filters.sort in _ALLOWED_SORTS else "created_at"
    order_field = "_created_at" if sort == "created_at" else "_edited_at"
    qs = (
        cast("Any", model_cls)
        .objects.select_related(
            "_created_by",
            *_select_related_fields(fields_with_kind),
        )
        .order_by(f"-{order_field}", "-_public_id")
    )
    paginator = Paginator(qs, filters.per_page, orphans=5)
    page_obj = paginator.get_page(filters.page)

    column_defs = [_column_def(f) for f, _ in fields_with_kind]
    rows = [
        _row_item(fields_with_kind, cast("BaseModel", instance))
        for instance in page_obj.object_list
    ]

    props = ModelRowsProps(
        model_name=model_cls.__name__,
        columns=column_defs,
        rows=rows,
        pagination=RowListPagination(
            page=page_obj.number,
            total_pages=paginator.num_pages,
            total_count=paginator.count,
        ),
        filters=RowListFilters(per_page=filters.per_page, page=page_obj.number, sort=sort),
    )
    return InertiaResponse(request, "ModelRows", {"props": props.model_dump()})


@manage_router.get("/models/{model_name}/id/{public_id}", response=None)
def row_detail_page(
    request: HttpRequest,
    model_name: str,
    public_id: str,
) -> HttpResponse:
    """Show a single row by its _public_id, with all columns serialised."""
    require_superuser(request)
    model_cls = _model_or_404(model_name)
    fields_with_kind = _fields_with_kind(model_cls)
    model = cast("Any", model_cls)
    try:
        instance = model.objects.select_related(
            "_created_by",
            *_select_related_fields(fields_with_kind),
        ).get(_public_id=public_id)
    except model.DoesNotExist as exc:
        raise Http404 from exc

    column_defs = [_column_def(f) for f, _ in fields_with_kind]
    row = _row_item(fields_with_kind, instance)
    props = RowDetailProps(
        model_name=model_cls.__name__,
        public_id=row.public_id,
        columns=column_defs,
        values=row.values,
        created_by=row.created_by,
        created_at=row.created_at,
        edited_at=row.edited_at,
    )
    return InertiaResponse(request, "RowDetail", {"props": props.model_dump()})


manage_api = NinjaAPI(urls_namespace="manage-http")
manage_api.add_router("manage", manage_router)


# Re-export for type-checkers that scan module members.
__all__ = [
    "ColumnDef",
    "FieldKind",
    "FkValue",
    "ModelItem",
    "ModelListProps",
    "ModelRowsProps",
    "RowDetailProps",
    "RowItem",
    "RowListFilters",
    "RowListPagination",
    "manage_api",
    "manage_router",
    "model_rows_page",
    "models_page",
    "row_detail_page",
]

# Kept honest against BaseModel.get_absolute_url() in djangoapp/models/base.py:
# the detail route (model_rows_page/row_detail_page) must equal
# MANAGE_MODELS_URL_PREFIX + "/<model>/id/<id>".
