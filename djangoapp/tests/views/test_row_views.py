from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import Any, ClassVar, cast

from inertia.test import InertiaTestCase

from djangoapp.models import Application, User
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    DateTimeColumn,
    DecimalColumn,
    ForeignKeyColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)
from djangoapp.models.dynamic import dynamic_models

_APP = "OrdersData"


class RowListPageTests(
    InertiaTestCase,
):
    """Superuser-only paginated row list for a table's dynamic model.

    - test_non_superuser_404, non-superuser gets 404
    - test_missing_app_404, unknown app resolves to 404
    - test_missing_table_404, unknown table resolves to 404
    - test_default_sort_and_pagination, defaults sort=created_at, per_page=25, page=1
    - test_invalid_sort_falls_back, unknown sort falls back to created_at (no 500)
    - test_edited_at_sort, sort=edited_at orders by most-recently-edited first
    - test_owner_cell_pk_free, owner user column is a pk-free profile keyed by name
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")
        cls.app = Application.objects.create(name=_APP)

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        self.table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[
                CharColumn("code", max_length=100),
                IntegerColumn("qty", nullable=True),
                BooleanColumn("active"),
                DecimalColumn("price", max_digits=10, decimal_places=2, nullable=True),
                UserColumn("owner", nullable=True),
            ],
        )
        self.model = cast("Any", self.table.as_model())
        self.r1 = self.model.objects.create(
            code="A1", owner=self.superuser, _created_by=self.superuser
        )
        self.r2 = self.model.objects.create(
            code="A2", owner=self.superuser, _created_by=self.superuser
        )
        # Re-save r1 so its _edited_at is the latest (drives edited_at sort).
        self.r1.save()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def test_non_superuser_404(self) -> None:
        """non-superuser gets 404."""
        self.client.force_login(self.plain)
        resp = self.client.get(f"/manage/apps/{_APP}/items/list")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_missing_app_404(self) -> None:
        """Unknown app resolves to 404."""
        self.client.force_login(self.superuser)
        resp = self.client.get("/manage/apps/UnknownApp/items/list")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_missing_table_404(self) -> None:
        """Unknown table resolves to 404."""
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/manage/apps/{_APP}/nope/list")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_default_sort_and_pagination(self) -> None:
        """Defaults sort=created_at, per_page=25, page=1."""
        self.client.force_login(self.superuser)
        self.client.get(f"/manage/apps/{_APP}/items/list")
        self.assertComponentUsed("TableRows")
        props = self.props()["props"]
        self.assertEqual(props["filters"], {"per_page": 25, "page": 1, "sort": "created_at"})
        # created_at desc: r2 (created later) comes first.
        self.assertEqual(props["rows"][0]["public_id"], self.r2._public_id)
        self.assertEqual(props["pagination"]["total_count"], 2)

    def test_invalid_sort_falls_back(self) -> None:
        """Unknown sort falls back to created_at (no 500)."""
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/manage/apps/{_APP}/items/list?sort=bogus")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(self.props()["props"]["filters"]["sort"], "created_at")

    def test_edited_at_sort(self) -> None:
        """sort=edited_at orders by most-recently-edited first."""
        self.client.force_login(self.superuser)
        self.client.get(f"/manage/apps/{_APP}/items/list?sort=edited_at")
        # r1 was re-saved last, so it is first under edited_at desc.
        self.assertEqual(self.props()["props"]["rows"][0]["public_id"], self.r1._public_id)

    def test_owner_cell_pk_free(self) -> None:
        """Owner user column is a pk-free profile keyed by name."""
        self.client.force_login(self.superuser)
        self.client.get(f"/manage/apps/{_APP}/items/list")
        owner_value = self.props()["props"]["rows"][0]["values"]["owner"]
        self.assertEqual(owner_value["public_id"], self.superuser.public_id)


class RowDetailPageTests(
    InertiaTestCase,
):
    """Superuser-only single-row detail by _public_id.

    - test_non_superuser_404, non-superuser gets 404
    - test_missing_row_404, unknown public_id resolves to 404
    - test_created_by_pk_free, created_by is a {public_id, title} profile with no pk
    - test_timestamps_iso, created_at/edited_at are ISO strings
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")
        cls.app = Application.objects.create(name=_APP)

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        self.table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[CharColumn("code", max_length=100), UserColumn("owner", nullable=True)],
        )
        self.model = cast("Any", self.table.as_model())
        self.row = self.model.objects.create(code="A1", _created_by=self.superuser)

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def test_non_superuser_404(self) -> None:
        """non-superuser gets 404."""
        self.client.force_login(self.plain)
        resp = self.client.get(f"/manage/apps/{_APP}/items/id/{self.row._public_id}")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_missing_row_404(self) -> None:
        """Unknown public_id resolves to 404."""
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/manage/apps/{_APP}/items/id/does-not-exist")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_created_by_pk_free(self) -> None:
        """created_by is a {public_id, title} profile with no pk."""
        self.client.force_login(self.superuser)
        self.client.get(f"/manage/apps/{_APP}/items/id/{self.row._public_id}")
        self.assertComponentUsed("RowDetail")
        props = self.props()["props"]
        self.assertEqual(
            props["created_by"],
            {"public_id": self.superuser.public_id, "title": self.superuser.display_name},
        )

    def test_timestamps_iso(self) -> None:
        """created_at/edited_at are ISO strings."""
        self.client.force_login(self.superuser)
        self.client.get(f"/manage/apps/{_APP}/items/id/{self.row._public_id}")
        props = self.props()["props"]
        self.assertEqual(props["created_at"], self.row._created_at.isoformat())
        self.assertEqual(props["edited_at"], self.row._edited_at.isoformat())


class RowValuesViewTests(InertiaTestCase):
    """All column types rendered in the list/detail views + list sort/pagination.

    Seeds a table spanning every column type (char/text/int/bool/decimal/
    datetime/user/foreign_key) plus a target table for the FK, and a page's
    worth of rows, then asserts each cell's serialised value is present in both
    the list and the detail page, the foreign_key column def carries the target
    table, and that the list sorts (created_at / edited_at) and paginates
    (per_page=25).

    - test_all_values_in_list, every column-type value serialised in list rows
    - test_all_values_in_detail, every column-type value serialised on detail
    - test_foreign_key_column_def_links_to_target, FK column def carries the target table
    - test_default_sort_created_at_desc, newest row first under default sort
    - test_edited_at_sort, re-saved row jumps to front under sort=edited_at
    - test_pagination_splits_rows_by_per_page, per_page=25 splits 31 rows into 25 + 6
    - test_invalid_per_page_rejected, per_page outside {25,50,100} rejected with 422
    """

    superuser: ClassVar[User]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(
            username="values-admin", is_superuser=True, is_staff=True
        )
        cls.app = Application.objects.create(name=_APP)

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        # "targets" exists before "items" so the foreign_key column can resolve.
        self.target_table = dynamic_models.create_application_table(
            application=_APP,
            table="targets",
            columns=[CharColumn("code", max_length=10)],
        )
        self.target_model = cast("Any", self.target_table.as_model())
        self.target = self.target_model.objects.create(code="T1")
        self.table = dynamic_models.create_application_table(
            application=_APP,
            table="items",
            columns=[
                CharColumn("code", max_length=100),
                TextColumn("note"),
                IntegerColumn("qty", nullable=True),
                BooleanColumn("active"),
                DecimalColumn("price", max_digits=10, decimal_places=2, nullable=True),
                DateTimeColumn("due", nullable=True),
                UserColumn("owner", nullable=True),
                ForeignKeyColumn("ref", target=(_APP, "targets"), nullable=True),
            ],
        )
        self.model = cast("Any", self.table.as_model())
        self.client.force_login(self.superuser)
        # 31 rows: with per_page=25 and Paginator orphans=5, the last page
        # keeps its 6 rows (orphans only merge ≤5), so pagination yields two
        # real pages. Created in order so created_at ascends with the index.
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
                ref=self.target,
                _created_by=self.superuser,
            )
            for i in range(31)
        ]

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _expected_values(self, row: Any) -> dict[str, Any]:  # noqa: ANN401 dynamic-model row, attributes are runtime-defined
        """Return the client-facing serialisation for a row across all column types."""
        return {
            "code": row.code,
            "note": row.note,
            "qty": row.qty,
            "active": row.active,
            "price": str(row.price),
            "due": row.due.isoformat(),
            "owner": {"public_id": self.superuser.public_id, "title": self.superuser.display_name},
            "ref": {"public_id": self.target._public_id},
        }

    def _list_props(self, query: str = "") -> dict[str, Any]:
        url = f"/manage/apps/{_APP}/items/list"
        if query:
            url += f"?{query}"
        self.client.get(url)
        return cast("dict[str, Any]", self.props()["props"])

    def test_all_values_in_list(self) -> None:
        """List rows serialise every column type (decimal→str, datetime→ISO, user→profile)."""
        rows = self._list_props()["rows"]
        by_id = {r["public_id"]: r["values"] for r in rows}
        # The newest row (last created) is row[30].
        self.assertEqual(by_id[self.rows[30]._public_id], self._expected_values(self.rows[30]))

    def test_all_values_in_detail(self) -> None:
        """Detail serialises every column type (decimal→str, datetime→ISO, user→profile)."""
        self.client.get(f"/manage/apps/{_APP}/items/id/{self.rows[15]._public_id}")
        values = cast("dict[str, Any]", self.props()["props"]["values"])
        self.assertEqual(values, self._expected_values(self.rows[15]))

    def test_foreign_key_column_def_links_to_target(self) -> None:
        """A foreign_key column def carries the target table (frontend links to its row)."""
        columns = self._list_props()["columns"]
        ref_col = next(c for c in columns if c["name"] == "ref")
        self.assertEqual(ref_col["type"], "foreign_key")
        self.assertEqual(
            ref_col["fk_target"],
            {"app_name": _APP, "table_name": "targets"},
        )

    def test_default_sort_created_at_desc(self) -> None:
        """Newest row first under default sort."""
        rows = self._list_props("per_page=100")["rows"]
        self.assertEqual(rows[0]["public_id"], self.rows[30]._public_id)
        self.assertEqual(rows[-1]["public_id"], self.rows[0]._public_id)

    def test_edited_at_sort(self) -> None:
        """re-saved row jumps to front under sort=edited_at."""
        # rows[0] is oldest by created_at; re-saving bumps its _edited_at.
        self.rows[0].save()
        rows = self._list_props("sort=edited_at&per_page=100")["rows"]
        self.assertEqual(rows[0]["public_id"], self.rows[0]._public_id)

    def test_pagination_splits_rows_by_per_page(self) -> None:
        """per_page=25 splits 31 rows into 25 + 6 (orphans=5 keeps the 6)."""
        page1 = self._list_props("per_page=25&page=1")
        self.assertEqual(len(page1["rows"]), 25)
        self.assertEqual(page1["pagination"]["total_count"], 31)
        self.assertEqual(page1["pagination"]["total_pages"], 2)
        page2 = self._list_props("per_page=25&page=2")
        self.assertEqual(len(page2["rows"]), 6)
        self.assertEqual(page2["pagination"]["page"], 2)

    def test_invalid_per_page_rejected(self) -> None:
        """per_page outside {25,50,100} is rejected with 422 (sent as a string)."""
        resp = self.client.get(f"/manage/apps/{_APP}/items/list?per_page=10")
        self.assertEqual(resp.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
