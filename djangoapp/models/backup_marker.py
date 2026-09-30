from __future__ import annotations

import secrets

from django.db import models


class BackupMarker(models.Model):
    """Sentinel rows proving backup/restore round-trips on the live DB.

    The checkframework2 gate writes a marker, takes a backup, writes a
    second marker (the live DB now diverges from the backup), restores
    the backup ONTO the live server, and reads the latest marker back.
    """

    value = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        get_latest_by = ("created_at", "pk")
        ordering = ("-created_at", "-pk")

    @classmethod
    def set_next(cls) -> str:
        """Insert a fresh marker and return its value."""
        return cls.objects.create(value=secrets.token_urlsafe(24)).value

    @classmethod
    def latest_value(cls) -> str:
        """Return the newest marker's value."""
        return cls.objects.latest().value
