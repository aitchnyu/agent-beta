"""Tests for the Notification model + Web Push delivery (``notify_sessions``)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.test import override_settings
from django.utils import timezone
from pywebpush import WebPushException

from djangoapp.models import (
    Notification,
    PushSubscription,
    User,
    UserSessionIndex,
    is_push_enabled,
    notify_sessions,
    push_test,
    vapid_public_key,
    vapid_subject,
)
from djangoapp.tests._base import BaseTestCase


class _FakeResponse:
    """Stand-in for the ``requests.Response`` WebPushException carries."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        # The warning path reads .text (bounded); give it something to say.
        self.text = f"fake {status_code} body"


# Deterministic regardless of the local .env: every dispatch test forces a
# fully-configured VAPID (values are fake — pywebpush itself is mocked).
PUSH_CONFIGURED = override_settings(VAPID_PRIVATE_KEY="fake-private-key")


class PushEnabledTests(BaseTestCase):
    """``is_push_enabled``: can the server deliver browser pushes at all.

    It means exactly "VAPID_PRIVATE_KEY is configured" — in-app storage,
    the bell and the list page do NOT depend on it; only Web Push
    fan-out does. The subject is derived, not configured.

    - test_disabled_when_key_missing, empty private key → False
    - test_enabled_when_key_set, key set → True
    """

    def test_disabled_when_key_missing(self) -> None:
        """Empty private key disables push."""
        with override_settings(VAPID_PRIVATE_KEY=""):
            self.assertFalse(is_push_enabled())

    def test_enabled_when_key_set(self) -> None:
        """Private key set → enabled (no other knob)."""
        with PUSH_CONFIGURED:
            self.assertTrue(is_push_enabled())


class VapidSubjectTests(BaseTestCase):
    """``vapid_subject`` derives the RFC 8292 contact from superusers.

    Push services need a ``sub`` contact so their abuse desk can reach
    the sender; the first superuser IS the operator, so their email is
    that contact (first = lowest pk, email-less ones skipped).

    - test_first_superuser_email, lowest-pk superuser with an email wins
    - test_skips_emailless_superusers, empty emails are passed over
    """

    def setUp(self) -> None:
        super().setUp()
        # lru_cache outlives test data: always start these tests cold.
        vapid_subject.cache_clear()

    def test_first_superuser_email(self) -> None:
        """Lowest-pk superuser with an email is the mailto: contact."""
        User.objects.create_user(
            username="root", password="pw", email="root@example.com", is_superuser=True
        )
        User.objects.create_user(
            username="root2", password="pw", email="later@example.com", is_superuser=True
        )
        self.assertEqual(vapid_subject(), "mailto:root@example.com")

    def test_skips_emailless_superusers(self) -> None:
        """A later superuser with an email beats an earlier email-less one."""
        User.objects.create_user(username="root", password="pw", is_superuser=True)
        User.objects.create_user(
            username="root2", password="pw", email="root2@example.com", is_superuser=True
        )
        self.assertEqual(vapid_subject(), "mailto:root2@example.com")


class VapidPublicKeyTests(BaseTestCase):
    """``vapid_public_key`` derives the browser-side applicationServerKey.

    The browser's ``applicationServerKey`` must equal the key signing the
    pushes, and py_vapid computes that key but never exposes it — hence
    the app-side derivation.

    - test_derivation_matches_known_curve_point, scalar 1 → the fixed P-256 generator point
    - test_empty_private_yields_empty_public, disabled VAPID → empty string
    """

    def test_derivation_matches_known_curve_point(self) -> None:
        """A known private scalar derives its known public point (P-256)."""
        # Deterministic vector: private scalar 1 (big-endian 32 bytes as
        # base64url) → the curve generator point. Catches encoding slips
        # (base64 vs hex, compressed vs uncompressed, padding).
        with override_settings(VAPID_PRIVATE_KEY="AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"):
            self.assertEqual(
                vapid_public_key(),
                "BJu_BtrZq1kF4FRxzhbVIiyJwsqjnyYmesB0cSmIX71EG8x_qE3hIKNnVdrzCm9H6MDUvdwVA27So0R9-nodPog",
            )

    def test_empty_private_yields_empty_public(self) -> None:
        """No private key configured → empty public key (push disabled)."""
        with override_settings(VAPID_PRIVATE_KEY=""):
            self.assertEqual(vapid_public_key(), "")


class NotificationRecordTests(BaseTestCase):
    """``Notification.record`` stores the row and schedules the fan-out.

    - test_record_creates_and_returns_row, all fields land, public_id minted
    - test_record_schedules_push_only_after_commit, on_commit gates the push enqueue
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_record_creates_and_returns_row(self) -> None:
        """Record stores recipient/kind/body/url and returns the row."""
        notification = Notification.record(
            recipient=self.user, kind="task.done", body="Import finished", url="/tasks/1"
        )
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.kind, "task.done")
        self.assertEqual(notification.body, "Import finished")
        self.assertEqual(notification.url, "/tasks/1")
        self.assertIsNone(notification.read_at)
        self.assertTrue(notification.public_id)
        self.assertTrue(Notification.objects.filter(public_id=notification.public_id).exists())

    def test_record_schedules_push_only_after_commit(self) -> None:
        """The push ENQUEUE waits for on_commit — a rolled-back row never pushes."""
        with patch("djangoapp.models.notifications.deliver_push") as schedule_mock:
            # capture(execute=True) collects AND runs the on_commit
            # callbacks when ITS context exits — still inside the patch,
            # so the deferred enqueue lands on the mock. The assert inside
            # the block fails if record() ever pushes eagerly; the count
            # pins that exactly one thing — the push enqueue — was
            # scheduled, carrying the stored row's fields.
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                notification = Notification.record(
                    recipient=self.user, kind="k", body="b", url="/x"
                )
                schedule_mock.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            schedule_mock.assert_called_once()
            user_pk, payload_arg = schedule_mock.call_args.args
            self.assertEqual(user_pk, self.user.pk)
            self.assertEqual(
                payload_arg,
                {"public_id": notification.public_id, "kind": "k", "body": "b", "url": "/x"},
            )


class PushDispatchTests(BaseTestCase):
    """``notify_sessions`` fan-out: per-subscription delivery, pruning, isolation.

    - test_push_called_once_per_subscription, one webpush call per endpoint
    - test_push_payload_carries_row_fields, payload mirrors the stored row
    - test_gone_status_prunes_subscription, 404/410 deletes the endpoint row
    - test_other_error_keeps_subscription, non-gone failures prune nothing
    - test_non_webpush_exception_never_propagates, arbitrary exceptions are contained
    - test_disabled_vapid_skips_webpush, unset VAPID means no push attempts
    - test_no_superuser_email_skips_webpush, no contact to sign for → skip
    - test_push_test_enqueues_without_row, push_test counts + enqueues, stores nothing
    - test_push_test_zero_devices_schedules_nothing, count 0 enqueues nothing
    """

    def setUp(self) -> None:
        super().setUp()
        # vapid_subject's lru_cache outlives test data — start cold here
        # too: the claims assertions below depend on THIS class's fixtures.
        vapid_subject.cache_clear()
        User.objects.create_user(
            username="root", password="pw", email="root@example.com", is_superuser=True
        )
        self.user = User.objects.create_user(username="alice", password="pw")

    def _subscription(self, endpoint: str) -> PushSubscription:
        # Direct row creation needs the O2O's index row (the CASCADE
        # chain root) — mint a session + index to hang it from.
        session_row = Session.objects.create(
            session_key=uuid.uuid4().hex,
            session_data="",
            expire_date=timezone.now() + timedelta(days=14),
        )
        index = UserSessionIndex.objects.create(
            user=self.user, session=session_row, expire_date=session_row.expire_date
        )
        return PushSubscription.objects.create(
            user=self.user,
            endpoint=endpoint,
            p256dh="p256dh-key",
            auth="auth-key",
            session_index=index,
        )

    def _notify(self) -> None:
        # Dispatch tests exercise the delivery core directly — record()
        # only enqueues the Huey task (see the record tests above).
        notify_sessions(
            self.user,
            {"public_id": "x1", "kind": "task.done", "body": "hi", "url": "/x"},
        )

    @PUSH_CONFIGURED
    def test_push_called_once_per_subscription(self) -> None:
        """One webpush call per subscription, carrying the endpoint's keys."""
        self._subscription("https://push.example/e1")
        self._subscription("https://push.example/e2")
        with patch("djangoapp.models.notifications.webpush") as webpush_mock:
            self._notify()
        self.assertEqual(webpush_mock.call_count, 2)
        endpoints = sorted(
            call.kwargs["subscription_info"]["endpoint"] for call in webpush_mock.call_args_list
        )
        self.assertEqual(endpoints, ["https://push.example/e1", "https://push.example/e2"])
        first = webpush_mock.call_args_list[0].kwargs
        self.assertEqual(first["subscription_info"]["keys"]["p256dh"], "p256dh-key")
        self.assertEqual(first["vapid_private_key"], "fake-private-key")
        self.assertEqual(first["vapid_claims"], {"sub": "mailto:root@example.com"})
        self.assertGreater(first["ttl"], 0)

    @PUSH_CONFIGURED
    def test_push_payload_carries_row_fields(self) -> None:
        """The JSON payload mirrors the row (public_id/kind/body/url)."""
        self._subscription("https://push.example/e1")
        with patch("djangoapp.models.notifications.webpush") as webpush_mock:
            self._notify()
        payload = json.loads(webpush_mock.call_args.kwargs["data"])
        self.assertEqual(payload["public_id"], "x1")
        self.assertEqual(payload["kind"], "task.done")
        self.assertEqual(payload["body"], "hi")
        self.assertEqual(payload["url"], "/x")

    @PUSH_CONFIGURED
    def test_gone_status_prunes_subscription(self) -> None:
        """404/410 responses delete the dead endpoint (RFC 8030)."""
        for status in (404, 410):
            with self.subTest(status=status):
                self._subscription("https://push.example/dead")
                with patch(
                    "djangoapp.models.notifications.webpush",
                    side_effect=WebPushException("gone", response=_FakeResponse(status)),
                ):
                    self._notify()
                self.assertFalse(
                    PushSubscription.objects.filter(endpoint="https://push.example/dead").exists()
                )

    @PUSH_CONFIGURED
    def test_other_error_keeps_subscription(self) -> None:
        """A 500-ish push failure keeps the subscription for the next try."""
        self._subscription("https://push.example/flaky")
        with patch(
            "djangoapp.models.notifications.webpush",
            side_effect=WebPushException("boom", response=_FakeResponse(500)),
        ):
            self._notify()
        self.assertTrue(
            PushSubscription.objects.filter(endpoint="https://push.example/flaky").exists()
        )

    @PUSH_CONFIGURED
    def test_non_webpush_exception_never_propagates(self) -> None:
        """Arbitrary exceptions inside delivery are contained (logged, not raised)."""
        self._subscription("https://push.example/e1")
        with patch("djangoapp.models.notifications.webpush", side_effect=OSError("network")):
            self._notify()  # must not raise

    def test_disabled_vapid_skips_webpush(self) -> None:
        """Unset VAPID (the dev sentinel default) skips push attempts entirely."""
        self._subscription("https://push.example/e1")
        with (
            override_settings(VAPID_PRIVATE_KEY=""),
            patch("djangoapp.models.notifications.webpush") as webpush_mock,
        ):
            count = notify_sessions(self.user, {"public_id": "x", "kind": "k", "body": "b"})
            self.assertEqual(count, 0)  # off is off, even with a subscription present
        webpush_mock.assert_not_called()

    @PUSH_CONFIGURED
    def test_push_test_enqueues_without_row(self) -> None:
        """push_test returns the device count and enqueues — no row, no inline delivery."""
        self._subscription("https://push.example/e1")
        self._subscription("https://push.example/e2")
        with patch("djangoapp.models.notifications.deliver_push") as schedule_mock:
            count = push_test(self.user)
        self.assertEqual(count, 2)
        _user_pk, payload = schedule_mock.call_args.args
        self.assertEqual(payload["kind"], "test")
        self.assertEqual(payload["url"], "/")
        self.assertEqual(Notification.objects.count(), 0)

    @PUSH_CONFIGURED
    def test_push_test_zero_devices_schedules_nothing(self) -> None:
        """No subscriptions → count 0 and nothing enqueued."""
        with patch("djangoapp.models.notifications.deliver_push") as schedule_mock:
            self.assertEqual(push_test(self.user), 0)
        schedule_mock.assert_not_called()

    @PUSH_CONFIGURED
    def test_no_superuser_email_skips_webpush(self) -> None:
        """Key set but no superuser email (no RFC 8292 contact) → skip."""
        User.objects.filter(username="root").delete()
        vapid_subject.cache_clear()
        self._subscription("https://push.example/e1")
        with patch("djangoapp.models.notifications.webpush") as webpush_mock:
            self._notify()
        webpush_mock.assert_not_called()


class PushSubscriptionModelTests(BaseTestCase):
    """PushSubscription basics: user cascade + endpoint uniqueness.

    - test_user_deletion_cascades, deleting the user removes subscriptions
    """

    def test_user_deletion_cascades(self) -> None:
        """Deleting the user removes their subscriptions (and notifications)."""
        user = User.objects.create_user(username="bob", password="pw")
        session_row = Session.objects.create(
            session_key=uuid.uuid4().hex,
            session_data="",
            expire_date=timezone.now() + timedelta(days=14),
        )
        index = UserSessionIndex.objects.create(
            user=user, session=session_row, expire_date=session_row.expire_date
        )
        PushSubscription.objects.create(
            user=user, endpoint="https://push.example/e1", p256dh="p", auth="a", session_index=index
        )
        Notification.record(recipient=user, kind="k", body="b")
        user.delete()
        self.assertFalse(PushSubscription.objects.exists())
        self.assertFalse(Notification.objects.exists())
