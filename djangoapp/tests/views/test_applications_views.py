from __future__ import annotations

from http import HTTPStatus
from typing import Any, ClassVar, cast

from inertia.test import InertiaTestCase

from djangoapp.models import Application, ApplicationCollection, User
from djangoapp.models.columns import CharColumn
from djangoapp.models.dynamic import dynamic_models


class ApplicationsViewsTests(
    InertiaTestCase,
):
    """Superuser-only read views for collections/apps/tables.

    Uses the Inertia test case (``self.props``/``assertComponentUsed``) to
    assert the served component and that props mirror the DB — collections
    listed, apps listed for a collection, and /manage row counts matching
    live rows. Non-superusers get 404 (never 403).

    - test_collections_page_superuser, Collections component + props mirror DB collections
    - test_collections_page_non_superuser_404, non-superuser gets 404
    - test_app_list_page, AppList component + props mirror the collection's apps
    - test_manage_page_shows_row_counts, Manage component + row counts match live rows
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
        cls.app = cls.collection.applications.create(
            name="orders",
        )

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def test_collections_page_superuser(self) -> None:
        """Collections component renders and props mirror the DB collections."""
        self.client.force_login(self.superuser)
        self.client.get("/apps/collections")
        self.assertComponentUsed("Collections")
        props = self.props()["props"]
        self.assertEqual([c["name"] for c in props["collections"]], ["inv"])

    def test_collections_page_non_superuser_404(self) -> None:
        """Non-superuser gets 404 (must not learn the page exists)."""
        self.client.force_login(self.plain)
        resp = self.client.get("/apps/collections")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_app_list_page(self) -> None:
        """AppList component renders and props mirror the collection's apps."""
        self.client.force_login(self.superuser)
        self.client.get("/apps/a/inv/list")
        self.assertComponentUsed("AppList")
        props = self.props()["props"]
        self.assertEqual(props["collection_name"], "inv")
        self.assertEqual([a["name"] for a in props["apps"]], ["orders"])

    def test_manage_page_shows_row_counts(self) -> None:
        """/manage row counts match the live row count from the dynamic model."""
        table = dynamic_models.create_application_table(
            collection="inv",
            application="orders",
            table="items",
            columns=[CharColumn("code", max_length=10)],
        )
        # Insert one row via the dynamic model so the count must be 1.
        model = cast("Any", table.as_model())
        model.objects.create(code="A1")
        self.client.force_login(self.superuser)
        self.client.get("/apps/a/inv/orders/manage")
        self.assertComponentUsed("Manage")
        tables = self.props()["props"]["tables"]
        self.assertEqual([t["name"] for t in tables], ["items"])
        self.assertEqual(tables[0]["row_count"], 1)
