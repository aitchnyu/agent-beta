"""Superuser-only read views for application collections/apps/tables.

These are server-rendered Inertia pages (no JSON API yet). All three
require a superuser; anyone else gets a 404 (per the project access rule
that an unauthorised user must not learn a resource exists). The
``/manage`` page lists an app's tables with live row counts read from
each dynamic model.
"""

from __future__ import annotations

from typing import Any, cast

from django.http import Http404, HttpRequest, HttpResponse
from inertia import render
from pydantic import BaseModel

from djangoapp.models import (
    Application,
    ApplicationCollection,
)
from djangoapp.models.dynamic import dynamic_models


def _require_superuser(request: HttpRequest) -> None:
    """Gate the view to a superuser, else 404 (never 403)."""
    viewer = request.user
    if not (viewer.is_authenticated and viewer.is_superuser):
        raise Http404


class CollectionItem(BaseModel):
    name: str


class CollectionsProps(BaseModel):
    collections: list[CollectionItem]


class AppItem(BaseModel):
    name: str


class AppListProps(BaseModel):
    collection_name: str
    apps: list[AppItem]


class TableItem(BaseModel):
    name: str
    row_count: int


class ManageProps(BaseModel):
    collection_name: str
    app_name: str
    tables: list[TableItem]


def collections_page(request: HttpRequest) -> HttpResponse:
    """List every application collection."""
    _require_superuser(request)
    items = [
        CollectionItem(name=c.name) for c in ApplicationCollection.objects.all().order_by("name")
    ]
    props = CollectionsProps(collections=items)
    return render(request, "Collections", props.model_dump())  # type: ignore[no-any-return] # inertia.render is untyped


def app_list_page(request: HttpRequest, collection_name: str) -> HttpResponse:
    """List the applications within one collection."""
    _require_superuser(request)
    try:
        collection = ApplicationCollection.objects.get(name=collection_name)
    except ApplicationCollection.DoesNotExist as exc:
        raise Http404 from exc
    items = [AppItem(name=a.name) for a in collection.applications.all().order_by("name")]
    props = AppListProps(
        collection_name=collection.name,
        apps=items,
    )
    return render(request, "AppList", props.model_dump())  # type: ignore[no-any-return] # inertia.render is untyped


def manage_page(request: HttpRequest, collection_name: str, app_name: str) -> HttpResponse:
    """List an app's tables with live row counts (read from dynamic models)."""
    _require_superuser(request)
    try:
        app = Application.objects.get(
            name=app_name,
            application_collection__name=collection_name,
        )
    except Application.DoesNotExist as exc:
        raise Http404 from exc
    table_rows: list[TableItem] = []
    for table in app.tables.all().order_by("name"):
        # Row counts come from the generated model bound to the live table.
        model = cast("Any", dynamic_models.get_model(table.physical_name))
        table_rows.append(TableItem(name=table.name, row_count=model.objects.count()))
    props = ManageProps(
        collection_name=app.application_collection.name,
        app_name=app.name,
        tables=table_rows,
    )
    return render(request, "Manage", props.model_dump())  # type: ignore[no-any-return] # inertia.render is untyped


# Re-export for type-checkers that scan module members.
__all__ = [
    "AppItem",
    "AppListProps",
    "CollectionItem",
    "CollectionsProps",
    "ManageProps",
    "TableItem",
    "app_list_page",
    "collections_page",
    "manage_page",
]
