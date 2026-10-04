"""Tests for the framework Huey task (``deliver_push``)."""

from __future__ import annotations

from unittest.mock import patch

from djangoapp.models import User
from djangoapp.tasks import deliver_push
from djangoapp.tests._base import BaseTestCase


class DeliverPushTaskTests(BaseTestCase):
    """``deliver_push`` bridges the queue to ``notify_sessions``.

    The task crosses the queue as a pk (task args serialize; a stale
    instance would push stale data). These run it inline via
    ``.call_local()`` — huey's synchronous, queue-bypassing invocation,
    so no consumer is needed.

    - test_fans_out_to_notify_sessions, a live pk hands user + payload to notify_sessions
    - test_missing_user_raises, a deleted user's pk raises (honest signal)
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_fans_out_to_notify_sessions(self) -> None:
        """The task hands the fetched user and the payload to notify_sessions."""
        with patch("djangoapp.models.notify_sessions") as notify_mock:
            deliver_push.call_local(self.user.pk, {"kind": "k", "body": "b"})
        notify_mock.assert_called_once()
        user_arg, payload_arg = notify_mock.call_args.args
        self.assertEqual(user_arg, self.user)
        self.assertEqual(payload_arg, {"kind": "k", "body": "b"})

    def test_missing_user_raises(self) -> None:
        """A pk whose user is gone raises — their subscriptions CASCADE-died anyway."""
        pk = self.user.pk
        self.user.delete()
        with self.assertRaises(User.DoesNotExist):
            deliver_push.call_local(pk, {"kind": "k", "body": "b"})
