# ruff: noqa: INP001, ARG001 # fixture app loaded by file path, not a package; request param unused by some endpoints
"""Endpoint-serving fixture: one of each endpoint verb.

Feeds ``test_endpoints.py`` (HTTP serving of every verb at ``.../e/<fn>``):
``random_code`` (GET) returns a seeded code at random; ``endpoint_page`` (GET)
renders the first row's code as an Inertia page; ``echo`` (POST) inserts a row,
``rename_first`` (PUT) re-titles one, ``drop_first`` (DELETE) removes one. No
``frontend/`` bundle — ``app_bundle`` is a pure path derivation, so the inertia-URL
test needs no built file (Vue *rendering* is exercised by ``Tests/Browser`` via
buildfrontend).
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    CharColumn,
    HttpRequest,
    InertiaPage,
    a_test_request,
    backend_test,
    delete_endpoint,
    dynamic_models,
    get_endpoint,
    post_endpoint,
    put_endpoint,
    setup,
)

APP = "EndpointsApp"
TABLE = "items"
# ≥2 distinct codes so the randomness test sees more than one value.
ITEMS = ["A1", "A2", "A3"]


class EndpointPageProps(BaseModel):
    """Props for the EndpointPage component."""

    code: str


class CodeOut(BaseModel):
    """A row's code, returned by the ``random_code`` GET endpoint."""

    code: str


class CreatedOut(BaseModel):
    """The code created by the ``echo`` POST, returned for the round-trip assertion."""

    created: str


class CountOut(BaseModel):
    """The row count, returned by the write endpoints."""

    count: int


@setup
def setup_app() -> None:
    """Create the EndpointsApp app + an items table seeded with rows."""
    dynamic_models.create_application(
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    model = Application.objects.get(name=APP).table_as_model(TABLE)
    model.objects.bulk_create([model(code=code) for code in ITEMS])


def _row_count() -> int:
    # table_as_model returns a dynamic model typed as Any, so annotate the local
    # to keep the int return type without a cast (count() is int at runtime).
    count: int = Application.objects.get(name=APP).table_as_model(TABLE).objects.count()
    return count


@get_endpoint
def random_code(request: HttpRequest) -> CodeOut:
    """GET endpoint returning one seeded code at random."""
    model = Application.objects.get(name=APP).table_as_model(TABLE)
    row = model.objects.order_by("?").first()
    return CodeOut(code=row.code if row else "")


@get_endpoint
def default(request: HttpRequest) -> CodeOut:
    """GET endpoint served at the bare ``/e`` route (the app's default page)."""
    model = Application.objects.get(name=APP).table_as_model(TABLE)
    row = model.objects.first()
    return CodeOut(code=row.code if row else "")


@get_endpoint
def endpoint_page(request: HttpRequest) -> InertiaPage[EndpointPageProps]:
    """GET endpoint rendering the first seeded row's code as an Inertia page."""
    row = Application.objects.get(name=APP).table_as_model(TABLE).objects.first()
    return InertiaPage(
        component="EndpointPage", props=EndpointPageProps(code=row.code if row else "")
    )


@post_endpoint
def echo(request: HttpRequest) -> CreatedOut:
    """POST: insert a fixed row and return its code (exercises POST dispatch)."""
    row = Application.objects.get(name=APP).table_as_model(TABLE).objects.create(code="echoed")
    return CreatedOut(created=row.code)


@put_endpoint
def rename_first(request: HttpRequest) -> CountOut:
    """PUT: re-title the first row's code, then return the (unchanged) row count."""
    row = Application.objects.get(name=APP).table_as_model(TABLE).objects.first()
    if row is not None:
        row.code = "renamed"
        row.save()
    return CountOut(count=_row_count())


@delete_endpoint
def drop_first(request: HttpRequest) -> CountOut:
    """DELETE: remove the first row, then return the new (lower) row count."""
    row = Application.objects.get(name=APP).table_as_model(TABLE).objects.first()
    if row is not None:
        row.delete()
    return CountOut(count=_row_count())


@backend_test
def test_random_code_returns_a_seeded_code() -> None:
    """A call returns a code drawn from the seeded set."""
    assert random_code(a_test_request()).code in ITEMS


@backend_test
def test_random_code_varies() -> None:
    """Over many calls the endpoint returns more than one distinct code."""
    seen = {random_code(a_test_request()).code for _ in range(30)}
    assert len(seen) > 1, f"random_code is not random: only got {seen}"
