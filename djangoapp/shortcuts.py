"""Project shortcuts: small request/user helpers.

Mirrors ``django.shortcuts``'s role — tiny, importable-from-anywhere helpers
used by both the framework and ``ourapp``: views import ``maybe_user`` /
``user_or_404`` (which avoid the ``request.user`` ``User | AnonymousUser`` typing
trap by narrowing here, not at every call site).
"""

from __future__ import annotations

from django.http import Http404, HttpRequest

from djangoapp.models import User

__all__ = ["maybe_user", "user_or_404"]


def maybe_user(request: HttpRequest) -> User | None:
    """Return the authenticated ``User``, or ``None`` for an anonymous request.

    Use for optional-auth lookups. Narrows ``request.user``
    (``User | AnonymousUser``) once, here, instead of ``# type: ignore`` at each
    call site.
    """
    user = request.user
    return user if isinstance(user, User) else None


def user_or_404(request: HttpRequest) -> User:
    """Return the authenticated ``User``, or raise ``Http404``.

    Anonymous access reads as "not found" (the resource is private to its owner)
    rather than 401/403, so a page's existence stays hidden from anon users.
    """
    user = maybe_user(request)
    if user is None:
        raise Http404
    return user
