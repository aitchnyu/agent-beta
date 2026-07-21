# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""Multi-step setup fixture, renamed: ``setup1`` + a renamed ``setup_two``.

Feeds ``BuildBackendResumeTests.test_prefix_mismatch_refuses_resume``: after
step2 has recorded ``executed_setups=["setup1", "setup2"]``, this file's
``["setup1", "setup_two"]`` is the same length but differs at position 1, so
the prefix check refuses to resume (rename detection). ``setup1`` is identical
to step1/step2's; ``setup_two`` is never reached in the test (the check fires
first).
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
    """Create the MultiStepApp app + alpha table (identical to step1/step2's setup1)."""
    dynamic_models.create_application(
        name=APP,
        tables={ALPHA: [CharColumn("code", max_length=10)]},
    )
    Application.objects.get(name=APP).table_as_model(ALPHA).objects.create(code=SEED)


@setup
def setup_two() -> None:
    """Stand in for v2's setup2 under a new name so the prefix check fails."""
    dynamic_models.create_application_table(
        application=APP,
        table=BETA,
        columns=[CharColumn("code", max_length=10)],
    )
