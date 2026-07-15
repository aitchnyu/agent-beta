# ruff: noqa: INP001, ARG001 # fixture app loaded by file path, not a package; Any dynamic model; required request_context signature
"""Example app: a table spanning every column class, served as one typed row.

Exercises all ``Column`` classes end-to-end through the app framework:
``@setup`` builds a table with one of each type and a seed row;
``@get_endpoint row`` returns that row's typed values;
``@backend_test`` checks each column type round-trips.
"""

from __future__ import annotations

from decimal import Decimal

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    BooleanColumn,
    CharColumn,
    DateTimeColumn,
    DecimalColumn,
    ForeignKeyColumn,
    IntegerColumn,
    RequestContext,
    TextColumn,
    UserColumn,
    backend_test,
    dynamic_models,
    fake_context,
    get_endpoint,
    setup,
)

COLLECTION = "Tests"
APP = "AllTypes"
TABLE = "row"
CATEGORY = "category"


class RowOut(BaseModel):
    """One row's typed values, JSON-safe via the view's model_dump(mode='json')."""

    code: str
    note: str
    qty: int
    active: bool
    price: str
    due: str | None
    category: str | None


@setup
def setup_app() -> None:
    """Create the Schema/AllTypes app + one-each-type table + a seed row."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={
            CATEGORY: [CharColumn("code", max_length=10)],
            TABLE: [
                CharColumn("code", max_length=10),
                TextColumn("note"),
                IntegerColumn("qty", default=0),
                BooleanColumn("active", default=False),
                DecimalColumn("price", max_digits=8, decimal_places=2),
                DateTimeColumn("due", nullable=True),
                UserColumn("owner", nullable=True),
                ForeignKeyColumn("category", target=(COLLECTION, APP, CATEGORY), nullable=True),
            ],
        },
    )
    category_model = Application.get_by_names(COLLECTION, APP).table_as_model(CATEGORY)
    cat = category_model.objects.create(code="C1")
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    model.objects.create(
        code="A1",
        note="hi",
        qty=7,
        active=True,
        price=Decimal("9.99"),
        due=None,
        owner=None,
        category=cat,
    )


@get_endpoint
def row(request_context: RequestContext) -> RowOut:
    """Return the single seed row's typed values."""
    model = Application.get_by_names(COLLECTION, APP).table_as_model(TABLE)
    instance = model.objects.first()
    assert instance is not None
    return RowOut(
        code=instance.code,
        note=instance.note,
        qty=instance.qty,
        active=instance.active,
        price=str(instance.price),
        due=str(instance.due) if instance.due else None,
        category=instance.category.code if instance.category else None,
    )


@backend_test
def test_row_round_trips_every_type() -> None:
    """The endpoint returns the seed row with each type intact."""
    out = row(fake_context())
    assert out.code == "A1"
    assert out.note == "hi"
    assert out.qty == 7
    assert out.active is True
    assert out.price == "9.99"
    assert out.due is None
    assert out.category == "C1"
