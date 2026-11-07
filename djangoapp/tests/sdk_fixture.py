"""Synthetic module for generatesdk unit tests: an api with a nested mount.

Imported only by ``djangoapp/tests/test_generatesdk.py`` — never part of
the running app (no urls.py wiring). The op router sits ONE add_router
level under the mounted router, so the generator's recursive walk and
prefix joining are pinned by the tests.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from ninja import Router
from pydantic import BaseModel

from djangoapp.ninja_api import make_ninja_api

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router()


class Item(BaseModel):
    public_id: str
    quantity: int
    price: Decimal
    label: Literal["a", "b"]
    note: str | None = None
    tags: list[str]


class ItemPageProps(BaseModel):
    """Page props — unreachable from any endpoint; must NOT emit."""

    items: list[Item]
    path_prefix: str


class Filters(BaseModel):
    q: str = ""
    page: int = 1


class ItemResponse(BaseModel):
    item: Item


class ItemCreate(BaseModel):
    """Request body model — reachable via the create op; must emit."""

    label: Literal["a", "b"]
    quantity: int = 1


@router.get("/items", response=ItemResponse)
def list_items(request: HttpRequest, filters: Filters) -> ItemResponse:
    raise NotImplementedError


@router.post("/items/{public_id}/price", response=ItemResponse)
def set_price(request: HttpRequest, public_id: str, price: Decimal) -> ItemResponse:
    raise NotImplementedError


@router.post("/items/create", response=ItemResponse)
def create_item(request: HttpRequest, payload: ItemCreate) -> ItemResponse:
    raise NotImplementedError


@router.delete("/items/{public_id}", response=ItemResponse)
def delete_item(request: HttpRequest, public_id: str) -> ItemResponse:
    raise NotImplementedError


@router.get("/page", response=None, include_in_schema=False)
def page(request: HttpRequest) -> None:
    raise NotImplementedError


# The op router nests ONE add_router level under the mounted router: the
# walk must recurse and join prefixes (/fixture/nested/...).
parent_router = Router()
parent_router.add_router("nested", router)

# Mounted with a prefix so generated URLs carry /fixture (the users and
# notifications pattern).
fixture_api = make_ninja_api("fixture", parent_router, prefix="fixture")
