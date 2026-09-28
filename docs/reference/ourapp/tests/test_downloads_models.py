"""Tests for the downloads models (``Download`` lifecycle + sweep)."""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from djangoapp.models import SKIP_ROW_VERSION_CHECK, User
from djangoapp.tests._base import BaseTestCase

from ourapp.models import DEFAULT_DOWNLOAD_WINDOW, Download


class DownloadModelTests(BaseTestCase):
    """``Download``: default expiry, storage naming, ``delete_expired`` sweep.

    - test_default_expiry_one_week, a fresh row expires exactly the window out
    - test_storage_names_in_downloads_folder, Django's storage names files in
      the feature's downloads/ folder; same-name uploads coexist via random
      collision suffixes
    - test_is_expired_boundary, is_expired flips at expires_at
    - test_delete_expired_sweeps_rows_and_bytes, expired rows + files go,
      live ones stay (bytes via on_commit)
    - test_delete_expired_returns_count, the sweep returns the number swept
    """

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()  # noqa: SIM115 # test-scoped, cleaned up below
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(MEDIA_ROOT=Path(self._tmp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.admin = User.objects.create_user(username="admin")

    def _download(self, **kwargs) -> Download:
        """Build one download the way the app does: the uploaded file's own
        name is the original name; the storage name is Django's choice."""
        upload = SimpleUploadedFile("notes.txt", b"dl-bytes")
        download = Download(file=upload, **kwargs)
        download.save_plus(actor=self.admin, expected_row_version=SKIP_ROW_VERSION_CHECK)
        return download

    def test_default_expiry_one_week(self) -> None:
        """A fresh row expires exactly the default window from now."""
        before = timezone.now()
        download = self._download()
        after = timezone.now()
        self.assertGreaterEqual(download.expires_at, before + DEFAULT_DOWNLOAD_WINDOW)
        self.assertLessEqual(download.expires_at, after + DEFAULT_DOWNLOAD_WINDOW)

    def test_storage_names_in_downloads_folder(self) -> None:
        """Files land in downloads/ under their own name; same-name uploads
        coexist (Django's random collision suffix — no overwrites)."""
        one = self._download()
        two = self._download()
        self.assertEqual(one.file.name, "downloads/notes.txt")
        self.assertTrue(two.file.name.startswith("downloads/notes"))
        self.assertNotEqual(one.file.name, two.file.name)
        # Both rows' bytes survive — the collision suffix kept both files.
        self.assertTrue(default_storage.exists(one.file.name))
        self.assertTrue(default_storage.exists(two.file.name))

    def test_is_expired_boundary(self) -> None:
        """is_expired is False before expires_at, True at/after it."""
        download = self._download(expires_at=timezone.now() + timedelta(hours=1))
        self.assertFalse(download.is_expired)
        download.expires_at = timezone.now() - timedelta(seconds=1)
        self.assertTrue(download.is_expired)

    def test_delete_expired_sweeps_rows_and_bytes(self) -> None:
        """Expired rows + files go; live ones stay (bytes via on_commit)."""
        expired = self._download(expires_at=timezone.now() - timedelta(minutes=1))
        live = self._download()
        expired_name, live_name = expired.file.name, live.file.name
        with self.captureOnCommitCallbacks(execute=True):
            swept = Download.delete_expired()
        self.assertEqual(swept, 1)
        self.assertFalse(Download.objects.filter(pk=expired.pk).exists())
        self.assertFalse(default_storage.exists(expired_name))
        self.assertTrue(Download.objects.filter(pk=live.pk).exists())
        self.assertTrue(default_storage.exists(live_name))

    def test_delete_expired_returns_count(self) -> None:
        """The sweep returns the number of rows it removed."""
        self._download(expires_at=timezone.now() - timedelta(hours=2))
        self._download(expires_at=timezone.now() - timedelta(hours=1))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(Download.delete_expired(), 2)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(Download.delete_expired(), 0)  # nothing left
