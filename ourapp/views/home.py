"""Home feature — the app's landing page.

Owns the single public route ``/`` (rendered as the Inertia component
``ours/Home``). It shows login state and links to the app's features; the
integer ``pk`` is never exposed, only the ``public_id``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from inertia import InertiaResponse
from ninja import Router

from djangoapp.logging import get_logger
from djangoapp.shortcuts import maybe_user

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = get_logger(__name__)

router = Router()


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
