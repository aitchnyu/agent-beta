import time
from typing import Any

from django.db import migrations, models


def backfill_physical_name(apps: Any, schema_editor: Any) -> None:
    """Set physical_name for any pre-existing rows (pre-prod: usually none).

    Uses name + timestamp + pk to guarantee global uniqueness regardless of
    how many rows share a display name across collections.
    """
    ApplicationTable = apps.get_model("djangoapp", "ApplicationTable")
    stamp = int(time.time())
    for table in ApplicationTable.objects.all():
        table.physical_name = f"{table.name}{stamp}{table.pk}"
        table.save(update_fields=["physical_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0006_drop_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationtable",
            name="physical_name",
            field=models.CharField(editable=False, max_length=200, null=True),
        ),
        migrations.RunPython(backfill_physical_name, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="applicationtable",
            name="physical_name",
            field=models.CharField(editable=False, max_length=200, unique=True),
        ),
    ]
