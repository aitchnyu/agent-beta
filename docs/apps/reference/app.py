# ruff: noqa: INP001, ANN401, ARG001 # template reference app; loaded by path, not a package; Any dynamic model; required request_context signature
"""Reference app: copy this to ``apps/<collection>/<app>/`` to start a new app.

Demonstrates the full contract:

- ``@setup`` installs the collection/app + a table;
- ``@get_endpoint current_count`` returns JSON the page fetches (axios + zod);
- ``@inertia_endpoint reference_page`` renders an Inertia page with the app's own
  bundle;
- ``@backend_test`` self-tests the page prop;
- ``@playwright_test`` drives the built UI (render + Refresh interaction).

See ``docs/apps/README.md`` for the mandatory-shell checklist + commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    playwright_test,
    setup,
)

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

COLLECTION = "Reference"
APP = "Demo"
TABLE = "items"


class ReferencePageProps(BaseModel):
    """Props for the ReferencePage component."""

    count: int


class CountOut(BaseModel):
    """The seeded row count, returned by the ``current_count`` GET endpoint."""

    count: int


def _model() -> Any:
    return Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)


@setup
def setup_app() -> None:
    """Create the collection/app/table and seed one row."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    _model().objects.create(code="A1")


@get_endpoint
def current_count(request_context: RequestContext) -> CountOut:
    """GET endpoint the page's Refresh button calls (the seeded row count)."""
    return CountOut(count=_model().objects.count())


@inertia_endpoint
def reference_page(request_context: RequestContext) -> InertiaPage[ReferencePageProps]:
    """Inertia page: how many rows are seeded."""
    return InertiaPage(
        component="ReferencePage", props=ReferencePageProps(count=_model().objects.count())
    )


@backend_test
def test_reference_page_count() -> None:
    """The page reports the seeded row count."""
    assert reference_page(fake_context()).props.count == 1


@playwright_test
def test_reference_page_renders_and_interacts(context: BrowserContext, base_url: str) -> None:
    """The built app mounts, renders the count, and Refresh round-trips the GET endpoint."""
    page = context.new_page()
    try:
        page.goto(f"{base_url}/apps/a/Reference/Demo/endpoint/inertia/reference_page")
        page.wait_for_selector(".ref-count")
        assert page.locator(".ref-count").text_content() == "1"
        page.locator(".ref-refresh").click()
        page.wait_for_selector(".ref-fetched")
        assert page.locator(".ref-fetched").text_content() == "1"
    finally:
        page.close()
