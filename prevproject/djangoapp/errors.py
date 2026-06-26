"""Consistent API error handling for all ninja endpoints.

``ApiError`` is the single exception type raised from API/submit operations.
``register_api_error_handlers`` installs handlers for ``ApiError`` and ``Http404``
on a ``NinjaAPI`` so every JSON error carries a client-facing message.

Only ninja-handled routes (``NinjaAPI.urls`` and the ``Router`` ops registered
via ``BaseView.get_router``) are affected. Django ``path()`` page views keep
raising ``Http404`` and render the HTML 404 page as before.
"""

from typing import TYPE_CHECKING

from django.http import Http404, HttpRequest, HttpResponse
from ninja.errors import HttpError

if TYPE_CHECKING:
    from ninja import NinjaAPI
    from ninja.types import DictStrAny


class ApiError(HttpError):
    """API error carrying an optional structured payload.

    When ``payload`` is given it replaces the JSON response body verbatim
    (e.g. ``{"code": "dup", "message": "Tag exists"}``); ``message`` is kept
    only for logging and ``str()``. When ``payload`` is ``None`` the body is
    ``{"detail": message}``, matching ninja's default ``HttpError`` contract so
    existing frontend code that reads ``response.data.detail`` keeps working.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        payload: DictStrAny | None = None,
    ) -> None:
        super().__init__(status_code, message)
        self.payload = payload


def register_api_error_handlers(api: NinjaAPI) -> None:
    """Register ``ApiError`` and ``Http404`` JSON handlers on ``api``.

    The ``Http404`` override propagates the exception's message (previously
    discarded by ninja's default ``{"detail": "Not Found"}``), so model helpers
    like ``Article.get_or_404`` surface a useful message from API endpoints.
    """

    @api.exception_handler(ApiError)
    def on_api_error(request: HttpRequest, exc: ApiError) -> HttpResponse:
        body: DictStrAny = exc.payload if exc.payload is not None else {"detail": str(exc)}
        return api.create_response(request, body, status=exc.status_code)

    @api.exception_handler(Http404)
    def on_http_404(request: HttpRequest, exc: Exception) -> HttpResponse:
        return api.create_response(request, {"detail": str(exc) or "Not Found"}, status=404)
