from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ourapp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="row_version",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="book",
            name="row_version",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
    ]
