"""File-cleanup test-support model — ``FileCleanupDoc``.

Exists for ``djangoapp/tests/models/test_basemodel_file_cleanup_project.py``:
a row carrying two independent FileFields, so the tests can pin that
``save_plus`` deletes a replaced/cleared file's bytes after commit,
``delete_plus`` takes every file of the row with it, and bare/bulk paths
leave the bytes on disk.
"""

from django.db import models

from djangoapp.models import BaseModel


class FileCleanupDoc(BaseModel):
    """A row with two independent stored files (document + thumbnail)."""

    document = models.FileField(upload_to="attachments", max_length=255)
    thumbnail = models.FileField(upload_to="attachments", max_length=255)

    def __str__(self) -> str:
        """Return the document's storage basename."""
        return self.document.name.rsplit("/", 1)[-1] if self.document.name else ""
