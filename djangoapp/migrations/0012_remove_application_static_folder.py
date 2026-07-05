# Removes the redundant Application.static_folder field — the folder is derived
# from the collection/app names (default_static_folder), not stored.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0011_apps_generation"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="application",
            name="static_folder",
        ),
    ]
