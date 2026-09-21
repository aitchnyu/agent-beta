"""Query-budget base classes that catch N+1 read regressions in view tests.

A test fails if it runs more SELECT queries than its budget. Only read queries
(`SELECT` / `WITH ... SELECT`) are counted, so fixture INSERTs and the
savepoint/transaction overhead that `django.test.TestCase` wraps each test in
do not inflate the count - the budget reflects the view's actual reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import TestCase

from django.db import connection
from django.test.utils import CaptureQueriesContext

from djangoapp.tests._base import BaseInertiaTestCase, BaseTestCase

if TYPE_CHECKING:
    from collections.abc import Callable

_READ_PREFIXES = ("select", "with")


def _is_read_query(sql: str) -> bool:
    lowered = sql.lstrip().lower()
    return lowered.startswith(_READ_PREFIXES)


class QueryBudgetMixin(TestCase):
    """Fails a test whose SELECT-query count exceeds `max_select_queries`.

    Plain-``unittest.TestCase`` cooperative mixin: mix FIRST (before the
    real test base) so ``super().setUp()`` chains down the MRO. The class
    attribute is the frozen baseline; ``allow_more_queries`` ADDS to it —
    per-test extras only, and framework shifts re-freeze one line.
    """

    max_select_queries: int = 8

    def setUp(self) -> None:
        super().setUp()
        self.max_select_queries = type(self).max_select_queries
        self._query_capture: CaptureQueriesContext = CaptureQueriesContext(connection)
        self._query_capture.__enter__()
        self.addCleanup(self._assert_select_budget)

    def allow_more_queries(self, count: int) -> None:
        """Raise this test's SELECT-query budget BY `count` (state why at the call site)."""
        self.max_select_queries += count

    def captured_select_queries(self) -> list[dict[str, str]]:
        return [q for q in self._query_capture.captured_queries if _is_read_query(q["sql"])]

    def select_count(self, request: Callable[[], object]) -> int:
        """Run `request` once and return how many SELECT/WITH queries it made."""
        with CaptureQueriesContext(connection) as ctx:
            request()
        return sum(1 for q in ctx.captured_queries if _is_read_query(q["sql"]))

    def _assert_select_budget(self) -> None:
        self._query_capture.__exit__(None, None, None)
        selects = self.captured_select_queries()
        count = len(selects)
        if count <= self.max_select_queries:
            return
        detail = "\n".join(f"  [{i + 1}] {q['sql'][:200]}" for i, q in enumerate(selects))
        self.fail(
            f"{count} SELECT queries exceed budget of {self.max_select_queries} "
            f"in {self.id()}.\nQueries:\n{detail}",
        )


class QueryBudgetTestCase(QueryBudgetMixin, BaseTestCase):
    """Query-budget base for view tests that don't need inertia assertions."""


class QueryBudgetInertiaTestCase(  # type: ignore[misc] # library-internal client clash; see _base.BaseInertiaTestCase
    QueryBudgetMixin,
    BaseInertiaTestCase,
):
    """Query-budget base for view tests that assert on inertia props.

    The fast hasher is inherited through ``BaseInertiaTestCase`` →
    ``BaseTestCase`` (no decorator of its own).
    """
