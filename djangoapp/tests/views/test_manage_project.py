from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, cast

from django.apps import apps

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase
from djangoapp.tests.views import skip_unless_env

if TYPE_CHECKING:
    from django.db.models import Model


@skip_unless_env("RUN_PROJECT_TESTS")
class ManageProjectTests(BaseInertiaTestCase):
    """Real models-management coverage against the test app's models.

    Runs only in checkframework1's project stage (sets ``RUN_PROJECT_TESTS`` and
    overlays the test app onto ``ourapp/``); self-skips elsewhere (the var is unset and
    ``ourapp/`` is empty). Models are fetched via ``apps.get_model`` so the module
    imports safely when collected in checkframework1 (no top-level ``ourapp`` import).

    - test_model_list_lists_testapp_models, /manage/models lists Author +
      Book + FileCleanupDoc + Shelf
    - test_book_list, /manage/models/Book/list columns + both FK cell kinds
    - test_book_list_pagination_and_sort, per_page paging + id/last_updated_at sort
    - test_per_page_invalid_422, a per_page outside {25,50,100} → 422
    - test_book_detail, /manage/models/Book/id/<pid> renders RowDetail
    - test_book_detail_unknown_id_404, an unknown public_id → 404
    - test_non_basemodel_model_detail_404, a plain (non-BaseModel) model has no detail page
    - test_shelf_fk_and_scalar_column_kinds, plain-model FK unlinked; float/date as char
    - test_book_detail_logs_after_save_plus, a save_plus edit feeds the lazy logs partial
    - test_author_list_renders, /manage/models/Author/list renders rows
    """

    # Model classes resolved lazily in setUpTestData (ourapp is empty in checkframework1,
    # so they can't be imported at module load — the class is skipped there).
    Author: ClassVar[type[Any]]
    Book: ClassVar[type[Any]]
    Shelf: ClassVar[type[Any]]

    superuser: ClassVar[User]
    author: ClassVar[Any]
    book: ClassVar[Any]

    @classmethod
    def setUpTestData(cls) -> None:
        # Locally typed type[Any]: AppConfig.get_model returns type[Model],
        # which would narrow cls.Author/Book and fail .objects access below.
        ourapp = apps.get_app_config("ourapp")
        author_model: type[Any] = ourapp.get_model("Author")
        book_model: type[Any] = ourapp.get_model("Book")
        cls.Author = author_model
        cls.Book = book_model
        cls.Shelf = ourapp.get_model("Shelf")
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.author = cls.Author.objects.create(
            name="Ada", bio="Mathematician", rating="4.50", active=True
        )
        cls.book = cls.Book.objects.create(
            title="Notes",
            description="A book",
            pages=200,
            author=cls.author,
            reviewer=cls.superuser,
        )

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.superuser)
        # self.inertia is a separate Client (X-Inertia defaults on); log it in
        # too so partial-reload tests pass require_superuser.
        self.inertia.force_login(self.superuser)

    # --- helpers -----------------------------------------------------------
    # created_at is auto_now_add (save() would override it), so the helpers use
    # queryset.update() to set the timestamps directly.

    def _rows_props(self, model: str, query: str = "") -> dict[str, Any]:
        """GET a model's /list (+ optional query string) → parsed ModelRows props."""
        url = f"/manage/models/{model}/list"
        if query:
            url = f"{url}?{query}"
        self.client.get(url)
        return cast("dict[str, Any]", self.props()["props"])

    def _stamp_book(self, book: Model, *, created_at: datetime, edited_at: datetime) -> None:
        """Force a book's created_at/last_updated_at via update() (save() would reset them)."""
        self.Book.objects.filter(pk=book.pk).update(
            created_at=created_at,
            last_updated_at=edited_at,
        )

    # --- model index -------------------------------------------------------

    def test_model_list_lists_testapp_models(self) -> None:
        """/manage/models lists the test app's models with docstrings + counts."""
        # Example response: models = [
        #   {"name": "Author", "docstring": "An author of books.", "row_count": 1},
        #   {"name": "Book",   "docstring": "A book ...",          "row_count": 1},
        # ]
        self.client.get("/manage/models")
        self.assertComponentUsed("ModelList")

        # Every test-app model appears, each with its live row count.
        models = {m["name"]: m for m in self.props()["props"]["models"]}
        self.assertEqual(set(models), {"Author", "Book", "FileCleanupDoc", "Shelf"})
        self.assertEqual(models["Author"]["row_count"], 1)
        self.assertEqual(models["Book"]["row_count"], 1)
        self.assertEqual(models["FileCleanupDoc"]["row_count"], 0)
        self.assertEqual(models["Shelf"]["row_count"], 0)

        # The model list surfaces each class docstring (used as a caption).
        self.assertIn("author of books", models["Author"]["docstring"].lower())

    # --- list view (Book) --------------------------------------------------

    def test_book_list(self) -> None:
        """Book row list exposes column types + both FK cell kinds (pk-free)."""
        # Example response (ModelRowsProps):
        #   {"model_name": "Book",
        #    "columns": [{"name": "author", "type": "foreign_key", "has_choices": false}, ...],
        #    "rows": [{"public_id": "...", "values": {
        #        "title": "Notes",
        #        "author":   {"public_id": "...", "url": ".../Author/id/...", "title": "Ada"},
        #        "reviewer": {"public_id": "...", "title": "admin"}}, ...}],
        #    "pagination": {"page": 1, "total_pages": 1, "total_count": 1},
        #    "filters": {"per_page": 25, "page": 1, "sort": "created_at"}}
        props = self._rows_props("Book")
        self.assertComponentUsed("ModelRows")

        # Column types: a BaseModel FK → "foreign_key", a User FK → "user".
        col_types = {c["name"]: c["type"] for c in props["columns"]}
        self.assertEqual(col_types["author"], "foreign_key")
        self.assertEqual(col_types["reviewer"], "user")

        row = props["rows"][0]

        # FK→BaseModel cell: linked via get_absolute_url(), pk-free.
        author_cell = cast("dict[str, str]", row["values"]["author"])
        self.assertEqual(author_cell["public_id"], self.author.public_id)
        self.assertEqual(author_cell["url"], f"/manage/models/Author/id/{self.author.public_id}")
        self.assertEqual(author_cell["title"], "Ada")

        # FK→User cell: a pk-free profile (public_id + title), no url key.
        reviewer_cell = cast("dict[str, str]", row["values"]["reviewer"])
        self.assertEqual(reviewer_cell["public_id"], self.superuser.public_id)
        self.assertNotIn("url", reviewer_cell)

    def test_book_list_pagination_and_sort(self) -> None:
        """List supports per_page pagination + id/last_updated_at sort (Book)."""
        # Seed 31 books with staggered timestamps, plus the "Notes" fixture → 32
        # total. With per_page=25 and orphans=5 that's 25 on page 1, 7 on page 2
        # (7 > 5, so no merge). created_at ascends with i; edited_at descends, so
        # the two sort orders are exact reverses of each other.
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(31):
            self._stamp_book(
                self.Book.objects.create(
                    title=f"Bulk {i:02d}",
                    description="",
                    pages=i,
                    author=self.author,
                    reviewer=self.superuser,
                ),
                created_at=base + timedelta(seconds=i + 1),
                edited_at=base + timedelta(seconds=32 - i),
            )
        # Push the "Notes" fixture to the bottom of both orders so it never leads.
        self._stamp_book(self.book, created_at=base, edited_at=base)

        # Pagination (default per_page=25): page 1 holds 25 of 32.
        page1 = self._rows_props("Book")
        self.assertEqual(page1["pagination"]["page"], 1)
        self.assertEqual(page1["pagination"]["total_pages"], 2)
        self.assertEqual(page1["pagination"]["total_count"], 32)
        self.assertEqual(len(page1["rows"]), 25)

        # Page 2 holds the older 7 rows.
        page2 = self._rows_props("Book", "page=2")
        self.assertEqual(page2["pagination"]["page"], 2)
        self.assertEqual(len(page2["rows"]), 7)

        # Sort by -id (default), newest-first: "Bulk 30" leads.
        newest_created = self._rows_props("Book", "sort=-id")["rows"][0]
        self.assertEqual(newest_created["values"]["title"], "Bulk 30")

        # Sort by -last_updated_at, newest-first: reverse order, "Bulk 00" leads.
        newest_edited = self._rows_props("Book", "sort=-last_updated_at")["rows"][0]
        self.assertEqual(newest_edited["values"]["title"], "Bulk 00")

    def test_per_page_invalid_422(self) -> None:
        """A per_page outside {25, 50, 100} is rejected by the props validator (422)."""
        response = self.client.get("/manage/models/Book/list?per_page=7")
        self.assertEqual(response.status_code, 422)

    # --- detail view (Book) ------------------------------------------------

    def test_book_detail(self) -> None:
        """/manage/models/Book/id/<pid> renders RowDetail with the book's columns."""
        # Example response (RowDetailProps):
        #   {"model_name": "Book", "public_id": "...",
        #    "columns": [{"name": "title", "type": "char", "has_choices": false}, ...],
        #    "values": {"title": "Notes", "pages": 200, ...},
        #    "created_by": {"public_id": "...", "title": "admin"},
        #    "created_at": "...", "edited_at": "..."}
        self.client.get(f"/manage/models/Book/id/{self.book.public_id}")
        self.assertComponentUsed("RowDetail")
        props = self.props()["props"]

        # Builtins (public_id/created_by/created_at/row_version/last_updated_at/
        # last_updated_by) are columns like any other, so they lead before
        # Book's own fields.
        self.assertEqual(
            [c["name"] for c in props["columns"]],
            [
                "public_id",
                "created_by",
                "created_at",
                "row_version",
                "last_updated_at",
                "last_updated_by",
                "title",
                "description",
                "pages",
                "weight",
                "released",
                "published",
                "author",
                "shelf",
                "reviewer",
            ],
        )

        # Values are serialised by column kind (char passes through raw).
        self.assertEqual(props["model_name"], "Book")
        self.assertEqual(props["public_id"], self.book.public_id)
        self.assertEqual(props["values"]["title"], "Notes")

        # Logs are a lazy Inertia prop: absent from the top-level page props on the full page load
        self.assertNotIn("logs", self.props())

    def test_book_detail_logs_load_on_partial_reload(self) -> None:
        """The lazy ``logs`` prop is evaluated only on a partial reload."""
        url = f"/manage/models/Book/id/{self.book.public_id}"

        # Partial reload: inertia client + only:["logs"] + matching component.
        self.inertia.get(
            url,
            HTTP_X_INERTIA_PARTIAL_DATA="logs",
            HTTP_X_INERTIA_PARTIAL_COMPONENT="RowDetail",
        )
        props = self.props()
        # The callable ran (otherwise the key would be absent). The list is empty
        # because setUpTestData seeds the book via plain objects.create() (not
        # save_plus), so no BaseModelUpdateLog row exists for it.
        self.assertIn("logs", props)
        self.assertEqual(props["logs"], [])

    def test_book_detail_logs_after_save_plus(self) -> None:
        """A save_plus edit feeds the lazy logs partial with a serialised entry."""
        self.book.title = "Edited Notes"
        self.book.save_plus(actor=self.superuser, expected_row_version=self.book.row_version)

        self.inertia.get(
            f"/manage/models/Book/id/{self.book.public_id}",
            HTTP_X_INERTIA_PARTIAL_DATA="logs",
            HTTP_X_INERTIA_PARTIAL_COMPONENT="RowDetail",
        )
        logs = self.props()["logs"]
        self.assertEqual(len(logs), 1)
        # to_entry_item shape: pk-free, action + actor + the field diff.
        self.assertEqual(logs[0]["action"], "updated")
        self.assertEqual(logs[0]["old_values"].get("title"), "Notes")
        self.assertEqual(logs[0]["new_values"].get("title"), "Edited Notes")

    def test_book_detail_unknown_id_404(self) -> None:
        """An unknown-but-well-formed public_id → 404, never a 500."""
        response = self.client.get("/manage/models/Book/id/ffffffff-ffff-7fff-8fff-ffffffffffff")
        self.assertEqual(response.status_code, 404)

    def test_non_basemodel_model_detail_404(self) -> None:
        """A plain (non-BaseModel) model has no detail page — 404 by design."""
        response = self.client.get("/manage/models/Shelf/id/whatever")
        self.assertEqual(response.status_code, 404)

    def test_shelf_fk_and_scalar_column_kinds(self) -> None:
        """Plain-model FK renders unlinked (None); float/date fall through to char."""
        shelf = self.Shelf.objects.create(code="A1")
        self.Book.objects.create(
            title="On a shelf",
            description="",
            pages=1,
            weight=0.75,
            released=date(2026, 1, 1),
            author=self.author,
            shelf=shelf,
            reviewer=self.superuser,
        )
        props = self._rows_props("Book")
        row = next(r for r in props["rows"] if r["values"]["title"] == "On a shelf")

        # Unmapped scalars (float, date) degrade to the char kind…
        col_types = {c["name"]: c["type"] for c in props["columns"]}
        self.assertEqual(col_types["weight"], "char")
        self.assertEqual(col_types["released"], "char")
        # …their values coerced to JSON-safe strings (date is not one natively).
        self.assertEqual(row["values"]["weight"], 0.75)
        self.assertEqual(row["values"]["released"], "2026-01-01")

        # FK to a plain model: no management URL, renders as unset — and no
        # str() is called on it, so no pk can leak.
        self.assertIsNone(row["values"]["shelf"])

    # --- list view (Author) ------------------------------------------------

    def test_author_list_renders(self) -> None:
        """/manage/models/Author/list renders ModelRows for a no-FK model."""
        # Example response (ModelRowsProps, no foreign_key/user columns):
        #   {"model_name": "Author",
        #    "columns": [{"name": "name", "type": "char", "has_choices": false},
        #                {"name": "rating", "type": "decimal", ...},
        #                {"name": "active", "type": "boolean", ...}],
        #    "rows": [...]}
        props = self._rows_props("Author")
        self.assertComponentUsed("ModelRows")

        # Author has no FK columns; every column is a plain field kind.
        self.assertEqual(props["model_name"], "Author")
        self.assertEqual(len(props["rows"]), 1)
        self.assertNotIn("foreign_key", {c["type"] for c in props["columns"]})
