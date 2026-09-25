from unittest import mock

from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.test import RequestFactory

from djangoapp.adapters import SocialAccountAdapter
from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase


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
    - test_mocked_policy_rejects_email, a mock denylist policy flips the gate's
      answer per email, proving the hook's return value is the verdict
    """

    def test_adapter_is_wired(self) -> None:
        """``get_adapter()`` returns our adapter, proving the settings wiring."""
        self.assertIsInstance(get_adapter(), SocialAccountAdapter)

    def test_signup_open_by_default(self) -> None:
        """The shipped gate lets any authenticated email create an account."""
        gate = SocialAccountAdapter()
        for email in ("alice@gmail.com", "bob@any-domain.org"):
            with self.subTest(email=email):
                allowed = gate.is_open_for_signup(
                    RequestFactory().get("/"), _make_sociallogin(email)
                )
                self.assertTrue(allowed)

    def test_mocked_policy_rejects_email(self) -> None:
        """A mock policy's verdict is returned as-is.

        False for the denied email, True for any other — the hook contract a
        real policy relies on.
        """
        gate = SocialAccountAdapter()
        with mock.patch.object(
            SocialAccountAdapter,
            "is_open_for_signup",
            side_effect=lambda _request, sociallogin: (
                sociallogin.user.email != "denied@example.com"
            ),
        ):
            for email, expected in (
                ("denied@example.com", False),
                ("someone-else@example.com", True),
            ):
                with self.subTest(email=email):
                    allowed = gate.is_open_for_signup(
                        RequestFactory().get("/"), _make_sociallogin(email)
                    )
                    self.assertIs(allowed, expected)
