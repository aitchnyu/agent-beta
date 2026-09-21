"""Tests for the notifications endpoints (page + API)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client, override_settings
from django.utils import timezone

from djangoapp.models import (
    Notification,
    PushSubscription,
    User,
    UserSessionIndex,
)
from djangoapp.tests._base import BaseInertiaTestCase


def _make_subscription(
    user: User, endpoint: str, p256dh: str = "p", auth: str = "a"
) -> PushSubscription:
    """Create a subscription row directly, with its CASCADE-chain root.

    The O2O to UserSessionIndex is required, so a direct row needs a
    Session + index row to hang from (the API path builds these via the
    request's own session; tests without one mint them here).
    """
    session_row = Session.objects.create(
        session_key=uuid.uuid4().hex,
        session_data="",
        expire_date=timezone.now() + timedelta(days=14),
    )
    index = UserSessionIndex.objects.create(
        user=user, session=session_row, expire_date=session_row.expire_date
    )
    return PushSubscription.objects.create(
        user=user, endpoint=endpoint, p256dh=p256dh, auth=auth, session_index=index
    )


PUSH_CONFIGURED = override_settings(VAPID_PRIVATE_KEY="fake-private-key")


class NotificationsPageTests(BaseInertiaTestCase):
    """GET /notifications renders the list, owner-scoped and pk-free.

    - test_anonymous_404, anon requests read as not found
    - test_page_lists_own_newest_first, own rows newest-first, pk-free props with config
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")

    def test_anonymous_404(self) -> None:
        """Anonymous GET is 404 (private page, anon reads as not found)."""
        self.assertEqual(self.client.get("/notifications/").status_code, 404)

    def test_page_lists_own_newest_first(self) -> None:
        """Only the viewer's rows render, newest first, in a pk-free shape."""
        Notification.record(recipient=self.user, kind="k.old", body="first")
        Notification.record(recipient=self.user, kind="k.new", body="second")
        Notification.record(recipient=self.other, kind="k.other", body="not mine")
        self.inertia.force_login(self.user)
        self.inertia.get("/notifications/")
        self.assertComponentUsed("Notifications")
        page = self.props()["props"]
        kinds = [n["kind"] for n in page["notifications"]]
        self.assertEqual(kinds, ["k.new", "k.old"])
        self.assertEqual(page["unread_count"], 2)
        self.assertIn("push_enabled", page)
        self.assertIn("vapid_public_key", page)
        self.assertEqual(
            set(page["notifications"][0].keys()),
            {"public_id", "kind", "body", "url", "read", "created_at"},
        )


class NotificationActionTests(BaseInertiaTestCase):
    """read/read-all/delete/clear: owner-scoped, idempotent, pk-free paths.

    - test_mark_read_is_idempotent, POST marks read; re-POST is 200 with the same read_at
    - test_mark_read_other_users_row_404, another user's row 404s
    - test_mark_all_read_only_own, read-all touches only the viewer's rows
    - test_delete_removes_row, DELETE removes the row
    - test_delete_other_users_row_404, another user's row can't be deleted
    - test_clear_deletes_only_own, clear wipes the viewer's rows only
    - test_send_test_notification, POST test records a real row and schedules its push
    - test_send_test_anonymous_404, anonymous POST is 404
    """

    def setUp(self) -> None:
        super().setUp()
        self.alice = User.objects.create_user(username="alice", password="pw")
        self.bob = User.objects.create_user(username="bob", password="pw")
        self.alices = Notification.record(recipient=self.alice, kind="k", body="a")
        self.bobs = Notification.record(recipient=self.bob, kind="k", body="b")
        # AFTER super().setUp(): the inertia test base rebinds clients there,
        # which would drop a session logged in before it ran.
        self.client.force_login(self.alice)

    @override_settings(VAPID_PRIVATE_KEY="")
    def test_send_test_notification(self) -> None:
        """POST test records a real row and schedules its push on commit.

        Delivery is async (a Huey task); deliver_push is mocked — the
        row + response contract is what this endpoint owns. VAPID is
        forced OFF to pin that the enqueue is unconditional (the task
        itself gates on VAPID/subscriptions), whatever the ambient .env.
        """
        with (
            patch("djangoapp.models.notifications.deliver_push") as schedule_mock,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post("/notifications/api/test")
        self.assertEqual(response.status_code, 200)
        notification = Notification.objects.get(recipient=self.alice, kind="test")
        self.assertEqual(notification.body, "This is a test notification")
        self.assertEqual(notification.url, "/")
        self.assertEqual(json.loads(response.content)["id"], notification.public_id)
        schedule_mock.assert_called_once()
        user_pk, payload = schedule_mock.call_args.args
        self.assertEqual(user_pk, self.alice.pk)
        self.assertEqual(payload["public_id"], notification.public_id)

    def test_send_test_anonymous_404(self) -> None:
        """Anonymous POST is 404."""
        anon = Client()
        self.assertEqual(anon.post("/notifications/api/test").status_code, 404)

    def test_mark_read_is_idempotent(self) -> None:
        """POST read marks the row read; re-POST keeps the original read_at."""
        response = self.client.post(f"/notifications/api/{self.alices.public_id}/read")
        self.assertEqual(response.status_code, 200)
        self.alices.refresh_from_db()
        self.assertIsNotNone(self.alices.read_at)
        first = self.alices.read_at
        response = self.client.post(f"/notifications/api/{self.alices.public_id}/read")
        self.assertEqual(response.status_code, 200)
        self.alices.refresh_from_db()
        self.assertEqual(self.alices.read_at, first)

    def test_mark_read_other_users_row_404(self) -> None:
        """Marking another user's row is 404 and leaves it unread."""
        response = self.client.post(f"/notifications/api/{self.bobs.public_id}/read")
        self.assertEqual(response.status_code, 404)
        self.bobs.refresh_from_db()
        self.assertIsNone(self.bobs.read_at)

    def test_mark_all_read_only_own(self) -> None:
        """read-all marks the viewer's unread rows, nobody else's."""
        Notification.record(recipient=self.alice, kind="k2", body="a2")
        response = self.client.post("/notifications/api/read-all")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["count"], 2)
        self.bobs.refresh_from_db()
        self.assertIsNone(self.bobs.read_at)

    def test_delete_removes_row(self) -> None:
        """DELETE removes the viewer's row."""
        public_id = self.alices.public_id
        response = self.client.delete(f"/notifications/api/{public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.filter(public_id=public_id).exists())

    def test_delete_other_users_row_404(self) -> None:
        """Another user's row can't be deleted (404, row survives)."""
        response = self.client.delete(f"/notifications/api/{self.bobs.public_id}")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=self.bobs.pk).exists())

    def test_clear_deletes_only_own(self) -> None:
        """Clear wipes the viewer's rows and nobody else's."""
        response = self.client.post("/notifications/api/clear")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["count"], 1)
        self.assertTrue(Notification.objects.filter(pk=self.bobs.pk).exists())


@PUSH_CONFIGURED
class LogoutUnsubscribeTests(BaseInertiaTestCase):
    """Server-side logout unsubscribe: this browser's row dies, others live.

    - test_logout_drops_this_sessions_subscription, logout drops only this session's row
    - test_resubscribe_rebinds_session, re-subscribing under a new login rebinds the key
    """

    def setUp(self) -> None:
        super().setUp()
        self.alice = User.objects.create_user(username="alice", password="pw")
        # A second browser: same user, its own session and subscription.
        self.other_browser = Client()
        self.other_browser.force_login(self.alice)
        self.other_browser.post(
            "/notifications/api/subscriptions",
            {"endpoint": "https://push.example/phone", "p256dh": "p", "auth": "a"},
            content_type="application/json",
        )
        self.client.force_login(self.alice)
        self.client.post(
            "/notifications/api/subscriptions",
            {"endpoint": "https://push.example/laptop", "p256dh": "p", "auth": "a"},
            content_type="application/json",
        )
        self.assertEqual(PushSubscription.objects.count(), 2)

    def test_logout_drops_this_sessions_subscription(self) -> None:
        """POST logout deletes the laptop row; the phone row survives."""
        response = self.client.post("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        endpoints = set(PushSubscription.objects.values_list("endpoint", flat=True))
        self.assertEqual(endpoints, {"https://push.example/phone"})

    def test_resubscribe_rebinds_session(self) -> None:
        """A new login re-subscribing rebinds the row to the new session."""
        self.client.post("/accounts/logout/")
        self.assertEqual(PushSubscription.objects.count(), 1)
        self.client.force_login(self.alice)
        # The session cookie the NEXT request will actually carry (the
        # wire truth — later responses may rotate it again).
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.client.post(
            "/notifications/api/subscriptions",
            {"endpoint": "https://push.example/phone", "p256dh": "p", "auth": "a"},
            content_type="application/json",
        )
        # One row, O2O-bound to the subscribing session's index row.
        sub = PushSubscription.objects.get(endpoint="https://push.example/phone")
        self.assertEqual(sub.session_index.session_id, cookie)


class PushSubscriptionEndpointTests(BaseInertiaTestCase):
    """subscribe/unsubscribe: upsert semantics, VAPID gate, scoping.

    - test_subscribe_creates_subscription, POST saves endpoint + keys
    - test_subscribe_resubscribe_rebinds_user, same endpoint under a new user rebinds
    - test_subscribe_rotated_endpoint_replaces_row, same-session endpoint rotation replaces the row
    - test_subscribe_rejects_non_http_endpoint, scheme validation is 422
    - test_unsubscribe_own_endpoint, DELETE drops the viewer's endpoint
    - test_unsubscribe_other_users_endpoint_noop, another user's endpoint survives
    - test_subscribe_requires_csrf_token, tokenless POST is 403
    """

    def setUp(self) -> None:
        super().setUp()
        self.alice = User.objects.create_user(username="alice", password="pw")
        self.bob = User.objects.create_user(username="bob", password="pw")

    def _payload(self, endpoint: str = "https://push.example/e1") -> dict[str, str]:
        return {"endpoint": endpoint, "p256dh": "p-key", "auth": "a-key"}

    @PUSH_CONFIGURED
    def test_subscribe_creates_subscription(self) -> None:
        """POST saves endpoint + keys for the viewer, bound to this session."""
        self.client.force_login(self.alice)
        response = self.client.post(
            "/notifications/api/subscriptions",
            self._payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["subscribed"])
        sub = PushSubscription.objects.get(endpoint="https://push.example/e1")
        self.assertEqual(sub.user, self.alice)
        self.assertEqual(sub.p256dh, "p-key")
        self.assertEqual(sub.auth, "a-key")
        self.assertEqual(sub.session_index.session_id, self.client.session.session_key)

    @PUSH_CONFIGURED
    def test_subscribe_resubscribe_rebinds_user(self) -> None:
        """The same browser under a new account takes the endpoint over."""
        _make_subscription(self.bob, "https://push.example/e1", p256dh="old", auth="old")
        self.client.force_login(self.alice)
        response = self.client.post(
            "/notifications/api/subscriptions",
            self._payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PushSubscription.objects.count(), 1)
        sub = PushSubscription.objects.get(endpoint="https://push.example/e1")
        self.assertEqual(sub.user, self.alice)
        self.assertEqual(sub.p256dh, "p-key")

    @PUSH_CONFIGURED
    def test_subscribe_rotated_endpoint_replaces_row(self) -> None:
        """A rotated endpoint on the same session replaces the old row.

        Browsers renew subscriptions mid-session; both sides of the O2O
        are unique, so the naive insert would violate UNIQUE(session_index)
        → 500 (the backend review's major). The pre-delete makes the new
        endpoint take over instead.
        """
        self.client.force_login(self.alice)
        self.client.post(
            "/notifications/api/subscriptions",
            self._payload(endpoint="https://push.example/old"),
            content_type="application/json",
        )
        response = self.client.post(
            "/notifications/api/subscriptions",
            self._payload(endpoint="https://push.example/new"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        endpoints = set(PushSubscription.objects.values_list("endpoint", flat=True))
        self.assertEqual(endpoints, {"https://push.example/new"})

    @PUSH_CONFIGURED
    def test_subscribe_rejects_non_http_endpoint(self) -> None:
        """A non-http(s) endpoint is 422 (stored verbatim, so scheme-checked)."""
        self.client.force_login(self.alice)
        response = self.client.post(
            "/notifications/api/subscriptions",
            self._payload(endpoint="javascript:alert(1)"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    @PUSH_CONFIGURED
    def test_unsubscribe_own_endpoint(self) -> None:
        """DELETE drops the viewer's endpoint."""
        _make_subscription(self.alice, "https://push.example/e1")
        self.client.force_login(self.alice)
        response = self.client.delete(
            "/notifications/api/subscriptions",
            {"endpoint": "https://push.example/e1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PushSubscription.objects.filter(endpoint="https://push.example/e1").exists()
        )

    @PUSH_CONFIGURED
    def test_unsubscribe_other_users_endpoint_noop(self) -> None:
        """Unsubscribing another user's endpoint is a no-op for them."""
        _make_subscription(self.bob, "https://push.example/e1")
        self.client.force_login(self.alice)
        response = self.client.delete(
            "/notifications/api/subscriptions",
            {"endpoint": "https://push.example/e1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PushSubscription.objects.filter(endpoint="https://push.example/e1").exists()
        )

    @PUSH_CONFIGURED
    def test_subscribe_requires_csrf_token(self) -> None:
        """Tokenless POST is 403 (make_ninja_api's default csrf_guard)."""
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.alice)
        strict_client.get("/")  # bootstrap the csrftoken cookie
        response = strict_client.post(
            "/notifications/api/subscriptions",
            self._payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
