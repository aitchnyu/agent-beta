"""Example tests — copy into ``ourapp/tests.py`` or ``djangoapp/tests/``.

Regular Django tests. Seed inside the test; the test DB rolls back per test, so
each test starts clean. Assert state and endpoint return values here.

NoteViewTests:
- test_notes_page_lists_notes, GET /notes renders (200)
- test_create_note_returns_public_id, POST /notes/create returns the new id
- test_note_detail_shows_revision_count, GET /notes/<id> carries the count
- test_update_note_changes_title, PUT updates the title
- test_note_detail_404_for_missing, GET /notes/<bad-id> is 404
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from ourapp.models import Note

User = get_user_model()


class NoteViewTests(TestCase):
    """Notes list + create + detail + update (pk-free, audit-logged)."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="alice", password="x")
        self.client = Client()
        self.client.force_login(self.user)

    def _create_via_api(self, title: str = "Hi", body: str = "world") -> str:
        """POST /notes/create (audit-logged) → return the new public_id."""
        resp = self.client.post(
            "/notes/create",
            data={"title": title, "body": body},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["public_id"]

    def test_notes_page_lists_notes(self) -> None:
        # A seeded note (ORM, unaudited) still lists fine.
        Note.objects.create(title="Buy milk", owner=self.user)
        resp = self.client.get("/notes")
        self.assertEqual(resp.status_code, 200)

    def test_create_note_returns_public_id(self) -> None:
        public_id = self._create_via_api(title="Hi", body="world")
        # Returned id is the public UUID, never the integer pk.
        self.assertTrue(public_id)

    def test_note_detail_shows_revision_count(self) -> None:
        public_id = self._create_via_api()
        # X-Inertia makes InertiaResponse return the page JSON directly.
        resp = self.client.get(f"/notes/{public_id}", HTTP_X_INERTIA="true")
        self.assertEqual(resp.status_code, 200)
        # The revision count is asserted here (the detail page) — the one place
        # it's exposed. One revision so far (the "created" log).
        self.assertEqual(resp.json()["props"]["props"]["revisions"], 1)

    def test_update_note_changes_title(self) -> None:
        public_id = self._create_via_api(title="Old")
        resp = self.client.put(
            f"/notes/{public_id}",
            data={"title": "New", "body": "x"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "New")

    def test_note_detail_404_for_missing(self) -> None:
        resp = self.client.get("/notes/does-not-exist")
        self.assertEqual(resp.status_code, 404)
