"""Inertia request middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from inertia import share

from djangoapp.logging import bind_log_context, clear_log_context, get_logger
from djangoapp.models import User, UserProfile
from djangoapp.shortcuts import maybe_user

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


def _viewer_profile(user: object) -> UserProfile | None:
    """Build the shared viewer profile, or None when anonymous."""
    if not getattr(user, "is_authenticated", False):
        return None
    viewer = cast("User", user)
    return UserProfile(public_id=viewer.public_id, title=viewer.display_name)


class LoggingContextMiddleware:
    """Bind per-request fields into the log context and log the request.

    ``method``, ``path`` and the viewer identity (``user_public_id``,
    ``username``) are bound into structlog's contextvars so every log line
    emitted during the request carries them — no per-call boilerplate. The
    integer ``pk`` is never logged (the app is pk-free; only ``public_id`` is
    exposed, in logs as elsewhere).

    Runs after ``AuthenticationMiddleware`` (so ``request.user`` is resolved)
    and clears its contextvars in ``finally`` (runserver reuses threads, so a
    leak would smear one request's identity into the next).
    """

    def __init__(self, get_response: Callable[..., HttpResponse]) -> None:
        self.get_response = get_response
        self._logger = get_logger("djangoapp.request")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = maybe_user(request)
        tokens = bind_log_context(
            method=request.method,
            path=request.path,
            user_public_id=user.public_id if user is not None else None,
            username=user.username if user is not None else None,
        )
        # Log + serve inside the try so clear_log_context runs on every path
        # (a failure in the log line or get_response must not leak the bound
        # identity onto the next request reusing this thread).
        try:
            # One request log line carrying the authoritative viewer identity
            # (server-side source of truth; never trusted from the client).
            self._logger.info(
                "http request",
                method=request.method,
                path=request.path,
                user_public_id=user.public_id if user is not None else None,
                username=user.username if user is not None else None,
            )
            response = self.get_response(request)
        finally:
            clear_log_context(tokens)
        return response


class SharedPropsMiddleware:
    """Share the viewer profile + superuser flag on every Inertia page.

    ``share`` makes the viewer profile (``user``) and superuser flag
    (``viewer_is_superuser``) available to every page via ``usePage().props``,
    so views need not thread them per-page. pk-free: only the URL-safe
    ``public_id`` is sent.
    """

    def __init__(self, get_response: Callable[..., HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        profile = _viewer_profile(request.user)
        user = request.user
        share(
            request,
            user=profile.model_dump() if profile else None,
            viewer_is_superuser=bool(
                getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False)
            ),
        )
        return self.get_response(request)
