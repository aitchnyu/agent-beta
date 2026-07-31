import djangoapp.models.base
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Author",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "_public_id",
                    models.CharField(
                        db_index=True,
                        default=djangoapp.models.base.generate_uuid7_id,
                        editable=False,
                        max_length=100,
                    ),
                ),
                ("_created_at", models.DateTimeField(auto_now_add=True)),
                ("_edited_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("bio", models.TextField(blank=True, default="")),
                (
                    "rating",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=3, null=True
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "_created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.RESTRICT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Book",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "_public_id",
                    models.CharField(
                        db_index=True,
                        default=djangoapp.models.base.generate_uuid7_id,
                        editable=False,
                        max_length=100,
                    ),
                ),
                ("_created_at", models.DateTimeField(auto_now_add=True)),
                ("_edited_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("pages", models.IntegerField(blank=True, null=True)),
                ("published", models.DateTimeField(blank=True, null=True)),
                (
                    "_created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.RESTRICT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=models.deletion.RESTRICT,
                        related_name="books",
                        to="ourapp.author",
                    ),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.RESTRICT,
                        related_name="reviewed_books",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
