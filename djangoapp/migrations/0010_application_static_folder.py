# Generated for the required Application.static_folder field.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0009_application_script"),
    ]

    operations = [
        # One-time default ("") for any pre-existing application rows; the model
        # field carries no default, so new rows must supply static_folder
        # (create_application derives it when not given).
        migrations.AddField(
            model_name="application",
            name="static_folder",
            field=models.CharField(default="", max_length=400),
            preserve_default=False,
        ),
    ]
