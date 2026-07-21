# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""Negative example: setup itself raises, so the install must roll back.

``@setup`` calls ``create_application`` with a bad column (``CharColumn`` with
``max_length=0``), which raises during validation. The setup runner rolls back
the whole script and exits non-zero. Used by
``BuildBackendTests.test_fails_setup_rolls_back``.
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import CharColumn, dynamic_models, setup

APP = "FailsSetup"
TABLE = "things"


@setup
def setup_app() -> None:
    # The failure is the bad column (max_length=0), exercising setup-time
    # validation rollback.
    dynamic_models.create_application(
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=0)]},
    )
