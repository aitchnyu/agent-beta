"""Consistent JSON error handling + API setup for all ninja endpoints.

``ApiError`` is the single exception type raised from API/submit operations
with a developer-authored, client-facing message. ``register_api_error_handlers``
installs handlers on a ``NinjaAPI`` so every error is a friendly, leak-free JSON
body:

- ``ApiError``  → its own message/payload (controlled by the view).
- ``Http404`` → ``"Not found: <path>"`` (the requested path is the user's own
  input, safe to echo) — never ``str(exc)``, which could leak internals. A fully
  custom message belongs in ``ApiError``.
- ``PermissionDenied`` → a friendly 403. Registered explicitly so it keeps its
  status code instead of falling through to the catch-all below (→ 500).
- any other ``Exception`` → a generic ``"Something went wrong…"`` (the real
  exception is logged with a traceback server-side; the body never echoes it).
"""

from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from ninja import NinjaAPI, Router
from ninja.errors import HttpError

from djangoapp.logging import get_logger

if TYPE_CHECKING:
    from ninja.types import DictStrAny

logger = get_logger(__name__)

# Fixed, leak-free messages for error classes that shouldn't echo internals.
_NOT_FOUND = (
    "This is a 404. We couldn't show you what you were looking for or complete that "
    "action. This usually happens when the page has moved, the link has expired, "
    "or access is restricted."
)
_FORBIDDEN = "You don't have permission to do that."
_INTERNAL = "Something went wrong. Please try again, or reload if it keeps happening."


class ApiError(HttpError):
    """API error carrying an optional structured payload.

    When ``payload`` is given it replaces the JSON response body verbatim;
    ``message`` is kept only for logging and ``str()``. When ``payload`` is
    ``None`` the body is ``{"detail": message}``, matching ninja's default
    ``HttpError`` contract so frontend code reading ``response.data.detail``
    keeps working.
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
    """Register friendly, leak-free JSON handlers on ``api``."""

    @api.exception_handler(ApiError)
    def on_api_error(request: HttpRequest, exc: ApiError) -> HttpResponse:
        # str(exc) will return exc.message, thanks to HttpError __str__.
        body: DictStrAny = exc.payload if exc.payload is not None else {"detail": str(exc)}
        return api.create_response(request, body, status=exc.status_code)

    @api.exception_handler(Http404)
    def on_http_404(request: HttpRequest, _exc: Exception) -> HttpResponse:
        # Reveal the requested path (the user's own input — never a server-internal
        # leak) so a 404 names what wasn't found; never str(exc), which a message-
        # carrying Http404 could use to leak internals (use ApiError(404, …) for a
        # fully custom message).
        return api.create_response(request, {"detail": f"{_NOT_FOUND}: {request.path}"}, status=404)

    @api.exception_handler(PermissionDenied)
    def on_permission_denied(request: HttpRequest, _exc: Exception) -> HttpResponse:
        return api.create_response(request, {"detail": _FORBIDDEN}, status=403)

    @api.exception_handler(Exception)
    def on_unexpected(request: HttpRequest, exc: Exception) -> HttpResponse:
        # .exception() attaches exc_info (dict_tracebacks renders it as a
        # structured traceback); method/path come from LoggingContextMiddleware,
        # but echo them + the error type so the record is self-describing even
        # outside a request log.
        logger.exception(
            "unhandled exception",
            method=request.method,
            path=request.path,
            error_type=type(exc).__name__,
        )
        return api.create_response(request, {"detail": _INTERNAL}, status=500)


def make_ninja_api(name: str, router: Router, *, prefix: str | None = None) -> NinjaAPI:
    """Build an app NinjaAPI: URL namespace, error handlers, and router mount.

    ``prefix`` defaults to ``name``; pass ``""`` to mount the router at the API
    root (used when the API is itself mounted under a URL path, e.g. opencode).
    """
    api = NinjaAPI(urls_namespace=f"{name}-http")
    register_api_error_handlers(api)
    api.add_router(prefix if prefix is not None else name, router)
    return api
