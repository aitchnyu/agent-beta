"""E2e for the todos page (``/todos``): create + toggle flow."""

from __future__ import annotations

from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class TodosE2e(BasePlaywrightTestCase):
    """``/todos`` create + toggle flow end-to-end (headless chromium).

    - test_create_todo_renders, add a todo via the form and see it on the page
    - test_toggle_todo_completes, clicking toggle marks the todo complete
    """

    def setUp(self) -> None:
        super().setUp()
        # The base harness's 1s default is too tight for Inertia reloads; 5s
        # matches the framework e2e suites.
        self.page.set_default_timeout(5000)

    def test_create_todo_renders(self) -> None:
        "Add a todo via the form and see it on the page."
        page = self.page
        page.goto(f"{self.live_server_url}/todos", wait_until="networkidle")
        page.get_by_label("New todo").fill("E2E todo")
        page.get_by_role("button", name="Add todo").click()
        page.wait_for_selector(".ours-todo-item")
        self.assertIn("E2E todo", page.inner_text("body"))

    def test_toggle_todo_completes(self) -> None:
        "Clicking toggle marks the todo complete."
        page = self.page
        page.goto(f"{self.live_server_url}/todos", wait_until="networkidle")
        page.get_by_label("New todo").fill("Toggle me")
        page.get_by_role("button", name="Add todo").click()
        page.wait_for_selector(".ours-todo-item")
        # The toggle POSTs then reloads the list; wait for the completed class.
        page.get_by_role("button", name="Toggle complete").click()
        page.wait_for_selector(".ours-todo-completed")
        self.assertEqual(page.locator(".ours-todo-completed").count(), 1)
