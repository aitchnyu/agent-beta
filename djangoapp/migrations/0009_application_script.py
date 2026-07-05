# Generated for the required Application.script field.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0008_alter_applicationtablecolumn_type"),
    ]

    operations = [
        # One-time default ("") for any pre-existing application rows; the
        # model field itself carries no default, so new rows must supply
        # script (it is required).
        migrations.AddField(
            model_name="application",
            name="script",
            field=models.CharField(default="", max_length=300),
            preserve_default=False,
        ),
    ]
