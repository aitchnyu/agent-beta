"""Tests for the app's Huey task (``clear_expired_sessions``)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.utils import timezone

from djangoapp.models import PushSubscription, User, UserSessionIndex
from djangoapp.tests._base import BaseTestCase
from ourapp.tasks import clear_expired_sessions


class ClearExpiredSessionsTaskTests(BaseTestCase):
    """The daily cron GC: expired sessions die with their index/push rows.

    The chain (Session → UserSessionIndex → PushSubscription) means
    expired sessions must actually be DELETED for their subscriptions to
    die — the task pushes ``clearsessions`` to do it. Run inline via
    ``.call_local()`` — huey's synchronous, queue-bypassing invocation,
    so no consumer is needed.

    - test_expired_session_and_chain_deleted, the expired session and its index/push rows die
    - test_live_session_kept, an unexpired session and its rows survive
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="alice", password="pw")

    def _chain(self, expire_offset: timedelta) -> Session:
        """Build a session → index → push-subscription chain expiring at now+offset."""
        session_row = Session.objects.create(
            session_key=uuid.uuid4().hex,
            session_data="",
            expire_date=timezone.now() + expire_offset,
        )
        index = UserSessionIndex.objects.create(
            user=self.user, session=session_row, expire_date=session_row.expire_date
        )
        PushSubscription.objects.create(
            user=self.user,
            endpoint=f"https://push.example/{session_row.session_key}",
            p256dh="p256dh-key",
            auth="auth-key",
            session_index=index,
        )
        return session_row

    def test_expired_session_and_chain_deleted(self) -> None:
        """Clearsessions drops the expired session; CASCADE takes index + push rows."""
        expired = self._chain(timedelta(seconds=-1))
        clear_expired_sessions.call_local()
        self.assertFalse(Session.objects.filter(session_key=expired.session_key).exists())
        self.assertFalse(UserSessionIndex.objects.filter(session_id=expired.session_key).exists())
        self.assertFalse(
            PushSubscription.objects.filter(
                endpoint=f"https://push.example/{expired.session_key}"
            ).exists()
        )

    def test_live_session_kept(self) -> None:
        """An unexpired session and its chain rows survive the sweep."""
        live = self._chain(timedelta(days=14))
        clear_expired_sessions.call_local()
        self.assertTrue(Session.objects.filter(session_key=live.session_key).exists())
        self.assertTrue(UserSessionIndex.objects.filter(session_id=live.session_key).exists())
        self.assertTrue(
            PushSubscription.objects.filter(
                endpoint=f"https://push.example/{live.session_key}"
            ).exists()
        )
