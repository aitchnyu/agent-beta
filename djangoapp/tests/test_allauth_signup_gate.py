from __future__ import annotations

from typing import TYPE_CHECKING

from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from djangoapp.adapters import SocialAccountAdapter
from djangoapp.models import User, UserHistory
from djangoapp.tests._base import BaseTestCase

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


def _session_request() -> WSGIRequest:
    """Return a request with a real session.

    Only save_user's tests need it: allauth reads request.session during
    email setup; the gate tests never touch the request.
    """
    request = RequestFactory().get("/")
    request.session = SessionStore()
    return request


def _make_sociallogin(email: str) -> SocialLogin:  # type: ignore[no-any-unimported] # allauth ships no stubs (pyproject allow-lists it as untyped)
    """Build an unsaved Google SocialLogin for ``email``, as the OAuth callback delivers it."""
    return SocialLogin(
        user=User(email=email, username=email),
        account=SocialAccount(provider="google", uid=email),
        email_addresses=[EmailAddress(email=email, verified=True, primary=True)],
    )


class SignupGateTests(BaseTestCase):
    """The allauth signup gate: adapter wiring + default-open policy.

    ``SocialAccountAdapter.is_open_for_signup`` (``djangoapp/adapters.py``) is
    the single hook deciding whether a social login may CREATE an account; the
    settings must route allauth's adapter resolution to it, and the shipped
    default must be "open" (any email may sign up) so restricting signups is
    always an explicit code change in the adapter.

    - test_adapter_is_wired, allauth resolves SOCIALACCOUNT_ADAPTER to our adapter class
    - test_signup_open_by_default, is_open_for_signup returns True for any email
    """

    def test_adapter_is_wired(self) -> None:
        """``get_adapter()`` resolves to our adapter.

        - the SOCIALACCOUNT_ADAPTER setting routes allauth to the gate
        """
        self.assertIsInstance(get_adapter(), SocialAccountAdapter)

    def test_signup_open_by_default(self) -> None:
        """The shipped gate lets any authenticated email create an account.

        - is_open_for_signup returns True per email, no denylist shipped
        """
        gate = SocialAccountAdapter()
        for email in ("alice@gmail.com", "bob@any-domain.org"):
            with self.subTest(email=email):
                allowed = gate.is_open_for_signup(
                    RequestFactory().get("/"), _make_sociallogin(email)
                )
                self.assertTrue(allowed)


class SaveUserAuditTests(BaseTestCase):
    """``SocialAccountAdapter.save_user``: fresh signups get one history entry, re-signins none.

    - test_fresh_signup_records_created, a new social signup lands the
      user row, the linked SocialAccount, and exactly one "created"
      history entry whose user field is the new user itself
    - test_existing_signin_not_reaudited, an existing user signing in
      gets the SocialAccount link but no history entry at all
    """

    def test_fresh_signup_records_created(self) -> None:
        """A fresh social signup persists all three rows it must.

        - the user row exists (has a pk)
        - the Google SocialAccount row links to it
        - the history table holds exactly one entry for that user, with
          action "created"
        - that entry's user field points at the new user itself (no
          other account could have written it)
        """
        gate = SocialAccountAdapter()
        sociallogin = _make_sociallogin("fresh@gmail.com")
        request = _session_request()

        user = gate.save_user(request, sociallogin)

        self.assertIsNotNone(user.pk)
        self.assertTrue(SocialAccount.objects.filter(user=user, provider="google").exists())
        history = UserHistory.objects.filter(target_user=user)
        self.assertEqual(history.count(), 1)
        entry = history.get()
        self.assertEqual(entry.action, "created")
        self.assertEqual(entry.user, user)

    def test_existing_signin_not_reaudited(self) -> None:
        """save_user links a returning user and writes no history row itself.

        - the same user row comes back (same pk), with the Google
          SocialAccount row now linked to it
        - save_user writes no "created" entry — or any entry — for an
          existing user
        - zero entries total is expected here because only save_user
            runs: the "login" entry a real sign-in produces comes from
            the user_logged_in signal receiver (models/base.py), and this
            test never calls login()
        """
        existing = User.objects.create_user(username="back", email="back@gmail.com")
        gate = SocialAccountAdapter()
        sociallogin = SocialLogin(
            user=existing,
            account=SocialAccount(provider="google", uid="back@gmail.com"),
            email_addresses=[EmailAddress(email="back@gmail.com", verified=True, primary=True)],
        )
        request = _session_request()

        user = gate.save_user(request, sociallogin)

        self.assertEqual(user.pk, existing.pk)
        self.assertTrue(SocialAccount.objects.filter(user=existing, provider="google").exists())
        self.assertFalse(UserHistory.objects.filter(target_user=existing).exists())
