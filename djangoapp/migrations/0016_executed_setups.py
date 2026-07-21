"""Add Application.executed_setups (resumable multi-step install phase).

``executed_setups`` is a JSON list of the ``__name__``s of the app's
``@setup`` functions that have already completed, in completion order. The
``buildbackend`` runner resumes from it: it runs only the setups the loaded
module adds beyond this recorded prefix (forward-only, like DB migrations).

The column defaults to an empty list — correct for a freshly-created row
(``Application`` rows are created inside step 1 of an install, and the runner
appends each completed setup's name as it goes; a committed row is never
empty). Pre-existing rows, however, have all run their one ``@setup`` already,
and every app in the repo names that single setup ``setup_app``, so the data
step below truthfully marks each legacy row as ``["setup_app"]``. Without it,
a legacy row would carry ``[]`` and its next ``buildbackend`` would re-run
``setup_app`` → ``IntegrityError`` (``Application.name`` is unique).
"""

from typing import Any

from django.db import migrations, models


def mark_legacy_rows_fully_setup(apps: Any, schema_editor: Any) -> None:
    """Set every pre-existing row's executed_setups to ``["setup_app"]``.

    Every app in the repo (fixtures + TriviaFacts) names its single setup
    ``setup_app``, so this is honest: their one setup has run. New rows keep
    the column default (``[]``) and are populated by the runner as setups run.
    """
    Application = apps.get_model("djangoapp", "Application")
    Application.objects.update(executed_setups=["setup_app"])


class Migration(migrations.Migration):

    dependencies = [
        ("djangoapp", "0015_remove_collections"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="executed_setups",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            mark_legacy_rows_fully_setup,
            migrations.RunPython.noop,
        ),
    ]
