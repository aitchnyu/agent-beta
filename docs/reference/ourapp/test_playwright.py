"""Example Playwright e2e — copy into ``ourapp/test_playwright.py``.

Per-app e2e subclasses ``BasePlaywrightTestCase`` (which is ``@tag("playwright")``
and provides the live server + browser harness + console-error ``tearDown``).
Import it from ``djangoapp.tests.playwright._base`` — NOT from
``djangoapp.shortcuts`` (re-exporting it there was removed: it would pull the
playwright dependency into production code). ``./run playwrighttest`` runs every
``--tag playwright`` test.

NotesE2e:
- test_seeded_note_renders, an ORM-created note shows on the live /notes page
- test_edit_note_flow, edit a note and see the new title + revision count
"""

from __future__ import annotations

from djangoapp.tests.playwright._base import BasePlaywrightTestCase
from ourapp.models import Note


class NotesE2e(BasePlaywrightTestCase):
    """``/notes`` + edit flow end-to-end (headless firefox)."""

    def setUp(self) -> None:
        super().setUp()
        # The base harness's 1s default is too tight for Inertia reloads; 5s
        # matches the framework e2e suites.
        self.page = self.logged_in_page
        self.page.set_default_timeout(5000)

    def test_seeded_note_renders(self) -> None:
        """A note seeded in the DB renders on the real /notes page."""
        Note.objects.create(title="E2E note", owner=self.user)
        page = self.page
        page.goto(f"{self.live_server_url}/notes", wait_until="networkidle")
        self.assertIn("E2E note", page.inner_text("body"))

    def test_edit_note_flow(self) -> None:
        """Editing a note updates its title and bumps the revision count.

        Seeds via save_with_logs (1 "created" revision), edits the title in the
        browser, and asserts the detail page shows the new title + "Revisions: 2".
        """
        note = Note(title="Original", owner=self.user)
        note.save_with_logs(user=self.user)
        page = self.page
        page.goto(
            f"{self.live_server_url}/notes/{note.public_id}/edit",
            wait_until="networkidle",
        )
        # Accessible locators over CSS/text (steer.md "Playwright locators"):
        # get_by_label needs the input's aria-label (see NoteForm.vue).
        page.get_by_label("Title").fill("Edited title")
        page.get_by_role("button", name="Save note").click()
        # The edit handler visits the detail page on save.
        page.wait_for_url(f"**/notes/{note.public_id}", wait_until="networkidle")
        body = page.inner_text("body")
        self.assertIn("Edited title", body)
        # created + updated = 2 revisions.
        self.assertIn("Revisions: 2", body)
