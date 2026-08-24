from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect

from djangoapp.models import TestLoginKey


def require_superuser(request: HttpRequest) -> None:
    """Gate a view to a superuser, else 404 (never 403).

    Shared by the superuser-only read views (``/manage/models``,
    ``/files/...``). A 404 (not 403) keeps the page's existence hidden from
    unauthenticated / non-superuser viewers. (The web console lives at
    /agent under caddy — no Django route.)
    """
    viewer = request.user
    if not (viewer.is_authenticated and viewer.is_superuser):
        raise Http404


def agent_auth(request: HttpRequest) -> HttpResponse:
    """Caddy forward_auth verdict for /agent/* (the ttyd console).

    Caddy rewrites every /agent request (page fetch AND the WebSocket
    handshake — a GET) to this endpoint with the original headers, so
    the session cookie rides along and the viewer resolves exactly as on
    any app page. 2xx → caddy proxies to ttyd; the 404 from
    ``require_superuser`` → caddy relays it to the client. Anonymous and
    non-superuser both 404 (house gate: existence stays hidden, never
    403). Route is deliberately SLASHLESS (``agent/auth``).
    """
    require_superuser(request)
    return HttpResponse("")


def login_for_test_by_key(request: HttpRequest, key: str) -> HttpResponse:
    """Log in a user via a one-time key issued by ``makeloginlink``.

    The test VM cannot use Google OAuth (its ``.local`` hostname isn't
    registrable), so the operator mints these links over multipass exec. The
    key is the
    sole credential and redemption consumes it atomically — the link works
    exactly once. Any miss (unknown, used, expired) is a 404 like every other
    resource gate. Not DEBUG-gated: the unguessable, single-use key is the
    gate.
    """
    user = TestLoginKey.redeem(key)
    if user is None:
        raise Http404
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(settings.LOGIN_REDIRECT_URL)
