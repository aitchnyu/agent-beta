from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ourapp", "0003_filecleanupdoc"),
    ]

    operations = [
        migrations.CreateModel(
            name="Shelf",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("code", models.CharField(max_length=20)),
            ],
        ),
        migrations.AddField(
            model_name="book",
            name="weight",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="book",
            name="released",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="book",
            name="shelf",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="books",
                to="ourapp.shelf",
            ),
        ),
    ]
