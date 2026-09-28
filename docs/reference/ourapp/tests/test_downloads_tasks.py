"""Tests for the Huey task (``ourapp.tasks.delete_expired_downloads``).

The task body is a one-line wrapper over ``Download.delete_expired()``, so
these tests call the task via huey's ``call_local()`` (runs the wrapped
function immediately, bypassing the queue) — no consumer process is needed.
"""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase

from ourapp.models import Download
from ourapp.tasks import delete_expired_downloads


class DeleteExpiredDownloadsTaskTests(BaseTestCase):
    """The daily cron task sweeps expired downloads via the model classmethod.

    - test_task_sweeps_expired_keeps_live, call_local() removes the expired
      row + bytes, keeps the live one
    - test_task_no_op_when_nothing_expired, nothing expired → no error, no change
    """

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()  # noqa: SIM115 # test-scoped, cleaned up below
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(MEDIA_ROOT=Path(self._tmp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.admin = User.objects.create_user(username="admin")

    def _download(self, expires_at) -> Download:
        download = Download(
            file=SimpleUploadedFile("a.txt", b"task-bytes"),
            expires_at=expires_at,
        )
        download.save_plus(actor=self.admin, expected_row_version=0)
        return download

    def test_task_sweeps_expired_keeps_live(self) -> None:
        """call_local() removes the expired row + bytes, keeps the live one."""
        expired = self._download(timezone.now() - timedelta(hours=1))
        live = self._download(timezone.now() + timedelta(days=1))
        with self.captureOnCommitCallbacks(execute=True):
            delete_expired_downloads.call_local()
        self.assertFalse(Download.objects.filter(pk=expired.pk).exists())
        self.assertFalse(default_storage.exists(expired.file.name))
        self.assertTrue(Download.objects.filter(pk=live.pk).exists())

    def test_task_no_op_when_nothing_expired(self) -> None:
        """Nothing expired → the task is a clean no-op."""
        live = self._download(timezone.now() + timedelta(days=1))
        with self.captureOnCommitCallbacks(execute=True):
            delete_expired_downloads.call_local()
        self.assertEqual(Download.objects.count(), 1)
        self.assertTrue(default_storage.exists(live.file.name))
