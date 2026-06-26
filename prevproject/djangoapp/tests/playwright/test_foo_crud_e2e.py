"""Playwright E2E for the FooView CRUD pages (/allcolumns)."""

from djangoapp.models.app import AllColumns
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase


class FooCrudE2eTestCase(BasePlaywrightTestCase):
    """E2E for /allcolumns; verifies list/create/update/details pages.

    - test_list_renders: /allcolumns renders the FooList page with row links and no console errors
    - test_create: /create fills a field, submits, and lands on the new row's details
    - test_update: /update edits a field and lands on details with the change persisted
    - test_details: /id/<public_id> renders the FooDetails page with column values
    """

    def test_list_renders(self) -> None:
        """/allcolumns renders the FooList page with row links."""
        row = AllColumns.objects.create(char_field="hello", text_field="world")
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/allcolumns", wait_until="domcontentloaded")
        page.wait_for_selector(".list-group-item a")
        body = page.text_content("body") or ""
        # Row link text is str(row) == "AllColumns(<public_id>)".
        self.assertIn("AllColumns", body)
        self.assertIn(row.public_id, body)
        self.assertEqual(
            self.console_errors,
            [],
            f"unexpected console errors: {self.console_errors}",
        )

    def test_create(self) -> None:
        """/create fills a field, submits, and lands on the new row's details."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/allcolumns/create", wait_until="domcontentloaded")
        page.wait_for_selector("#integer_field")
        page.fill("#integer_field", "42")
        page.click("button[type='submit']")
        page.wait_for_selector(".foo-details")  # FooDetails rendered after the SPA visit
        rows = list(AllColumns.objects.all())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].integer_field, 42)

    def test_update(self) -> None:
        """/update edits integer_field and lands on details with the change persisted."""
        row = AllColumns.objects.create(char_field="x", integer_field=7)
        page = self.logged_in_page
        page.goto(
            f"{self.live_server_url}/allcolumns/update/{row.public_id}",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector("#integer_field")
        page.fill("#integer_field", "99")
        page.click("button[type='submit']")
        page.wait_for_selector(".foo-details")
        row.refresh_from_db()
        self.assertEqual(row.integer_field, 99)

    def test_details(self) -> None:
        """/id/<public_id> renders the FooDetails page with column values."""
        row = AllColumns.objects.create(char_field="abc", text_field="def")
        page = self.logged_in_page
        page.goto(
            f"{self.live_server_url}/allcolumns/id/{row.public_id}", wait_until="domcontentloaded"
        )
        page.wait_for_selector(".foo-details")
        body = page.text_content("body") or ""
        self.assertIn("abc", body)
        self.assertIn("def", body)
