from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, ClassVar

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import override_settings

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase
from djangoapp.tests.views import skip_unless_env


@skip_unless_env("RUN_PROJECT_TESTS")
class BaseModelFileCleanupTests(BaseTestCase):
    """FileField cleanup riding ``BaseModel.save_plus``/``delete_plus``.

    Runs only under ``checkproject`` (sets ``RUN_PROJECT_TESTS`` and overlays the
    test app onto ``ourapp/``); self-skips in ``checkframework1``. The test
    app's ``FileCleanupDoc`` carries two FileFields, so these tests pin the cleanup
    contract at the framework level, independent of any feature app:

    - test_replace_deletes_old_file_after_commit, a replaced field's old bytes
      go after commit; the untouched field's bytes stay
    - test_clear_deletes_old_file_after_commit, clearing a field deletes its
      bytes too (not just replacements)
    - test_unchanged_file_survives_save, a save that keeps the name keeps the
      bytes (only a CHANGED name queues a deletion)
    - test_stale_version_rollback_keeps_file, a failed save (stale
      expected_row_version) never deletes — rollback keeps the old bytes
    - test_delete_plus_removes_every_file, deleting a row takes every file of
      the row with it (both fields)
    - test_bulk_delete_leaves_files, a queryset ``.delete()`` bypasses
      ``delete_plus``: rows go, bytes stay — the documented boundary
    """

    FileCleanupDoc: ClassVar[type[Any]]
    actor: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        ourapp = apps.get_app_config("ourapp")
        cls.FileCleanupDoc = ourapp.get_model("FileCleanupDoc")
        cls.actor = User.objects.create_user(username="actor", is_superuser=True, is_staff=True)

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()  # test-scoped, cleaned up below
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(MEDIA_ROOT=Path(self._tmp.name))
        override.enable()
        self.addCleanup(override.disable)

        # A fresh attachment per test, built via save_plus on create (create
        # cleans nothing — there is nothing to replace).
        self.row = self.FileCleanupDoc(
            document=SimpleUploadedFile("doc.txt", b"doc-bytes"),
            thumbnail=SimpleUploadedFile("thumb.txt", b"thumb-bytes"),
        )
        self.row.save_plus(actor=self.actor, expected_row_version=0)

    def test_replace_deletes_old_file_after_commit(self) -> None:
        """A replaced field's old bytes go after commit.

        The untouched field's bytes stay.
        """
        row = self.row
        old_name = row.document.name
        row.document = SimpleUploadedFile("v2.txt", b"v2-bytes")
        with self.captureOnCommitCallbacks(execute=True):
            row.save_plus(actor=self.actor, expected_row_version=row.row_version)
        self.assertNotEqual(row.document.name, old_name)
        self.assertFalse(default_storage.exists(old_name))
        self.assertTrue(default_storage.exists(row.document.name))
        self.assertTrue(default_storage.exists(row.thumbnail.name))

    def test_clear_deletes_old_file_after_commit(self) -> None:
        """Clearing a field deletes its bytes too (not just replacements)."""
        row = self.row
        old_name = row.document.name
        row.document = None
        with self.captureOnCommitCallbacks(execute=True):
            row.save_plus(actor=self.actor, expected_row_version=row.row_version)
        self.assertFalse(default_storage.exists(old_name))
        self.assertFalse(self.FileCleanupDoc.objects.get(pk=row.pk).document)
        self.assertTrue(default_storage.exists(row.thumbnail.name))

    def test_unchanged_file_survives_save(self) -> None:
        """A save that keeps the name keeps the bytes.

        Only a CHANGED name queues a deletion.
        """
        row = self.row
        with self.captureOnCommitCallbacks(execute=True):
            row.save_plus(actor=self.actor, expected_row_version=row.row_version)
        self.assertTrue(default_storage.exists(row.document.name))
        self.assertTrue(default_storage.exists(row.thumbnail.name))

    def test_stale_version_rollback_keeps_file(self) -> None:
        """A failed save (stale expected_row_version) never deletes.

        The rollback keeps the row and the old bytes together.
        """
        row = self.row
        old_name = row.document.name
        row.document = SimpleUploadedFile("v2.txt", b"v2-bytes")
        with self.assertRaises(Http404), self.captureOnCommitCallbacks(execute=True):
            row.save_plus(actor=self.actor, expected_row_version=row.row_version + 5)
        self.assertTrue(default_storage.exists(old_name))
        self.assertEqual(self.FileCleanupDoc.objects.get(pk=row.pk).document.name, old_name)
        self.assertFalse(default_storage.exists("attachments/v2.txt"))

    def test_delete_plus_removes_every_file(self) -> None:
        """Deleting a row takes every file of the row with it (both fields)."""
        row = self.row
        doc_name, thumb_name = row.document.name, row.thumbnail.name
        with self.captureOnCommitCallbacks(execute=True):
            row.delete_plus(actor=self.actor)
        self.assertFalse(self.FileCleanupDoc.objects.filter(pk=row.pk).exists())
        self.assertFalse(default_storage.exists(doc_name))
        self.assertFalse(default_storage.exists(thumb_name))

    def test_bulk_delete_leaves_files(self) -> None:
        """A queryset ``.delete()`` bypasses ``delete_plus``: rows go, bytes stay.

        This pins the documented boundary — cleanup rides the tracked pair
        only; bulk deletes, like bare ones, orphan files by design.
        """
        row = self.row
        doc_name, thumb_name = row.document.name, row.thumbnail.name
        with self.captureOnCommitCallbacks(execute=True):
            self.FileCleanupDoc.objects.filter(pk=row.pk).delete()
        self.assertFalse(self.FileCleanupDoc.objects.filter(pk=row.pk).exists())
        self.assertTrue(default_storage.exists(doc_name))
        self.assertTrue(default_storage.exists(thumb_name))
