from datetime import timedelta

import time_machine
from django.contrib.sessions.models import Session
from django.test import Client, override_settings
from django.utils import timezone

from djangoapp.models import User, UserHistory, UserSessionIndex
from djangoapp.tests._base import BaseTestCase


class SessionIndexTests(BaseTestCase):
    """The user→sessions index: login logging, CASCADE, idle touch.

    The ``user_logged_in`` receiver records logins; ALL index rows are
    written by ``SessionIdleTouchMiddleware`` (backfill on the first
    authenticated request — at login time the final session key is not
    knowable: auth.login may flush or not-yet-save the session).
    - test_login_records_history, any auth.login fires the receiver: history entry
    - test_session_deletion_cascades_index, deleting the session row removes the index row
    - test_touch_rearms_when_past_half_life, a due row is bumped and the cookie re-issued
    - test_touch_skips_fresh_sessions, a fresh row is left untouched (amortized: no writes)
    - test_touch_window_follows_setting, a shorter SESSION_COOKIE_AGE slides by that window
    - test_touch_fires_after_half_window_of_idleness, time travel: 8 idle days re-arm to now+14d
    - test_lazy_backfill_reindexes_preexisting_session, missing row gets one on the next request
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="alice", password="pw", first_name="Alice", last_name="Doe"
        )
        super().setUp()

    def _row(self) -> UserSessionIndex:
        return UserSessionIndex.objects.get(user=self.user)

    def test_login_records_history(self) -> None:
        """Any auth.login fires the receiver: history entry (log rides along)."""
        client = Client()
        client.force_login(self.user)
        self.assertTrue(UserHistory.objects.filter(target_user=self.user, action="login").exists())

    def test_session_deletion_cascades_index(self) -> None:
        """Deleting the session row removes the index row (CASCADE)."""
        client = Client()
        client.force_login(self.user)
        client.get("/")  # backfill creates the index row
        key = self._row().session_id
        Session.objects.get(session_key=key).delete()
        self.assertFalse(UserSessionIndex.objects.filter(user=self.user).exists())

    def test_touch_rearms_when_past_half_life(self) -> None:
        """A due row (past half the window) is bumped; cookie re-issued."""
        client = Client()
        client.force_login(self.user)
        client.get("/")  # backfill creates the index row
        row = self._row()
        # Over half the 14-day window has elapsed → due.
        UserSessionIndex.objects.filter(pk=row.pk).update(
            expire_date=timezone.now() + timedelta(days=4)
        )
        response = client.get("/")
        row.refresh_from_db()
        self.assertAlmostEqual(
            row.expire_date, timezone.now() + timedelta(days=14), delta=timedelta(seconds=60)
        )
        # session.modified flipped → SessionMiddleware re-saved and re-issued.
        self.assertIn("sessionid", response.cookies)

    def test_touch_skips_fresh_sessions(self) -> None:
        """A fresh row is left untouched (the amortized no-write path)."""
        client = Client()
        client.force_login(self.user)
        client.get("/")  # backfill creates the index row
        before = self._row().expire_date
        client.get("/")
        self.assertEqual(self._row().expire_date, before)

    @override_settings(SESSION_COOKIE_AGE=3600)  # a 1-hour idle window
    def test_touch_window_follows_setting(self) -> None:
        """A shorter SESSION_COOKIE_AGE slides the deadline by that window.

        Both the middleware and Django's session save read the setting
        dynamically, so the whole chain (due-check, index row, re-saved
        session row) honors the knob — this pins that nothing hardcodes
        the default 14 days. (SESSION_IDLE_DAYS itself is read once at
        settings import; it only feeds SESSION_COOKIE_AGE.)
        """
        client = Client()
        client.force_login(self.user)
        client.get("/")  # backfill at the 1-hour window
        row = self._row()
        # 25 minutes left — past half of the SHORT window → due.
        UserSessionIndex.objects.filter(pk=row.pk).update(
            expire_date=timezone.now() + timedelta(minutes=25)
        )
        client.get("/")
        row.refresh_from_db()
        # Re-armed to the full 1-hour window (not 14 days) — the setting won.
        self.assertAlmostEqual(
            row.expire_date, timezone.now() + timedelta(hours=1), delta=timedelta(seconds=60)
        )

    def test_touch_fires_after_half_window_of_idleness(self) -> None:
        """Time travel: 8 idle days (> half the window) re-arm to now+14d.

        Unlike the sibling touch tests (which edit expire_date to fake
        urgency), this advances the clock itself — the touch must fire from
        the elapsed time alone.
        """
        client = Client()
        client.force_login(self.user)
        client.get("/")  # backfill
        with time_machine.travel(timezone.now() + timedelta(days=8)):
            client.get("/")
            row = UserSessionIndex.objects.get(user=self.user)
            self.assertAlmostEqual(
                row.expire_date,
                timezone.now() + timedelta(days=14),
                delta=timedelta(seconds=60),
            )

    def test_lazy_backfill_reindexes_preexisting_session(self) -> None:
        """A session missing its row (pre-index login) gets one on request."""
        client = Client()
        client.force_login(self.user)
        UserSessionIndex.objects.filter(user=self.user).delete()
        client.get("/")
        row = self._row()
        self.assertEqual(row.user, self.user)
        session_row = Session.objects.get(session_key=row.session_id)
        self.assertEqual(row.expire_date, session_row.expire_date)
