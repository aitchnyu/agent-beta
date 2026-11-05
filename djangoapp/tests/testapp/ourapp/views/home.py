"""Home feature — the test app's landing page.

``GET /`` renders the Inertia page ``Home`` with no page props (login
state is the shared viewer prop). Plain Django view: pages never ride a
Router.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from inertia import InertiaResponse

if TYPE_CHECKING:
    from django.http import HttpRequest


def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``Home``), no page props."""
    return InertiaResponse(request, "Home", {"props": {}})
