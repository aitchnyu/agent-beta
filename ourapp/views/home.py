"""Home feature — the app's landing page (plus the mockup hatch route).

Owns the single public route ``/`` (rendered as the Inertia component
``Home``). It shows login state and links to the app's features; the
integer ``pk`` is never exposed, only the ``public_id``. Both routes
are PLAIN Django views (pages never ride a ninja Router — that is for
JSON APIs only; see steer.md § View/router shapes).
"""

from __future__ import annotations

import base64
import json
import typing
from typing import TYPE_CHECKING

from django.http import HttpResponseBase, JsonResponse
from inertia import InertiaResponse
from pydantic import RootModel, ValidationError, model_validator

from djangoapp.logging import get_logger
from djangoapp.shortcuts import maybe_user
from djangoapp.views import require_superuser

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = get_logger(__name__)


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


def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``Home``).

    Login state is the shared viewer prop (``user``, injected on every page
    by SharedPropsMiddleware).
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
    return InertiaResponse(request, "Home", {"props": {}})


def mockup_page(request: HttpRequest, page: str) -> HttpResponseBase:
    """Render the Inertia component ``<page>`` — one route hosts every mockup.

    - The URL carries the component name verbatim:
      ``/mockup/MockupTodos`` → ``MockupTodos``
    - adding a mockup is a single ``frontend/src/app/pages/<name>.vue`` —
      the backend never changes and ``./run deployscratch`` takes the fast
      deploy path
    - mockups keep the three markers from ``agentconfig/steer.md``
      § Mockups: superuser-only route (404 otherwise), no data plumbing
      (no props, no DB), component wraps in ``div.mockup``
    - ``?props=<base64url JSON object>`` presets the page's props — deep-link
      a mockup's client-side state (still nothing saves). The raw query
      string is validated in-view by the schema; a bad value is a
      standard 422.
    """
    require_superuser(request)
    page_props: dict[str, typing.Any] = {}
    props = request.GET.get("props")
    if props is not None:
        try:
            page_props = _B64JsonProps.model_validate(props).root
        except ValidationError as exc:
            # A 422 like any other bad endpoint input.
            msg = exc.errors()[0]["msg"]
            return JsonResponse({"detail": msg}, status=422)
    return InertiaResponse(request, page, {"props": page_props})
