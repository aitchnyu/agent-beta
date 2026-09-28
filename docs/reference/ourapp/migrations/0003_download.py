import djangoapp.models.base
from django.conf import settings
from django.db import migrations, models

import ourapp.models.downloads


class Migration(migrations.Migration):
    dependencies = [
        ("ourapp", "0002_row_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="Download",
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
                    "public_id",
                    models.CharField(
                        db_index=True,
                        default=djangoapp.models.base.generate_uuid7_id,
                        editable=False,
                        max_length=100,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_updated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "file",
                    models.FileField(max_length=255, upload_to="downloads"),
                ),
                (
                    "expires_at",
                    models.DateTimeField(default=ourapp.models.downloads.default_expiry),
                ),
                (
                    "row_version",
                    models.PositiveBigIntegerField(default=0, editable=False),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.RESTRICT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "last_updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.RESTRICT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
