import io
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from djangoapp.models.base import FileMarkedForDeletion


class MaintainCommandTest(TestCase):
    def test_delete_existing_file(self) -> None:
        """Test that an existing file is deleted and the record is removed."""
        # Create a FileMarkedForDeletion with a mock path
        marked_file = FileMarkedForDeletion.objects.create(file="test_file.txt")
        file_path = marked_file.file.path

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "unlink") as mock_unlink,
        ):
            stdout = io.StringIO()
            call_command("maintain", stdout=stdout)

            # Check that unlink was called
            mock_unlink.assert_called_once_with()
            # Check stdout messages
            output = stdout.getvalue()
            self.assertIn(f"Successfully deleted file: {file_path}", output)
            # Check that the record was deleted
            self.assertFalse(FileMarkedForDeletion.objects.filter(id=marked_file.pk).exists())

    def test_delete_nonexistent_file(self) -> None:
        """Test that a warning is issued for a nonexistent file and the record is removed."""
        marked_file = FileMarkedForDeletion.objects.create(file="nonexistent_file.txt")
        file_path = marked_file.file.path

        with patch.object(Path, "exists", return_value=False):
            stdout = io.StringIO()
            call_command("maintain", stdout=stdout)

            output = stdout.getvalue()
            self.assertIn(f"Warning: File not found: {file_path}", output)
            self.assertFalse(FileMarkedForDeletion.objects.filter(id=marked_file.pk).exists())
