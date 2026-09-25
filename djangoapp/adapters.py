"""Allauth extension seam: the signup gate for social accounts.

Google login is the only way in (``SOCIALACCOUNT_ONLY``), so this one hook
decides whether a just-authenticated email may CREATE an account. It runs for
new signups only — existing users sign in unchecked, and locking one out is a
data question (``User.is_active = False``), not a code question. Returning
``False`` makes allauth render its stock ``account/signup_closed`` page, which
already extends our layout override. Example policies (invite-based allowlist,
denylist) live in docs/social-login.md.
"""

from __future__ import annotations

import typing

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest


class SocialAccountAdapter(DefaultSocialAccountAdapter):  # type: ignore[misc, no-any-unimported] # base resolves to Any: allauth ships no stubs (pyproject allow-lists it as untyped)
    """``SOCIALACCOUNT_ADAPTER`` target; edit ``is_open_for_signup`` to restrict signups."""

    def is_open_for_signup(  # type: ignore[no-any-unimported] # SocialLogin resolves to Any: allauth ships no stubs (pyproject allow-lists it as untyped)
        self,
        request: HttpRequest,  # noqa: ARG002 # allauth's hook signature; unread by the open default
        sociallogin: SocialLogin,  # noqa: ARG002 # allauth's hook signature; unread by the open default
    ) -> bool:
        """Whether ``sociallogin.user.email`` may create an account (default: anyone)."""
        return True
