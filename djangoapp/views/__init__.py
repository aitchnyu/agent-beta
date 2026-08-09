from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login
from django.http import Http404, HttpRequest, HttpResponse

from djangoapp.models import User


def require_superuser(request: HttpRequest) -> None:
    """Gate a view to a superuser, else 404 (never 403).

    Shared by the superuser-only read views (``/manage/models``, ``/agent/``,
    ``/files/...``). A 404 (not 403) keeps the page's existence hidden from
    unauthenticated / non-superuser viewers.
    """
    viewer = request.user
    if not (viewer.is_authenticated and viewer.is_superuser):
        raise Http404


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
