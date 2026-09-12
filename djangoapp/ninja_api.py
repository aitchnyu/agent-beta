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

import http
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from ninja import NinjaAPI, Router
from ninja.errors import HttpError
from ninja.utils import check_csrf

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


def _wants_html(request: HttpRequest) -> bool:
    """Return True for a browser navigation, False for API/XHR clients.

    Browsers send ``Accept: text/html, …`` on navigations; every API client
    this app has (Inertia visits, ky, useHttp) sends ``application/json``.
    Django's test client sends ``*/*``, so tests keep exercising the JSON
    contract unchanged.
    """
    return "text/html" in request.headers.get("Accept", "") and not request.headers.get("X-Inertia")


def register_api_error_handlers(api: NinjaAPI) -> None:
    """Register friendly, leak-free JSON handlers on ``api``."""

    @api.exception_handler(ApiError)
    def on_api_error(request: HttpRequest, exc: ApiError) -> HttpResponse:
        # str(exc) will return exc.message, thanks to HttpError __str__.
        if exc.status_code == http.HTTPStatus.NOT_FOUND and _wants_html(request):
            # ApiError messages are developer-authored and client-facing (the
            # class contract), so a browser navigation shows the message on
            # the HTML 404 page instead of raw JSON.
            return render(request, "404.html", {"message": str(exc)}, status=exc.status_code)
        body: DictStrAny = exc.payload if exc.payload is not None else {"detail": str(exc)}
        return api.create_response(request, body, status=exc.status_code)

    @api.exception_handler(Http404)
    def on_http_404(request: HttpRequest, _exc: Exception) -> HttpResponse:
        # Reveal the requested path (the user's own input — never a server-internal
        # leak) so a 404 names what wasn't found; never str(exc), which a message-
        # carrying Http404 could use to leak internals (use ApiError(404, …) for a
        # fully custom message).
        detail = f"{_NOT_FOUND}: {request.path}"
        if _wants_html(request):
            # A browser navigation (Accept: text/html) gets the same message
            # rendered on the HTML 404 page instead of raw JSON.
            return render(request, "404.html", {"message": detail}, status=404)
        return api.create_response(request, {"detail": detail}, status=404)

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


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class _CsrfPrincipal:
    """Truthy sentinel ``request.auth`` value set when the guard passes.

    Not an identity — a bare ``True`` would invite ``if request.auth:``
    identity checks later; the repr makes log/debug output self-describing.
    """

    def __repr__(self) -> str:
        return "<csrf-guard-passed>"


_CSRF_PRINCIPAL = _CsrfPrincipal()


def csrf_guard(request: HttpRequest) -> _CsrfPrincipal:
    """Django's CSRF check (token + Origin/Referer) on unsafe methods.

    Installed by ``make_ninja_api`` as the API-level ``auth`` — ninja
    otherwise exempts its views from ``CsrfViewMiddleware``. Safe methods
    and ``csrf=False`` mounts pass. Returns a truthy sentinel (a None return
    ninja reads as auth failure); an explicit ``auth=`` override replaces
    this guard entirely.
    """
    if request.method not in _SAFE_METHODS and check_csrf(request) is not None:
        # check_csrf runs the real CsrfViewMiddleware logic (token match +
        # Origin/Referer); non-None is its rejection.
        raise ApiError(403, "CSRF verification failed.")
    return _CSRF_PRINCIPAL


def make_ninja_api(
    name: str,
    router: Router,
    *,
    prefix: str | None = None,
    csrf: bool = True,
) -> NinjaAPI:
    """Build an app NinjaAPI: URL namespace, error handlers, and router mount.

    ``prefix`` defaults to ``name``; pass ``""`` to mount the router at the API
    root (used when the API is itself mounted under a URL path, e.g. opencode).

    CSRF is ON by default via the API-level ``csrf_guard`` auth (token +
    Origin/Referer on unsafe methods). Pass ``csrf=False`` only for anonymous
    sinks where tokenless POSTs are the point — and say why at the call site.
    """
    api = NinjaAPI(
        urls_namespace=f"{name}-http",
        auth=csrf_guard if csrf else None,
    )
    register_api_error_handlers(api)
    api.add_router(prefix if prefix is not None else name, router)
    return api
