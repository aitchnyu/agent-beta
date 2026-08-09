"""Home feature — the app's landing page.

Owns the single public route ``/`` (rendered as the Inertia component
``ours/Home``). It shows login state and links to the app's features; the
integer ``pk`` is never exposed, only the ``public_id``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from inertia import InertiaResponse
from ninja import Router

from djangoapp.shortcuts import maybe_user

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router()


@router.get("/", response=None)
def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``ours/Home``).

    Anonymous visitors get ``is_authenticated=False`` with empty identity
    fields; an authenticated viewer gets their display name and ``public_id``.
    """
    user = maybe_user(request)
    if user is None:
        props = {
            "is_authenticated": False,
            "display_name": "",
            "public_id": "",
        }
    else:
        props = {
            "is_authenticated": True,
            "display_name": user.display_name,
            "public_id": user.public_id,
        }
    return InertiaResponse(request, "ours/Home", {"props": props})
