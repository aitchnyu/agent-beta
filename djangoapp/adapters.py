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
from django.db import transaction

from djangoapp.models import User, UserHistory

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

    # TODO how to consolidate code in one place, ie models?
    def save_user(  # type: ignore[no-any-unimported] # allauth ships no stubs (pyproject allow-lists it as untyped)
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        form: typing.Any | None = None,  # noqa: ANN401 # allauth's signup form is untyped upstream
    ) -> User:
        """Persist the social signup, auditing fresh accounts as "created".

        Existing users signing in again are not re-audited (``is_existing``).
        No request actor exists at signup — the new user is recorded as its
        own actor, matching the ``createuser`` convention.
        """
        created = not sociallogin.is_existing
        # Atomic: a failure between allauth's row and our audit entry must
        # not strand an unaudited user.
        with transaction.atomic():
            user: User = super().save_user(request, sociallogin, form=form)
            if created:
                UserHistory.record_created(user, user, user.snapshot())
        return user
