"""Inertia request middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from inertia import share

from djangoapp.models import User, UserProfile

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


def _viewer_profile(user: object) -> UserProfile | None:
    """Build the shared viewer profile, or None when anonymous."""
    if not getattr(user, "is_authenticated", False):
        return None
    viewer = cast("User", user)
    return UserProfile(public_id=viewer.public_id, title=viewer.display_name)


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
