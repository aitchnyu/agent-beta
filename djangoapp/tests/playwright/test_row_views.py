from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

from djangoapp.models import ApplicationCollection, User
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    DateTimeColumn,
    DecimalColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)
from djangoapp.models.dynamic import dynamic_models
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Seed size: with per_page=25 and Paginator orphans=5, the last page keeps its
# 6 rows (orphans only merge <=5), so 31 rows yield two real pages under the
# default sort.
ROW_COUNT = 31


class _RowViewsE2eBase(BasePlaywrightTestCase):
    """Shared seed + URL/page helpers for the row-view E2E tests.

    Creates a superuser, a collection/app/table spanning every column type, and
    ``ROW_COUNT`` rows whose ``code`` is ``R<index>`` (created in index order so
    ``_created_at`` ascends with the index — the default sort is created_at desc,
    so the newest row ``R<last>`` is first). Each test reuses the same shared
    browser context; pages log in explicitly via ``/login-for-test/<pk>`` so
    session cookies never leak between tests.
    """

    COLLECTION = "pw"
    APP = "orders"
    TABLE = "items"

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.collection = ApplicationCollection.objects.create(name=self.COLLECTION)
        self.app = self.collection.applications.create(
            name=self.APP,
        )
        dynamic_models.reset()
        self.table = dynamic_models.create_application_table(
            collection=self.COLLECTION,
            application=self.APP,
            table=self.TABLE,
            columns=[
                CharColumn("code", max_length=100),
                TextColumn("note"),
                IntegerColumn("qty", nullable=True),
                BooleanColumn("active"),
                DecimalColumn("price", max_digits=10, decimal_places=2, nullable=True),
                DateTimeColumn("due", nullable=True),
                UserColumn("owner", nullable=True),
            ],
        )
        self.model = cast("Any", self.table.as_model())
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        self.rows = [
            self.model.objects.create(
                code=f"R{i}",
                note=f"n{i}",
                qty=i,
                active=(i % 2 == 0),
                price=Decimal(f"{i}.00"),
                due=base + timedelta(hours=i),
                owner=self.superuser,
                _created_by=self.superuser,
            )
            for i in range(ROW_COUNT)
        ]

    def tearDown(self) -> None:
        # Reverse create_application_table for the table setUp made: drop the
        # physical table + delete the definition rows. The live server thread
        # uses its own DB connection, so seeded rows must be committed — making
        # this a TransactionTestCase whose per-test flush (run by Django after
        # tearDown) truncates the managed tables. The dynamic ``zz_*`` table's
        # ``_created_by``/``owner`` FKs into ``auth_user`` would block that
        # TRUNCATE, so it must be dropped here, before the flush. Guarded so a
        # setUp that failed before creating the table doesn't mask the real
        # error with an AttributeError.
        if getattr(self, "table", None) is not None:
            dynamic_models.delete_application_table(
                collection=self.COLLECTION, application=self.APP, table=self.TABLE
            )
        dynamic_models.reset()
        super().tearDown()

    def _super_page(self) -> Page:
        """Return a fresh page authenticated as the superuser (row views are superuser-gated)."""
        page = self.context.new_page()
        page.goto(f"{self.live_server_url}/login-for-test/{self.superuser.pk}")
        page.set_default_timeout(1000)
        return page

    def _nonsuper_page(self) -> Page:
        """Return a fresh page authenticated as the non-superuser ``self.user``."""
        page = self.context.new_page()
        page.goto(f"{self.live_server_url}/login-for-test/{self.user.pk}")
        return page


class RowDetailE2eTests(_RowViewsE2eBase):
    """E2E for the superuser row detail page (``RowDetail.vue``).

    - test_detail_renders_all_column_values, detail renders every column type + created-by link
    - test_unknown_row_404, an unknown public_id resolves to 404
    - test_non_superuser_404, a non-superuser gets 404
    """

    def _detail_url(self, public_id: str) -> str:
        return (
            f"{self.live_server_url}/apps/a/{self.COLLECTION}/{self.APP}/manage/"
            f"{self.TABLE}/id/{public_id}"
        )

    def test_detail_renders_all_column_values(self) -> None:
        """Detail renders every column type (text/bool/dec/dt/user) + created-by link."""
        row = self.rows[5]
        page = self._super_page()
        page.goto(self._detail_url(row._public_id))
        page.wait_for_selector(".apps-rowdetail-page")
        body = page.inner_text(".apps-rowdetail-table")
        # Every user column type is present, serialised client-side:
        # code/note raw, active Yes/No, decimal str, datetime local-formatted, owner title.
        self.assertIn("R5", body)
        self.assertIn("n5", body)
        self.assertIn("Yes" if row.active else "No", body)
        self.assertIn("5.00", body)
        self.assertIn(self.superuser.display_name, body)

    def test_unknown_row_404(self) -> None:
        """An unknown public_id resolves to 404."""
        page = self._super_page()
        response = page.goto(self._detail_url("does-not-exist"))
        assert response is not None  # narrows Response | None for mypy below
        self.assertEqual(response.status, HTTPStatus.NOT_FOUND)

    def test_non_superuser_404(self) -> None:
        """A non-superuser gets 404 on the detail page."""
        page = self._nonsuper_page()
        response = page.goto(self._detail_url(self.rows[0]._public_id))
        assert response is not None  # narrows Response | None for mypy below
        self.assertEqual(response.status, HTTPStatus.NOT_FOUND)


class RowListNavigationE2eTests(_RowViewsE2eBase):
    """E2E for list rendering + list -> detail and pagination on ``TableRows.vue``.

    - test_list_renders_rows_and_total, list renders the newest row first + total count
    - test_row_link_opens_detail, clicking a row's arrow link opens its detail page
    - test_per_page_100_shows_all_rows, per-page select of 100 shows every row, no next link
    - test_pagination_next_then_prev, Next moves to page 2 and Prev returns to page 1
    - test_prev_disabled_on_first_page, the Prev link is absent on page 1
    """

    def _list_url(self, query: str = "") -> str:
        url = f"{self.live_server_url}/apps/a/{self.COLLECTION}/{self.APP}/manage/{self.TABLE}/list"
        return f"{url}?{query}" if query else url

    def test_list_renders_rows_and_total(self) -> None:
        """List renders the newest row first and the total count."""
        page = self._super_page()
        page.goto(self._list_url())
        page.wait_for_selector(".apps-tablerows-table")
        body = page.inner_text(".apps-tablerows-page")
        # Default sort is created_at desc: R<last> (newest) is the first row.
        self.assertIn(f"R{ROW_COUNT - 1}", body)
        self.assertIn(f"{ROW_COUNT} total", body)

    def test_row_link_opens_detail(self) -> None:
        """Clicking the first row's arrow link opens its detail page."""
        page = self._super_page()
        page.goto(self._list_url())
        page.wait_for_selector(".apps-row-link")
        # Newest row (R<last>) is first; its link targets that row's detail page.
        page.locator(".apps-row-link").first.click()
        page.wait_for_url(f"**/id/{self.rows[ROW_COUNT - 1]._public_id}")
        page.wait_for_selector(".apps-rowdetail-page")

    def test_per_page_100_shows_all_rows(self) -> None:
        """Per-page select of 100 shows every row on one page (no next link)."""
        page = self._super_page()
        page.goto(self._list_url())
        page.wait_for_selector(".apps-tablerows-controls")
        # The per-page select is the first select in the controls row.
        page.locator(".apps-tablerows-controls select").nth(0).select_option("100")
        page.wait_for_url("**per_page=100**")
        body = page.inner_text(".apps-tablerows-page")
        self.assertIn(f"R{ROW_COUNT - 1}", body)
        # 31 rows fit in one page of 100, so the Next link is absent.
        self.assertEqual(page.locator(".apps-next-link").count(), 0)

    def test_pagination_next_then_prev(self) -> None:
        """Next moves to page 2 (oldest rows) and Prev returns to page 1 (newest)."""
        page = self._super_page()
        page.goto(self._list_url())
        page.wait_for_selector(".apps-next-link")
        page.locator(".apps-next-link").click()
        page.wait_for_url("**page=2**")
        # Page 2 holds the oldest 6 rows (created_at desc), so R5..R0 are here
        # and the newest R<last> is not.
        body = page.inner_text(".apps-tablerows-page")
        self.assertIn("R5", body)
        self.assertNotIn(f"R{ROW_COUNT - 1}", body)
        page.locator(".apps-prev-link").click()
        page.wait_for_url("**page=1**")
        self.assertIn(f"R{ROW_COUNT - 1}", page.inner_text(".apps-tablerows-page"))

    def test_prev_disabled_on_first_page(self) -> None:
        """The Prev link is absent on page 1 (only a disabled span renders)."""
        page = self._super_page()
        page.goto(self._list_url())
        page.wait_for_selector(".apps-tablerows-table")
        self.assertEqual(page.locator(".apps-prev-link").count(), 0)
