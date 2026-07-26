# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""SchemaApp: a POST endpoint using ``BaseSchema``, for the HTTP-level 422 test.

Feeds ``EndpointViewTests.test_base_schema_422_over_http``: a valid body serves
200; an invalid body is rendered as HTTP **422** with the structured
``{"detail": [...]}`` body (not a 500). The in-process ``BaseSchemaTests`` prove
``from_json_request`` raises ``ninja.errors.ValidationError``; this fixture proves
the app-endpoint → ninja-handler seam surfaces it as HTTP 422. No tables — ``echo``
only validates the body.
"""

from __future__ import annotations

from pydantic import Field

from djangoapp.apps.shortcuts import (
    BaseSchema,
    HttpRequest,
    dynamic_models,
    post_endpoint,
    setup,
)


class EchoIn(BaseSchema):
    """POST body for ``echo``: a non-empty ``name``."""

    name: str = Field(min_length=1)


@setup
def setup_app() -> None:
    """Create the app row (no tables — echo only validates the body)."""
    dynamic_models.create_application(name="SchemaApp")


@post_endpoint
def echo(request: HttpRequest) -> EchoIn:
    """Echo the validated body back; 422 (via BaseSchema) on a bad body."""
    return EchoIn.from_json_request(request)
