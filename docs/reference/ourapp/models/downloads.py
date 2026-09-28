"""Downloads feature models — a time-limited shared ``Download``.

The illustration of the media primitives: a ``FileField`` stored in this
feature's own folder under ``MEDIA_ROOT`` (``downloads/``) with Django's
storage choosing the filename (collisions get a random suffix — two rows
may share an original name), file cleanup riding the tracked pair
(``save_plus`` deletes a replaced file's bytes after commit;
``delete_plus`` removes the row with its file — see views/downloads.py),
and serving via ``djangoapp.media.serve_file`` behind an expiry gate.

Lifecycle: a row is created at upload (``expires_at`` defaults to one week
out), serves anonymously until ``expires_at`` passes, then the daily sweep
(``tasks/downloads.py`` → :meth:`Download.delete_expired`) removes row + bytes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import ClassVar

from django.db import models
from django.utils import timezone

from djangoapp.logging import get_logger
from djangoapp.models import BaseModel

logger = get_logger(__name__)

#: How long a fresh download stays live when the admin doesn't pick a date.
DEFAULT_DOWNLOAD_WINDOW = timedelta(days=7)


def default_expiry() -> datetime:
    """Field default: one week from creation (a named callable, migration-serialisable)."""
    return timezone.now() + DEFAULT_DOWNLOAD_WINDOW


class Download(BaseModel):
    """A file shared for anonymous download until ``expires_at``."""

    # One fixed folder for the feature; Django's storage chooses the
    # filename (the original name, deconflicted with a random suffix on
    # collision) — same-name uploads coexist, and over-long names are
    # truncated to max_length (with a suffix) instead of hitting the OS
    # limit. The original name needs no column: it is recovered as the
    # storage name's basename.
    file = models.FileField(upload_to="downloads", max_length=255)
    expires_at = models.DateTimeField(default=default_expiry)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """Return the file's basename (what the uploader called it)."""
        return self.basename

    @property
    def basename(self) -> str:
        """The original name, recovered from the field (no column needed)."""
        return self.file.name.rsplit("/", 1)[-1] if self.file.name else ""

    @property
    def is_expired(self) -> bool:
        """Whether the download window has passed (serve → 404 when True)."""
        return timezone.now() >= self.expires_at

    @classmethod
    def delete_expired(cls) -> int:
        """Sweep every expired row: row + audit log + bytes, post-commit.

        The daily task's whole body (fat model, thin wrapper): per expired
        row, ``delete_plus`` — so a swept delete removes the row, its log
        entry, and its file together or not at all. Returns the count swept.
        """
        swept = 0
        for download in cls.objects.filter(expires_at__lte=timezone.now()):
            download.delete_plus(actor=None)
            swept += 1
        if swept:
            logger.info("expired downloads swept", count=swept)
        return swept
