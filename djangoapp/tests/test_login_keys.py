from __future__ import annotations

import re
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from djangoapp.models import TestLoginKey, User
from djangoapp.tests._base import BaseTestCase

_KEY_URL_RE = re.compile(r"(/login-for-test/by-key/[A-Za-z0-9_\-]+/)")


class TestLoginKeyTests(BaseTestCase):
    """Issue/redeem semantics for one-time login keys.

    Keys are hashed at rest, redeem exactly once, and refuse expired or
    unknown values.

    - test_issue_stores_hash_not_raw_key, the raw key never reaches the table
    - test_redeem_consumed_after_success, a second redeem returns None
    - test_redeem_expired_is_none, past-expiry keys are refused
    - test_redeem_garbage_is_none, unknown keys are refused
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="linkuser", email="link@example.com")

    def test_issue_stores_hash_not_raw_key(self) -> None:
        """The table holds only the SHA-256; the raw key exists solely in the return."""
        raw = TestLoginKey.issue(self.user, minutes=15)
        row = TestLoginKey.objects.get()
        self.assertNotEqual(row.key_hash, raw)
        self.assertEqual(len(row.key_hash), 64)
        self.assertIsNone(row.used_at)
        self.assertGreater(row.expires_at, timezone.now())

    def test_redeem_consumed_after_success(self) -> None:
        """A valid key returns its user once, then None forever after."""
        raw = TestLoginKey.issue(self.user, minutes=15)
        redeemed = TestLoginKey.redeem(raw)
        self.assertEqual(redeemed, self.user)
        self.assertIsNone(TestLoginKey.redeem(raw))

    def test_redeem_expired_is_none(self) -> None:
        """Keys past their expires_at are refused and never marked used."""
        raw = TestLoginKey.issue(self.user, minutes=15)
        TestLoginKey.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertIsNone(TestLoginKey.redeem(raw))

    def test_redeem_garbage_is_none(self) -> None:
        """Unknown keys hash to nothing and return None."""
        self.assertIsNone(TestLoginKey.redeem("not-a-real-key"))


class MakeLoginLinkCommandTests(BaseTestCase):
    """`makeloginlink` end to end: command output drives a working login.

    Mirrors the VM operator flow — run over ssh, paste the printed URL —
    including the failure guards shared with makesuperuser.

    - test_prints_working_one_time_url, printed URL logs the user in once
    - test_missing_email_errors, unknown email raises CommandError
    - test_duplicate_email_errors, ambiguous email raises CommandError
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="cmduser", email="cmd@example.com")

    def test_prints_working_one_time_url(self) -> None:
        """The URL in stdout authenticates the session once, then 404s."""
        out = StringIO()
        call_command("makeloginlink", self.user.email, base_url="https://vm.example", stdout=out)
        match = _KEY_URL_RE.search(out.getvalue())
        assert match is not None  # test-side invariant: the command always prints the URL
        path = match.group(1)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_missing_email_errors(self) -> None:
        """No user row means no link — the command refuses."""
        with self.assertRaises(CommandError):
            call_command("makeloginlink", "nobody@example.com", stdout=StringIO())

    def test_duplicate_email_errors(self) -> None:
        """Two users sharing an email is ambiguous — refuse rather than guess."""
        User.objects.create_user(username="cmduser2", email="cmd@example.com")
        with self.assertRaises(CommandError):
            call_command("makeloginlink", self.user.email, stdout=StringIO())
