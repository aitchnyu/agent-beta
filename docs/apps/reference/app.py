# ruff: noqa: INP001, ANN401, ARG001 # template reference app; loaded by path, not a package; Any dynamic model; request param unused by these endpoints
"""Reference app: copy this to ``apps/<app>/`` to start a new app.

Demonstrates the full contract:

- ``@setup`` installs the app + a table;
- ``@get_endpoint current_count`` returns JSON the page fetches (axios + zod);
- ``@get_endpoint reference_page`` renders an Inertia page (via an ``InertiaPage``
  return) with the app's own bundle;
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
    HttpRequest,
    InertiaPage,
    a_test_request,
    backend_test,
    dynamic_models,
    get_endpoint,
    playwright_test,
    setup,
)

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

APP = "ReferenceDemo"
TABLE = "items"


class ReferencePageProps(BaseModel):
    """Props for the ReferencePage component."""

    count: int


class CountOut(BaseModel):
    """The seeded row count, returned by the ``current_count`` GET endpoint."""

    count: int


def _model() -> Any:
    return Application.objects.get(name=APP).table_as_model(TABLE)


@setup
def setup_app() -> None:
    """Create the app/table and seed one row."""
    dynamic_models.create_application(
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    _model().objects.create(code="A1")


@get_endpoint
def current_count(request: HttpRequest) -> CountOut:
    """GET endpoint the page's Refresh button calls (the seeded row count)."""
    return CountOut(count=_model().objects.count())


@get_endpoint
def reference_page(request: HttpRequest) -> InertiaPage[ReferencePageProps]:
    """Inertia page: how many rows are seeded."""
    return InertiaPage(
        component="ReferencePage", props=ReferencePageProps(count=_model().objects.count())
    )


@backend_test
def test_reference_page_count() -> None:
    """The page reports the seeded row count."""
    assert reference_page(a_test_request()).props.count == 1


@playwright_test
def test_reference_page_renders_and_interacts(context: BrowserContext, base_url: str) -> None:
    """The built app mounts, renders the count, and Refresh round-trips the GET endpoint."""
    page = context.new_page()
    try:
        page.goto(f"{base_url}/apps/{APP}/e/reference_page")
        page.wait_for_selector(".ref-count")
        assert page.locator(".ref-count").text_content() == "1"
        page.locator(".ref-refresh").click()
        page.wait_for_selector(".ref-fetched")
        assert page.locator(".ref-fetched").text_content() == "1"
    finally:
        page.close()
