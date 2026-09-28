"""Tests for the todos views (``GET /todos``, create, toggle)."""

from django.test import Client

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase
from ourapp.models import Todo


class TodosViewTests(BaseTestCase):
    """The /todos page + create/toggle endpoints (pk-free, owner-scoped).

    - test_todos_page_404_anonymous, anon GET /todos is 404 (private)
    - test_todos_page_lists_owner_todos, authed GET /todos renders only the user's todos (pk-free)
    - test_create_todo_returns_public_id, POST /todos/create returns the new todo (pk-free, attributed to owner)
    - test_toggle_todo_flips_completion, POST /todos/<id>/toggle flips completed both ways (pk-free body)
    - test_toggle_foreign_todo_404, toggling another user's todo is 404
    - test_create_anon_404, anon POST /todos/create is 404 (private)
    - test_toggle_anon_404, anon POST /todos/<id>/toggle is 404 (private)
    - test_toggle_stale_row_version_404, a stale row_version is 404
    - test_create_nonzero_row_version_404, a nonzero expected_row_version on create is 404
    """

    def setUp(self) -> None:
        self.alice = User.objects.create_user(username="alice", password="x")
        self.bob = User.objects.create_user(username="bob", password="x")
        self.alice_todo = Todo.objects.create(text="Alice's task", owner=self.alice)
        self.client = Client()
        self.client.force_login(self.alice)

    def _toggle(self, public_id: str, expected_row_version: int):
        # Toggle always sends the version it holds — the optimistic-lock echo.
        return self.client.post(
            f"/todos/{public_id}/toggle",
            data={"expected_row_version": expected_row_version},
            content_type="application/json",
        )

    def test_todos_page_404_anonymous(self) -> None:
        "Anon GET /todos is 404 (the list is private to its owner)."
        anon = Client()
        resp = anon.get("/todos")
        self.assertEqual(resp.status_code, 404)

    def test_todos_page_lists_owner_todos(self) -> None:
        "Authed GET /todos renders only the user's todos (pk-free)."
        Todo.objects.create(text="Bob's task", owner=self.bob)
        props = self.client.get("/todos", HTTP_X_INERTIA="true").json()["props"]["props"]
        todos = props["todos"]
        self.assertEqual({t["public_id"] for t in todos}, {self.alice_todo.public_id})
        for t in todos:
            self.assertNotIn("id", t)  # pk-free: public_id, never the integer pk

    def test_create_todo_returns_public_id(self) -> None:
        "POST /todos/create returns the new todo (pk-free, attributed to owner)."
        resp = self.client.post(
            "/todos/create",
            data={"text": "Buy milk", "expected_row_version": 0},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["public_id"])
        self.assertEqual(body["text"], "Buy milk")
        self.assertFalse(body["completed"])
        self.assertEqual(body["row_version"], 0)
        self.assertEqual(body["owner_public_id"], self.alice.public_id)
        self.assertNotIn("id", body)

    def test_toggle_todo_flips_completion(self) -> None:
        "POST /todos/<id>/toggle flips completed both ways (pk-free body)."
        public_id = self.alice_todo.public_id
        # First toggle: incomplete → complete (a fresh objects.create row is at
        # row_version=0; the response carries the bumped 1).
        resp = self._toggle(public_id, 0)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["completed"])
        self.assertEqual(resp.json()["row_version"], 1)
        self.assertNotIn("id", resp.json())
        # Second toggle: complete → incomplete, echoing expected_row_version=1.
        resp = self._toggle(public_id, 1)
        self.assertFalse(resp.json()["completed"])

    def test_toggle_foreign_todo_404(self) -> None:
        "Toggling another user's todo is 404 (existence hidden)."
        bob_todo = Todo.objects.create(text="Bob's task", owner=self.bob)
        resp = self._toggle(bob_todo.public_id, 0)
        self.assertEqual(resp.status_code, 404)

    def test_create_anon_404(self) -> None:
        "Anon POST /todos/create is 404 (the endpoints are private to the owner)."
        resp = Client().post(
            "/todos/create",
            data={"text": "x", "expected_row_version": 0},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_toggle_anon_404(self) -> None:
        "Anon POST /todos/<id>/toggle is 404 (the endpoints are private to the owner)."
        resp = Client().post(
            f"/todos/{self.alice_todo.public_id}/toggle",
            data={"expected_row_version": 0},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_toggle_stale_row_version_404(self) -> None:
        "A stale row_version is 404 — the row moved on without the client."
        public_id = self.alice_todo.public_id
        resp = self._toggle(public_id, 0)
        self.assertEqual(resp.status_code, 200)
        # The client missed the update above and still holds 0: stale → 404
        # (save_plus raises Http404 itself), and nothing changed (the
        # failed save rolled back).
        resp = self._toggle(public_id, 0)
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Todo.objects.get(pk=self.alice_todo.pk).completed)
        # The same fate meets a number the row never had (too high).
        resp = self._toggle(public_id, 42)
        self.assertEqual(resp.status_code, 404)
        # The current number still works after the stale attempts.
        resp = self._toggle(public_id, 1)
        self.assertEqual(resp.status_code, 200)

