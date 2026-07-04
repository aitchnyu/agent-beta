"""Seed a "Facts" collection with an "animals" table and 10 animal facts.

Usage: ./run python scripts/20260630_seed-facts.py

Creates the collection/app/table (if absent) via the applications command's
schema layer, then inserts 10 rows into the dynamic "animals" model directly
through the ORM. Idempotent at the collection/app/table level; re-running
without --reset will simply append another 10 rows.
"""

from __future__ import annotations

import os
import sys
from typing import Any, cast

import django

# scripts/ is sys.path[0]; add the project root so djangoproject is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
django.setup()

from django.db import transaction  # noqa: E402 # setup() must run first

from djangoapp.models import ApplicationCollection, ApplicationTable  # noqa: E402
from djangoapp.models.dynamic import dynamic_models  # noqa: E402

COLLECTION_NAME = "Facts"
APP_NAME = "Animals"
TABLE_NAME = "animals"

COLUMNS: list[dict[str, object]] = [
    {"name": "name", "type": "text"},
    {"name": "content", "type": "text"},
]

FACTS: list[tuple[str, str]] = [
    ("Octopus", "An octopus has three hearts and blue blood."),
    ("Honeybee", "A honeybee can fly at about 15 miles per hour."),
    ("Cheetah", "Cheetahs can accelerate from 0 to 60 mph in under three seconds."),
    ("Snail", "A snail can sleep for up to three years."),
    ("Bat", "Bats are the only mammals capable of sustained flight."),
    ("Elephant", "An elephant can smell water from several miles away."),
    ("Polar bear", "Polar bears have black skin under their white fur."),
    ("Dolphin", "Dolphins give each other names and respond to their own."),
    ("Shark", "Sharks predate trees, having existed for over 400 million years."),
    ("Giraffe", "A giraffe's tongue is about 20 inches long and dark blue."),
]


def _ensure_table() -> ApplicationTable:
    """Return the animals table, creating the collection/app/table if missing."""
    try:
        collection = ApplicationCollection.objects.get(name=COLLECTION_NAME)
    except ApplicationCollection.DoesNotExist:
        collection = ApplicationCollection.objects.create(name=COLLECTION_NAME)

    app = collection.applications.filter(name=APP_NAME).first()
    if app is None:
        app = collection.applications.create(name=APP_NAME)

    table = app.tables.filter(name=TABLE_NAME).first()
    if table is not None:
        return table
    return dynamic_models.create_application_table(
        appcollection=COLLECTION_NAME,
        app=APP_NAME,
        name=TABLE_NAME,
        columns=COLUMNS,
    )


def main() -> int:
    with transaction.atomic():
        table = _ensure_table()
        model = cast("Any", dynamic_models.get_model(table.physical_name))
        created = model.objects.bulk_create(
            [model(name=name, content=content) for name, content in FACTS]
        )
    print(f"Inserted {len(created)} rows into {COLLECTION_NAME}.{APP_NAME}.{TABLE_NAME} (db_table zz_{table.physical_name}).")  # noqa: E501 let one-line summary stay long
    return 0


if __name__ == "__main__":
    sys.exit(main())
