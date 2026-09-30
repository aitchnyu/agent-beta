from __future__ import annotations

from django.core.management.base import BaseCommand

from djangoapp.models import BackupMarker


class Command(BaseCommand):
    """Set or read the backup-marker sentinel, printing exactly one value.

    The checkframework2 gate drives the backup round-trip through this
    command (``set`` before a backup, ``set`` again to diverge,
    ``latest`` after a restore onto the live server): stdout is exactly
    the marker value, one line, nothing else — the gate string-compares
    it. Human-readable motivation on the model: ``BackupMarker``.
    """

    help = "Set a fresh backup marker (prints it) or print the latest one."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(  # type: ignore[attr-defined]
            "action", choices=["set", "latest"]
        )

    def handle(self, *args: object, **options: object) -> None:  # noqa: ARG002 # Django's handle signature
        action = options["action"]
        assert isinstance(action, str)
        if action == "set":
            self.stdout.write(BackupMarker.set_next())
        else:
            self.stdout.write(BackupMarker.latest_value())
