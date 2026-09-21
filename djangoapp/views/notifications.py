"""Web notifications: list page + user-scoped API (read/delete/subscriptions).

Every route is scoped to ``request.user`` (``user_or_404``): a user only
ever sees and acts on their own rows, addressed by ``public_id`` only. The
navbar bell's unread count lives in the Inertia shared props
(SharedPropsMiddleware) — this module owns just the page and its actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.contrib.sessions.models import Session
from django.utils import timezone
from inertia import InertiaResponse
from ninja import Router
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, field_validator

from djangoapp.models import (
    Notification,
    NotificationItem,
    PushSubscription,
    UserSessionIndex,
    is_push_enabled,
    vapid_public_key,
)
from djangoapp.ninja_api import ApiError, make_ninja_api
from djangoapp.shortcuts import user_or_404

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

    from djangoapp.models import User

# Rows shown on the list page: newest first, capped so the page stays a
# bounded render; older rows remain reachable via the API/delete-all.
PAGE_SIZE = 200

router = Router()


class NotificationsPageProps(PydanticBaseModel):
    notifications: list[NotificationItem]
    unread_count: int
    push_enabled: bool
    # The base64url public half of the VAPID keypair; empty when disabled.
    vapid_public_key: str


class MessageResponse(PydanticBaseModel):
    id: str = ""


class CountResponse(PydanticBaseModel):
    count: int


class SubscribeResponse(PydanticBaseModel):
    subscribed: bool


class PushSubscriptionSchema(PydanticBaseModel):
    """A browser PushSubscription, flattened from the Push API shape."""

    endpoint: str = Field(min_length=1, max_length=500)
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=200)

    @field_validator("endpoint")
    @classmethod
    def _https_endpoint(cls, v: str) -> str:
        """https-only scheme check: endpoints are capability URLs stored VERBATIM.

        pydantic's URL types normalize (append a trailing slash to a bare
        host, lowercase it — verified against 2.13) and would corrupt the
        subscription's identity, so a plain string + scheme check is all
        the validation that is safe to do. https-only (never plain http):
        every real push service is TLS, this server POSTs payloads to the
        endpoint, and rejecting http shrinks the authenticated-SSRF
        surface to TLS hosts.
        """
        if urlparse(v).scheme != "https":
            msg = "endpoint must be an https URL"
            raise ValueError(msg)
        return v


class PushUnsubscribeSchema(PydanticBaseModel):
    endpoint: str = Field(min_length=1, max_length=500)


def _own_notification_or_404(request: HttpRequest, public_id: str) -> Notification:
    """Fetch one of the requesting user's notifications, else 404.

    Owner-scoped by the queryset, so another user's row reads as "not
    found" — its existence stays private (same gate as ``user_or_404``).
    """
    user = user_or_404(request)
    try:
        notification: Notification = Notification.objects.get(recipient=user, public_id=public_id)
    except Notification.DoesNotExist:
        raise ApiError(404, "Notification not found") from None
    return notification


@router.get("/", response=None, include_in_schema=False)
def notifications_page(request: HttpRequest) -> HttpResponse:
    """Render the notifications list (component ``Notifications``)."""
    user = user_or_404(request)
    rows = Notification.objects.filter(recipient=user)[:PAGE_SIZE]
    props = NotificationsPageProps(
        notifications=[n.to_item() for n in rows],
        unread_count=Notification.objects.filter(recipient=user, read_at__isnull=True).count(),
        push_enabled=is_push_enabled(),
        vapid_public_key=vapid_public_key(),
    )
    return InertiaResponse(request, "Notifications", {"props": props.model_dump()})


@router.post("/api/read-all", response=CountResponse)
def mark_all_read(request: HttpRequest) -> CountResponse:
    """Mark every unread notification of the user read."""
    user = user_or_404(request)
    marked = Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return CountResponse(count=marked)


# NOTE: every LITERAL /api/... route must register BEFORE the /api/{public_id}
# wildcards below — ninja compiles one Django URL pattern per operation in
# registration order, so the wildcards would otherwise shadow (and 405)
# /api/test, /api/subscriptions, /api/clear and /api/read-all.


@router.post("/api/test", response=MessageResponse)
def send_test_notification(request: HttpRequest) -> MessageResponse:
    """Record a test notification for the viewer — the real pipeline.

    The page's "Send test" button: a genuine ``Notification.record`` (row
    in the list, badge bump, on_commit push fan-out to every subscribed
    device) — the click exercises exactly what any notification does.
    """
    user = user_or_404(request)
    notification = Notification.record(
        recipient=user, kind="test", body="This is a test notification", url="/"
    )
    return MessageResponse(id=notification.public_id)


def _session_index(request: HttpRequest, user: User) -> UserSessionIndex:
    """Return the requesting session's index row, backfilled if needed.

    The index middleware creates rows lazily on the session's first
    authenticated REQUEST — which is THIS one for a first-visit
    subscribe (middleware runs on the response, after the view), so the
    same get_or_create-the-row-from-the-Session-expiry pattern runs here
    as insurance. 400 when the session row is somehow missing — binding
    the subscription to it is the CASCADE contract, no fallback exists.
    """
    key = request.session.session_key
    expire_date = (
        Session.objects.filter(session_key=key).values_list("expire_date", flat=True).first()
        if key
        else None
    )
    if key is None or expire_date is None:
        raise ApiError(400, "No session to bind the push subscription to.")
    row: UserSessionIndex = UserSessionIndex.objects.get_or_create(
        session_id=key, defaults={"user": user, "expire_date": expire_date}
    )[0]
    return row


@router.post("/api/subscriptions", response=SubscribeResponse)
def subscribe(request: HttpRequest, payload: PushSubscriptionSchema) -> SubscribeResponse:
    """Save (or rebind) this browser's push subscription for the user.

    ``update_or_create`` by endpoint: re-enabling on a device reuses the
    row, and a second user on a shared browser takes the endpoint over —
    the browser can only hold one subscription, so delivery follows the
    last subscriber. The row binds O2O to the subscribing session's
    index row: any session death (logout, logout-all, clearsessions GC)
    CASCADE-drops exactly this browser's subscription.
    """
    user = user_or_404(request)
    if not is_push_enabled():
        msg = "Web Push is not configured on this server (VAPID keys missing)."
        raise ApiError(400, msg)
    session_index = _session_index(request, user)
    # Browsers ROTATE endpoints (subscription renewal, permission
    # re-enable) within a live session: this session's index row may
    # already own a subscription with a DIFFERENT endpoint. Both sides of
    # the O2O are unique, so the insert would violate UNIQUE(session_index)
    # — drop the session's stale row first (symmetric rebind semantics:
    # the new endpoint takes over, whatever the old one was).
    PushSubscription.objects.filter(session_index=session_index).exclude(
        endpoint=payload.endpoint
    ).delete()
    PushSubscription.objects.update_or_create(
        endpoint=payload.endpoint,
        defaults={
            "user": user,
            "p256dh": payload.p256dh,
            "auth": payload.auth,
            "session_index": session_index,
        },
    )
    return SubscribeResponse(subscribed=True)


@router.delete("/api/subscriptions", response=SubscribeResponse)
def unsubscribe(request: HttpRequest, payload: PushUnsubscribeSchema) -> SubscribeResponse:
    """Drop this browser's subscription — owner-scoped, silently idempotent.

    Fired best-effort on logout. Deleting another user's endpoint is a
    no-op (the filter carries ``user``); a shared browser's subscription
    stays with its current owner.
    """
    user = user_or_404(request)
    PushSubscription.objects.filter(user=user, endpoint=payload.endpoint).delete()
    return SubscribeResponse(subscribed=False)


@router.post("/api/clear", response=CountResponse)
def clear_all(request: HttpRequest) -> CountResponse:
    """Delete every notification of the user."""
    user = user_or_404(request)
    deleted, _rows = Notification.objects.filter(recipient=user).delete()
    return CountResponse(count=deleted)


@router.post("/api/{public_id}/read", response=MessageResponse)
def mark_read(request: HttpRequest, public_id: str) -> MessageResponse:
    """Mark one notification read (idempotent; no-op if already read)."""
    notification = _own_notification_or_404(request, public_id)
    if notification.read_at is None:
        Notification.objects.filter(pk=notification.pk).update(read_at=timezone.now())
    return MessageResponse(id=notification.public_id)


@router.delete("/api/{public_id}", response=MessageResponse)
def delete_notification(request: HttpRequest, public_id: str) -> MessageResponse:
    """Delete one notification (deletion is the only lifecycle end)."""
    notification = _own_notification_or_404(request, public_id)
    notification.delete()
    return MessageResponse(id=notification.public_id)


# POST/DELETE routes ride make_ninja_api's default csrf_guard (token +
# Origin/Referer); the frontend's ky layer sends X-CSRFToken always.
notifications_api = make_ninja_api("notifications", router, prefix="notifications")
