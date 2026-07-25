# ruff: noqa: INP001, ANN401, ARG001 # template reference app; loaded by path, not a package; Any dynamic model; request param unused by read endpoints
"""Reference app: copy this to ``apps/<app>/`` to start a new app.

Demonstrates the full contract, including the write side:

- ``@setup`` installs the app + a table;
- ``@get_endpoint default`` renders the Inertia landing page at the app root
  ``/apps/<app>`` (GET only);
- ``@get_endpoint current_count`` returns JSON the page fetches (axios + zod);
- ``@post_endpoint add_item`` writes a row, validating the body and returning a
  400 on bad input (django-ninja ``HttpError``) — never indexing the body blindly;
- ``@backend_test`` self-tests the page prop and the POST (happy path + rejection);
- ``@playwright_test`` drives the built UI (render + Refresh) and asserts a POST's
  response (a mutation is visible only within its own request — see the test).

See ``docs/apps/README.md`` for the mandatory-shell checklist + commands.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ninja.errors import HttpError

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    CharColumn,
    HttpRequest,
    InertiaPage,
    a_test_request,
    backend_test,
    dynamic_models,
    expect_error,
    get_endpoint,
    playwright_test,
    post_endpoint,
    setup,
)

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

APP = "ReferenceDemo"
TABLE = "items"
CODE_MAX_LENGTH = 10
BAD_REQUEST = 400
CODE_REQUIRED = "'code' is required."
CODE_TOO_LONG = f"'code' must be {CODE_MAX_LENGTH} chars or fewer."


class ReferencePageProps(BaseModel):
    """Props for the ReferencePage component."""

    count: int


class CountOut(BaseModel):
    """The row count, returned by the ``current_count`` GET endpoint."""

    count: int


class ItemOut(BaseModel):
    """A created item, returned by the ``add_item`` POST endpoint."""

    code: str


def _model() -> Any:
    return Application.app_or_404(APP).table_as_model(TABLE)


@setup
def setup_app() -> None:
    """Create the app/table and seed one row."""
    dynamic_models.create_application(
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=CODE_MAX_LENGTH)]},
    )
    _model().objects.create(code="A1")


@get_endpoint
def default(request: HttpRequest) -> InertiaPage[ReferencePageProps]:
    """App root (``/apps/<app>``): the Inertia landing page with the row count."""
    return InertiaPage(
        component="ReferencePage",
        props=ReferencePageProps(count=_model().objects.count()),
    )


@get_endpoint
def current_count(request: HttpRequest) -> CountOut:
    """GET endpoint the page's Refresh button calls (the row count)."""
    return CountOut(count=_model().objects.count())


@post_endpoint
def add_item(request: HttpRequest) -> ItemOut:
    """Create a row from a JSON body ``{"code": "..."}``.

    Validate the body and return a 400 on bad input (django-ninja ``HttpError``) —
    never index the body blindly, since a missing key would raise ``KeyError`` and
    500. Returns the created item.
    """
    data = json.loads(request.body or "{}")
    code = data.get("code")
    if not isinstance(code, str) or not code.strip():
        raise HttpError(BAD_REQUEST, CODE_REQUIRED)
    if len(code) > CODE_MAX_LENGTH:
        raise HttpError(BAD_REQUEST, CODE_TOO_LONG)
    code = code.strip()
    _model().objects.create(code=code)
    return ItemOut(code=code)


@backend_test
def test_default_reports_count() -> None:
    """The landing page reports the seeded row count."""
    assert default(a_test_request()).props.count == 1


@backend_test
def test_add_item_creates_and_returns() -> None:
    """A POST with a valid body inserts the row and returns it (within the savepoint)."""
    out = add_item(a_test_request(method="POST", json={"code": "X9"}))
    assert out.code == "X9"
    assert _model().objects.filter(code="X9").exists()


@backend_test
def test_add_item_rejects_bad_input() -> None:
    """Bad input raises HttpError (400) instead of 500-ing on a KeyError/DB error."""
    with expect_error() as e:  # missing code
        add_item(a_test_request(method="POST", json={}))
    assert isinstance(e.exception, HttpError)
    with expect_error() as e:  # over the column's max_length
        add_item(a_test_request(method="POST", json={"code": "X" * (CODE_MAX_LENGTH + 1)}))
    assert isinstance(e.exception, HttpError)
    assert e.exception.status_code == BAD_REQUEST


@playwright_test
def test_reference_page_renders_and_interacts(context: BrowserContext, base_url: str) -> None:
    """Render at the app root, then a Refresh GET and an Add POST.

    The Add insert reverts after the request (the rollback middleware), so the
    POST response — not a later page load — is what's asserted.
    """
    # No try/finally page.close(): the driver closes each test's BrowserContext
    # (and its pages) after it returns — see buildfrontend._drive_playwright_tests.
    page = context.new_page()
    page.goto(f"{base_url}/apps/{APP}")  # app root → the `default` endpoint
    page.wait_for_selector(".ref-count")
    assert page.locator(".ref-count").text_content() == "1"
    page.locator(".ref-refresh").click()
    page.wait_for_selector(".ref-fetched")
    assert page.locator(".ref-fetched").text_content() == "1"
    # A mutation is visible only within its own request's response — it reverts
    # before the next GET, so assert the POST response, not a later page load.
    resp = context.request.post(
        f"{base_url}/apps/{APP}/e/add_item",
        data={"code": "ADDED9"},  # unique marker
    )
    assert resp.ok
    assert resp.json()["code"] == "ADDED9"
