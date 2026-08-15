from __future__ import annotations

from djangoapp.models import User
from djangoapp.tests.playwright._base import BasePlaywrightTestCase

# Stable files under main/ourapp/ (tracked) used as browse/preview targets.
# main/-prefixed because the browse root is the project parent (BASE_DIR.parent).
# The user app splits models into a package, so point at the package's __init__
# (which documents BaseModel + the models-management UI) for the preview tests.
_DIR = "main/ourapp"
_TEXT_FILE = "main/ourapp/models/__init__.py"
_ENTRY_DIR = "migrations"
_LEAF = "ourapp"  # breadcrumb leaf segment (the current dir)


class FilesBrowserE2e(BasePlaywrightTestCase):
    """Basic E2E for the superuser ``/files`` browser (headless firefox).

    ``/files`` is superuser-only, so ``setUp`` re-auths the shared page as a
    superuser via ``login_as`` (cookie replacement — the harness's plain-user
    session is simply overwritten) and drives the real repo tree
    (``ourapp/`` and its ``models/`` package). ``tearDown`` fails the test on
    any browser console error.

    - test_browse_lists_entries_and_breadcrumb, entries + root/ourapp breadcrumb
    - test_clicking_directory_entry_navigates, an entry link SPA-navigates into the dir
    - test_text_file_preview, a code file's content renders (escaped)
    - test_text_preview_is_html_escaped, file markup is escaped text, not live elements
    - test_humanized_time_toggles_to_absolute, clicking the time swaps relative → absolute
    """

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(
            username="filesadmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(self.admin)

    def _files(self, rel: str = "") -> str:
        return f"{self.live_server_url}/files/{rel}"

    def test_browse_lists_entries_and_breadcrumb(self) -> None:
        """The ourapp/ listing renders its entries and a root/ourapp breadcrumb."""
        page = self.page
        page.goto(self._files(_DIR))
        body = page.inner_text("body")
        self.assertIn(_ENTRY_DIR, body)
        self.assertIn("urls.py", body)
        crumb = page.locator(".files-breadcrumb")
        self.assertTrue(crumb.get_by_role("link", name="root").is_visible())
        self.assertTrue(crumb.get_by_role("link", name=_LEAF).is_visible())

    def test_clicking_directory_entry_navigates(self) -> None:
        """Clicking a directory entry navigates into it (Inertia SPA nav)."""
        page = self.page
        page.goto(self._files(_DIR))
        page.get_by_role("link", name=_ENTRY_DIR).click()
        page.wait_for_url(lambda url: f"/files/{_DIR}/{_ENTRY_DIR}" in url)
        self.assertIn(f"/files/{_DIR}/{_ENTRY_DIR}", page.url)

    def test_text_file_preview(self) -> None:
        """A code file renders its (escaped) content in the preview."""
        page = self.page
        # The preview <pre> renders visible-but-empty — content arrives only
        # after mount — so wait on the page root's data-files-state flipping to
        # "rendered" (component state), not on content magic strings, the
        # element (already visible), or network quiescence (~0.7s slower).
        page.goto(self._files(_TEXT_FILE))
        page.wait_for_selector('.files-page[data-files-state="rendered"]')
        preview = page.locator(".files-code")
        text = preview.text_content() or ""
        self.assertIn("BaseModel", text)
        self.assertIn("models-management", text)

    def test_text_preview_is_html_escaped(self) -> None:
        """File markup previews as escaped text, never as live elements.

        Guards against a ``v-html`` regression: previews a tracked ``.vue`` source
        file (→ kind=code, highlighted) whose markup (``<template>``/``<script>``)
        appears as escaped text — never parsed into live DOM elements.
        """
        page = self.page
        page.goto(self._files("main/frontend/src/pages/FileBrowser.vue"))
        # Same as test_text_file_preview: wait on component state, not content.
        page.wait_for_selector('.files-page[data-files-state="rendered"]')
        preview = page.locator(".files-code")
        # The file's markup is shown as text (highlight.js escapes it), not parsed.
        self.assertIn("<template>", preview.text_content() or "")
        # A v-html regression would parse the file's tags into live elements.
        self.assertEqual(page.locator(".files-code script").count(), 0)
        self.assertEqual(page.locator(".files-code template").count(), 0)
        self.assertEqual(page.locator(".files-code div").count(), 0)

    def test_humanized_time_toggles_to_absolute(self) -> None:
        """Clicking the time swaps the relative label for the absolute one."""
        page = self.page
        page.goto(self._files(_DIR))
        t = page.locator(".humanized-time").first
        relative = t.text_content()
        t.click()
        # The deemphasized time small only exists in the absolute view.
        t.locator("small.humanized-time-time").wait_for(state="visible")
        self.assertNotEqual(relative, t.text_content())

    def test_markdown_renders_with_image(self) -> None:
        """Markdown shows a raw-source link, then rendered HTML, then raw source.

        Asserts the link precedes the rendered prose + rewritten
        image, which precede the raw block. The raw block shows the markdown
        source (not the rendered HTML). Clicking the link scrolls to it (hash nav).
        """
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/sample.md"))
        # Both the rendered view and the raw block fill asynchronously — wait
        # on the component state flip, not their (already-visible) elements.
        page.wait_for_selector('.files-page[data-files-state="rendered"]')
        rendered = page.locator(".files-markdown")
        self.assertIn("Sample markdown", rendered.inner_text())
        img = rendered.locator("img")
        img.wait_for(state="visible")
        self.assertEqual(
            img.get_attribute("src"),
            "/files/raw/main/djangoapp/tests/filefixtures/diagram.svg",
        )

        # A deemphasized link targets the raw block.
        link = page.locator(".files-raw-link a")
        self.assertEqual(link.get_attribute("href"), "#files-raw-source")

        # The raw block shows the markdown source, not the rendered HTML: the
        # image is the literal `![…](…)` syntax, not an <img> element.
        raw = page.locator("#files-raw-source")
        raw_text = raw.text_content() or ""
        self.assertIn("# Sample markdown", raw_text)
        self.assertIn("![A blue square](diagram.svg)", raw_text)
        self.assertEqual(raw.locator("img").count(), 0)

        # Clicking the link scrolls to the raw block (native hash navigation).
        link.click()
        self.assertIn("#files-raw-source", page.url)
