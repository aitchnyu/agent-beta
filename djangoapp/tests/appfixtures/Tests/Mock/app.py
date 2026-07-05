# ruff: noqa: INP001, ARG001 # fixture app loaded by file path, not a package; Any dynamic model; required request_context signature
"""Example app: an endpoint that calls an external HTTP API, mocked in its test.

Demonstrates mocking the HTTP helper inside a ``@backend_test``. ``setup_app``
creates a small table with a fallback fact; ``random_fact`` fetches a fact from
a URL via ``_fetch_json`` (the real HTTP call) and falls back to a stored row.
The backend test patches ``_fetch_json`` to a canned response so no real network
call runs.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any, cast
from unittest.mock import patch

from djangoapp.apps.shortcuts import (
    Application,
    BaseModel,
    RequestContext,
    TextColumn,
    backend_test,
    dynamic_models,
    fake_context,
    get_endpoint,
    setup,
)

COLLECTION = "Tests"
APP = "Mock"
TABLE = "facts"
FACT_URL = "https://example.com/facts/random"


class FactOut(BaseModel):
    fact: str


def _fetch_json(url: str) -> dict[str, Any]:
    """GET ``url`` and return its JSON body (the real HTTP call)."""
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 # fixture example; url is a module constant
        return cast("dict[str, Any]", json.loads(resp.read().decode("utf-8")))


@setup
def setup_app() -> None:
    """Create the Http/Mock app + a facts table seeded with a fallback row."""
    dynamic_models.create_application_collection(COLLECTION)
    dynamic_models.create_application(
        collection=COLLECTION,
        name=APP,
        tables={TABLE: [TextColumn("content")]},
    )
    model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
    model.objects.create(content="local fallback fact")


@get_endpoint
def random_fact(request_context: RequestContext) -> FactOut:
    """Return the external API's fact, falling back to a stored row on error."""
    try:
        data = _fetch_json(FACT_URL)
        return FactOut(fact=str(data["fact"]))
    except OSError, KeyError, ValueError:
        model = Application.get_by_names(COLLECTION, APP).get_table(TABLE)
        row = model.objects.order_by("?").first()
        return FactOut(fact=row.content if row else "")


@backend_test
def test_random_fact_uses_mocked_http() -> None:
    """random_fact returns the patched response; no real network call is made."""
    module = sys.modules[__name__]
    with patch.object(module, "_fetch_json", return_value={"fact": "mocked fact"}) as mock_fetch:
        out = random_fact(fake_context())
    mock_fetch.assert_called_once_with(FACT_URL)
    assert out.fact == "mocked fact"
