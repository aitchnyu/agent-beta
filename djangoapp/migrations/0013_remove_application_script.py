# Removes Application.script — the app.py path is now derived from the apps
# root + collection/app names, not stored.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0012_remove_application_static_folder"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="application",
            name="script",
        ),
    ]
