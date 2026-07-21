"""Remove ApplicationCollection; apps live in one flat namespace.

Drops the application_collection FK on Application, deletes the
ApplicationCollection model + its table, removes the now-impossible
collection-scoped uniqueness constraint, and makes Application.name globally
unique (max_length=10, 2–10-char validator).

DB is disposable: existing rows are not preserved (physical app tables
``zz_<physical_name>`` never carried the collection, so they survive a
re-install unchanged).
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0014_applicationtablecolumn_fk_target"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="application",
            name="application_collection_name_unique",
        ),
        migrations.RemoveField(
            model_name="application",
            name="application_collection",
        ),
        migrations.DeleteModel(
            name="ApplicationCollection",
        ),
        migrations.AlterField(
            model_name="application",
            name="name",
            field=models.CharField(
                max_length=100,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[A-Za-z][A-Za-z0-9]{9,}$",
                        "App names must be at least 10 chars, start with a "
                        "letter, and contain only letters and digits.",
                    )
                ],
            ),
        ),
    ]
