# Adds ApplicationTableColumn.fk_target_table (nullable RESTRICT FK to
# ApplicationTable) — the metadata relation for foreign_key columns — and the
# new 'foreign_key' choice on the `type` field (derived from ColumnType).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0013_remove_application_script"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationtablecolumn",
            name="fk_target_table",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.RESTRICT,
                related_name="referencing_columns",
                to="djangoapp.applicationtable",
            ),
        ),
        migrations.AlterField(
            model_name="applicationtablecolumn",
            name="type",
            field=models.CharField(
                choices=[
                    ("char", "char"),
                    ("text", "text"),
                    ("integer", "integer"),
                    ("boolean", "boolean"),
                    ("decimal", "decimal"),
                    ("datetime", "datetime"),
                    ("user", "user"),
                    ("foreign_key", "foreign_key"),
                ],
                max_length=20,
            ),
        ),
    ]
