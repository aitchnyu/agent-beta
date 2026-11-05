"""Synthetic module for generatesdk unit tests: an api + flagged models.

Imported only by ``djangoapp/tests/test_generatesdk.py`` — never part of
the running app (no urls.py wiring).
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from ninja import Router
from pydantic import BaseModel

from djangoapp.ninja_api import ExportedSchemaMixin, make_ninja_api

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router()


class Item(BaseModel, ExportedSchemaMixin):
    """flagged."""

    public_id: str
    quantity: int
    price: Decimal
    label: Literal["a", "b"]
    note: str | None = None
    tags: list[str]


class ItemPageProps(BaseModel, ExportedSchemaMixin):
    """flagged."""

    items: list[Item]
    path_prefix: str


class Filters(BaseModel, ExportedSchemaMixin):
    """flagged."""

    q: str = ""
    page: int = 1


class ItemResponse(BaseModel, ExportedSchemaMixin):
    """flagged."""

    item: Item


class SecretInternal(BaseModel):
    """unflagged — must NOT appear in the sdk."""

    key: str


@router.get("/items", response=ItemResponse)
def list_items(request: HttpRequest, filters: Filters) -> ItemResponse:
    raise NotImplementedError


@router.post("/items/{public_id}/price", response=ItemResponse)
def set_price(request: HttpRequest, public_id: str, price: Decimal) -> ItemResponse:
    raise NotImplementedError


@router.delete("/items/{public_id}", response=ItemResponse)
def delete_item(request: HttpRequest, public_id: str) -> ItemResponse:
    raise NotImplementedError


@router.get("/page", response=None, include_in_schema=False)
def page(request: HttpRequest) -> None:
    raise NotImplementedError


@router.post("/internal", response=SecretInternal)
def internal(request: HttpRequest) -> SecretInternal:
    raise NotImplementedError


# Mounted with a prefix so generated URLs carry /fixture (the users and
# notifications pattern).
fixture_api = make_ninja_api("fixture", router, prefix="fixture")
