"""Example tests — copy into ``ourapp/tests.py`` or ``djangoapp/tests/``.

Regular Django tests. Seed inside the test; the test DB rolls back per test, so
each test starts clean. Assert state and endpoint return values here.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from ourapp.models import Note

User = get_user_model()


class NoteViewTests(TestCase):
    """Notes list + create.

    - test_notes_page_lists_notes, GET /notes renders (200)
    - test_create_note_returns_public_id, POST /notes/create returns the new id
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="alice", password="x")
        self.client = Client()
        self.client.force_login(self.user)

    def test_notes_page_lists_notes(self) -> None:
        Note.objects.create(title="Buy milk", owner=self.user)
        resp = self.client.get("/notes")
        self.assertEqual(resp.status_code, 200)

    def test_create_note_returns_public_id(self) -> None:
        resp = self.client.post(
            "/notes/create",
            data={"title": "Hi", "body": "world"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("public_id", body)
        self.assertEqual(body["title"], "Hi")
