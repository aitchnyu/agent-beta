# ruff: noqa: INP001, ARG001 # fixture app loaded by file path, not a package; Any dynamic model; required request_context signature
"""Comprehensive fixture app: the happy path + an Inertia page + a browser test.

Covers the full happy path in one app:
- ``@setup`` creates the collection/app + an ``items`` table seeded with rows;
- ``current_code`` (first row) + ``random_code`` (a random row) ``@get_endpoint``s;
- ``demo_page`` is an ``@inertia_endpoint`` rendered with the app's own bundle;
- ``@backend_test``s assert the random endpoint draws from the seed, that it
  varies, and that a backend test's writes roll back (savepoint isolation);
- ``@playwright_test`` drives the built UI (render + Refresh interaction).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    from playwright.sync_api import Page

COLLECTION = "Tests"
APP = "Page"
TABLE = "items"
# Seeded codes; first() is "A1" (what the page + current_code report).
ITEMS = ["A1", "A2", "A3"]


class DemoPageProps(BaseModel):
    """Props for the DemoPage component."""

    label: str


class CodeOut(BaseModel):
    """A row's code, returned by the ``current_code`` / ``random_code`` GET endpoints."""

    code: str


@setup
def setup_app() -> None:
    """Create the Tests/Page app + an items table seeded with several rows."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
    model.objects.bulk_create([model(code=code) for code in ITEMS])


@inertia_endpoint
def demo_page(request_context: RequestContext) -> InertiaPage[DemoPageProps]:
    """Inertia page: the first seeded row's code as a prop."""
    model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
    row = model.objects.first()
    return InertiaPage(component="DemoPage", props=DemoPageProps(label=row.code if row else ""))


@get_endpoint
def current_code(request_context: RequestContext) -> CodeOut:
    """GET endpoint the page's Refresh button calls (the first row's code)."""
    model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
    row = model.objects.first()
    return CodeOut(code=row.code if row else "")


@get_endpoint
def random_code(request_context: RequestContext) -> CodeOut:
    """GET endpoint returning one seeded code at random."""
    model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
    row = model.objects.order_by("?").first()
    return CodeOut(code=row.code if row else "")


@backend_test
def test_random_code_returns_a_seeded_code() -> None:
    """A call returns a code drawn from the seeded set."""
    assert random_code(fake_context()).code in ITEMS


@backend_test
def test_random_code_varies() -> None:
    """Over many calls the endpoint returns more than one distinct code."""
    seen = {random_code(fake_context()).code for _ in range(30)}
    assert len(seen) > 1, f"random_code is not random: only got {seen}"


@backend_test
def test_backend_test_writes_roll_back() -> None:
    """A backend_test's writes must not persist past setup (savepoint isolation)."""
    model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
    before = model.objects.count()
    model.objects.create(code="Tmp")
    assert model.objects.count() == before + 1


@playwright_test
def test_demo_page_renders_and_interacts(page: Page, base_url: str) -> None:
    """The built app mounts, renders the prop, and Refresh round-trips the GET endpoint."""
    page.goto(f"{base_url}/apps/a/Tests/Page/endpoint/inertia/demo_page")
    # Vue mounted + the Inertia prop rendered.
    page.wait_for_selector(".demo-label")
    assert page.locator(".demo-label").text_content() == "A1"
    # Interaction: the button fires current_code and writes the result.
    page.locator(".demo-refresh").click()
    page.wait_for_selector(".demo-fetched")
    assert page.locator(".demo-fetched").text_content() == "A1"
