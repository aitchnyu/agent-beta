"""Inertia request middleware."""

from __future__ import annotations

import http
from datetime import timedelta
from typing import TYPE_CHECKING, cast

from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers import registry
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from inertia import share

from djangoapp.logging import bind_log_context, clear_log_context, get_logger
from djangoapp.models import Notification, User, UserProfile, UserSessionIndex
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


def _login_providers(request: HttpRequest) -> list[dict[str, str]]:
    """Build the configured social-login provider list for the navbar dropdown.

    Mirrors the allauth login page's provider list (DB-driven, current
    site). distinct("provider") keeps one entry per provider even if
    duplicate SocialApp rows exist (lowest pk wins — deterministic); a
    leftover row whose provider module is no longer installed is skipped —
    registry.get_class() returning None means SocialApp.get_provider()
    would call None(...) (TypeError), and a stale row must not 500 every
    page.
    """
    providers: list[dict[str, str]] = []
    apps = (
        SocialApp.objects.filter(sites__id=settings.SITE_ID)
        .order_by("provider", "pk")
        .distinct("provider")
    )
    for app in apps:
        if registry.get_class(app.provider) is None:
            continue
        provider = app.get_provider(request)
        providers.append(
            {
                "id": app.provider,
                "name": provider.name,
                "url": provider.get_login_url(request),
            }
        )
    return providers


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
    """Share viewer profile, superuser flag, login providers, unread count.

    Read via ``usePage().props`` (the navbar); pk-free — ``public_id`` only.
    """

    def __init__(self, get_response: Callable[..., HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        profile = _viewer_profile(request.user)
        user = maybe_user(request)
        # The login-rebind flow, step by step:
        # 1. on_user_logged_in (models/base.py) sets
        #    session["just_logged_in"] on the login request — which then
        #    redirects, so the flag crosses requests via the session.
        # 2. Here it is READ without popping: the render shares it with
        #    the bell, but consumption is decided AFTER the response.
        # 3. Only a successful FULL page pops it — HTML content, no
        #    X-Inertia request header, not a 5xx. A racing XHR, an
        #    Inertia partial, or an error page must not burn the one shot.
        # 4. NotificationsBell, mounted by that landing page, re-POSTs the
        #    browser's still-held push subscription — recreating the row
        #    logout's CASCADE deleted, bound to the fresh session.
        just_logged_in = user is not None and "just_logged_in" in request.session
        share(
            request,
            user=profile.model_dump() if profile else None,
            viewer_is_superuser=bool(
                getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False)
            ),
            # Signed-in: no Sign-in dropdown → null, no provider lookup.
            login_providers=None if profile else _login_providers(request),
            # The bell badge (NotificationsBell.vue): fresh on every visit,
            # partial-reloaded between them. One COUNT per AUTHENTICATED
            # request (API calls too); anonymous gets a static 0.
            unread_notifications=(
                Notification.objects.filter(recipient=user, read_at__isnull=True).count()
                if user is not None
                else 0
            ),
            just_logged_in=just_logged_in,
        )
        response = self.get_response(request)
        # Consume (step 3): a non-5xx, non-Inertia, HTML response — the
        # bell's landing render. Anything else leaves the flag for the
        # real landing to pick up.
        if (
            just_logged_in
            and response.status_code < http.HTTPStatus.INTERNAL_SERVER_ERROR
            and not request.headers.get("x-inertia")
            and response.headers.get("Content-Type", "").startswith("text/html")
        ):
            request.session.pop("just_logged_in", None)
        return response


class SessionIdleTouchMiddleware(MiddlewareMixin):
    """Sliding idle expiry for authenticated sessions.

    Sessions die SESSION_COOKIE_AGE after the user's last request, not
    after login. Half-life touch, amortized: only when more than half the
    window has elapsed does anything write. The deadline lives in TWO
    places, both re-armed here: (1) the UserSessionIndex row — direct
    single-column UPDATE below; (2) the session row itself — NOT here:
    setting ``session.modified`` makes SessionMiddleware's save (its
    ``create_model_instance``) recompute ``expire_date = now + window`` and
    re-issue the cookie. A daily-active user writes ~once per week instead
    of per request. Also lazily backfills index rows for sessions created
    before the index existed. Runs AFTER SessionMiddleware in MIDDLEWARE so
    this ``process_response`` fires first (responses run bottom-up) and the
    modified flag is still seen.
    """

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # 5xx responses skip the touch: SessionMiddleware also skips its
        # save for status >= 500 (a failing request must not extend the
        # session)
        if response.status_code >= http.HTTPStatus.INTERNAL_SERVER_ERROR:
            return response

        session = getattr(request, "session", None)
        user = getattr(request, "user", None)
        key = session.session_key if session is not None else None
        if session is None or not key or user is None or not user.is_authenticated:
            return response

        now = timezone.now()
        window = timedelta(seconds=settings.SESSION_COOKIE_AGE)
        row = UserSessionIndex.objects.filter(session_id=key).first()
        if row is None:
            # Lazy backfill: session predates the index (or the receiver
            # missed); copy the authoritative expire_date from the row.
            session_row = (
                Session.objects.filter(session_key=key)
                .values_list("expire_date", flat=True)
                .first()
            )
            if session_row is None:
                return response
            UserSessionIndex.objects.get_or_create(
                session_id=key,
                defaults={"user": user, "expire_date": session_row},
            )
            return response
        if now > row.expire_date - window / 2:
            new_expiry = now + window
            UserSessionIndex.objects.filter(pk=row.pk).update(expire_date=new_expiry)
            # re-saves the session row with the same deadline and
            # re-issues the cookie with the fresh max-age.
            session.modified = True
        return response
