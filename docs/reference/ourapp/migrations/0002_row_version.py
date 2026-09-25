from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ourapp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fact",
            name="row_version",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="factoftheday",
            name="row_version",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="todo",
            name="row_version",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="topic",
            name="row_version",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
    ]
