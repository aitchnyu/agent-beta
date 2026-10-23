"""Home feature — the app's landing page (plus the mockup hatch route).

Owns the single public route ``/`` (rendered as the Inertia component
``ours/Home``). It shows login state and links to the app's features; the
integer ``pk`` is never exposed, only the ``public_id``.
"""

from __future__ import annotations

import base64
import json
import typing
from typing import TYPE_CHECKING

from inertia import InertiaResponse
from ninja import Router
from ninja.errors import HttpError
from pydantic import RootModel, ValidationError, model_validator

from djangoapp.logging import get_logger
from djangoapp.shortcuts import maybe_user
from djangoapp.views import require_superuser

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = get_logger(__name__)

router = Router()


class _B64JsonProps(RootModel[dict[str, typing.Any]]):
    """``?props=<base64url JSON object>`` — decoded by schema validation.

    A value that is not base64url JSON (or not an object) is a standard
    ninja validation error (422), like every other bad endpoint input.
    """

    @model_validator(mode="before")
    @classmethod
    def _decode(cls, value: typing.Any) -> typing.Any:  # noqa: ANN401 # pydantic hands the validator raw input
        if not isinstance(value, str):
            return value
        padded = value + "=" * (-len(value) % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        # RecursionError: deeply-nested JSON (json.loads parses recursively).
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            msg = "props must be a base64url-encoded JSON object"
            raise ValueError(msg) from exc


@router.get("/", response=None)
def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``ours/Home``).

    Anonymous visitors get ``is_authenticated=False`` with empty identity
    fields; an authenticated viewer gets their display name and ``public_id``.
    """
    user = maybe_user(request)
    # Example structured log lines (see agentconfig/steer.md § Logging). The
    # event is a short human phrase (spaces, not snake_case); key/value fields
    # make the line jq-filterable. method/path/user_public_id/username are
    # already bound by LoggingContextMiddleware, so they're not repeated here.
    if user is None:
        logger.info("home viewed", viewer="anonymous")
    else:
        logger.info("home viewed", viewer=user.username)
    props = (
        {
            "is_authenticated": False,
            "display_name": "",
            "public_id": "",
        }
        if user is None
        else {
            "is_authenticated": True,
            "display_name": user.display_name,
            "public_id": user.public_id,
        }
    )
    return InertiaResponse(request, "ours/Home", {"props": props})


@router.get("/mockup/{page}", response=None)
def mockup_page(
    request: HttpRequest,
    page: str,
    props: str | None = None,
) -> InertiaResponse:
    """Render the Inertia component ``ours/<page>`` — one route hosts every mockup.

    - The URL carries the component name verbatim:
      ``/mockup/MockupTodos`` → ``ours/MockupTodos``
    - adding a mockup is a single ``frontend/src/ours/pages/<name>.vue`` —
      the backend never changes and ``./run deployscratch`` takes the fast
      deploy path
    - mockups keep the three markers from ``agentconfig/steer.md``
      § Mockups: superuser-only route (404 otherwise), no data plumbing
      (no props, no DB), component wraps in ``div.mockup``
    - ``?props=<base64url JSON object>`` presets the page's props — deep-link
      a mockup's client-side state (still nothing saves)
    """
    require_superuser(request)
    page_props: dict[str, typing.Any] = {}
    if props is not None:
        try:
            page_props = _B64JsonProps.model_validate(props).root
        except ValidationError as exc:
            # A 422 like any other bad endpoint input.
            raise HttpError(422, exc.errors()[0]["msg"]) from exc
    return InertiaResponse(request, f"ours/{page}", {"props": page_props})
