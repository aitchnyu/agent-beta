from typing import Any

from django.core.management.base import BaseCommand

from djangoapp.models.base import RowUpdateUserNotification


class Command(BaseCommand):
    help = "Delete all RowUpdateUserNotification objects"

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN401, ARG002 # Django fixes *args/**options; values are Any
        count, _ = RowUpdateUserNotification.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} notifications"),
        )
