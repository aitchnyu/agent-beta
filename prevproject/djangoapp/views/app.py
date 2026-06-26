# ---------------- Our test views -------------------
import typing
from typing import Any, Literal

from django.conf import settings
from django.db.models import F, QuerySet
from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI
from pydantic import field_validator

from djangoapp.columns import (
    Booleanfield,
    CharChoicefield,
    Charfield,
    Column,
    Datetimefield,
    Decimalfield,
    Filefield,
    Integerfield,
    Textfield,
)
from djangoapp.models.app import (
    AllColumns,
    BooleanFieldModel,
    CategoryModel,
    CharFieldModel,
    ConditionalRowUpdatePermissionModel,
    DatetimeFieldModel,
    DecimalFieldModel,
    FirstStuff,
    ForeignKeyModel,
    IntegerFieldModel,
    MoreStuff,
    ProxyUser,
    PublicIdSequenceTestModel1,
    PublicIdSequenceTestModel2,
    PublicIdUuid7TestModel,
    PublicIdUuid7TestModel2,
    PublicIdUuid7TestModel3,
    Ref,
    SlotDemoModel,
    TestFileUploadModel,
)
from djangoapp.models.base import User
from djangoapp.responses import IntegerFieldContent, ThSchema
from djangoapp.views.articles import article_editors, article_participants
from djangoapp.views.base import (
    BaseView,
    ListPageSchema,
    ListRows2Context,
    ListRowsContext,
    RowDetails2Context,
    RowDetailsContext,
    add_views,
)
from djangoapp.views.crud import FooView
from djangoapp.views.foo import ListView, mrouter


class RefStuffView(BaseView):
    model = Ref


class FirstStuffView(BaseView):
    model = FirstStuff
    list_component = "FirstStuffListRows"

    def list_rows(self, context: ListRowsContext) -> ListRows2Context:
        result = super().list_rows(context)
        result.slot_props = {
            "row_count": context.queryset.count(),
            "distinct_integers": list(
                context.queryset.values_list("integer_field", flat=True)
                .distinct()
                .order_by("integer_field")
            ),
        }
        return result


class MoreStuffView(BaseView):
    model = MoreStuff


class UserStuffView(BaseView):
    model = ProxyUser


class TestFileUploadModelView(BaseView):
    model = TestFileUploadModel


class BooleanFieldModelView(BaseView):
    model = BooleanFieldModel


class IntegerFieldModelView(BaseView):
    model = IntegerFieldModel


class DecimalFieldModelView(BaseView):
    model = DecimalFieldModel


class CharFieldModelView(BaseView):
    model = CharFieldModel


class DatetimeFieldModelView(BaseView):
    model = DatetimeFieldModel


class ForeignKeyModelView(BaseView):
    model = ForeignKeyModel


class CategoryModelView(BaseView):
    model = CategoryModel


class ConditionalRowUpdatePermissionModelView(BaseView):
    model = ConditionalRowUpdatePermissionModel


class SlotDemoListPageSchema(ListPageSchema):
    diff: Literal["any"] | int | None = None

    @field_validator("diff")
    @classmethod
    def diff_must_be_positive(cls, v: int | Literal["any"] | None) -> int | Literal["any"] | None:
        if v is not None and v != "any" and v <= 0:
            msg = "diff must be a positive integer, 'any', or null"
            raise ValueError(msg)
        return v


class SlotDemoView(BaseView):
    """Demo view showing custom filters, child pages, and row details.

    **List rows**: Shows how to create a view with a custom
    ``ListPageSchema`` subclass (``SlotDemoListPageSchema`` with a
    ``diff`` field) and a custom Vue component (``SlotDemoListRows``)
    that provides a diff filter UI.

    To create a similar list view:

    1. Define a ``ListPageSchema`` subclass with extra fields for your
       custom filter parameters.
    2. Set ``list_page_schema`` to your schema class.
    3. Set ``list_component`` to the name of your Vue page component
       (resolved from ``pages/`` or ``components/custom/``).
    4. Override ``list_rows`` to read your custom fields from
       ``context.list_page_schema`` and apply filtering/annotations.

    **Row details**: Shows how to override ``row_details`` to pass
    custom data (prev/next navigation) to a custom details page
    component (``SlotDemoRowDetails``).

    To create a similar details view:

    1. Set ``details_component`` to the name of your Vue page component.
    2. Override ``row_details`` to set ``context.slot_props`` with
       custom data.
    3. The frontend component receives ``slot_props`` and fills named
       slots (``before-row``, ``after-row``) of ``RowDetailsContent``.
    """

    model = SlotDemoModel
    list_page_schema: type[ListPageSchema] = SlotDemoListPageSchema
    list_component = "SlotDemoListRows"
    details_component = "SlotDemoRowDetails"

    def row_details(self, context: RowDetailsContext) -> RowDetails2Context:
        ctx2 = super().row_details(context)
        pk = context.row.pk
        qs = SlotDemoModel.list_rows(user=context.user)
        slot: dict[str, Any] = {}
        prev_row = qs.filter(pk__lt=pk).order_by("-pk").first()
        if prev_row is not None:
            annotated = SlotDemoModel.queryset_with_title().get(pk=prev_row.pk)
            slot["prev"] = {
                "title": str(annotated.annotated_text),
                "id": prev_row.public_id,
            }
        next_row = qs.filter(pk__gt=pk).order_by("pk").first()
        if next_row is not None:
            annotated = SlotDemoModel.queryset_with_title().get(pk=next_row.pk)
            slot["next"] = {
                "title": str(annotated.annotated_text),
                "id": next_row.public_id,
            }
        ctx2.slot_props = slot
        return ctx2

    def list_rows(self, context: ListRowsContext) -> ListRows2Context:
        list_page_schema = context.list_page_schema
        assert isinstance(list_page_schema, SlotDemoListPageSchema)
        diff_value = list_page_schema.diff

        qs = context.queryset.annotate(diff=F("int1") - F("int2"))

        show_diff_column = diff_value is not None
        if diff_value == "any":
            qs = qs.filter(diff__gt=0)
        elif diff_value is not None:
            qs = qs.filter(diff__gte=diff_value)

        context = ListRowsContext(
            request=context.request,
            columns=context.columns,
            column_schemas=context.column_schemas,
            queryset=qs,
            list_page_schema=list_page_schema,
        )
        result = super().list_rows(context)

        if show_diff_column:
            diff_th = ThSchema(name="diff", component="/components/cells/IntegerFieldTd")
            result.th_columns["diff"] = diff_th
            for row, obj in zip(result.cell_values, qs, strict=False):
                row["diff"] = IntegerFieldContent(value=obj.diff)

        return result


class PublicIdUuid7TestModelView(BaseView):
    model = PublicIdUuid7TestModel


class PublicIdUuid7TestModel2View(BaseView):
    model = PublicIdUuid7TestModel2


class PublicIdSequenceTestModel1View(BaseView):
    model = PublicIdSequenceTestModel1


class PublicIdSequenceTestModel2View(BaseView):
    model = PublicIdSequenceTestModel2


class PublicIdUuid7TestModel3View(BaseView):
    model = PublicIdUuid7TestModel3


# Register views and create URL patterns
tables_urls = add_views(
    url_prefix="/tables",
    views=[
        RefStuffView,
        FirstStuffView,
        MoreStuffView,
        UserStuffView,
        TestFileUploadModelView,
        BooleanFieldModelView,
        IntegerFieldModelView,
        DecimalFieldModelView,
        CharFieldModelView,
        DatetimeFieldModelView,
        ForeignKeyModelView,
        CategoryModelView,
        ConditionalRowUpdatePermissionModelView,
        SlotDemoView,
        PublicIdUuid7TestModelView,
        PublicIdUuid7TestModel2View,
        PublicIdSequenceTestModel1View,
        PublicIdSequenceTestModel2View,
        PublicIdUuid7TestModel3View,
    ],
)


def login_for_test(request: HttpRequest, userid: int) -> HttpResponse:
    """Login a user for testing, debug mode only."""
    if not settings.DEBUG:
        return HttpResponse("Forbidden: Debug mode required", status=403)
    try:
        user = User.objects.get(pk=userid)
    except User.DoesNotExist:
        return HttpResponse("User not found", status=404)
    from django.contrib.auth import login  # noqa: PLC0415

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return HttpResponse(f"Logged in as {user.username}")


@article_editors
def _article_editors() -> QuerySet[User, User]:
    return User.objects.filter(is_superuser=True)


@article_participants
def _article_participants() -> QuerySet[User, User]:
    return User.objects.all()


# ---------------- Experimental class-based views ----------------
# Example endpoints (C1/C2) and their NinjaAPI mount. The CBV machinery
# (RouteMeta, MRouter/mrouter, SomeBase, ListView) lives in views/foo.py.


class C1(ListView):
    """Mounted at /c1; exposes /c1/list."""

    def list(self) -> list[int]:
        return [1, 2, 3]


class C2(ListView):
    """Mounted at /c2; exposes /c2/list and /c2/custom."""

    def list(self) -> list[str]:
        return ["a", "b", "c"]

    @mrouter.get("/custom")
    def custom(self, request: HttpRequest) -> str:  # noqa: ARG002 # request required by Ninja's call convention
        """Extra endpoint only on C2."""
        return "hello"


# Mount the experimental class-based views on one NinjaAPI for urls.py.
cbv_api = NinjaAPI(urls_namespace="cbv", openapi_url=None)
cbv_api.add_router("c1", C1.get_router())
cbv_api.add_router("c2", C2.get_router())


# ---------------- Foo CRUD (class-based) ----------------
class AllColumnsView(FooView):
    """FooView over AllColumns, mounted at /allcolumns."""

    model = AllColumns
    columns: typing.ClassVar[dict[str, Column]] = {
        "char_field": Charfield(editable="createonly"),
        "char_choice_field": CharChoicefield(),
        "text_field": Textfield(),
        "integer_field": Integerfield(),
        "boolean_field": Booleanfield(),
        "decimal_field": Decimalfield(),
        "datetime_field": Datetimefield(),
        "file_field": Filefield(editable="createonly"),
    }


# Mount the Foo CRUD router on its own NinjaAPI for urls.py.
foo_api = NinjaAPI(urls_namespace="foo", openapi_url=None)
foo_api.add_router("allcolumns", AllColumnsView.get_router())
