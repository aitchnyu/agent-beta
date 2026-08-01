"""Example Playwright e2e — copy into ``ourapp/test_playwright.py``.

Per-app e2e subclasses ``BasePlaywrightTestCase`` (which is ``@tag("playwright")``
and provides the live server + browser harness + console-error ``tearDown``).
Import it from ``djangoapp.tests.playwright._base`` — NOT from
``djangoapp.shortcuts`` (re-exporting it there was removed: it would pull the
playwright dependency into production code). ``./run playwrighttest`` runs every
``--tag playwright`` test.
"""

from __future__ import annotations

from djangoapp.tests.playwright._base import BasePlaywrightTestCase
from ourapp.models import Note


class NotesE2e(BasePlaywrightTestCase):
    """``/notes`` renders end-to-end (headless firefox).

    - test_seeded_note_renders, an ORM-created note shows on the live page
    """

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
