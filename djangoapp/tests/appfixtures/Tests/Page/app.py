# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""Install/seed fixture: the happy-path install + a backend-test rollback proof.

Feeds ``test_buildbackend.py``: ``@setup`` seeds an ``items`` table, and a
``@backend_test`` writes a row during install — proving the install savepoint
rolls it back (the row count is unchanged after install). No endpoints or
inertia here; endpoint serving lives in ``Tests/Endpoints``.
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import (
    Application,
    CharColumn,
    backend_test,
    dynamic_models,
    setup,
)

COLLECTION = "Tests"
APP = "Page"
TABLE = "items"
# Seeded codes; the install tests assert this count.
ITEMS = ["A1", "A2", "A3"]


@setup
def setup_app() -> None:
    """Create the Tests/Page app + an items table seeded with several rows."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    model.objects.bulk_create([model(code=code) for code in ITEMS])


@backend_test
def test_backend_test_writes_roll_back() -> None:
    """A backend_test's writes must not persist past setup (savepoint isolation)."""
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    before = model.objects.count()
    model.objects.create(code="Tmp")
    assert model.objects.count() == before + 1
