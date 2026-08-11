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
            name="Topic",
            options={"ordering": ["name"]},
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
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=100, unique=True)),
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
        ),
        migrations.CreateModel(
            name="Fact",
            options={"ordering": ["-created_at"]},
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
                ("text", models.TextField()),
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
                (
                    "topic",
                    models.ForeignKey(
                        on_delete=models.deletion.RESTRICT,
                        related_name="facts",
                        to="ourapp.topic",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FactOfTheDay",
            options={
                "ordering": ["-last_updated_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["singleton"],
                        name="factoftheday_singleton_row",
                    ),
                ],
            },
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
                ("singleton", models.SmallIntegerField(default=1, editable=False)),
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
                (
                    "fact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="daily_picks",
                        to="ourapp.fact",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Todo",
            options={"ordering": ["-created_at"]},
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
                ("text", models.CharField(max_length=500)),
                ("completed", models.BooleanField(default=False)),
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
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=models.deletion.RESTRICT,
                        related_name="todos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
