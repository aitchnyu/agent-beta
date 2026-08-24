from __future__ import annotations

from typing import Any, ClassVar

from django.apps import apps

from djangoapp.models import BaseModelUpdateLog, User
from djangoapp.tests._base import BaseTestCase
from djangoapp.tests.views import skip_unless_env


@skip_unless_env("RUN_PROJECT_TESTS")
class BaseModelUpdateLogTests(BaseTestCase):
    """``BaseModel.save_with_logs`` / ``delete_with_logs`` against the real Book model.

    Runs only under ``checkproject`` (sets ``RUN_PROJECT_TESTS`` and overlays the
    test app onto ``ourapp/``); self-skips in ``checkframework1`` (the var is unset and
    ``ourapp/`` is empty). Models are fetched via ``apps.get_model`` so the module
    imports safely when collected in checkframework1 (no top-level ``ourapp`` import).

    - test_create_logs_created_with_full_new_values, create log: old={}, new=all columns
    - test_update_logs_changed_values, update log old/new reflect the changed field
    - test_noop_update_writes_no_log, no-field-change update → no log row
    - test_delete_logs_deleted_no_snapshot, delete log: old/new both {} (no snapshot)
    - test_value_shapes, int→str, FK→{id,url,name}, null passthrough, no pk leak
    - test_log_model_name_resolution, log.model == log_model_name(); log_as_name overrides
    - test_performed_by_none, actor=None recorded as a null actor
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
        # A fresh author + book per test, created via save_with_logs (each emits
        # exactly one 'created' log attributed to the actor).
        self.author = self.Author(name="Ada", bio="", rating="4.50", active=True)
        self.author.save_with_logs(actor=self.actor)
        self.book = self.Book(
            title="Notes",
            description="",
            pages=200,
            author=self.author,
            reviewer=self.actor,
        )
        self.book.save_with_logs(actor=self.actor)

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
        self.book.save_with_logs(actor=self.actor)

        updated = self._logs(action="updated")
        self.assertEqual(len(updated), 1)
        log = updated[0]
        self.assertEqual(log.old_values["title"], "Notes")
        self.assertEqual(log.new_values["title"], "Updated Notes")

    def test_noop_update_writes_no_log(self) -> None:
        """An update that changes no data column writes no 'updated' log."""
        # last_updated_at/by are re-stamped but excluded from the diff, so a
        # no-field-change save_with_logs produces no log row.
        self.book.save_with_logs(actor=self.actor)
        self.assertEqual(self._logs(action="updated"), [])

    def test_delete_logs_deleted_no_snapshot(self) -> None:
        """Delete writes a 'deleted' log with empty old/new values; the log outlives the row."""
        pk = self.book.pk
        self.book.delete_with_logs(actor=self.actor)

        log = BaseModelUpdateLog.objects.get(
            model=self.Book.log_model_name(), model_pk=pk, action="deleted"
        )
        # A delete records only that the row was removed — no field snapshot.
        self.assertEqual(log.old_values, {})
        self.assertEqual(log.new_values, {})
        # The row is gone, but the log (keyed by model + integer pk) survives.
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
        book.save_with_logs(actor=None)
        log = BaseModelUpdateLog.objects.filter(
            model=self.Book.log_model_name(), model_pk=book.pk, action="created"
        ).get()
        self.assertIsNone(log.performed_by)
