from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from djangoapp.models.base import FileMarkedForDeletion


class Command(BaseCommand):
    help = "Remove files and models marked for deletion, etc"

    def handle(self, *args: list[str], **options: dict[str, Any]) -> None:  # noqa: ARG002
        for marked_file in FileMarkedForDeletion.objects.all():
            file_path = marked_file.file.path
            if Path(file_path).exists():
                Path(file_path).unlink()
                self.stdout.write(f"Successfully deleted file: {file_path}")
            else:
                self.stdout.write(f"Warning: File not found: {file_path}")
            marked_file.delete()
