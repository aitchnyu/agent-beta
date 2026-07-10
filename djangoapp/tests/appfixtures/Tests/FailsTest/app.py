# ruff: noqa: INP001, ARG001, PT015 # fixture app loaded by file path; required request_context signature; intentional assert False
"""Negative example: a backend test that fails, so the install must roll back.

``@setup`` creates a valid app, but ``@backend_test`` raises. The setup runner
rolls back the whole script (the app, its table, the physical table, and the
registry cache), so after the failed run nothing remains. Used by
``InstallOrUpdateTests.test_fails_backend_test_rolls_back``.
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import (
    BaseModel,
    CharColumn,
    RequestContext,
    backend_test,
    dynamic_models,
    get_endpoint,
    setup,
)

COLLECTION = "Tests"
APP = "FailsTest"
TABLE = "things"


class ThingsOut(BaseModel):
    count: int


@setup
def setup_app() -> None:
    """Create a valid app (the failure is in the backend test, not here)."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [CharColumn("code", max_length=10)]},
    )


@get_endpoint
def things(request_context: RequestContext) -> ThingsOut:
    return ThingsOut(count=0)


@backend_test
def test_that_always_fails() -> None:
    assert False, "intentional backend-test failure"  # noqa: B011 # assert False is the point of this fixture
