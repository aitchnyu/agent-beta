from __future__ import annotations

from djangoapp.models import User
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase

# Stable files under apps/ (tracked) used as browse/preview targets.
_DIR = "apps"
_TEXT_FILE = "apps/.gitignore"
_ENTRY_DIR = "TriviaFacts"


class FilesBrowserE2e(BasePlaywrightTestCase):
    """Basic E2E for the superuser ``/files`` browser (headless firefox).

    Re-auths the shared page as a superuser (the base harness logs in a plain
    user; ``/files`` is superuser-only) and drives the real repo tree
    (``apps/``, ``apps/.gitignore``). ``tearDown`` fails the test on any browser
    console error. Uses Python assert methods; ``networkidle`` navigation (and
    targeted ``wait_for``) ensure Inertia has hydrated before asserting.

    - test_browse_lists_entries_and_breadcrumb, entries + root/apps breadcrumb
    - test_clicking_directory_entry_navigates, an entry link SPA-navigates into the dir
    - test_text_file_preview, a text file's content renders (escaped)
    - test_text_preview_is_html_escaped, file markup is escaped text, not live elements
    - test_humanized_time_toggles_to_absolute, clicking the time swaps relative → absolute
    """

    def setUp(self) -> None:
        super().setUp()
        # The base class logged in a plain user; /files is superuser-only (404
        # otherwise), so re-auth as a superuser on the shared page.
        self.admin = User.objects.create_user(
            username="filesadmin", password="x", is_staff=True, is_superuser=True
        )
        self.page = self.logged_in_page
        self.page.set_default_timeout(5000)
        self.page.goto(
            f"{self.live_server_url}/login-for-test/{self.admin.pk}",
            wait_until="networkidle",
        )

    def _files(self, rel: str = "") -> str:
        return f"{self.live_server_url}/files/{rel}"

    def test_browse_lists_entries_and_breadcrumb(self) -> None:
        """The apps/ listing renders its entries and a root/apps breadcrumb."""
        page = self.page
        page.goto(self._files(_DIR), wait_until="networkidle")
        body = page.inner_text("body")
        self.assertIn(_ENTRY_DIR, body)
        self.assertIn(".gitignore", body)
        crumb = page.locator(".files-breadcrumb")
        self.assertTrue(crumb.get_by_role("link", name="root").is_visible())
        self.assertTrue(crumb.get_by_role("link", name=_DIR).is_visible())

    def test_clicking_directory_entry_navigates(self) -> None:
        """Clicking a directory entry navigates into it (Inertia SPA nav)."""
        page = self.page
        page.goto(self._files(_DIR), wait_until="networkidle")
        page.get_by_role("link", name=_ENTRY_DIR).click()
        page.wait_for_url(lambda url: f"/files/{_DIR}/{_ENTRY_DIR}" in url)
        self.assertIn(f"/files/{_DIR}/{_ENTRY_DIR}", page.url)

    def test_text_file_preview(self) -> None:
        """A text file renders its (escaped) content in the preview."""
        page = self.page
        page.goto(self._files(_TEXT_FILE), wait_until="networkidle")
        text = page.locator(".files-text").text_content() or ""
        self.assertIn("node_modules", text)
        self.assertIn("__pycache__", text)

    def test_text_preview_is_html_escaped(self) -> None:
        """File markup previews as escaped text, never as live elements.

        Guards against a ``v-html`` regression: previews a tracked source file
        with markup (``<template>``/``<script>``/``<div>``) and checks Vue's
        interpolation escaped it (``&lt;template&gt;``) with no parsed elements.
        """
        page = self.page
        page.goto(
            self._files("frontend/src/pages/FileBrowser.vue"),
            wait_until="networkidle",
        )
        preview = page.locator(".files-text")
        preview.wait_for(state="visible")
        inner = preview.evaluate("el => el.innerHTML")
        # Interpolation escapes markup → "<template>" renders as "&lt;template&gt;".
        self.assertIn("&lt;template&gt;", inner)
        # A v-html regression would parse the file's tags into live elements.
        self.assertEqual(page.locator(".files-text script").count(), 0)
        self.assertEqual(page.locator(".files-text template").count(), 0)

    def test_humanized_time_toggles_to_absolute(self) -> None:
        """Clicking the time swaps the relative label for the absolute one."""
        page = self.page
        page.goto(self._files(_DIR), wait_until="networkidle")
        t = page.locator(".humanized-time").first
        relative = t.text_content()
        t.click()
        # The deemphasized time small only exists in the absolute view.
        t.locator("small.humanized-time-time").wait_for(state="visible")
        self.assertNotEqual(relative, t.text_content())
