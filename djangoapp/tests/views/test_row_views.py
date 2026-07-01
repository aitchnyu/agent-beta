from __future__ import annotations

from http import HTTPStatus
from typing import Any, ClassVar, cast

from inertia.test import InertiaTestCase

from djangoapp.models import Application, ApplicationCollection, User
from djangoapp.models.dynamic import dynamic_models


class RowListPageTests(
    InertiaTestCase,
):
    """Superuser-only paginated row list for a table's dynamic model.

    - test_non_superuser_404, non-superuser gets 404
    - test_missing_collection_404, unknown collection resolves to 404
    - test_missing_table_404, unknown table resolves to 404
    - test_default_sort_and_pagination, defaults sort=created_at, per_page=25, page=1
    - test_invalid_sort_falls_back, unknown sort falls back to created_at (no 500)
    - test_edited_at_sort, sort=edited_at orders by most-recently-edited first
    - test_owner_cell_pk_free, owner user column is a pk-free profile keyed by name
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]
    collection: ClassVar[ApplicationCollection]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")
        cls.collection = ApplicationCollection.objects.create(name="inv")
        cls.app = cls.collection.applications.create(name="orders")

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        self.table = dynamic_models.create_application_table(
            "inv",
            "orders",
            "items",
            [
                {"name": "code", "type": "char"},
                {"name": "qty", "type": "integer", "nullable": True},
                {"name": "active", "type": "boolean"},
                {"name": "price", "type": "decimal", "nullable": True},
                {"name": "owner", "type": "user", "nullable": True},
            ],
        )
        self.model = cast("Any", dynamic_models.get_model(self.table.physical_name))
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
        resp = self.client.get("/apps/a/inv/orders/manage/items/list")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_missing_collection_404(self) -> None:
        """Unknown collection resolves to 404."""
        self.client.force_login(self.superuser)
        resp = self.client.get("/apps/a/nope/orders/manage/items/list")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_missing_table_404(self) -> None:
        """Unknown table resolves to 404."""
        self.client.force_login(self.superuser)
        resp = self.client.get("/apps/a/inv/orders/manage/nope/list")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_default_sort_and_pagination(self) -> None:
        """Defaults sort=created_at, per_page=25, page=1."""
        self.client.force_login(self.superuser)
        self.client.get("/apps/a/inv/orders/manage/items/list")
        self.assertComponentUsed("TableRows")
        props = self.props()["props"]
        self.assertEqual(props["filters"], {"per_page": 25, "page": 1, "sort": "created_at"})
        # created_at desc: r2 (created later) comes first.
        self.assertEqual(props["rows"][0]["public_id"], self.r2._public_id)
        self.assertEqual(props["pagination"]["total_count"], 2)

    def test_invalid_sort_falls_back(self) -> None:
        """Unknown sort falls back to created_at (no 500)."""
        self.client.force_login(self.superuser)
        resp = self.client.get("/apps/a/inv/orders/manage/items/list?sort=bogus")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(self.props()["props"]["filters"]["sort"], "created_at")

    def test_edited_at_sort(self) -> None:
        """sort=edited_at orders by most-recently-edited first."""
        self.client.force_login(self.superuser)
        self.client.get("/apps/a/inv/orders/manage/items/list?sort=edited_at")
        # r1 was re-saved last, so it is first under edited_at desc.
        self.assertEqual(self.props()["props"]["rows"][0]["public_id"], self.r1._public_id)

    def test_owner_cell_pk_free(self) -> None:
        """Owner user column is a pk-free profile keyed by name."""
        self.client.force_login(self.superuser)
        self.client.get("/apps/a/inv/orders/manage/items/list")
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
    collection: ClassVar[ApplicationCollection]
    app: ClassVar[Application]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")
        cls.collection = ApplicationCollection.objects.create(name="inv2")
        cls.app = cls.collection.applications.create(name="orders")

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        self.table = dynamic_models.create_application_table(
            "inv2",
            "orders",
            "items",
            [
                {"name": "code", "type": "char"},
                {"name": "owner", "type": "user", "nullable": True},
            ],
        )
        self.model = cast("Any", dynamic_models.get_model(self.table.physical_name))
        self.row = self.model.objects.create(code="A1", _created_by=self.superuser)

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def test_non_superuser_404(self) -> None:
        """non-superuser gets 404."""
        self.client.force_login(self.plain)
        resp = self.client.get(f"/apps/a/inv2/orders/manage/items/id/{self.row._public_id}")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_missing_row_404(self) -> None:
        """Unknown public_id resolves to 404."""
        self.client.force_login(self.superuser)
        resp = self.client.get("/apps/a/inv2/orders/manage/items/id/does-not-exist")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_created_by_pk_free(self) -> None:
        """created_by is a {public_id, title} profile with no pk."""
        self.client.force_login(self.superuser)
        self.client.get(f"/apps/a/inv2/orders/manage/items/id/{self.row._public_id}")
        self.assertComponentUsed("RowDetail")
        props = self.props()["props"]
        self.assertEqual(
            props["created_by"],
            {"public_id": self.superuser.public_id, "title": self.superuser.display_name},
        )

    def test_timestamps_iso(self) -> None:
        """created_at/edited_at are ISO strings."""
        self.client.force_login(self.superuser)
        self.client.get(f"/apps/a/inv2/orders/manage/items/id/{self.row._public_id}")
        props = self.props()["props"]
        self.assertEqual(props["created_at"], self.row._created_at.isoformat())
        self.assertEqual(props["edited_at"], self.row._edited_at.isoformat())
