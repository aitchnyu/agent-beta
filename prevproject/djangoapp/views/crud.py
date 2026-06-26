"""FooView: self-contained class-based CRUD view on a standalone FooModel.

Built on the experimental CBV (SomeBase/mrouter). Endpoints are declared with
@mrouter.get/@mrouter.post and mounted via get_router(). There is no row
resolution or permission checking, and nothing is imported from serializers.py
or models/base.py -- column (de)serialization lives in the columns module, and
response payloads are plain dicts.
"""

from __future__ import annotations

import typing
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.db.models.fields.files import FieldFile
from django.http import FileResponse, HttpRequest, HttpResponse
from inertia import InertiaResponse

from djangoapp.columns import OPERATIONS, UNCHANGED, Column, Field, ResolvedColumn
from djangoapp.views.foo import SomeBase, mrouter

if typing.TYPE_CHECKING:
    from djangoapp.models.base import FooModel


def _success(public_id: str) -> dict[str, Any]:
    return {"d": "success", "id": public_id}


def _validation_error(errors: dict[str, str], top: str | None = None) -> dict[str, Any]:
    return {"d": "validation_error", "errors": errors, "top_level_error": top}


class FooView(SomeBase):
    """CRUD view over a FooModel, driven by a `columns` dict.

    `columns` maps field name -> Column descriptor (which carries the
    editable rule + (de)serialization behavior). No row resolution or
    permission checks -- all rows are accessible.
    """

    model: typing.ClassVar[type[FooModel]]
    columns: typing.ClassVar[dict[str, Column]] = {}
    list_component: str = "FooList"
    details_component: str = "FooDetails"

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401 # forwarded to object.__init_subclass__
        """Smoke-check: concrete FooViews must declare `columns` -> real fields."""
        super().__init_subclass__(**kwargs)
        model = getattr(cls, "model", None)
        if model is None:
            return
        columns = getattr(cls, "columns", None)
        if not columns:
            msg = f"{cls.__name__} must define a non-empty `columns` dict"
            raise TypeError(msg)
        for name, column in columns.items():
            column.accepts(model._meta.get_field(name))  # noqa: SLF001

    # -- helpers ----------------------------------------------------------

    def _viewname(self) -> str:
        return self.model.__name__.lower()

    def _columns_for(self, operation: OPERATIONS) -> list[ResolvedColumn]:
        """ResolvedColumns for an operation, applying `editable` rules.

        create/update -> only editable columns (createonly excluded on update);
        list/details -> every declared column (display).
        """
        model = self.model
        editable = operation in ("create", "update")
        cols: list[ResolvedColumn] = []
        for name, column in self.columns.items():
            field = cast(Field, model._meta.get_field(name))  # noqa: SLF001
            if editable:
                if column.is_editable(operation):
                    cols.append(ResolvedColumn(field=field, column=column))
            else:
                cols.append(ResolvedColumn(field=field, column=column))
        return cols

    def _user(self, request: HttpRequest) -> dict[str, Any] | None:
        u = request.user
        if not getattr(u, "is_authenticated", False):
            return None
        first = getattr(u, "first_name", "") or ""
        last = getattr(u, "last_name", "") or ""
        title = (f"{first} {last}").strip() or getattr(u, "username", "")
        return {"id": u.pk, "title": title}

    def _feed(
        self,
        instance: FooModel,
        posted: dict[str, str],
        files: dict[str, UploadedFile],
        columns: list[ResolvedColumn],
    ) -> dict[str, str]:
        """Parse posted values onto the instance; return {field: error}."""
        present = set(posted) | set(files)
        errors: dict[str, str] = {}
        for rc in columns:
            if rc.name not in present:
                continue
            raw = posted.get(rc.name, "")
            try:
                value = rc.parse(raw, files)
            except ValidationError as e:
                errors[rc.name] = ".".join(e.messages)
                continue
            if value is UNCHANGED:
                continue
            setattr(instance, rc.name, value)
        return errors

    # -- create -----------------------------------------------------------

    @mrouter.get("/create")
    def create_get(self, request: HttpRequest) -> InertiaResponse:
        """/create GET: render the create form for create-editable columns."""
        columns = self._columns_for("create")
        blank = self.model()
        fields = {rc.name: rc.to_input(getattr(blank, rc.name)) for rc in columns}
        props = {
            "viewname": self._viewname(),
            "column_names": [rc.name for rc in columns],
            "fields": fields,
            "user": self._user(request),
        }
        return InertiaResponse(request, "FooCreate", {"props": props})

    @mrouter.post("/create")
    def create_post(self, request: HttpRequest) -> object:
        """/create POST: validate + save a new row; returns its public id."""
        columns = self._columns_for("create")
        instance = self.model()
        posted = {k: v[0] for k, v in request.POST.lists()}
        files = {k: cast(UploadedFile, request.FILES[k]) for k in request.FILES}
        errors = self._feed(instance, posted, files, columns)
        if errors:
            return _validation_error(errors)
        try:
            instance.validate_unique(exclude=["public_id"])
            instance.save()
        except ValidationError as e:
            return _validation_error({"_top": ".".join(e.messages)})
        return _success(instance.public_id)

    # -- update -----------------------------------------------------------

    @mrouter.get("/update/{public_id}")
    def update_get(self, request: HttpRequest, public_id: str) -> InertiaResponse:
        """/update GET: render the update form (createonly/never hidden)."""
        row = self.model.get_by_public_id_or_404(public_id)
        columns = self._columns_for("update")
        fields = {rc.name: rc.to_input(getattr(row, rc.name)) for rc in columns}
        props = {
            "viewname": self._viewname(),
            "column_names": [rc.name for rc in columns],
            "fields": fields,
            "user": self._user(request),
            "row_id": public_id,
        }
        return InertiaResponse(request, "FooUpdate", {"props": props})

    @mrouter.post("/update/{public_id}")
    def update_post(self, request: HttpRequest, public_id: str) -> object:
        """/update POST: validate + save edits; returns the public id."""
        instance = self.model.get_by_public_id_or_404(public_id)
        columns = self._columns_for("update")
        posted = {k: v[0] for k, v in request.POST.lists()}
        files = {k: cast(UploadedFile, request.FILES[k]) for k in request.FILES}
        errors = self._feed(instance, posted, files, columns)
        if errors:
            return _validation_error(errors)
        try:
            instance.validate_unique(exclude=["public_id"])
            instance.save()
        except ValidationError as e:
            return _validation_error({"_top": ".".join(e.messages)})
        return _success(instance.public_id)

    # -- details ----------------------------------------------------------

    @mrouter.get("/id/{public_id}")
    def details(self, request: HttpRequest, public_id: str) -> InertiaResponse:
        """/id/<public_id> GET: display all declared columns for a row."""
        row = self.model.get_by_public_id_or_404(public_id)
        columns = self._columns_for("details")
        cell_values = {rc.name: rc.to_td(getattr(row, rc.name)) for rc in columns}
        viewname = self._viewname()
        title = str(row)
        props = {
            "title": title,
            "viewname": viewname,
            "id": row.public_id,
            "column_names": [rc.name for rc in columns],
            "cell_values": cell_values,
            "user": self._user(request),
            "can_edit": bool(self._columns_for("update")),
            "can_delete": False,
            "page_title": f"{title} — {viewname.capitalize()}",
        }
        return InertiaResponse(request, self.details_component, {"props": props})

    # -- list (links only, no pagination) ---------------------------------

    @mrouter.get("")
    def list_rows(self, request: HttpRequest) -> InertiaResponse:
        """List every row as a link to its details page."""
        rows = [
            {"id": obj.public_id, "title": str(obj)} for obj in cast(Any, self.model).objects.all()
        ]
        return InertiaResponse(
            request,
            self.list_component,
            {"props": {"viewname": self._viewname(), "rows": rows}},
        )

    # -- download ---------------------------------------------------------

    @mrouter.get("/id/{public_id}/download/{column_name}")
    def download(
        self,
        request: HttpRequest,  # noqa: ARG002 # request required by Ninja's call convention
        public_id: str,
        column_name: str,
    ) -> FileResponse | HttpResponse:
        """Serve a file column for a row."""
        row = self.model.get_by_public_id_or_404(public_id)
        columns = self._columns_for("details")
        if column_name not in {rc.name for rc in columns}:
            return FileResponse(b"Field not accessible", status=403, content_type="text/plain")
        field = self.model._meta.get_field(column_name)  # noqa: SLF001
        if not isinstance(field, models.FileField):
            return FileResponse(b"Not a file field", status=400, content_type="text/plain")
        file_value = cast(FieldFile, getattr(row, column_name))
        if not file_value:
            return FileResponse(b"No file", status=404, content_type="text/plain")
        try:
            return FileResponse(file_value, as_attachment=True)
        except FileNotFoundError:
            return HttpResponse(b"File missing from storage", status=404, content_type="text/plain")
