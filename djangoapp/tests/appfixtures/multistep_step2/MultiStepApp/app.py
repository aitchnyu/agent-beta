# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""Multi-step setup fixture, step2: ``setup1`` (identical to step1) + ``setup2``.

The resume test installs step1 (``executed_setups=["setup1"]``), swaps
``_APPS_ROOT`` here, and verifies only ``setup2`` runs. ``setup1`` MUST be
compatible with step1's (the append-only contract): it is skipped on resume
because ``"setup1"`` is already in ``executed_setups`` — and since ``setup1``
does non-idempotent ``create_application`` work, the step2 install's success is
itself proof the skip happened. ``setup2`` adds a ``beta`` table.
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import (
    Application,
    CharColumn,
    dynamic_models,
    setup,
)

APP = "MultiStepApp"
ALPHA = "alpha"
BETA = "beta"
SEED = "a1"


@setup
def setup1() -> None:
    """Create the MultiStepApp app + alpha table (identical to step1's setup1)."""
    dynamic_models.create_application(
        name=APP,
        tables={ALPHA: [CharColumn("code", max_length=10)]},
    )
    Application.objects.get(name=APP).table_as_model(ALPHA).objects.create(code=SEED)


@setup
def setup2() -> None:
    """Add a beta table (runs only on resume from v1's executed_setups)."""
    dynamic_models.create_application_table(
        application=APP,
        table=BETA,
        columns=[CharColumn("code", max_length=10)],
    )
