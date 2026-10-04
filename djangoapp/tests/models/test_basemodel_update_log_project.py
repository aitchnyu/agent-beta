from __future__ import annotations

from typing import Any, ClassVar

from django.apps import apps
from django.http import Http404

from djangoapp.models import (
    SKIP_ROW_VERSION_CHECK,
    BaseModelUpdateLog,
    User,
)
from djangoapp.tests._base import BaseTestCase
from djangoapp.tests.views import skip_unless_env


@skip_unless_env("RUN_PROJECT_TESTS")
class BaseModelUpdateLogTests(BaseTestCase):
    """``BaseModel.save_plus`` / ``delete_plus`` against the real Book model.

    Runs only in checkframework1's project stage (sets ``RUN_PROJECT_TESTS`` and
    overlays the test app onto ``ourapp/``); self-skips elsewhere (the var is unset and
    ``ourapp/`` is empty). Models are fetched via ``apps.get_model`` so the module
    imports safely when collected in checkframework1 (no top-level ``ourapp`` import).

    Audit-log shape:
    - test_create_logs_created_with_full_new_values, create log: old={}, new=all columns
    - test_update_logs_changed_values, update log old/new reflect the changed field
    - test_noop_update_writes_no_log, no-field-change update → no log row
    - test_delete_purges_history_tombstones, delete purges created/updated
      history; only the empty tombstone survives (row gone)
    - test_value_shapes, int→str, FK→{id,url,name}, null passthrough, no pk leak
    - test_log_model_name_resolution, log.model == log_model_name(); log_as_name overrides
    - test_performed_by_none, actor=None recorded as a null actor

    Optimistic lock (expected_row_version):
    - test_create_rejects_nonzero_row_version, nonzero version on create → Http404, no row
    - test_row_version_increments_per_update, each exact-match update bumps row_version by 1
    - test_update_rejects_stale_row_version, stale AND too-high numbers raise Http404
    - test_skip_row_version_check_sentinel, sentinel bypasses the check, still increments
    """

    Book: ClassVar[type[Any]]
    Author: ClassVar[type[Any]]
    actor: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        ourapp = apps.get_app_config("ourapp")
        cls.Book = ourapp.get_model("Book")
        cls.Author = ourapp.get_model("Author")
        cls.actor = User.objects.create_user(username="actor", is_superuser=True, is_staff=True)

    def setUp(self) -> None:
        super().setUp()
        # A fresh author + book per test, created via save_plus (each emits
        # exactly one 'created' log attributed to the actor; both start at
        # row_version=0).
        self.author = self.Author(name="Ada", bio="", rating="4.50", active=True)
        self.author.save_plus(actor=self.actor, expected_row_version=0)
        self.book = self.Book(
            title="Notes",
            description="",
            pages=200,
            author=self.author,
            reviewer=self.actor,
        )
        self.book.save_plus(actor=self.actor, expected_row_version=0)

    def _logs(self, **filters: object) -> list[BaseModelUpdateLog]:
        qs = BaseModelUpdateLog.objects.filter(
            model=self.Book.log_model_name(), model_pk=self.book.pk
        )
        if filters:
            qs = qs.filter(**filters)
        return list(qs.order_by("performed_at"))

    def test_create_logs_created_with_full_new_values(self) -> None:
        """Create writes one 'created' log: old={}, new has every supported column."""
        created = self._logs(action="created")
        self.assertEqual(len(created), 1)
        log = created[0]
        self.assertEqual(log.old_values, {})
        # Builtins + user fields are all audited columns.
        for key in (
            "public_id",
            "created_by",
            "created_at",
            "last_updated_at",
            "last_updated_by",
            "row_version",
            "title",
            "pages",
            "author",
            "reviewer",
        ):
            self.assertIn(key, log.new_values, key)
        self.assertEqual(log.performed_by, self.actor)

    def test_update_logs_changed_values(self) -> None:
        """Update writes an 'updated' log whose old/new reflect the changed field."""
        self.book.title = "Updated Notes"
        self.book.save_plus(actor=self.actor, expected_row_version=0)

        updated = self._logs(action="updated")
        self.assertEqual(len(updated), 1)
        log = updated[0]
        self.assertEqual(log.old_values["title"], "Notes")
        self.assertEqual(log.new_values["title"], "Updated Notes")
        # row_version bumps every update but never appears in the diff (it
        # would drown out the real change, like last_updated_at).
        self.assertNotIn("row_version", log.old_values)
        self.assertNotIn("row_version", log.new_values)

    def test_noop_update_writes_no_log(self) -> None:
        """An update that changes no data column writes no 'updated' log."""
        # last_updated_at/by + row_version change but are excluded from the
        # diff, so a no-field-change save_plus produces no log row.
        self.book.save_plus(actor=self.actor, expected_row_version=0)
        self.assertEqual(self._logs(action="updated"), [])

    def test_delete_purges_history_tombstones(self) -> None:
        """Delete purges the row's created/updated history; only the tombstone stays.

        Erasure by design — field values die with the row; who/when
        accountability lives forever.
        """
        # Give the row a history first: one created + one updated entry.
        self.book.title = "Updated Notes"
        self.book.save_plus(actor=self.actor, expected_row_version=0)
        pk = self.book.pk
        self.assertEqual(len(self._logs(action="created")), 1)
        self.assertEqual(len(self._logs(action="updated")), 1)

        self.book.delete_plus(actor=self.actor)

        log = BaseModelUpdateLog.objects.get(
            model=self.Book.log_model_name(), model_pk=pk, action="deleted"
        )
        # The tombstone records only who/when/model+pk — no field snapshot.
        self.assertEqual(log.old_values, {})
        self.assertEqual(log.new_values, {})
        # History entries (the field-value-bearing logs) are gone with the
        # row; reconstructing its contents is deliberately impossible.
        self.assertEqual(
            BaseModelUpdateLog.objects.filter(
                model=self.Book.log_model_name(), model_pk=pk
            ).count(),
            1,  # the tombstone alone
        )
        self.assertFalse(self.Book.objects.filter(pk=pk).exists())

    def test_value_shapes(self) -> None:
        """int→str, FK→{id,url,name}, null passthrough; pk never appears."""
        log = self._logs(action="created")[0]
        nv = log.new_values
        # Integer stored as a string (lossless for big ints / decimals).
        self.assertEqual(nv["pages"], "200")
        # FK→BaseModel: linked via get_absolute_url(), pk-free.
        self.assertEqual(nv["author"]["id"], self.author.public_id)
        self.assertEqual(nv["author"]["url"], self.author.get_absolute_url())
        self.assertEqual(nv["author"]["name"], "Ada")
        # FK→User: same shape; User has no get_absolute_url → blank url.
        self.assertEqual(nv["reviewer"]["id"], self.actor.public_id)
        self.assertEqual(nv["reviewer"]["url"], "")
        # Nullable column passes through as None.
        self.assertIsNone(nv["published"])
        # The integer pk is never serialised into the values.
        self.assertNotIn("id", nv)

    def test_log_model_name_resolution(self) -> None:
        """log.model matches Book.log_model_name(); log_as_name overrides it."""
        log = self._logs(action="created")[0]
        self.assertEqual(log.model, self.Book.log_model_name())
        # The override short-circuits the module.ClassName default (no DB needed).
        original = self.Book.log_as_name
        try:
            self.Book.log_as_name = "custom-alias"
            self.assertEqual(self.Book.log_model_name(), "custom-alias")
        finally:
            self.Book.log_as_name = original

    def test_performed_by_none(self) -> None:
        """Creating with actor=None records a null actor (no crash)."""
        book = self.Book(title="Anon", author=self.author)
        book.save_plus(actor=None, expected_row_version=0)
        log = BaseModelUpdateLog.objects.filter(
            model=self.Book.log_model_name(), model_pk=book.pk, action="created"
        ).get()
        self.assertIsNone(log.performed_by)

    def test_create_rejects_nonzero_row_version(self) -> None:
        """Creating with a nonzero row_version raises Http404; nothing is written."""
        book = self.Book(title="Bad", author=self.author)
        with self.assertRaisesMessage(Http404, "requires expected_row_version=0, got 3"):
            book.save_plus(actor=self.actor, expected_row_version=3)
        # The rollback left no row and no log.
        self.assertFalse(self.Book.objects.filter(title="Bad").exists())
        self.assertEqual(
            BaseModelUpdateLog.objects.filter(model=self.Book.log_model_name()).count(),
            1,  # only the setUp book's 'created' log
        )

    def test_row_version_increments_per_update(self) -> None:
        """Each exact-match update bumps the row's row_version by 1."""
        self.assertEqual(self.book.row_version, 0)
        self.book.pages = 201
        self.book.save_plus(actor=self.actor, expected_row_version=0)
        self.assertEqual(self.book.row_version, 1)
        # The value the client must echo next is the one now in the DB.
        fresh = self.Book.objects.get(pk=self.book.pk)
        self.assertEqual(fresh.row_version, 1)
        self.book.pages = 202
        self.book.save_plus(actor=self.actor, expected_row_version=1)
        self.assertEqual(self.Book.objects.get(pk=self.book.pk).row_version, 2)

    def test_update_rejects_stale_row_version(self) -> None:
        """A stale number (row moved on) and a too-high one both raise Http404."""
        self.book.pages = 201
        self.book.save_plus(actor=self.actor, expected_row_version=0)  # row is now at 1
        # Very early: the caller still holds the pre-update view (0).
        self.book.pages = 202
        with self.assertRaisesMessage(Http404, "is at row_version 1, got 0"):
            self.book.save_plus(actor=self.actor, expected_row_version=0)
        # Too high: no state of the row ever had this number.
        with self.assertRaisesMessage(Http404, "is at row_version 1, got 99"):
            self.book.save_plus(actor=self.actor, expected_row_version=99)
        # Nothing was written: pages and row_version unchanged in the DB, and
        # the failed attempts wrote no 'updated' log.
        fresh = self.Book.objects.get(pk=self.book.pk)
        self.assertEqual(fresh.pages, 201)
        self.assertEqual(fresh.row_version, 1)
        self.assertEqual(len(self._logs(action="updated")), 1)

    def test_skip_row_version_check_sentinel(self) -> None:
        """SKIP_ROW_VERSION_CHECK bypasses the match; row_version still increments."""
        self.book.pages = 201
        self.book.save_plus(actor=self.actor, expected_row_version=SKIP_ROW_VERSION_CHECK)
        self.assertEqual(self.Book.objects.get(pk=self.book.pk).row_version, 1)
        # Works regardless of how stale self.book's view is (single-writer
        # flows don't track the number at all).
        self.book.pages = 202
        self.book.save_plus(actor=self.actor, expected_row_version=SKIP_ROW_VERSION_CHECK)
        self.assertEqual(self.Book.objects.get(pk=self.book.pk).row_version, 2)
