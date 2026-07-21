# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""Multi-step setup fixture, step1: a single ``@setup``.

Feeds ``BuildBackendResumeTests``: install step1 (``executed_setups`` becomes
``["setup1"]``), then swap ``_APPS_ROOT`` to ``multistep_step2`` (which adds a
second ``@setup``) and verify only ``setup2`` runs. ``setup1`` creates the app
+ an ``alpha`` table; its ``__name__`` is what the runner stores in
``Application.executed_setups``.
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import (
    Application,
    CharColumn,
    dynamic_models,
    setup,
)

APP = "MultiStepApp"
TABLE = "alpha"
SEED = "a1"


@setup
def setup1() -> None:
    """Create the MultiStepApp app + an alpha table seeded with one row."""
    dynamic_models.create_application(
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    Application.objects.get(name=APP).table_as_model(TABLE).objects.create(code=SEED)
