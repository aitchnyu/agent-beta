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
from inertia.utils import optional
from ninja import (
    Query,
    Router,
)
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, field_validator

from djangoapp.models import BaseModel, BaseModelUpdateLog, user_profile
from djangoapp.models.base import User
from djangoapp.ninja_api import make_ninja_api
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
    # The manage detail link is keyed on public_id (never the integer pk — the
    # pk-leak rule). Non-BaseModel rows have no public id, so they get no link
    # (None here) and the /id/<public_id> route 404s for them.
    public_id: str | None
    # Cell values keyed by column name (builtins + user fields treated alike).
    # The frontend looks up each column's kind via ``columns`` to render: ``user``
    # cells are a {public_id, title} profile (pk-free), ``foreign_key`` cells are
    # an FkValue, decimal/datetime cells are strings, others are raw.
    values: dict[str, Any]


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
    # of producing a 422; the view clamps via _resolve_sort().
    sort: str = "-id"

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


# Sort options. id/-id work for every model; last_updated_at/-last_updated_at
# only for BaseModel subclasses (others have no such column).
_BASEMODEL_SORTS = {"id", "-id", "last_updated_at", "-last_updated_at"}
_GENERIC_SORTS = {"id", "-id"}


def _allowed_sorts(model_cls: type[models.Model]) -> set[str]:
    return _BASEMODEL_SORTS if issubclass(model_cls, BaseModel) else _GENERIC_SORTS


def _resolve_sort(model_cls: type[models.Model], sort: str) -> str:
    return sort if sort in _allowed_sorts(model_cls) else "-id"


manage_router = Router()


def _ourapp_models() -> list[type[models.Model]]:
    """Concrete models declared in the ourapp app, by name (BaseModel or not).

    Uses the Django app registry (not import scanning) so only installed,
    migrated models appear, in a stable alphabetical order. Sort/column logic
    branches on ``issubclass(m, BaseModel)`` per model.
    """
    cfg = apps.get_app_config("ourapp")
    return sorted(cfg.get_models(), key=lambda m: m.__name__)


def _model_or_404(model_name: str) -> type[models.Model]:
    """Resolve a URL segment to a ourapp model class, 404 on any miss."""
    for model_cls in _ourapp_models():
        if model_cls.__name__ == model_name:
            return model_cls
    raise Http404


def _columns(model_cls: type[models.Model]) -> list[models.Field[Any, Any]]:
    """Return a model's displayable columns: every concrete field except the auto ``id`` pk.

    BaseModel's built-ins (``public_id``/``created_by``/``created_at``/
    ``last_updated_at``/``last_updated_by``) are treated like any user-declared
    field and shown as columns; only the integer pk is hidden (and it must never
    reach the client).
    """
    return [
        f
        for f in model_cls._meta.fields  # noqa: SLF001 # _meta.fields is the stable field list
        if not f.primary_key
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


def _fk_value(related: BaseModel | None) -> FkValue | None:
    """Build the linked cell for a foreign-key column, or None when unset.

    Only ``BaseModel`` targets are linked (via ``get_absolute_url``); a foreign
    key to anything else (not ``User``, not a ``BaseModel``) has no management
    URL, so it renders as unset rather than raising — and ``str()`` is never
    called on it, so no pk can leak via a default ``Model.__str__``.
    """
    if related is None or not isinstance(related, BaseModel):
        return None
    return FkValue(public_id=related.public_id, url=related.get_absolute_url(), title=str(related))


def _cell_value(kind: FieldKind, instance: models.Model, field_name: str) -> object:
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
        return user_profile(cast("User | None", getattr(instance, field_name)))
    if kind == FieldKind.FOREIGN_KEY:
        return _fk_value(cast("BaseModel | None", getattr(instance, field_name)))
    msg = f"Unknown field kind: {kind}"
    raise ValueError(msg)


def _row_item(
    fields_with_kind: list[tuple[models.Field[Any, Any], FieldKind]],
    instance: models.Model,
) -> RowItem:
    """Build the pk-free serialised view of one row (shared by list + detail).

    Builtins are columns like any other, so they flow through ``values``; the
    separate ``public_id`` is only for the row-detail link (None for non-BaseModel
    rows, which have no public id and thus no detail page).
    """
    return RowItem(
        public_id=instance.public_id if isinstance(instance, BaseModel) else None,
        values={f.name: _cell_value(kind, instance, f.name) for f, kind in fields_with_kind},
    )


def _fields_with_kind(
    model_cls: type[models.Model],
) -> list[tuple[models.Field[Any, Any], FieldKind]]:
    """Pair each column with its kind (computed once, reused per row)."""
    return [(f, _field_kind(f)) for f in _columns(model_cls)]


def _select_related_fields(
    fields_with_kind: list[tuple[models.Field[Any, Any], FieldKind]],
) -> list[str]:
    """FK field names to select_related (avoids an N+1 per cell)."""
    return [
        f.name for f, kind in fields_with_kind if kind in {FieldKind.USER, FieldKind.FOREIGN_KEY}
    ]


def _row_logs(model_cls: type[BaseModel], pk: int) -> list[dict[str, Any]]:
    """Return one row's audit entries as JSON-safe dicts (newest-first via -performed_at).

    Takes the integer pk, not the instance — that's all the audit query needs, and
    capturing the pk (not the whole row) in the lazy prop's lambda is all that
    must outlive the request. Called from inside a lazy Inertia prop
    (``optional(lambda: …)``), so it only runs on the ``only:["logs"]`` partial
    reload — never on first page load.
    """
    return [
        log.to_entry_item().model_dump(mode="json")
        for log in BaseModelUpdateLog.objects.select_related("performed_by").filter(
            model=model_cls.log_model_name(), model_pk=pk
        )
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

    sort = _resolve_sort(model_cls, filters.sort)
    qs = (
        cast("Any", model_cls)
        .objects.select_related(*_select_related_fields(fields_with_kind))
        .order_by(sort, "-id")
    )
    paginator = Paginator(qs, filters.per_page, orphans=5)
    page_obj = paginator.get_page(filters.page)

    column_defs = [_column_def(f) for f, _ in fields_with_kind]
    rows = [_row_item(fields_with_kind, instance) for instance in page_obj.object_list]

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
    """Show a single row by its public_id (BaseModel only); logs load lazily.

    ``logs`` is an Inertia lazy prop: on a full page load it is dropped entirely.
    """
    require_superuser(request)
    model_cls = _model_or_404(model_name)
    if not issubclass(model_cls, BaseModel):
        # Non-BaseModel rows have no public_id, so no detail page.
        raise Http404
    fields_with_kind = _fields_with_kind(model_cls)
    model = cast("Any", model_cls)
    try:
        instance = model.objects.select_related(*_select_related_fields(fields_with_kind)).get(
            public_id=public_id
        )
    except model.DoesNotExist as exc:
        raise Http404 from exc

    column_defs = [_column_def(f) for f, _ in fields_with_kind]
    row = _row_item(fields_with_kind, instance)
    core = RowDetailProps(
        model_name=model_cls.__name__,
        public_id=cast("str", row.public_id),
        columns=column_defs,
        values=row.values,
    ).model_dump()

    # ``logs`` is a sibling top-level prop, deliberately NOT nested inside the
    # "props" wrapper: inertia's lazy machinery (IgnoreOnFirstLoadProp deletion,
    # and the only:["logs"] partial filter) keys off top-level prop names, so a
    # nested logs would be invisible to it (evaluated on every load, and the
    # partial would return empty). ``optional()`` drops it on first load (no
    # audit query); the client requests it on mount via router.reload(only:["logs"]).
    return InertiaResponse(
        request,
        "RowDetail",
        {
            "props": core,
            "logs": optional(lambda: _row_logs(model_cls, instance.pk)),
        },
    )


manage_api = make_ninja_api("manage", manage_router)


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
