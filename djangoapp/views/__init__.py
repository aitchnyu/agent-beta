from __future__ import annotations

from typing import cast

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpRequest, HttpResponse
from inertia import render

from djangoapp.models import User


def home(request: HttpRequest) -> HttpResponse:
    """Inertia Home page showing login state.

    Sends ``is_authenticated``, ``display_name`` and ``public_id`` to the
    client. The integer ``pk``/``id`` is never exposed.
    """
    user = request.user
    is_authed = user.is_authenticated and not isinstance(user, AnonymousUser)
    props = {
        "is_authenticated": is_authed,
        "display_name": cast(User, user).display_name if is_authed else "",
        "public_id": cast(User, user).public_id if is_authed else "",
    }
    return render(request, "Home", props)  # type: ignore[no-any-return] # inertia.render is untyped


def login_for_test(request: HttpRequest, userid: int) -> HttpResponse:
    """Log in a user by pk for E2E tests. Debug mode only.

    Bypasses Google OAuth so playwright tests can authenticate. Returns
    a plain-text body the harness asserts on. Disabled (404) outside DEBUG.
    """
    if not settings.DEBUG:
        raise Http404
    try:
        user = User.objects.get(pk=userid)
    except User.DoesNotExist:
        raise Http404 from None
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return HttpResponse(f"Logged in as {user.username}")
