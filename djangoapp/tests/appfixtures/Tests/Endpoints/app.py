# ruff: noqa: INP001, ARG001 # fixture app loaded by file path, not a package; required request_context signature
"""Endpoint-serving fixture: a random @get_endpoint + an @inertia_endpoint.

Feeds ``test_endpoints.py`` (HTTP serving of @get_endpoint / @inertia_endpoint):
``random_code`` returns a seeded code at random; ``endpoint_page`` renders the
first row's code as an Inertia page. No ``frontend/`` bundle — ``app_bundle`` is
a pure path derivation, so the inertia-URL test needs no built file (Vue
*rendering* is exercised by ``Tests/Browser`` via buildfrontend).
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    CharColumn,
    InertiaPage,
    RequestContext,
    backend_test,
    dynamic_models,
    fake_context,
    get_endpoint,
    inertia_endpoint,
    setup,
)

COLLECTION = "Tests"
APP = "Endpoints"
TABLE = "items"
# ≥2 distinct codes so the randomness test sees more than one value.
ITEMS = ["A1", "A2", "A3"]


class EndpointPageProps(BaseModel):
    """Props for the EndpointPage component."""

    code: str


class CodeOut(BaseModel):
    """A row's code, returned by the ``random_code`` GET endpoint."""

    code: str


@setup
def setup_app() -> None:
    """Create the Tests/Endpoints app + an items table seeded with rows."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    model.objects.bulk_create([model(code=code) for code in ITEMS])


@get_endpoint
def random_code(request_context: RequestContext) -> CodeOut:
    """GET endpoint returning one seeded code at random."""
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    row = model.objects.order_by("?").first()
    return CodeOut(code=row.code if row else "")


@inertia_endpoint
def endpoint_page(request_context: RequestContext) -> InertiaPage[EndpointPageProps]:
    """Inertia page: the first seeded row's code as a prop."""
    row = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE).objects.first()
    return InertiaPage(
        component="EndpointPage", props=EndpointPageProps(code=row.code if row else "")
    )


@backend_test
def test_random_code_returns_a_seeded_code() -> None:
    """A call returns a code drawn from the seeded set."""
    assert random_code(fake_context()).code in ITEMS


@backend_test
def test_random_code_varies() -> None:
    """Over many calls the endpoint returns more than one distinct code."""
    seen = {random_code(fake_context()).code for _ in range(30)}
    assert len(seen) > 1, f"random_code is not random: only got {seen}"
