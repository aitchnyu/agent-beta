# ruff: noqa: INP001, ANN401, ARG001 # template reference app; loaded by path, not a package; Any dynamic model; request param unused by read endpoints
"""Reference app: copy this to ``apps/<app>/`` to start a new app.

Demonstrates the full contract, including the write side:

- ``@setup`` installs the app + a table;
- ``@get_endpoint default`` renders the Inertia landing page at the app root
  ``/apps/<app>`` (GET only);
- ``@get_endpoint current_count`` returns JSON the page fetches (axios + zod);
- ``@post_endpoint add_item`` writes a row, validating the body via ``BaseSchema``
  and returning a 422 (``ninja.errors.ValidationError``) on bad input — never
  indexing the body blindly;
- ``@backend_test`` self-tests the page prop and the POST (happy path + rejection);
- ``@playwright_test`` drives the built UI (render + Refresh) and asserts a POST's
  response (a mutation is visible only within its own request — see the test).

See ``docs/apps/README.md`` for the mandatory-shell checklist + commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ninja.errors import ValidationError as NinjaValidationError
from pydantic import Field, field_validator

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    BaseSchema,
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
CODE_REQUIRED = "code is required"


class ReferencePageProps(BaseModel):
    """Props for the ReferencePage component."""

    count: int


class CountOut(BaseModel):
    """The row count, returned by the ``current_count`` GET endpoint."""

    count: int


class ItemOut(BaseModel):
    """A created item, returned by the ``add_item`` POST endpoint."""

    code: str


class CreateItem(BaseSchema):
    """POST body for ``add_item``: a non-blank ``code`` within the column's max length."""

    code: str = Field(max_length=CODE_MAX_LENGTH)

    @field_validator("code")
    @classmethod
    def _code_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(CODE_REQUIRED)
        return value


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

    ``CreateItem.from_json_request`` parses + validates the body and raises
    ``ninja.errors.ValidationError`` (→ HTTP 422) on bad input — so a
    missing/blank/over-long code or a non-JSON body is a structured 422, never a
    ``KeyError``/500. Returns the created item.
    """
    item = CreateItem.from_json_request(request)
    _model().objects.create(code=item.code)
    return ItemOut(code=item.code)


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
    """Bad input raises ninja ``ValidationError`` (→ 422) with a structured error body.

    ``BaseSchema.from_json_request`` raises ``ninja.errors.ValidationError``, which
    ninja serialises as ``{"detail": [{"loc": [...], "msg": "...", ...}, …]}`` (422).
    Asserting that body — not just that *something* raised — is the pattern to copy.
    """
    with expect_error() as e:  # missing code
        add_item(a_test_request(method="POST", json={}))
    assert isinstance(e.exception, NinjaValidationError)
    with expect_error() as e:  # over the column's max_length
        add_item(a_test_request(method="POST", json={"code": "X" * (CODE_MAX_LENGTH + 1)}))
    assert isinstance(e.exception, NinjaValidationError)
    # Expected 422 body for an over-length `code` (input/url are stripped —
    # see BaseSchema.from_json_request):
    #   {"detail": [
    #     {"type": "string_too_long",
    #      "loc": ["code"],
    #      "msg": "String should have at most 10 characters",
    #      "ctx": {"max_length": 10}}
    #   ]}
    # Validate the exact error: one error, on `code`, naming the length rule.
    err = e.exception.errors[0]
    assert tuple(err["loc"]) == ("code",)
    assert str(CODE_MAX_LENGTH) in err["msg"]
    with expect_error() as e:  # blank/whitespace code → the _code_non_blank validator
        add_item(a_test_request(method="POST", json={"code": "   "}))
    assert isinstance(e.exception, NinjaValidationError)
    # Expected 422 body (a field_validator's ValueError is wrapped):
    #   {"detail": [
    #     {"type": "value_error",
    #      "loc": ["code"],
    #      "msg": "Value error, code is required",
    #      "ctx": {"error": "code is required"}}
    #   ]}
    assert tuple(e.exception.errors[0]["loc"]) == ("code",)
    assert CODE_REQUIRED in e.exception.errors[0]["msg"]
    with expect_error() as e:  # non-JSON body → from_json_request's JSON guard
        add_item(a_test_request(method="POST", data={"not": "json"}))
    assert isinstance(e.exception, NinjaValidationError)
    # Expected 422 body (body isn't JSON; no `type` key — not a pydantic field error):
    #   {"detail": [
    #     {"loc": ["body"], "msg": "Request body must be valid JSON."}
    #   ]}


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
