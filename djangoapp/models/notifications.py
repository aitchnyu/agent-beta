"""Web notifications: stored rows + Web Push delivery.

``Notification`` rows live until the user deletes them (no TTL, no
auto-purge) and are created through :meth:`Notification.record` — the one
call shape tasks (Huey workers, no request) and page views alike use.
After the row is durably saved, ``transaction.on_commit`` fans it out to
every ``PushSubscription`` of the recipient via ``pywebpush`` (RFC 8291
payload encryption + RFC 8292 VAPID auth).

Both models are plain ``models.Model`` with a uuid7 ``public_id`` (the
``UserHistory`` pattern), NOT ``BaseModel``: rows are system-generated and
short-lived client state, and ``save_with_logs`` would double every write
with an audit-log entry.
"""

from __future__ import annotations

import base64
import json
import typing
from functools import lru_cache
from typing import ClassVar

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.db import models, transaction
from pydantic import BaseModel as PydanticBaseModel
from pywebpush import WebPushException, webpush

from djangoapp.logging import get_logger
from djangoapp.models.base import User, UserSessionIndex, generate_uuid7_id
from djangoapp.tasks import deliver_push

if typing.TYPE_CHECKING:
    from django.db.models.query import QuerySet

logger = get_logger(__name__)

# How long the push service keeps an undelivered message (the browser is
# offline): one day. The DB row is the source of truth and outlives the
# pushed copy by design ("till deleted").
_PUSH_TTL_SECONDS = 24 * 60 * 60

# Per-request socket timeout for the POST to the push service — on_commit
# runs synchronously inside the record() caller (view/task), so an
# unbounded default (pywebpush passes timeout=None to requests) would let
# one hung connection block the caller indefinitely.
_PUSH_TIMEOUT_SECONDS = 10

# Push-service statuses meaning "this subscription no longer exists" —
# the endpoint must be pruned (RFC 8030 §7.3).
_GONE_STATUSES = frozenset({404, 410})


def is_push_enabled() -> bool:
    """Whether Web Push is configured (private key present, no sentinel)."""
    return bool(settings.VAPID_PRIVATE_KEY)


@lru_cache(maxsize=1)
def vapid_subject() -> str:
    """``mailto:`` of the first superuser with an email (lowest pk).

    RFC 8292's contact claim — the operator is the push contact, so no
    VAPID_SUBJECT knob exists. Cached for the process life (tests
    ``cache_clear()``); "" (no email anywhere) makes ``_push`` skip
    delivery.
    """
    email = (
        User.objects.filter(is_superuser=True)
        .exclude(email="")
        .order_by("pk")
        .values_list("email", flat=True)
        .first()
    )
    return f"mailto:{email}" if email else ""


def vapid_public_key() -> str:
    """Derive the base64url uncompressed-point public key from the private one.

    The browser's ``applicationServerKey`` must match the key that signs
    the VAPID JWT; deriving (instead of storing a second env value) makes
    a mismatched pair impossible. py_vapid computes this exact value
    inside ``sign()`` but never exposes it — it only buries it in the
    Authorization/Crypto-Key headers — so the app derives it here. Read
    at CALL time (not import) so ``override_settings`` works in tests.
    Empty private (or a malformed one — logged, never raised) → empty
    public: push renders disabled instead of 500ing the page.
    """
    private = settings.VAPID_PRIVATE_KEY
    if not private:
        return ""
    try:
        raw = base64.urlsafe_b64decode(private + "=" * (-len(private) % 4))
        point = (
            ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
            .public_key()
            .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        )
    except (ValueError, TypeError) as exc:
        # Trailing newline inside quotes, a pasted PEM, a bad scalar —
        # operator paste errors land here; degrade to "disabled", loudly.
        logger.warning("VAPID_PRIVATE_KEY is malformed; browser push disabled", error=str(exc))
        return ""
    return base64.urlsafe_b64encode(point).decode().rstrip("=")


class NotificationItem(PydanticBaseModel):
    """Client-facing shape of one ``Notification`` row (pk-free)."""

    public_id: str
    kind: str
    body: str
    url: str
    read: bool
    created_at: int  # epoch ms — rendered via HumanizedTime


class Notification(models.Model):
    """One user-facing notification; deletion is the only lifecycle end.

    ``kind`` is a free-form bucket (e.g. ``task.done``) the frontend uses
    for icon/filter grouping — no choices constraint, so apps mint their
    own kinds without migrations. ``read_at`` is presentation state for
    the unread badge, not lifecycle: rows go away only via DELETE.
    """

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=50)
    body = models.TextField()
    url = models.CharField(max_length=500, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            # The list page + unread count: filter by recipient, newest
            # first. A read_at-partial index would serve counts better but
            # adds write cost for zero felt benefit at this scale.
            models.Index(fields=["recipient", "-created_at"]),
        ]
        # pk tiebreaker: same-microsecond rows otherwise order arbitrarily
        # across page loads.
        ordering: ClassVar[list[str]] = ["-created_at", "-pk"]

    def __str__(self) -> str:
        """One-line tail-log/traceback rendering."""
        return f"{self.kind} → {self.recipient} @ {self.created_at:%Y-%m-%d %H:%M}"

    def to_item(self) -> NotificationItem:
        return NotificationItem(
            public_id=self.public_id,
            kind=self.kind,
            body=self.body,
            url=self.url,
            read=self.read_at is not None,
            created_at=int(self.created_at.timestamp() * 1000),
        )

    @classmethod
    def record(
        cls,
        *,
        recipient: User,
        kind: str,
        body: str,
        url: str = "",
    ) -> typing.Self:
        """Store a notification and schedule its Web Push fan-out.

        Callable from views and Huey tasks alike (no request involved).
        The push is ENQUEUED as a Huey task on ``on_commit`` — never run
        inline — so neither a rolled-back row is pushed nor a request
        waits on push-service HTTP. In the Huey worker there is no
        surrounding transaction, so the enqueue fires immediately. Push
        failures never propagate — see ``notify_sessions``.
        """
        notification = cls.objects.create(recipient=recipient, kind=kind, body=body, url=url)
        # The fan-out is a Huey TASK, never inline: push-service HTTP is
        # seconds-slow worst case (10s timeout x N subscriptions), which no
        # view or task should wait on. on_commit gates it — a rolled-back
        # row never pushes; without a running consumer the task queues and
        # delivery degrades to in-app, gracefully.
        transaction.on_commit(
            lambda: deliver_push(
                recipient.pk,
                {
                    "public_id": notification.public_id,
                    "kind": kind,
                    "body": body,
                    "url": url,
                },
            )
        )
        return notification


class PushSubscription(models.Model):
    """One browser's Web Push subscription (endpoint + encryption keys).

    A user may hold several (one per browser); one browser holds at most
    one endpoint, so re-subscribing under a different account rebinds it
    (update_or_create by endpoint) — a shared computer delivers to
    whichever user enabled notifications last. The row is ONE-TO-ONE with
    the subscribing session's ``UserSessionIndex`` row, so the CASCADE
    chain (Session → index → subscription) makes ANY session death —
    logout flush, logout-all, clearsessions GC — drop exactly that
    browser's subscription, referentially, with no signal to time.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    # The push service's per-subscription URL — stored verbatim (its path
    # + query are the subscription's identity; never normalized).
    endpoint = models.URLField(max_length=500, unique=True)
    # Client public key + auth secret (RFC 8291), base64url strings sent
    # by the browser; only used to build the encryption envelope.
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=200)
    # The subscribing session's index row — the O2O that rides the
    # Session → UserSessionIndex → PushSubscription CASCADE chain. The
    # index middleware backfills lazily; subscribe get_or_creates as
    # insurance when a first-request subscribe beats the backfill.
    session_index = models.OneToOneField(
        UserSessionIndex,
        on_delete=models.CASCADE,
        related_name="push_subscription",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        """One-line tail-log/traceback rendering (host only, never keys)."""
        host = self.endpoint.split("/")[2] if "://" in self.endpoint else self.endpoint
        return f"{self.user} @ {host}"


def _endpoint_host(endpoint: str) -> str:
    """Push-service host of an endpoint URL — logs never carry the full URL.

    The endpoint is a capability URL (RFC 8030: knowing it lets a caller
    push to / delete the subscription), so it gets the same treatment as
    ``PushSubscription.__str__``: host only.
    """
    return endpoint.split("/")[2] if "://" in endpoint else endpoint


def notify_sessions(user: User, payload: dict[str, str]) -> int:
    """Web-Push a payload to every live-session subscription of the user.

    THE delivery entrypoint: subscriptions ride the CASCADE chain
    (Session → index → subscription), so "the user's subscription rows"
    already means "the user's active sessions' devices" — dead sessions'
    rows are gone referentially. Wrappers: ``Notification.record`` (store
    a row + this, on commit) and ``push_test`` (this alone, no row).

    Returns the subscription count the payload was handed to — 0 when
    push is off (dev sentinel), no superuser email exists for the VAPID
    subject, or the user simply has no subscriptions; callers decide
    what to tell the user. Failures NEVER propagate to the caller: a
    broken push (dead endpoint, network error, VAPID misconfiguration)
    is logged and skipped — see ``_deliver``.
    """
    if not is_push_enabled():
        # VAPID unset (dev sentinel / misconfigured deploy): rows still
        # store and show in-app — browser delivery is off, loudly.
        logger.warning("push skipped (VAPID unset)")
        return 0
    if not vapid_subject():
        # Key configured but no superuser email to serve as the RFC 8292
        # contact: nothing CAN be delivered — return 0, not the count, so
        # callers (the test button's "sent to N devices") never report
        # delivery that did not happen.
        logger.warning("push skipped (no superuser email for the VAPID subject)")
        return 0
    subscriptions: QuerySet[PushSubscription] = user.push_subscriptions.all()
    count = subscriptions.count()
    if not count:
        return 0
    _deliver(subscriptions, json.dumps(payload), log_id=payload.get("public_id", "push"))
    return count


def push_test(user: User) -> int:
    """Queue a test push to every subscription of the user — NO row stored.

    The notifications page's "Send test notification" button: a pure
    delivery check (the browser toast on each device IS the result), so
    unlike ``record`` nothing lands in the table or the badge. Returns
    the device count the enqueued task will fan out to (0 when push is
    off or none exist — the caller decides what to tell the user); the
    count gates mirror ``notify_sessions`` exactly so the number never
    promises a delivery the task would skip.
    """
    count = user.push_subscriptions.count() if is_push_enabled() and vapid_subject() else 0
    if count:
        deliver_push(
            user.pk,
            {
                "public_id": "test",
                "kind": "test",
                "body": "Clicking this will take you to homepage",
                "url": "/",
            },
        )
    return count


def _deliver(subscriptions: QuerySet[PushSubscription], payload: str, log_id: str) -> None:
    """Fan a serialized payload out to subscriptions; failures never propagate.

    Shared by ``record``'s committed pushes and ``push_test``'s rowless
    probes — both arrive pre-gated (VAPID set + subject resolvable; see
    ``notify_sessions``). A broken push (dead endpoint, network error,
    VAPID misconfiguration — or a DB hiccup fetching/pruning
    subscriptions) is logged and skipped. Dead endpoints (404/410 per
    RFC 8030) are pruned so the table self-cleans; every other outcome
    leaves the subscription for the next attempt.
    """
    subject = vapid_subject()
    try:
        for subscription in subscriptions.iterator():
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                    },
                    data=payload,
                    ttl=_PUSH_TTL_SECONDS,
                    # Bounded per-request socket timeout: on_commit runs
                    # synchronously in the record() caller, and pywebpush's
                    # default (timeout=None) would let one hung push-service
                    # connection block a view or task forever.
                    timeout=_PUSH_TIMEOUT_SECONDS,
                    # The public key is derived from the private one inside
                    # pywebpush (vapid_public_key param is gone since the RFC
                    # 8292 era) — the browser's applicationServerKey matches
                    # it via vapid_public_key()'s own derivation above.
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": subject},
                )
            except WebPushException as exc:
                # exc.status_code is None-safe (no response → None) — cleaner
                # than digging into exc.response. The response BODY is the
                # actionable part (the push service's error JSON), logged
                # bounded; the exception's own message is boilerplate.
                status = exc.status_code
                if status in _GONE_STATUSES:
                    subscription.delete()
                    logger.info(
                        "push subscription pruned",
                        endpoint_host=_endpoint_host(subscription.endpoint),
                        status=status,
                    )
                else:
                    # warning, not exception: a push-service 4xx/5xx is an
                    # expected, handled condition — status + response body
                    # are the actionable data, and pywebpush's message is
                    # boilerplate. logger.exception is for the branches
                    # below.
                    logger.warning(
                        "push delivery failed",
                        endpoint_host=_endpoint_host(subscription.endpoint),
                        status=status,
                        response=(exc.response.text[:500] if exc.response is not None else None),
                    )
            except Exception:  # the HTTP/crypto layer can raise anything
                logger.exception(
                    "push delivery crashed",
                    endpoint_host=_endpoint_host(subscription.endpoint),
                )
    except Exception:  # fetching/pruning subscriptions is DB I/O too; record() must survive it all
        logger.exception("push fan-out crashed", notification=log_id)
