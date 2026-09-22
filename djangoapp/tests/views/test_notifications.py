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
    - test_page_kind_filter, ?kind= narrows rows and echoes the filter (count stays global)
    - test_page_kind_filter_unknown_kind_empty, unknown kind renders empty, filter echoed
    - test_page_first_chunk_capped_with_has_more, the page caps at PAGE_SIZE with has_more
    - test_page_short_list_has_no_more, a short list flags has_more False
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

    def test_page_kind_filter(self) -> None:
        """?kind= narrows the rows to that kind and echoes the filter back."""
        Notification.record(recipient=self.user, kind="invoice.paid", body="a")
        Notification.record(recipient=self.user, kind="backup.done", body="b")
        self.inertia.force_login(self.user)
        self.inertia.get("/notifications/?kind=invoice.paid")
        page = self.props()["props"]
        self.assertEqual([n["kind"] for n in page["notifications"]], ["invoice.paid"])
        self.assertEqual(page["kind"], "invoice.paid")
        # unread_count stays global (it is the page header's number, not the
        # filtered slice's).
        self.assertEqual(page["unread_count"], 2)

    def test_page_kind_filter_unknown_kind_empty(self) -> None:
        """A kind with no rows renders an empty list, filter still echoed."""
        Notification.record(recipient=self.user, kind="k", body="a")
        self.inertia.force_login(self.user)
        self.inertia.get("/notifications/?kind=nope")
        page = self.props()["props"]
        self.assertEqual(page["notifications"], [])
        self.assertEqual(page["kind"], "nope")

    def test_page_first_chunk_capped_with_has_more(self) -> None:
        """The page renders PAGE_SIZE rows and flags that more exist."""
        for i in range(55):
            Notification.objects.create(recipient=self.user, kind="k", body=f"n{i}")
        self.inertia.force_login(self.user)
        self.inertia.get("/notifications/")
        page = self.props()["props"]
        self.assertEqual(len(page["notifications"]), 50)
        self.assertTrue(page["has_more"])

    def test_page_short_list_has_no_more(self) -> None:
        """Fewer than PAGE_SIZE rows → has_more False (no Load more)."""
        Notification.record(recipient=self.user, kind="k", body="a")
        self.inertia.force_login(self.user)
        self.inertia.get("/notifications/")
        page = self.props()["props"]
        self.assertEqual(len(page["notifications"]), 1)
        self.assertFalse(page["has_more"])


class NotificationPageApiTests(BaseInertiaTestCase):
    """GET /notifications/api/page — the Load more cursor endpoint.

    - test_page_next_chunk_after_cursor, ?after= returns strictly older rows
    - test_page_last_chunk_reports_no_more, the tail chunk has has_more False
    - test_page_respects_kind_filter, ?kind= pages within the filtered rows
    - test_page_after_beyond_end_empty, a cursor past the end is empty
    - test_page_anonymous_404, anonymous GET is 404
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="alice", password="pw")
        for i in range(55):
            Notification.objects.create(
                recipient=self.user, kind="even" if i % 2 == 0 else "odd", body=f"n{i}"
            )
        # The API tests exercise plain Django clients, not the Inertia test
        # harness — login the client itself (force_login on self.inertia
        # binds a different session and the API reads would 404).
        self.client.force_login(self.user)

    def test_page_next_chunk_after_cursor(self) -> None:
        """?after=<newest> returns the next 50, strictly older, has_more."""
        newest = Notification.objects.filter(recipient=self.user).latest("created_at")
        response = self.client.get(f"/notifications/api/page?after={newest.public_id}")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["notifications"]), 50)
        self.assertTrue(data["has_more"])
        self.assertNotIn(newest.public_id, [n["public_id"] for n in data["notifications"]])

    def test_page_last_chunk_reports_no_more(self) -> None:
        """Walking the cursor twice lands on the tail chunk: has_more False.

        55 rows: chunk 1 (after=newest) = 50, chunk 2 (after=chunk 1's
        last) = the remaining 4 — and no more behind them.
        """
        newest = Notification.objects.filter(recipient=self.user).latest("created_at")
        first = json.loads(
            self.client.get(f"/notifications/api/page?after={newest.public_id}").content
        )
        cursor = first["notifications"][-1]["public_id"]
        second = json.loads(self.client.get(f"/notifications/api/page?after={cursor}").content)
        self.assertEqual(len(second["notifications"]), 4)
        self.assertFalse(second["has_more"])

    def test_page_respects_kind_filter(self) -> None:
        """?kind= pages within the filtered rows only."""
        newest = Notification.objects.filter(recipient=self.user).latest("created_at")
        response = self.client.get(f"/notifications/api/page?after={newest.public_id}&kind=even")
        kinds = {n["kind"] for n in json.loads(response.content)["notifications"]}
        self.assertEqual(kinds, {"even"})

    def test_page_after_beyond_end_empty(self) -> None:
        """A cursor older than every row yields an empty chunk."""
        oldest = Notification.objects.filter(recipient=self.user).earliest("created_at")
        response = self.client.get(f"/notifications/api/page?after={oldest.public_id}")
        data = json.loads(response.content)
        self.assertEqual(data["notifications"], [])
        self.assertFalse(data["has_more"])

    def test_page_anonymous_404(self) -> None:
        """Anonymous GET is 404."""
        anon = Client()
        self.assertEqual(anon.get("/notifications/api/page").status_code, 404)


class NotificationActionTests(BaseInertiaTestCase):
    """read/read-all/delete/clear: owner-scoped, idempotent, pk-free paths.

    - test_send_test_notification, POST test records a real row and schedules its push
    - test_send_test_anonymous_404, anonymous POST is 404
    - test_mark_read_is_idempotent, POST marks read; re-POST is 200 with the same read_at
    - test_mark_read_other_users_row_404, another user's row 404s
    - test_mark_all_read_only_own, read-all touches only the viewer's rows
    - test_read_selected_marks_only_given_own, read-selected marks the given unread rows only
    - test_read_selected_is_idempotent, re-posting a read selection counts zero changes
    - test_read_selected_rejects_empty_list, an empty selection is 422
    - test_delete_selected_only_own, delete-selected removes the given rows, not foreign ids
    - test_bulk_endpoints_anonymous_404, anonymous bulk POSTs are 404
    - test_delete_removes_row, DELETE removes the row
    - test_delete_other_users_row_404, another user's row can't be deleted
    - test_clear_deletes_only_own, clear wipes the viewer's rows only
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

    def test_read_selected_marks_only_given_own(self) -> None:
        """read-selected marks exactly the given unread own rows."""
        second = Notification.record(recipient=self.alice, kind="k2", body="a2")
        response = self.client.post(
            "/notifications/api/read-selected",
            {"public_ids": [self.alices.public_id, self.bobs.public_id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["count"], 1)
        self.alices.refresh_from_db()
        self.assertIsNotNone(self.alices.read_at)
        second.refresh_from_db()
        self.assertIsNone(second.read_at)
        self.bobs.refresh_from_db()
        self.assertIsNone(self.bobs.read_at)

    def test_read_selected_is_idempotent(self) -> None:
        """Re-posting an already-read selection counts zero changed rows."""
        self.client.post(
            "/notifications/api/read-selected",
            {"public_ids": [self.alices.public_id]},
            content_type="application/json",
        )
        response = self.client.post(
            "/notifications/api/read-selected",
            {"public_ids": [self.alices.public_id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["count"], 0)

    def test_delete_selected_only_own(self) -> None:
        """delete-selected removes the given own rows; foreign ids survive."""
        Notification.record(recipient=self.alice, kind="k2", body="a2")
        response = self.client.post(
            "/notifications/api/delete-selected",
            {"public_ids": [self.alices.public_id, self.bobs.public_id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["count"], 1)
        self.assertFalse(Notification.objects.filter(pk=self.alices.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=self.bobs.pk).exists())

    def test_read_selected_rejects_empty_list(self) -> None:
        """An empty selection is 422 (the schema demands at least one id)."""
        response = self.client.post(
            "/notifications/api/read-selected",
            {"public_ids": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_bulk_endpoints_anonymous_404(self) -> None:
        """Anonymous bulk POSTs read as not found on both endpoints."""
        anon = Client()
        for path in ("/notifications/api/read-selected", "/notifications/api/delete-selected"):
            response = anon.post(path, {"public_ids": ["x"]}, content_type="application/json")
            self.assertEqual(response.status_code, 404, path)

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
