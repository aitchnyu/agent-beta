"""Superuser-only read views for apps/tables.

Apps live in one flat namespace, so every path is keyed by
``app_name`` alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from inertia import InertiaResponse
from ninja import (
    NinjaAPI,
    Query,
    Router,
)
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, field_validator

from djangoapp.models import (
    Application,
    ApplicationTable,
    ApplicationTableColumn,
    BaseTable,
    ColumnType,
    UserProfile,
)
from djangoapp.views import host_template_data

if TYPE_CHECKING:
    from datetime import datetime

    from djangoapp.models.base import User


def _require_superuser(request: HttpRequest) -> None:
    """Gate the view to a superuser, else 404 (never 403)."""
    viewer = request.user
    if not (viewer.is_authenticated and viewer.is_superuser):
        raise Http404


class AppItem(PydanticBaseModel):
    name: str


class AppListProps(PydanticBaseModel):
    apps: list[AppItem]


class TableItem(PydanticBaseModel):
    name: str
    row_count: int


class ManageProps(PydanticBaseModel):
    app_name: str
    tables: list[TableItem]


class FkTarget(PydanticBaseModel):
    """The table a foreign-key column points at (so the frontend can link to a row)."""

    app_name: str
    table_name: str


class RowListColumnDef(PydanticBaseModel):
    name: str
    type: ColumnType
    has_choices: bool
    # Set only for foreign_key columns: the target table, so the frontend can
    # link a cell to the referenced row's detail page.
    fk_target: FkTarget | None = None


class RowListItem(PydanticBaseModel):
    public_id: str
    # Cell values keyed by column name. The frontend looks up each column's
    # type via ``columns`` to render; ``user`` cells are a {public_id, title}
    # profile (pk-free), decimal/datetime cells are strings, others are raw.
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


class RowListProps(PydanticBaseModel):
    app_name: str
    table_name: str
    columns: list[RowListColumnDef]
    rows: list[RowListItem]
    pagination: RowListPagination
    filters: RowListFilters


class RowDetailProps(PydanticBaseModel):
    app_name: str
    table_name: str
    public_id: str
    columns: list[RowListColumnDef]
    values: dict[str, Any]
    created_by: UserProfile | None
    created_at: str
    edited_at: str


def _get_application_table_or_404(app_name: str, table_name: str) -> ApplicationTable:
    """Resolve (app, table) to an ApplicationTable, 404 on any miss.

    A single relation-spanning query (with ``select_related`` so the views can
    read ``table.application`` without extra hits). Follows the project access
    rule: a missing resource raises 404 (never reveals whether the parent
    exists).
    """
    try:
        return ApplicationTable.objects.select_related("application").get(
            application__name=app_name,
            name=table_name,
        )
    except ApplicationTable.DoesNotExist as exc:
        raise Http404 from exc


def _user_profile(user: User | None) -> UserProfile | None:
    """Build a pk-free profile for a row's _created_by, or None."""
    if user is None:
        return None
    return UserProfile(public_id=user.public_id, title=user.display_name)


def _cell_value(col_type: ColumnType, raw: object) -> object:
    """Return the client-facing value for one cell.

    ``user`` cells become a pk-free profile (or None); decimal/datetime cells
    are serialised to strings (precision- and JSON-safe); every other type
    passes through as-is for the frontend to cast by column type.
    """
    if col_type in {ColumnType.CHAR, ColumnType.TEXT, ColumnType.BOOLEAN, ColumnType.INTEGER}:
        return raw
    if col_type == ColumnType.DECIMAL:
        return str(raw) if raw is not None else None
    if col_type == ColumnType.DATETIME:
        return cast("datetime", raw).isoformat() if raw is not None else None
    if col_type == ColumnType.USER:
        return _user_profile(cast("User | None", raw))
    if col_type == ColumnType.FOREIGN_KEY:
        # raw is the related row (a BaseTable); the frontend links to it via
        # the column's fk_target table + this public_id. None = nullable, unset.
        return (
            {"public_id": cast("BaseTable", raw)._public_id}  # noqa: SLF001 # BaseTable built-in column
            if raw is not None
            else None
        )
    msg = f"Unknown column type: {col_type}"
    raise ValueError(msg)


def _column_def(c: ApplicationTableColumn) -> RowListColumnDef:
    """Build the client-facing column def, resolving a foreign_key target table."""
    fk_target = None
    if ColumnType(c.type) == ColumnType.FOREIGN_KEY and c.fk_target_table is not None:
        target = c.fk_target_table
        fk_target = FkTarget(
            app_name=target.application.name,
            table_name=target.name,
        )
    return RowListColumnDef(
        name=c.name, type=ColumnType(c.type), has_choices=bool(c.char_choices), fk_target=fk_target
    )


def _row_values(columns: list[ApplicationTableColumn], instance: BaseTable) -> dict[str, Any]:
    """Build the column-name -> cell-value map for a dynamic-model row."""
    return {c.name: _cell_value(ColumnType(c.type), getattr(instance, c.name)) for c in columns}


def _row_item(columns: list[ApplicationTableColumn], instance: BaseTable) -> RowListItem:
    """Build the pk-free serialised view of one row (shared by list + detail)."""
    return RowListItem(
        public_id=instance._public_id,  # noqa: SLF001 # BaseTable built-in column
        values=_row_values(columns, instance),
        created_by=_user_profile(instance._created_by),  # noqa: SLF001 # BaseTable built-in column
        created_at=instance._created_at.isoformat(),  # noqa: SLF001 # BaseTable built-in column
        edited_at=instance._edited_at.isoformat(),  # noqa: SLF001 # BaseTable built-in column
    )


_ALLOWED_SORTS = {"created_at", "edited_at"}

manage_router = Router()


@manage_router.get("/apps", response=None)
def apps_page(request: HttpRequest) -> HttpResponse:
    """List every application."""
    _require_superuser(request)
    items = [AppItem(name=a.name) for a in Application.objects.all().order_by("name")]
    props = AppListProps(apps=items)
    return InertiaResponse(
        request, "AppList", {"props": props.model_dump()}, template_data=host_template_data()
    )


@manage_router.get("/apps/{app_name}", response=None)
def manage_page(request: HttpRequest, app_name: str) -> HttpResponse:
    """List an app's tables with live row counts (read from dynamic models)."""
    _require_superuser(request)
    app = Application.app_or_404(app_name)
    table_rows: list[TableItem] = []
    for table in app.tables.all().order_by("name"):
        # Row counts come from the generated model bound to the live table.
        model = cast("Any", table.as_model())
        table_rows.append(TableItem(name=table.name, row_count=model.objects.count()))
    props = ManageProps(
        app_name=app.name,
        tables=table_rows,
    )
    return InertiaResponse(
        request, "Manage", {"props": props.model_dump()}, template_data=host_template_data()
    )


@manage_router.get("/apps/{app_name}/{table_name}/list", response=None)
def row_list_page(
    request: HttpRequest,
    app_name: str,
    table_name: str,
    filters: Query[RowListFilters],
) -> HttpResponse:
    """List rows of a table's dynamic model, paginated and sorted (newest first)."""
    _require_superuser(request)
    table = _get_application_table_or_404(app_name, table_name)
    columns = table.ordered_columns()

    sort = filters.sort if filters.sort in _ALLOWED_SORTS else "created_at"

    model = cast("Any", table.as_model())
    order_field = "_created_at" if sort == "created_at" else "_edited_at"
    qs = model.objects.order_by(f"-{order_field}", "-_public_id")
    paginator = Paginator(qs, filters.per_page, orphans=5)
    page_obj = paginator.get_page(filters.page)

    column_defs = [_column_def(c) for c in columns]
    # TODO make this an ApplicationTable method along with columns?
    rows = [_row_item(columns, instance) for instance in page_obj.object_list]

    props = RowListProps(
        app_name=table.application.name,
        table_name=table.name,
        columns=column_defs,
        rows=rows,
        pagination=RowListPagination(
            page=page_obj.number,
            total_pages=paginator.num_pages,
            total_count=paginator.count,
        ),
        filters=RowListFilters(per_page=filters.per_page, page=page_obj.number, sort=sort),
    )
    return InertiaResponse(
        request, "TableRows", {"props": props.model_dump()}, template_data=host_template_data()
    )


@manage_router.get("/apps/{app_name}/{table_name}/id/{public_id}", response=None)
def row_detail_page(
    request: HttpRequest,
    app_name: str,
    table_name: str,
    public_id: str,
) -> HttpResponse:
    """Show a single row by its _public_id, with all columns serialised."""
    _require_superuser(request)
    table = _get_application_table_or_404(app_name, table_name)
    columns = table.ordered_columns()
    model = cast("Any", table.as_model())
    try:
        instance = model.objects.get(_public_id=public_id)
    except model.DoesNotExist as exc:
        raise Http404 from exc

    column_defs = [_column_def(c) for c in columns]
    row = _row_item(columns, instance)
    props = RowDetailProps(
        app_name=table.application.name,
        table_name=table.name,
        public_id=row.public_id,
        columns=column_defs,
        values=row.values,
        created_by=row.created_by,
        created_at=row.created_at,
        edited_at=row.edited_at,
    )
    return InertiaResponse(
        request, "RowDetail", {"props": props.model_dump()}, template_data=host_template_data()
    )


manage_api = NinjaAPI(urls_namespace="manage-http")
manage_api.add_router("manage", manage_router)


# Re-export for type-checkers that scan module members.
__all__ = [
    "AppItem",
    "AppListProps",
    "FkTarget",
    "ManageProps",
    "RowDetailProps",
    "RowListColumnDef",
    "RowListFilters",
    "RowListItem",
    "RowListPagination",
    "RowListProps",
    "TableItem",
    "apps_page",
    "manage_api",
    "manage_page",
    "manage_router",
    "row_detail_page",
    "row_list_page",
]
