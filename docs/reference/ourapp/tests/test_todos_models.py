"""Tests for the todos model (``Todo``)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from ourapp.models import Todo

User = get_user_model()


class TodoModelTests(TestCase):
    """Todo __str__, owner scoping, and toggle.

    - test_str_is_text, __str__ is the text
    - test_active_for_scopes_to_owner, active_for only returns the user's todos
    - test_toggle_flips_completion, toggle() flips completed (caller saves)
    """

    def setUp(self) -> None:
        self.alice = User.objects.create_user(username="alice")
        self.bob = User.objects.create_user(username="bob")
        self.alice_todo = Todo.objects.create(text="Alice's task", owner=self.alice)
        Todo.objects.create(text="Bob's task", owner=self.bob)

    def test_str_is_text(self) -> None:
        "Todo __str__ is the text."
        self.assertEqual(str(self.alice_todo), "Alice's task")

    def test_active_for_scopes_to_owner(self) -> None:
        "active_for only returns the owner's todos."
        self.assertEqual(
            list(Todo.objects.active_for(self.alice)),
            [self.alice_todo],
        )

    def test_toggle_flips_completion(self) -> None:
        "toggle() flips completed; the caller persists it."
        self.assertFalse(self.alice_todo.completed)
        self.alice_todo.toggle()
        self.assertTrue(self.alice_todo.completed)
        self.alice_todo.toggle()
        self.assertFalse(self.alice_todo.completed)
