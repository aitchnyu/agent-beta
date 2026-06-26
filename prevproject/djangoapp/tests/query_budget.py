"""Query-budget base classes that catch N+1 read regressions in view tests.

A test fails if it runs more SELECT queries than its budget. Only read queries
(`SELECT` / `WITH ... SELECT`) are counted, so fixture INSERTs and the
savepoint/transaction overhead that `django.test.TestCase` wraps each test in
do not inflate the count - the budget reflects the view's actual reads.

Usage:
- plain view tests:        `class Foo(QueryBudgetTestCase)`
- inertia view tests:      `class Bar(QueryBudgetInertiaTestCase)`
- raise the ceiling where legitimate:
      `self.allow_more_queries(12)   # explain why at the call site`

The budget is enforced from setUp through the test body (captured via
`addCleanup`), so subclasses must call `super().setUp()`. See
prompts/20260622-misc-refactors.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from inertia.test import InertiaTestCase

if TYPE_CHECKING:
    from collections.abc import Callable

# Reads a view makes; writes/DDL/savepoints are excluded so the budget isolates
# the N+1 signal from fixture and transaction noise.
_READ_PREFIXES = ("select", "with")


def _is_read_query(sql: str) -> bool:
    lowered = sql.lstrip().lower()
    return lowered.startswith(_READ_PREFIXES)


class QueryBudgetMixin(TestCase):
    """Fails a test whose SELECT-query count exceeds `max_select_queries`."""

    max_select_queries: int = 8

    def setUp(self) -> None:
        super().setUp()
        # Per-test scope: start each test at the class-configured default so an
        # allow_more_queries() call only affects the test that makes it.
        # (unittest already gives a fresh instance per test; this is the
        # explicit guarantee against any lingering override.)
        self.max_select_queries = type(self).max_select_queries
        self._query_capture: CaptureQueriesContext = CaptureQueriesContext(connection)
        self._query_capture.__enter__()
        self.addCleanup(self._assert_select_budget)

    def allow_more_queries(self, count: int) -> None:
        """Raise this test's SELECT-query budget (state why at the call site)."""
        self.max_select_queries = count

    def captured_select_queries(self) -> list[dict[str, str]]:
        """Return the SELECT queries captured so far (for ad-hoc inspection)."""
        return [q for q in self._query_capture.captured_queries if _is_read_query(q["sql"])]

    def select_count(self, request: Callable[[], object]) -> int:
        """Run `request` once and return how many SELECT/WITH queries it made.

        Use for N+1 checks: run the same operation with few vs many rows and
        assert the counts are equal (constant overhead cancels in the diff).
        """
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


class QueryBudgetTestCase(QueryBudgetMixin):
    """Query-budget base for view tests that don't need inertia assertions."""


class QueryBudgetInertiaTestCase(QueryBudgetMixin, InertiaTestCase):
    """Query-budget base for view tests that assert on inertia props."""
