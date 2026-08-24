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
    """

    def setUp(self) -> None:
        self.alice = User.objects.create_user(username="alice", password="x")
        self.bob = User.objects.create_user(username="bob", password="x")
        self.alice_todo = Todo.objects.create(text="Alice's task", owner=self.alice)
        self.client = Client()
        self.client.force_login(self.alice)

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
            data={"text": "Buy milk"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["public_id"])
        self.assertEqual(body["text"], "Buy milk")
        self.assertFalse(body["completed"])
        self.assertEqual(body["owner_public_id"], self.alice.public_id)
        self.assertNotIn("id", body)

    def test_toggle_todo_flips_completion(self) -> None:
        "POST /todos/<id>/toggle flips completed both ways (pk-free body)."
        public_id = self.alice_todo.public_id
        # First toggle: incomplete → complete.
        resp = self.client.post(f"/todos/{public_id}/toggle")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["completed"])
        self.assertNotIn("id", resp.json())
        # Second toggle: complete → incomplete.
        resp = self.client.post(f"/todos/{public_id}/toggle")
        self.assertFalse(resp.json()["completed"])

    def test_toggle_foreign_todo_404(self) -> None:
        "Toggling another user's todo is 404 (existence hidden)."
        bob_todo = Todo.objects.create(text="Bob's task", owner=self.bob)
        resp = self.client.post(f"/todos/{bob_todo.public_id}/toggle")
        self.assertEqual(resp.status_code, 404)

    def test_create_anon_404(self) -> None:
        "Anon POST /todos/create is 404 (the endpoints are private to the owner)."
        resp = Client().post(
            "/todos/create",
            data={"text": "x"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_toggle_anon_404(self) -> None:
        "Anon POST /todos/<id>/toggle is 404 (the endpoints are private to the owner)."
        resp = Client().post(f"/todos/{self.alice_todo.public_id}/toggle")
        self.assertEqual(resp.status_code, 404)
