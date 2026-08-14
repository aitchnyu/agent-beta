"""Home feature — the test app's landing page.

``GET /`` renders the Inertia page ``ours/Home`` with login-state props only.
The component name is irrelevant to the server-side project tests; this view
exists so ``GET /`` resolves to an Inertia page (the framework no longer owns
a home route).
"""

from __future__ import annotations

from django.http import HttpRequest
from inertia import InertiaResponse
from ninja import Router

from djangoapp.shortcuts import maybe_user

router = Router()


@router.get("/", response=None)
def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``ours/Home``), login-state only."""
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
