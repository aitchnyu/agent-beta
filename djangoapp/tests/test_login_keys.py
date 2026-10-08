from __future__ import annotations

import re
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, override_settings, tag
from django.utils import timezone

from djangoapp.models import LoginKey, User
from djangoapp.tests._base import BaseTestCase

_KEY_URL_RE = re.compile(r"(/login-for-test/[A-Za-z0-9_\-]+/)")


class LoginKeyTests(BaseTestCase):
    """Issue/redeem semantics for one-time login keys.

    Keys are hashed at rest, redeem exactly once, and refuse expired or
    unknown values.

    - test_issue_stores_hash_not_raw_key, the raw key never reaches the table
    - test_issue_refuses_sub_hour, issue() itself enforces the 60-minute floor
    - test_issue_sweeps_expired_rows, issue() clears stale rows
    - test_redeem_consumed_after_success, a second redeem returns None
    - test_redeem_marks_used_at, success stamps used_at
    - test_redeem_expired_is_none, past-expiry keys are refused (unmarked)
    - test_redeem_garbage_is_none, unknown keys are refused
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="linkuser", email="link@example.com")

    def test_issue_stores_hash_not_raw_key(self) -> None:
        """The table holds only the SHA-256; the raw key exists solely in the return."""
        raw, _expires_at = LoginKey.issue(self.user)
        row = LoginKey.objects.get()
        self.assertNotEqual(row.key_hash, raw)
        self.assertEqual(len(row.key_hash), 64)
        self.assertIsNone(row.used_at)
        self.assertGreater(row.expires_at, timezone.now())

    def test_issue_refuses_sub_hour(self) -> None:
        """issue() itself refuses sub-hour lifetimes — the API path has no CLI guard."""
        with self.assertRaises(ValueError):
            LoginKey.issue(self.user, minutes=59)
        self.assertEqual(LoginKey.objects.count(), 0)

    def test_issue_sweeps_expired_rows(self) -> None:
        """issue() sweeps expired rows out of the table."""
        raw, _a = LoginKey.issue(self.user)
        LoginKey.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        LoginKey.issue(self.user)
        self.assertEqual(LoginKey.objects.count(), 1)
        self.assertIsNone(LoginKey.redeem(raw))

    @tag("scratch-test-subset")
    def test_redeem_consumed_after_success(self) -> None:
        """A valid key returns its user once, then None forever after."""
        raw, _expires_at = LoginKey.issue(self.user)
        redeemed = LoginKey.redeem(raw)
        self.assertEqual(redeemed, self.user)
        self.assertIsNone(LoginKey.redeem(raw))

    def test_redeem_marks_used_at(self) -> None:
        """A successful redeem stamps used_at (mark, not delete)."""
        raw, _expires_at = LoginKey.issue(self.user)
        LoginKey.redeem(raw)
        row = LoginKey.objects.get()
        self.assertIsNotNone(row.used_at)

    def test_redeem_expired_is_none(self) -> None:
        """Keys past their expires_at are refused and never marked used."""
        raw, _expires_at = LoginKey.issue(self.user)
        LoginKey.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertIsNone(LoginKey.redeem(raw))
        self.assertIsNone(LoginKey.objects.get().used_at)

    def test_redeem_garbage_is_none(self) -> None:
        """Unknown keys hash to nothing and return None."""
        self.assertIsNone(LoginKey.redeem("not-a-real-key"))


class MakeLoginLinkCommandTests(BaseTestCase):
    """`makeloginlink` end to end: command output drives a working login.

    Mirrors the VM operator flow — run over multipass exec, paste the
    printed URL — including the failure guards shared with promotetosuperuser.

    - test_prints_working_one_time_url, printed URL logs the user in once
    - test_printed_url_uses_the_first_origin, the link carries BASE_URLS[0]
    - test_redeem_rotates_session_key, login() cycles the session
    - test_missing_email_errors, unknown email raises CommandError
    - test_duplicate_email_errors, ambiguous email raises CommandError
    - test_case_variant_email_matches, lookup is iexact
    - test_minutes_must_be_at_least_an_hour, sub-hour --minutes refuses
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="cmduser", email="cmd@example.com")

    def test_prints_working_one_time_url(self) -> None:
        """The URL in stdout authenticates the session once, then 404s."""
        out = StringIO()
        call_command("makeloginlink", self.user.email, stdout=out)
        match = _KEY_URL_RE.search(out.getvalue())
        assert match is not None  # test-side invariant: the command always prints the URL
        path = match.group(1)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        # Single use: the same URL never logs in again. Asked from a FRESH
        # anonymous client — this one is now signed in (the redemption logged
        # it in), which the view refuses instead of 404ing.
        self.assertEqual(Client().get(path).status_code, 404)

    def test_printed_url_uses_the_first_origin(self) -> None:
        """The printed link carries the first BASE_URLS origin — never an assumed one."""
        out = StringIO()
        with override_settings(BASE_URLS=["https://vm.example", "https://other.example"]):
            call_command("makeloginlink", self.user.email, stdout=out)
        self.assertIn("https://vm.example/login-for-test/", out.getvalue())

    def test_redeem_rotates_session_key(self) -> None:
        """login() cycles the session key (fixation-safe)."""
        pre_key = self.client.session.session_key
        out = StringIO()
        call_command("makeloginlink", self.user.email, stdout=out)
        match = _KEY_URL_RE.search(out.getvalue())
        assert match is not None
        self.client.get(match.group(1))
        self.assertNotEqual(self.client.session.session_key, pre_key)

    def test_missing_email_errors(self) -> None:
        """No user row means no link — the command refuses."""
        with self.assertRaises(CommandError):
            call_command("makeloginlink", "nobody@example.com", stdout=StringIO())

    def test_duplicate_email_errors(self) -> None:
        """Two users sharing an email is ambiguous — refuse rather than guess."""
        User.objects.create_user(username="cmduser2", email="cmd@example.com")
        with self.assertRaises(CommandError):
            call_command("makeloginlink", self.user.email, stdout=StringIO())

    def test_case_variant_email_matches(self) -> None:
        """The email lookup is case-insensitive."""
        out = StringIO()
        call_command("makeloginlink", "CMD@example.com", stdout=out)
        self.assertIn("/login-for-test/", out.getvalue())

    def test_minutes_must_be_at_least_an_hour(self) -> None:
        """Sub-hour --minutes issues a link that dies before a human uses it — refuse."""
        for bad in (0, -5, 30, 59):
            with self.assertRaises(CommandError):
                call_command("makeloginlink", self.user.email, minutes=bad, stdout=StringIO())
