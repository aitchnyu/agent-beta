from __future__ import annotations

import hashlib
import secrets
from datetime import datetime as dt_datetime
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

if TYPE_CHECKING:
    from djangoapp.models import User


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class LoginKey(models.Model):
    """One-time login link issued by an admin (CLI or the details page).

    ``makeloginlink`` and the user-details page issue a secret URL that
    lets a chosen user sign in exactly once before it expires — the
    operator path for the VM or any environment without Google
    credentials; ``redeem_login_key`` redeems it. Only the SHA-256 of the
    key is stored — a database leak must not yield usable links — and
    redemption is atomic, so a link logs its user in exactly once, ever.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,  # house default; also keeps spent keys attributable
        related_name="login_keys",
    )
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, user: User, minutes: int = 15) -> tuple[str, dt_datetime]:
        """Create a fresh key row for ``user``; return the raw key + its expiry.

        The raw key exists only in this return value (and the caller's
        response/stdout) — never in the database. Expired rows are
        swept on every issue: they can never redeem again, so they're pure
        clutter.
        """
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
        key = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=minutes)
        cls.objects.create(
            user=user,
            key_hash=_hash_key(key),
            expires_at=expires_at,
        )
        return key, expires_at

    @classmethod
    def redeem(cls, key: str) -> User | None:
        """Exchange a raw key for its user, consuming the row.

        Returns ``None`` for unknown, already-used, or expired keys — callers
        treat that as a 404 like every other resource gate. ``select_for_update``
        serialises concurrent redemptions so "one time only" holds even under
        a double-click race.
        """
        with transaction.atomic():
            row = (
                cls.objects.select_for_update()
                .filter(
                    key_hash=_hash_key(key),
                    used_at__isnull=True,
                    expires_at__gt=timezone.now(),
                )
                .first()
            )
            if row is None:
                return None
            row.used_at = timezone.now()
            row.save(update_fields=["used_at"])
            return row.user
