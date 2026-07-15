# ruff: noqa: INP001, ARG001 # fixture app loaded by file path, not a package; required request_context signature
"""Minimal fixture app dedicated to buildfrontend's browser phase.

A focused counterpart to ``Tests/Page`` (the comprehensive demo): just enough to
exercise ``buildfrontend`` end to end — ``@setup`` seeds one row, an
``@inertia_endpoint`` renders it with the app's own bundle, and a
``@playwright_test`` does a real browser-based assertion (mount + Refresh
interaction).

The rollback-proof ``@playwright_test``s exercise both of buildfrontend's rollback
layers so ``BuildFrontendDrivesPlaywrightTests`` can assert the drive left the DB
unchanged:

- an in-process write (rolled back by the drive's ``transaction.atomic``);
- a browser insert and a browser modify of the existing seed row (each visible
  only for its request, then rolled back by ``RollbackEveryRequestMiddleware``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    CharColumn,
    InertiaPage,
    RequestContext,
    dynamic_models,
    get_endpoint,
    inertia_endpoint,
    playwright_test,
    setup,
)

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

COLLECTION = "Tests"
APP = "Browser"
TABLE = "items"
SEED = "hi"
# Codes the browser rollback-proof @playwright_test writes; within the ``code``
# column's max_length=10 so the inserts/updates validate.
BROWSER_WRITE = "bw1"  # code create_row inserts (browser write; middleware reverts)
MODIFY_TO = "modified"  # code modify_seed sets on the seed (browser write; middleware reverts)


class BrowserPageProps(BaseModel):
    """Props for the BrowserPage component."""

    value: str


class ValueOut(BaseModel):
    """The seeded value, returned by the ``current_value`` GET endpoint."""

    value: str


class CreatedOut(BaseModel):
    """The code ``create_row`` inserted, returned to the browser within the request."""

    created: str


class ModifiedOut(BaseModel):
    """The seed's new code after ``modify_seed``, returned within the request."""

    value: str


@setup
def setup_app() -> None:
    """Create the Tests/Browser app + an items table seeded with one row."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    Application.get_by_names(COLLECTION, APP).table_as_model(TABLE).objects.create(code=SEED)


@inertia_endpoint
def browser_page(request_context: RequestContext) -> InertiaPage[BrowserPageProps]:
    """Inertia page: the seeded row's code as a prop."""
    row = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE).objects.first()
    return InertiaPage(
        component="BrowserPage", props=BrowserPageProps(value=row.code if row else "")
    )


@get_endpoint
def current_value(request_context: RequestContext) -> ValueOut:
    """GET endpoint the page's Refresh button calls (the seeded value)."""
    row = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE).objects.first()
    return ValueOut(value=row.code if row else "")


@get_endpoint
def create_row(request_context: RequestContext) -> CreatedOut:
    """Insert a row — a browser-triggered write the rollback middleware reverts per request.

    Exists only so a ``@playwright_test`` can trigger a write over HTTP (the app
    framework exposes only ``@get_endpoint`` GETs): the insert is visible within
    this request's response, then ``RollbackEveryRequestMiddleware`` rolls it back.
    """
    Application.get_by_names(COLLECTION, APP).table_as_model(TABLE).objects.create(
        code=BROWSER_WRITE
    )
    return CreatedOut(created=BROWSER_WRITE)


@get_endpoint
def modify_seed(request_context: RequestContext) -> ModifiedOut:
    """Update the seed row's code — a browser-triggered write reverted per request.

    Like :func:`create_row`, a test-fixture-only side-effecting GET: the new code
    is visible within this request's response, then rolled back.
    """
    row = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE).objects.get(code=SEED)
    row.code = MODIFY_TO
    row.save()
    return ModifiedOut(value=MODIFY_TO)


@playwright_test
def test_page_renders_seed(context: BrowserContext, base_url: str) -> None:
    """The built app mounts, renders the seed, and Refresh round-trips the GET endpoint."""
    page = context.new_page()
    try:
        page.goto(f"{base_url}/apps/a/{COLLECTION}/{APP}/endpoint/inertia/browser_page")
        page.wait_for_selector(".browser-value")
        assert page.locator(".browser-value").text_content() == SEED
        page.locator(".browser-refresh").click()
        page.wait_for_selector(".browser-fetched")
        assert page.locator(".browser-fetched").text_content() == SEED
    finally:
        page.close()


# Marker the rollback-probe test writes in-process. Short enough for the code
# column (CharColumn max_length=10). buildfrontend's drive wraps each @playwright_test
# in a rolled-back savepoint, so this row never commits;
# BuildFrontendDrivesPlaywrightTests asserts it's gone after the drive (end-to-end
# rollback proof).
ROLLBACK_PROBE = "smoke"


@playwright_test
def test_inprocess_write_is_visible_to_self(context: BrowserContext, base_url: str) -> None:
    """An in-process write is visible to the test on its own connection.

    Writes a probe row; visible here (same connection), but buildfrontend wraps the
    test in a rolled-back savepoint so it never commits — the server's separate
    connection can't see it, hence no browser verify. BuildFrontendDrivesPlaywrightTests
    asserts the probe is gone after the drive.
    """
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    model.objects.create(code=ROLLBACK_PROBE)
    assert model.objects.filter(code=ROLLBACK_PROBE).exists()


@playwright_test
def test_browser_insert_round_trips(context: BrowserContext, base_url: str) -> None:
    """An insert via the browser is visible within its request, then reverts.

    ``context.request.get`` is a real live-server request through the rollback
    middleware; the inserted code is in the response (visible for the request's
    lifetime), and the middleware rolls it back after.
    """
    resp = context.request.get(f"{base_url}/apps/a/{COLLECTION}/{APP}/endpoint/get/create_row")
    assert resp.ok
    assert resp.json()["created"] == BROWSER_WRITE


@playwright_test
def test_browser_modify_round_trips(context: BrowserContext, base_url: str) -> None:
    """Modifying an existing row via the browser is visible within its request, then reverts.

    The seed's new code is in the response (visible for the request's lifetime);
    the middleware rolls the update back after, so the seed keeps its original
    value.
    """
    resp = context.request.get(f"{base_url}/apps/a/{COLLECTION}/{APP}/endpoint/get/modify_seed")
    assert resp.ok
    assert resp.json()["value"] == MODIFY_TO
