"""Screenshot captures for the reference app's screens.

The docs embed four captures — home, facts, todos, downloads — and they
must match reality: regenerate them per the Screenshots section of
docs/reference/README.md whenever a page changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from djangoapp.models import User
from djangoapp.tests.playwright.test_screenshots import BaseScreenshotTestCase
from ourapp.models import Download, Fact, FactOfTheDay, Topic


class ReferenceScreenshots(BaseScreenshotTestCase):
    """The reference app's four doc captures — one test per shot.

    - test_home, home.png — the landing page with today's Fact of the Day
    - test_facts, facts.png — the facts list grouped by topic
    - test_todos, todos.png — the todo list with one open and one completed row
    - test_downloads, downloads.png — the file shelf with one seeded file
    """

    # Captures land next to the docs that embed them — in a scratch run, the
    # scratch's own docs/reference subtree, which the README's recipe copies
    # back verbatim (main's docs/screenshots is never touched).
    screenshot_dir: ClassVar[Path] = (
        Path(str(settings.BASE_DIR))
        / "docs"
        / "reference"
        / "ourapp"
        / "docs"
        / "screenshots"
    )

    def setUp(self) -> None:
        super().setUp()
        self.page.set_default_timeout(5000)

    def test_home(self) -> None:
        """home.png — a visitor opens the landing page and reads today's pick."""
        topic = Topic.objects.create(name="general", slug="general")
        Fact.objects.create(
            text="The reference app is a worked example you can copy.", topic=topic
        )
        FactOfTheDay.choose_for_today()
        self.page.goto(f"{self.live_server_url}/", wait_until="networkidle")
        self.page.get_by_text("worked example you can copy").first.wait_for()
        self.capture_below_navbar("home")

    def test_facts(self) -> None:
        """facts.png — a visitor opens /facts and reads facts grouped by topic."""
        topic = Topic.objects.create(name="cars", slug="cars")
        Fact.objects.create(text="E2E fact about cars", topic=topic)
        self.page.goto(f"{self.live_server_url}/facts", wait_until="networkidle")
        self.page.get_by_text("E2E fact about cars").first.wait_for()
        self.capture_below_navbar("facts")

    def test_todos(self) -> None:
        """todos.png — a user opens /todos, adds two todos, completes the first."""
        self.page.goto(f"{self.live_server_url}/todos", wait_until="networkidle")
        self.page.get_by_label("New todo").fill("Read the reference docs")
        self.page.get_by_role("button", name="Add todo").click()
        self.page.wait_for_selector(".ours-todo-item")
        self.page.get_by_label("New todo").fill("Ship something small")
        self.page.get_by_role("button", name="Add todo").click()
        self.page.wait_for_selector(".ours-todo-item")
        # Complete the first so the shot shows both states.
        self.page.locator(".ours-todo-item").first.get_by_role(
            "button", name="Toggle complete"
        ).click()
        self.page.locator(".ours-todo-completed").wait_for()
        self.capture_below_navbar("todos")

    def test_downloads(self) -> None:
        """downloads.png — a superuser opens /downloads; one seeded file."""
        admin = User.objects.create_user(
            username="shotsadmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(admin)
        Download(file=SimpleUploadedFile("field-notes.txt", b"reference notes")).save_plus(
            actor=admin, expected_row_version=0
        )
        self.page.goto(f"{self.live_server_url}/downloads", wait_until="networkidle")
        self.page.get_by_text("field-notes.txt").first.wait_for()
        self.capture_below_navbar("downloads")
