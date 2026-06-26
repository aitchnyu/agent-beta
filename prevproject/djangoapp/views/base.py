import abc
import functools
import inspect
from dataclasses import dataclass
from typing import Any, Literal, cast

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.paginator import Paginator
from django.db import models
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.urls import URLPattern, path, register_converter, reverse
from inertia import InertiaResponse
from ninja import NinjaAPI, Router
from ninja.constants import NOT_SET
from prison import dumps, loads
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError

from djangoapp import serializers
from djangoapp.errors import ApiError, register_api_error_handlers
from djangoapp.filters import (
    ForeignKeyChoiceFilter,
    NullFilter,
    RowUpdateFilter,
    UnionFilter,
)
from djangoapp.models.base import (
    RowUpdate,
    RowUpdateUserNotification,
    SaveContext,
    User,
    UserWithPublicId,
    _BaseModelMixin,
    annotate_fk_titles,
)
from djangoapp.responses import (
    BaseContent,
    BaseFieldSchema,
    CommentResponse,
    DeleteNotificationsResponse,
    DeleteRowResponse,
    InputSchema,
    NotificationItem,
    NotificationListResponse,
    NullContent,
    RowUpdateListResponse,
    RowUpdateResponse,
    SearchRowItem,
    SearchRowsResponse,
    ThSchema,
    UserSchema,
)
from djangoapp.utils import sanitize_html

JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]


class _AliasModel(PydanticBaseModel):
    model_config = ConfigDict(
        populate_by_name=True, serialize_by_alias=True, validate_by_alias=True
    )


# ------------------ Module-level singletons for tables ---------------------
# These are populated by add_views() and used by serializers and views.
TABLES_PREFIX: str = ""
TABLES_VIEW_DICT: dict[str, BaseView] = {}
TABLES_MODELS_TO_VIEWS: dict[type[_BaseModelMixin], str] = {}
TABLES_USER_VIEW: BaseView | None = None

ninja_api = NinjaAPI(
    urls_namespace="tables-api",
    title="Tables API",
)
register_api_error_handlers(ninja_api)


class NotificationsDeleteIn(PydanticBaseModel):
    notification_ids: list[int]


class NotificationsClearIn(PydanticBaseModel):
    viewname: str | None = None


@ninja_api.get("/_search-users")
def _search_users_api(request: HttpRequest, q: str = "") -> SearchRowsResponse:  # noqa: ARG001 # Ninja requires request parameter
    if TABLES_USER_VIEW is None:
        raise ApiError(404, "User search is not available")
    qs = TABLES_USER_VIEW.model.search_text(q)
    return SearchRowsResponse(
        rows=[SearchRowItem(id=obj.public_id, title=str(obj.annotated_text)) for obj in qs]
    )


@ninja_api.post("/notifications/delete")
def _notifications_delete_api(
    request: HttpRequest, body: NotificationsDeleteIn
) -> DeleteNotificationsResponse:
    user = user_or_404(request)
    deleted, _ = RowUpdateUserNotification.objects.filter(
        id__in=body.notification_ids, user=user
    ).delete()
    return DeleteNotificationsResponse(deleted_count=deleted)


@ninja_api.post("/notifications/clear")
def _notifications_clear_api(
    request: HttpRequest, body: NotificationsClearIn
) -> DeleteNotificationsResponse:
    user = user_or_404(request)
    qs = RowUpdateUserNotification.objects.filter(user=user)
    if body.viewname:
        modelname = _viewname_to_modelname(body.viewname)
        if modelname:
            qs = qs.filter(modelname=modelname)
    deleted, _ = qs.delete()
    return DeleteNotificationsResponse(deleted_count=deleted)


def _notifications_page(request: HttpRequest) -> InertiaResponse:
    user_schema = get_authenticated_user_as_schema(request)
    if not user_schema:
        raise Http404

    assert request.user.is_authenticated
    user = request.user

    qs = RowUpdateUserNotification.objects.filter(user=user).order_by("-id")

    viewname_filter = request.GET.get("viewname", "")
    if viewname_filter:
        modelname = _viewname_to_modelname(viewname_filter)
        if modelname:
            qs = qs.filter(modelname=modelname)
        else:
            qs = qs.none()

    total_count = qs.count()

    viewname_counts_qs = (
        RowUpdateUserNotification.objects.filter(user=user)
        .values("modelname")
        .annotate(count=models.Count("id"))
    )
    viewname_counts: dict[str, int] = {}
    for entry in viewname_counts_qs:
        mn = entry["modelname"]
        vn = _modelname_to_viewname(mn)
        if vn:
            viewname_counts[vn] = entry["count"]

    per_page = 50
    page = int(request.GET.get("page", "1"))
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page)

    notifications = []
    for notification in page_obj:
        vn = _modelname_to_viewname(notification.modelname)
        if not vn:
            continue

        notifications.append(
            NotificationItem(
                id=str(notification.id),
                viewname=vn,
                row_public_id=notification.row_public_id,
                row_update=notification.content,
            )
        )

    response = NotificationListResponse(
        notifications=notifications,
        viewname_counts=viewname_counts,
        total_count=total_count,
        current_page=page,
        total_pages=paginator.num_pages,
    )

    return InertiaResponse(
        request,
        "Notifications",
        {
            "props": {
                "user": user_schema.model_dump() if user_schema else None,
                "notifications": [n.model_dump() for n in response.notifications],
                "viewname_counts": response.viewname_counts,
                "total_count": response.total_count,
                "current_page": response.current_page,
                "total_pages": response.total_pages,
                "active_viewname": viewname_filter or None,
            },
        },
    )


def _viewname_to_modelname(viewname: str) -> str | None:
    for model_cls, vn in TABLES_MODELS_TO_VIEWS.items():
        if vn == viewname:
            return model_cls.modelname()
    return None


def _modelname_to_viewname(modelname: str) -> str | None:
    for model_cls, vn in TABLES_MODELS_TO_VIEWS.items():
        if model_cls.modelname() == modelname:
            return vn
    return None


def _debug_view(request: HttpRequest) -> HttpResponse:
    """Debug view to list all table URLs.

    This view displays all registered table URLs and user info.
    """
    if not settings.DEBUG:
        return HttpResponse("Debug mode is off", status=403)

    # Get all view names from the module-level TABLES_VIEW_DICT
    # list(TABLES_VIEW_DICT.keys())
    table_urls = [
        TableUrlSchema(
            name=view_name,
            url=reverse(
                f"tables-http:list-{view_name}",
                kwargs={"params": view.list_page_schema().model_dump(exclude_none=True)},
            ),
        )
        for view_name, view in TABLES_VIEW_DICT.items()
    ]

    return InertiaResponse(
        request,
        "Debug",
        {
            "props": DebugViewSchema(
                table_urls=table_urls,
                user=get_authenticated_user_as_schema(request),
            ).model_dump()
        },
    )


def mount_prefix(path_prefix: str, owner: type) -> str:
    """Validate a view's ``path_prefix`` and return it without slashes.

    ``path_prefix`` backs both link building (``{path_prefix}/api/...`` ->
    ``/articles/api/...``) and URL mounting, so it must be a single
    leading-slash segment. A missing leading slash, a trailing slash, or
    extra segments would silently produce wrong URLs, hence the asserts.

    Args:
        path_prefix: The class's ``path_prefix`` (e.g. ``"/articles"``).
        owner: The view class, used in assertion messages.

    Returns:
        The prefix with slashes stripped (e.g. ``"articles"``).

    """
    assert path_prefix.startswith("/"), (
        f"{owner.__name__}.path_prefix must start with '/', got {path_prefix!r}"
    )
    assert not path_prefix.endswith("/"), (
        f"{owner.__name__}.path_prefix must not end with '/', got {path_prefix!r}"
    )
    prefix = path_prefix.strip("/")
    assert prefix, f"{owner.__name__}.path_prefix must not be empty"
    assert "/" not in prefix, (
        f"{owner.__name__}.path_prefix must be a single path segment, got {path_prefix!r}"
    )
    return prefix


def add_views(
    url_prefix: str,
    views: list[type[BaseView]],  # BaseView defined later in this file
) -> list[URLPattern]:
    """Create URL patterns for the given views under the specified prefix.

    This function populates the module-level TABLES_VIEW_DICT and TABLES_MODELS_TO_VIEWS
    singletons, and returns URL patterns that can be included in the main URLconf.

    Args:
        url_prefix: The URL prefix (e.g., "/tables"). Must start with '/'
            and contain only alphanumeric chars after.

        views: List of BaseView subclasses to register.

    Returns:
        A list of URLPatterns for HTTP page endpoints.
        Ninja API endpoints are registered on the module-level ``ninja_api`` directly.

    Raises:
        ValueError: If url_prefix is invalid or viewnames conflict.

    """
    global TABLES_PREFIX, TABLES_VIEW_DICT, TABLES_MODELS_TO_VIEWS, TABLES_USER_VIEW  # noqa: PLW0603, PLW0602 # type: ignore[no-untyped-def] # Global statement needed for module-level singletons

    # Validate prefix
    if not url_prefix.startswith("/"):
        msg = "url_prefix must start with '/'"
        raise ValueError(msg)
    # After the leading '/', should be alphanumeric (no special chars)
    after_slash = url_prefix[1:]
    if after_slash and not after_slash.replace("_", "").isalnum():
        msg = "url_prefix must contain only alphanumeric characters and underscores after '/'"
        raise ValueError(msg)

    TABLES_PREFIX = url_prefix

    # Clear any existing registrations (for tests that call add_views multiple times)
    TABLES_VIEW_DICT.clear()
    TABLES_MODELS_TO_VIEWS.clear()

    # Register views
    for view_class in views:
        # Get viewname from class (before instantiation)
        viewname = view_class.get_viewname_class()
        # Validate: viewnames starting with _ are not allowed
        if viewname.startswith("_"):
            msg = f"Viewname '{viewname}' is not allowed: viewnames starting with '_' are reserved"
            raise ValueError(msg)
        assert viewname not in TABLES_VIEW_DICT, f"Duplicate viewname: {viewname}"

        view_class()
        TABLES_VIEW_DICT[viewname] = view_class()

        assert view_class.model not in TABLES_MODELS_TO_VIEWS
        TABLES_MODELS_TO_VIEWS[view_class.model] = viewname

    # Set the model_to_viewname callable in serializers module
    # Use .get() to handle cases where model is not registered (e.g., in tests)
    serializers.model_to_viewname = lambda model: TABLES_MODELS_TO_VIEWS.get(
        model, f"__unregistered_{model.__name__}__"
    )

    # Find and set TABLES_USER_VIEW for user search functionality
    # Look for a view whose model is a proxy of the User model
    TABLES_USER_VIEW = None
    for _view in TABLES_VIEW_DICT.values():
        if (
            _view.model is not None
            and _view.model._meta.concrete_model == User  # Django _meta  # noqa: SLF001
            and _view.model._meta.proxy  # Django _meta is standard API  # noqa: SLF001
        ):
            TABLES_USER_VIEW = _view
            break

    http_patterns: list[URLPattern] = [
        path("_debug", _debug_view, name="tables-debug"),
        path("notifications/page", _notifications_page, name="tables-notifications-page"),
    ]
    for _view in TABLES_VIEW_DICT.values():
        http_patterns.extend(_view.get_url_patterns())

    # Reset ninja_api registrations (for tests that call add_views multiple times)
    # Module-level routes (decorators) are preserved — only per-view routers reset.
    default_router_reg = (
        "",
        ninja_api.default_router,
        NOT_SET,
        NOT_SET,
        None,
        None,
    )
    ninja_api._router_registrations = [default_router_reg]  # no public API to reset  # noqa: SLF001
    ninja_api._routers = [("", ninja_api.default_router)]  # no public API to reset  # noqa: SLF001
    ninja_api._bound_routers_cache = None  # no public API to reset  # noqa: SLF001
    ninja_api.default_router._frozen = False  # no public API to reset  # noqa: SLF001

    for _view in TABLES_VIEW_DICT.values():
        ninja_api.add_router("", _view.get_router())

    return http_patterns


class TableUrlSchema(_AliasModel):
    name: str
    url: str


class DebugViewSchema(_AliasModel):
    table_urls: list[TableUrlSchema]
    user: UserSchema | None


class RowDetailsProps(_AliasModel):
    title: str
    viewname: str
    view_url: str
    id: str
    column_names: list[str]
    fields: dict[str, ThSchema]
    cell_values: dict[str, Any]
    user: UserSchema | None
    can_edit: bool = False
    can_delete: bool = False
    row_updates: list[RowUpdateResponse] | None = None
    can_comment: bool | None = None
    slot_props: dict[str, Any] | None = None
    page_title: str = "Tables"
    ssr_html: str | None = None


class CreateRowProps(_AliasModel):
    viewname: str
    column_names: list[str]
    fields: dict[str, InputSchema]
    user: UserSchema | None


class UpdateRowProps(CreateRowProps):
    row_id: str


class SuccessResponse(_AliasModel):
    discriminator: Literal["success"] = Field(default="success", alias="d")
    id: str


class ValidationErrorResponse(_AliasModel):
    discriminator: Literal["validation_error"] = Field(default="validation_error", alias="d")
    errors: dict[str, str]
    top_level_error: str | None = None


class CommentRequest(PydanticBaseModel):
    comment_content: str = Field(min_length=1, max_length=1000)

    @field_validator("comment_content")
    @classmethod
    def sanitize_comment(cls, v: str) -> str:
        return sanitize_html(v)


class PaginationSchema(_AliasModel):
    page_number: int = Field(default=1, alias="page")
    per_page: int = Field(default=25, alias="per")


class ListPageSchema(_AliasModel):
    pagination: PaginationSchema = Field(default_factory=PaginationSchema, alias="p")
    filter_map: dict[str, UnionFilter] = Field(default_factory=dict, alias="f")
    row_update_filter: RowUpdateFilter | None = Field(default=None, alias="uf")

    def validate_filters(
        self,
        user: UserWithPublicId | None,  # noqa: ARG002
        model_class: type[_BaseModelMixin],  # noqa: ARG002
        column_schemas: dict[str, BaseFieldSchema],
    ) -> None:
        """Validate and remove invalid filters in-place."""
        visible_names: set[str] = set(column_schemas.keys())

        to_remove = []
        for col_name, filt in self.filter_map.items():
            if col_name not in visible_names:
                to_remove.append(col_name)
                continue

            field_schema = column_schemas.get(col_name)

            if not field_schema:
                to_remove.append(col_name)
                continue

            # Validate filter parameters first (only for filters that have validation)
            validate_method = getattr(filt, "validate_filter", None)
            if validate_method and callable(validate_method):
                try:
                    validate_method()
                except ValueError:
                    # Filter parameters are invalid, mark for removal
                    to_remove.append(col_name)
                    continue

            # Validate null filters - only allowed on nullable fields
            if (
                isinstance(filt, NullFilter)
                and field_schema
                and getattr(field_schema, "required", False)
            ):
                to_remove.append(col_name)
                continue

            # Get the field type from the schema and filter.
            # _field_type is a PrivateAttr on filter schemas that stores the Django field class
            # (e.g., CharField, IntegerField). It's used to validate that the filter matches
            # the column's actual field type, preventing mismatched filters.
            schema_field_type = getattr(field_schema, "_field_type", None)
            filter_field_type = getattr(filt, "_field_type", None)

            # Check if filter's field type matches schema's field type
            if schema_field_type and filter_field_type and schema_field_type == filter_field_type:
                continue

            to_remove.append(col_name)

        for col in to_remove:
            del self.filter_map[col]

    def human_row_references(
        self, model_class: type[_BaseModelMixin], column_schemas: dict[str, BaseFieldSchema]
    ) -> dict[str, dict[str, str]]:
        """Generate human-readable references for foreign key filter values.

        Returns format (example): {'user': {'1': 'John Smith'}}
        """
        references: dict[str, dict[str, str]] = {}

        # Process regular foreign key filters in filter_map
        for column_name, filt in self.filter_map.items():
            if filt.discriminator != "fk":
                continue

            assert isinstance(filt, ForeignKeyChoiceFilter)
            ids = filt.options

            if ids:
                # Find the field schema to get the related model information
                field_schema = self._find_field_schema(column_name, column_schemas)
                if not field_schema:
                    continue

                # Get related model from schema or fallback to model introspection
                related_model = self._get_related_model(column_name, field_schema, model_class)
                if not related_model:
                    continue

                # Generate references from the related model records
                ref_dict = self._generate_references(
                    cast(type[_BaseModelMixin], related_model), ids
                )
                references[column_name] = ref_dict

        # Process RowUpdateFilter user_ids if present
        if (
            self.row_update_filter
            and self.row_update_filter.user_ids
            and TABLES_USER_VIEW is not None
        ):
            user_model = TABLES_USER_VIEW.model
            user_viewname = TABLES_USER_VIEW.get_viewname_class()
            qs = user_model.filter_by_public_ids(
                user_model.queryset_with_title(), self.row_update_filter.user_ids
            )
            references[user_viewname] = {u.public_id: str(u.annotated_text) for u in qs}
        return references

    def _find_field_schema(
        self, column_name: str, column_schemas: dict[str, BaseFieldSchema]
    ) -> BaseFieldSchema | None:
        """Find field schema by column name."""
        return column_schemas.get(column_name)

    def _get_related_model(
        self, column_name: str, field_schema: BaseFieldSchema, model_class: type[_BaseModelMixin]
    ) -> type[models.Model] | None:
        """Get related model from schema or fallback to model introspection."""
        # Try to get related model from schema properties
        if hasattr(field_schema, "view_name"):
            # TODO: Implement proper related model lookup from view_name
            pass

        # Fallback to model introspection
        try:
            field = model_class._meta.get_field(column_name)  # noqa: SLF001
            return field.related_model if hasattr(field, "related_model") else None  # type: ignore[return-value]
        except FieldDoesNotExist, AttributeError:
            return None

    def _generate_references(
        self, related_model: type[_BaseModelMixin], ids: list[str]
    ) -> dict[str, str]:
        """Generate human-readable references from related model records."""
        annotated = related_model.queryset_with_title().filter(
            **{f"{related_model.public_id_field}__in": ids}
        )
        return {obj.public_id: str(obj.annotated_text) for obj in annotated}


class ListRowsProps(PydanticBaseModel):
    viewname: str
    column_names: list[str]
    columns: dict[str, ThSchema]
    columns_raw: dict[str, Any]
    rows: list[dict[str, Any]]
    list_page_schema: Any
    page: dict[str, int]
    user: UserSchema | None
    human_row_references: dict[str, dict[str, str]] = Field(default_factory=dict)
    user_viewname: str | None = None
    slot_props: dict[str, Any] | None = None
    page_title: str = "Tables"
    ssr_html: str | None = None


class RisonArgsConverter:
    regex = r".+"

    def to_python(self, value: str) -> dict[str, Any]:
        rison_str = value.replace("&39;", "'")
        try:
            args_dict: dict[str, Any] = loads(rison_str)
        except (ValueError, Exception) as e:
            msg = f"Invalid rison args: {e}"
            raise ValueError(msg) from e
        return args_dict

    def to_url(self, value: dict[str, Any]) -> str:
        return str(dumps(value))


register_converter(RisonArgsConverter, "risonargs")

type DjangoField = models.Field
type ValueStuff = Any


# Returns a plain Django User (or None). UserWithPublicId is a type alias
# for readability — the object does not have _BaseModelMixin attributes.
def maybe_user(request: HttpRequest) -> UserWithPublicId | None:
    if request.user.is_authenticated:
        return request.user
    return None


def user_or_404(request: HttpRequest) -> UserWithPublicId:
    """Get authenticated user or raise 404 error."""
    if not request.user.is_authenticated:
        msg = "Authentication required"
        raise Http404(msg)
    return request.user


def get_authenticated_user_as_schema(request: HttpRequest) -> UserSchema | None:
    if request.user.is_authenticated:
        user = request.user
        title = (f"{user.first_name} {user.last_name}").strip() or user.username
        user_id = user.pk
        return UserSchema(id=user_id, title=title)
    return None


@dataclass
class Toast:
    type: Literal["warning", "error", "success", "info", "question"]
    message: str


@dataclass
class ListRowsContext:
    request: HttpRequest
    columns: list[DjangoField]
    column_schemas: dict[str, BaseFieldSchema]
    queryset: models.QuerySet[Any]
    list_page_schema: ListPageSchema


@dataclass
class ListRows2Context:
    """Context for list rows response.

    - column_schemas: sent to client for filtering
    - th_columns: dict of ThSchema keyed by field name
    - raw_rows: the actual objects fetched from orm and are part
      of the page. They are then processed into cell_values.
    """

    column_schemas: dict[str, BaseFieldSchema]
    th_columns: dict[str, ThSchema]
    cell_values: list[dict[str, str | BaseContent]]
    page: dict[str, int]
    human_row_references: dict[str, dict[str, str]]
    raw_rows: list[_BaseModelMixin]
    slot_props: dict[str, Any] | None = None
    ssr_html: str | None = None


@dataclass
class RowDetailsContext:
    request: HttpRequest
    row: _BaseModelMixin
    user: UserWithPublicId | None
    columns: list[DjangoField]
    column_schemas: dict[str, BaseFieldSchema]


@dataclass
class RowDetails2Context:
    th_columns: dict[str, ThSchema]
    cell_values: dict[str, Any]
    slot_props: dict[str, Any] | None = None
    ssr_html: str | None = None


class OurRouter(Router):
    """Router subclass with convenience method for adding bound method handlers."""

    def add_method(self, path: str, methods: list[str], bound_method: Any) -> None:  # noqa: ANN401
        """Register a bound view method as an API endpoint.

        Django Ninja's ``add_api_operation`` expects a plain function with
        inspectable parameters. Bound methods carry ``self`` which confuses
        Ninja's parameter introspection. This wrapper strips ``self`` by
        forwarding via a closure and re-attaches the original signature so
        Ninja sees only the request/path parameters it expects.
        """
        sig = inspect.signature(bound_method)

        @functools.wraps(bound_method.__func__)
        def handler(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc] # signature overridden below  # noqa: ANN401
            return bound_method(*args, **kwargs)

        handler.__signature__ = sig  # type: ignore[attr-defined]
        self.add_api_operation(path, methods, handler)


class BaseView(abc.ABC):
    model: type[_BaseModelMixin]
    viewname_override: str | None = None
    list_page_schema: type[ListPageSchema] = ListPageSchema
    list_component: str = "ListRows"
    details_component: str = "RowDetails"

    def __init__(self) -> None:
        self._fk_cache: dict[str, dict[int, str]] | None = None

    @staticmethod
    def is_browser(request: HttpRequest) -> bool:
        return bool(request.headers.get("X-Inertia"))

    @classmethod
    def get_viewname_class(cls) -> str:
        """Return the viewname for this view class (before instantiation).

        For example, if we have a model `FirstStuff`, viewname is `firststuff`
        and urls like `/tables/firststuff/id/60`.
        """
        if cls.viewname_override is not None:
            return cls.viewname_override
        return cls.model.__name__.lower()

    def _validation_error_data(self, e: ValidationError) -> ValidationErrorResponse:
        errors: dict[str, str] = {}
        top_level: str | None = None

        if hasattr(e, "error_dict"):
            if e.message_dict.get("_top"):
                top_level = ".".join(e.message_dict["_top"])
            for field_name, messages in e.message_dict.items():
                if field_name.startswith("_"):
                    continue
                errors[field_name] = ".".join(messages)
        else:
            top_level = str(e.message)

        return ValidationErrorResponse(
            errors=errors,
            top_level_error=top_level,
        )

    def _list_rows(self, request: HttpRequest, params: dict[str, Any]) -> HttpResponse:
        try:
            list_page_schema = self.list_page_schema(**params)
        except PydanticValidationError as e:
            return HttpResponse(str(e), status=400, content_type="text/plain")
        model_class = self.model
        user = maybe_user(request)
        queryset = model_class.list_rows(user=user)

        columns = model_class.fields_or_404(user, "list")
        column_schemas = model_class.columns_schemas(columns)

        list_page_schema.validate_filters(user, model_class, column_schemas)

        for column_name, column_filter in list_page_schema.filter_map.items():
            queryset = column_filter.apply(queryset, column_name)

        if list_page_schema.row_update_filter:
            queryset = list_page_schema.row_update_filter.apply(queryset, "crud")

        ctx = ListRowsContext(
            request=request,
            columns=columns,
            column_schemas=column_schemas,
            queryset=queryset,
            list_page_schema=list_page_schema,
        )

        result = self.list_rows(ctx)

        page_title = self.get_viewname_class().capitalize()

        return InertiaResponse(
            request,
            self.list_component,
            {
                "props": ListRowsProps(
                    viewname=self.get_viewname_class(),
                    column_names=list(result.th_columns.keys()),
                    columns=result.th_columns,
                    columns_raw=column_schemas,
                    rows=result.cell_values,
                    list_page_schema=list_page_schema,
                    page=result.page,
                    user=get_authenticated_user_as_schema(request),
                    human_row_references=result.human_row_references,
                    user_viewname=TABLES_USER_VIEW.get_viewname_class()
                    if TABLES_USER_VIEW
                    else None,
                    slot_props=result.slot_props,
                    page_title=page_title,
                    ssr_html=result.ssr_html,
                ).model_dump()
            },
        )

    def list_rows(
        self,
        context: ListRowsContext,
    ) -> ListRows2Context:
        """Meant to be overridden."""
        model_class = self.model
        column_schemas = context.column_schemas
        columns = context.columns
        queryset = context.queryset
        list_page_schema = context.list_page_schema

        paginator = Paginator(queryset, list_page_schema.pagination.per_page, orphans=5)
        page = paginator.get_page(list_page_schema.pagination.page_number)

        page_objects = list(page.object_list)
        row_pks = [obj.pk for obj in page_objects]
        title_map: dict[int, str] = {}
        if row_pks:
            for obj in model_class.queryset_with_title().filter(pk__in=row_pks):
                title_map[obj.pk] = str(obj.annotated_text)

        annotate_fk_titles(columns, page_objects)

        th_columns = {
            name: cs.to_th() for name, cs in column_schemas.items() if name not in ("id", "title")
        }
        cell_values_list: list[dict[str, str | BaseContent]] = []
        for row in page_objects:
            wrappers = row.value_wrappers(columns, context="list")
            cell_row: dict[str, str | BaseContent] = {
                "id": row.public_id,
                "title": title_map[row.pk],
            }
            for name in column_schemas:
                if name in ("id", "title"):
                    continue
                cell_row[name] = wrappers[name].as_td()
            cell_values_list.append(cell_row)

        page_info = {
            "total_pages": paginator.num_pages,
            "total_count": paginator.count,
        }

        human_references = list_page_schema.human_row_references(model_class, column_schemas)

        ssr_html: str | None = None
        if not self.is_browser(context.request):
            rows_html: list[dict[str, Any]] = []
            for cell_row in cell_values_list:
                html_row: dict[str, str | BaseContent] = {"title": cell_row.get("title", "")}
                for name in th_columns:
                    html_row[name] = cell_row.get(name) or NullContent()
                rows_html.append(html_row)
            ssr_html = render_to_string(
                "tables/ssr_list.html",
                {
                    "fields": list(th_columns.values()),
                    "rows": rows_html,
                },
            )

        return ListRows2Context(
            column_schemas=column_schemas,
            th_columns=th_columns,
            cell_values=cell_values_list,
            page=page_info,
            human_row_references=human_references,
            raw_rows=page_objects,
            ssr_html=ssr_html,
        )

    def row_details(self, context: RowDetailsContext) -> RowDetails2Context:
        """Meant to be overridden."""
        th_columns = {name: cs.to_th() for name, cs in context.column_schemas.items()}

        annotate_fk_titles(context.columns, [context.row])
        wrappers = context.row.value_wrappers(context.columns, context="details")
        cell_values: dict[str, Any] = {
            name: wrappers[name].as_td() for name in context.column_schemas
        }

        ssr_html: str | None = None
        if not self.is_browser(context.request):
            viewname = self.get_viewname_class()
            view_url = reverse(
                f"tables-http:list-{viewname}",
                kwargs={"params": self.list_page_schema().model_dump(exclude_none=True)},
            )
            ssr_html = render_to_string(
                "tables/ssr_details.html",
                {
                    "view_url": view_url,
                    "fields": list(th_columns.values()),
                    "cell_values": cell_values,
                },
            )

        return RowDetails2Context(th_columns=th_columns, cell_values=cell_values, ssr_html=ssr_html)

    def _row_details(self, request: HttpRequest, row_id: str) -> HttpResponse:
        model = self.model
        user = maybe_user(request)
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "read")
        except model.DoesNotExist:
            return HttpResponse("Not found", status=404)

        columns = model.fields_or_404(user, "details", row)
        column_schemas = model.columns_schemas(columns)

        ctx = RowDetailsContext(
            request=request,
            row=row,
            user=user,
            columns=columns,
            column_schemas=column_schemas,
        )
        ctx2 = self.row_details(ctx)

        annotated_row = model.queryset_with_title().get(pk=row.pk)
        title = str(annotated_row.annotated_text)

        can_edit = False
        if user is not None:
            try:
                model.fields_or_404(user, "update", row)
                can_edit = True
            except Http404:
                pass

        can_delete = False
        try:
            model.get_row_for_user_and_operation(row_id, user, "delete")
            can_delete = True
        except model.DoesNotExist:
            pass

        viewname = self.get_viewname_class()
        page_title = f"{title} — {viewname.capitalize()}"
        view_url = reverse(
            f"tables-http:list-{viewname}",
            kwargs={"params": self.list_page_schema().model_dump(exclude_none=True)},
        )

        return InertiaResponse(
            request,
            self.details_component,
            {
                "props": RowDetailsProps(
                    title=title,
                    viewname=viewname,
                    view_url=view_url,
                    id=row.public_id,
                    column_names=list(ctx2.th_columns.keys()),
                    fields=ctx2.th_columns,
                    cell_values=ctx2.cell_values,
                    user=get_authenticated_user_as_schema(request),
                    can_edit=can_edit,
                    can_delete=can_delete,
                    row_updates=None,
                    slot_props=ctx2.slot_props,
                    page_title=page_title,
                    ssr_html=ctx2.ssr_html,
                ).model_dump()
            },
        )

    def create_row(self, request: HttpRequest) -> CreateRowProps:
        """Override to customize fields.

        Replace items in ``input_schemas`` with your own ``BaseInputSchema``
        subclass (e.g. custom ``component`` path) to swap input widgets.
        """
        assert request.method == "GET"
        model = self.model
        user = user_or_404(request)
        user_schema = get_authenticated_user_as_schema(request)

        columns = model.fields_or_404(user, "create")

        blank = model()
        wrappers = blank.value_wrappers(columns, context="input")
        input_schemas = {col.name: wrappers[col.name].as_input() for col in columns}

        return CreateRowProps(
            viewname=self.get_viewname_class(),
            column_names=[col.name for col in columns],
            fields=input_schemas,
            user=user_schema,
        )

    def _create_row(self, request: HttpRequest) -> HttpResponse:
        props = self.create_row(request)
        return InertiaResponse(
            request,
            "CreateRow",
            {"props": props.model_dump()},
        )

    def create_row_submit(self, request: HttpRequest) -> dict[str, Any]:
        assert request.method == "POST"
        model = self.model
        user = user_or_404(request)

        model.fields_or_404(user, "create")

        instance = model()
        posted = {k: v[0] for k, v in request.POST.lists()}
        files = {k: cast(UploadedFile, request.FILES[k]) for k in request.FILES}
        columns = model.fields_or_404(user, "create", None)
        collected_problems = instance.feed_values(posted, files, columns, None)

        if collected_problems.has_failed():
            return ValidationErrorResponse(
                errors=collected_problems.fields,
                top_level_error=collected_problems.top_level,
            ).model_dump()

        try:
            instance.save_stuff(SaveContext(user=user, existing_row=None))
        except ValidationError as e:
            return self._validation_error_data(e).model_dump()

        return SuccessResponse(id=instance.public_id).model_dump()

    def update_row(self, request: HttpRequest, row_id: str) -> UpdateRowProps:
        """Override to customize fields.

        Replace items in ``input_schemas`` with your own ``BaseInputSchema``
        subclass (e.g. custom ``component`` path) to swap input widgets.
        """
        assert request.method == "GET"
        model = self.model
        user = user_or_404(request)
        user_schema = get_authenticated_user_as_schema(request)

        try:
            row = model.get_row_for_user_and_operation(row_id, user, "update")
        except model.DoesNotExist:
            raise Http404 from None

        try:
            columns = model.fields_or_404(user, "update", row)
        except Http404:
            raise Http404 from None
        model.columns_schemas(columns)
        annotate_fk_titles(columns, [row])
        wrappers = row.value_wrappers(columns, context="input")
        input_schemas = {col.name: wrappers[col.name].as_input() for col in columns}

        return UpdateRowProps(
            viewname=self.get_viewname_class(),
            column_names=[col.name for col in columns],
            fields=input_schemas,
            user=user_schema,
            row_id=row_id,
        )

    def _update_row(self, request: HttpRequest, row_id: str) -> HttpResponse:
        props = self.update_row(request, row_id)
        return InertiaResponse(
            request,
            "UpdateRow",
            {"props": props.model_dump()},
        )

    def update_row_submit(self, request: HttpRequest, row_id: str) -> dict[str, Any]:
        assert request.method == "POST"
        model = self.model
        user = user_or_404(request)
        try:
            instance = model.get_row_for_user_and_operation(row_id, user, "update")
        except model.DoesNotExist:
            raise ApiError(404, "Row not found") from None

        existing_instance = model.get_by_public_id_or_404(
            model.objects.all(),  # type: ignore[attr-defined]
            row_id,
        )
        posted = {k: v[0] for k, v in request.POST.lists()}
        files = {k: cast(UploadedFile, request.FILES[k]) for k in request.FILES}
        columns = model.fields_or_404(user, "update", existing_instance)
        collected_problems = instance.feed_values(posted, files, columns, existing_instance)

        if collected_problems.has_failed():
            return ValidationErrorResponse(
                errors=collected_problems.fields,
                top_level_error=collected_problems.top_level,
            ).model_dump()

        try:
            instance.save_stuff(
                SaveContext(
                    user=user,
                    existing_row=existing_instance,
                )
            )
        except ValidationError as e:
            return self._validation_error_data(e).model_dump()

        return SuccessResponse(id=instance.public_id).model_dump()

    def delete_row(self, request: HttpRequest, row_id: str) -> DeleteRowResponse:
        assert request.method == "POST"
        user = maybe_user(request)
        model = self.model
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "delete")
        except model.DoesNotExist:
            raise ApiError(404, "Row not found") from None
        row.delete_safely()
        return DeleteRowResponse(message="Deleted your row.")

    def search_rows(self, request: HttpRequest, columnname: str) -> SearchRowsResponse:
        model = self.model
        text = request.GET.get("query", "").strip()

        queryset = model.search_for_fk_column(
            column_name=columnname,
            user=maybe_user(request),
            search_text=text,
        )

        rows = queryset[:20]
        return SearchRowsResponse(
            rows=[SearchRowItem(id=row.public_id, title=row.annotated_text) for row in rows]
        )

    def download_file(
        self, request: HttpRequest, row_id: str, column_name: str
    ) -> FileResponse | HttpResponse:
        user = maybe_user(request)
        model = self.model
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "read")
        except model.DoesNotExist:
            return FileResponse(b"Not found", status=404, content_type="text/plain")

        # Resolve which columns are accessible
        columns = model.fields_or_404(user, "details", row)

        column_names = [f.name for f in columns]
        if column_name not in column_names:
            return FileResponse(b"Field not accessible", status=403, content_type="text/plain")
        field = model._meta.get_field(column_name)  # noqa: SLF001
        if not isinstance(field, models.FileField):
            return FileResponse(b"Not a file field", status=400, content_type="text/plain")
        file_value = getattr(row, column_name)
        if not file_value:
            return FileResponse(b"No file", status=404, content_type="text/plain")

        # TODO proxy to child
        try:
            return FileResponse(file_value, as_attachment=True)
        except FileNotFoundError:
            return HttpResponse(b"File missing from storage", status=404, content_type="text/plain")

    def row_updates(self, request: HttpRequest, row_id: str) -> RowUpdateListResponse:
        user = maybe_user(request)
        model = self.model
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "read")
        except model.DoesNotExist:
            raise ApiError(404, "Row not found") from None

        can_create = row.can_create_comment(user)
        edit_timeout = row.update_timeout(user)
        delete_timeout = row.delete_timeout(user)

        update_responses = row.rowupdates(user)

        return RowUpdateListResponse(
            can_create_comment=can_create,
            edit_comment_timeout=edit_timeout,
            delete_comment_timeout=delete_timeout,
            updates=update_responses,
        )

    def create_comment(
        self, request: HttpRequest, row_id: str, body: CommentRequest
    ) -> CommentResponse:
        user = user_or_404(request)

        model = self.model
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "read")
        except model.DoesNotExist:
            raise ApiError(404, "Row not found") from None

        if not row.can_create_comment(user):
            raise ApiError(404, "You cannot comment on this row")

        row_update = row.create_comment(user, body.comment_content)

        return CommentResponse(
            message="Comment added",
            comment_id=str(row_update.id),
        )

    def update_comment(
        self, request: HttpRequest, row_id: str, row_update_id: int, body: CommentRequest
    ) -> CommentResponse:
        user = user_or_404(request)

        model = self.model
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "read")
        except model.DoesNotExist:
            raise ApiError(404, "Row not found") from None

        try:
            row_update = RowUpdate.objects.get(pk=row_update_id)
        except RowUpdate.DoesNotExist:
            raise ApiError(404, "Comment not found") from None

        row.update_comment(user, row_update, body.comment_content)

        return CommentResponse(
            message="Comment updated",
            comment_id=str(row_update.id),
        )

    def delete_comment(
        self, request: HttpRequest, row_id: str, row_update_id: int
    ) -> DeleteRowResponse:
        user = user_or_404(request)

        model = self.model
        try:
            row = model.get_row_for_user_and_operation(row_id, user, "read")
        except model.DoesNotExist:
            raise ApiError(404, "Row not found") from None

        row_update = row.get_rowupdate_for_delete(user, row_update_id)
        if not row_update:
            raise ApiError(404, "Comment not found")

        row_update.delete_comment(user)

        return DeleteRowResponse(message="Comment deleted")

    def get_router(self) -> OurRouter:
        router = OurRouter(exclude_none=True, by_alias=True)
        vn = self.get_viewname_class()

        router.add_method(f"/{vn}/search-rows/{{columnname}}", ["GET"], self.search_rows)
        router.add_method(f"/{vn}/row-updates/{{row_id}}", ["GET"], self.row_updates)
        router.add_method(f"/{vn}/create-comment/{{row_id}}", ["POST"], self.create_comment)
        router.add_method(
            f"/{vn}/{{row_id}}/update-comment/{{row_update_id}}",
            ["POST"],
            self.update_comment,
        )
        router.add_method(
            f"/{vn}/{{row_id}}/delete-comment/{{row_update_id}}",
            ["POST"],
            self.delete_comment,
        )
        router.add_method(f"/{vn}/create-row-submit", ["POST"], self.create_row_submit)
        router.add_method(f"/{vn}/update-row-submit/{{row_id}}", ["POST"], self.update_row_submit)
        router.add_method(f"/{vn}/delete-row/{{row_id}}", ["POST"], self.delete_row)
        return router

    def get_url_patterns(self) -> list[URLPattern]:
        """Generate URL patterns for HTTP page endpoints."""
        viewname = self.get_viewname_class()
        return [
            path(
                f"{viewname}/list/-<risonargs:params>-",
                self._list_rows,
                name=f"list-{viewname}",
            ),
            path(
                f"{viewname}/id/<str:row_id>",
                self._row_details,
                name=f"id-{viewname}",
            ),
            path(
                f"{viewname}/create-row",
                self._create_row,
                name=f"create-row-{viewname}",
            ),
            path(
                f"{viewname}/update-row/<str:row_id>",
                self._update_row,
                name=f"update-row-{viewname}",
            ),
            path(
                f"{viewname}/download-file/<str:row_id>/<str:column_name>",
                self.download_file,
                name=f"download-file-{viewname}",
            ),
        ]
