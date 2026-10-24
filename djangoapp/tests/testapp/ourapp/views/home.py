"""Home feature — the test app's landing page.

``GET /`` renders the Inertia page ``Home`` with no page props (login
state is the shared viewer prop). The component name is irrelevant to the
server-side project tests; this view exists so ``GET /`` resolves to an
Inertia page (the framework no longer owns a home route).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from inertia import InertiaResponse
from ninja import Router

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router()


@router.get("/", response=None)
def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``Home``), no page props."""
    return InertiaResponse(request, "Home", {"props": {}})
