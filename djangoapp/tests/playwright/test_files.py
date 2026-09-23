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
    """Basic E2E for the superuser ``/files`` browser (headless chromium).

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
    - test_markdown_renders_with_image, a linked image resolves to /files/raw and renders
    - test_markdown_outline_renders_and_expands, the heading outline shows and its
      >300px cap expands via the toggle
    - test_no_mermaid_requests_without_diagrams, a diagram-free page fetches no
      mermaid chunk (the lazy-bundle tripwire)
    - test_markdown_hash_link_scrolls, an outline link scrolls its heading into view
    - test_markdown_links_to_other_files, relative links resolve to /files/<rel>;
      external and pure-hash links pass through
    - test_markdown_mermaid_fence_renders, a ```mermaid fence renders an SVG
    - test_markdown_heading_ids_dedupe, ids dedupe over taken ids (Foo/Foo 2/Foo,
      Section 1 vs the anonymous fallback)
    - test_markdown_mermaid_error_fallback, an invalid fence shows raw source
      in .rich-diagram-error (15s waits — the lazy mermaid chunk is slow on VMs)
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
        page.wait_for_selector('[data-files-state="rendered"]')
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
        page.wait_for_selector('[data-files-state="rendered"]')
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
        page.wait_for_selector('[data-files-state="rendered"]')
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

    def _goto_sample_md(self) -> None:
        """Open the markdown fixture and wait for the async preview to render."""
        self.page.goto(self._files("main/djangoapp/tests/filefixtures/sample.md"))
        self.page.wait_for_selector('[data-files-state="rendered"]')

    def test_markdown_outline_renders_and_expands(self) -> None:
        """The heading outline shows at the top and expands past its 300px cap.

        sample.md has 25+ headings, so the collapsed list is taller than the
        300px cap: the toggle must appear, start collapsed (capped class), and
        remove the cap on click.
        """
        page = self.page
        self._goto_sample_md()
        outline = page.locator("[data-outline]")
        outline.wait_for(state="visible")
        # Outline entries mirror the page's headings.
        links = outline.locator("a")
        self.assertGreater(links.count(), 20)
        self.assertEqual(
            outline.get_by_role("link", name="Section one").get_attribute("href"),
            "#section-one",
        )
        # The outline precedes the rendered markdown.
        outline_box = outline.bounding_box()
        markdown_box = page.locator(".files-markdown").bounding_box()
        assert outline_box is not None
        assert markdown_box is not None
        self.assertLess(outline_box["y"], markdown_box["y"])
        # Over the 300px cap → toggle visible, collapsed first, expands on click.
        toggle = page.locator("[data-outline-toggle]")
        toggle.wait_for(state="visible")
        listing = page.locator(".markdown-outline-list")
        self.assertIn("markdown-outline-collapsed", listing.get_attribute("class") or "")
        self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
        toggle.click()
        self.assertEqual(toggle.get_attribute("aria-expanded"), "true")
        self.assertNotIn("markdown-outline-collapsed", listing.get_attribute("class") or "")

    def test_markdown_hash_link_scrolls(self) -> None:
        """Clicking an outline link scrolls its heading into view (hash nav)."""
        page = self.page
        self._goto_sample_md()
        page.locator("[data-outline]").get_by_role("link", name="Heading 20").click()
        self.assertIn("#heading-20", page.url)
        heading = page.locator(".files-markdown h2#heading-20")
        heading.wait_for(state="attached")
        # Scrolled into view: the native anchor jump lands asynchronously on
        # slower machines (the VM), so poll the heading's box until it sits
        # inside the viewport. page.wait_for_timeout is a documented
        # exception here: anchor scrolling exposes no selector/state to wait
        # on, and wait_for_function is banned outright.
        viewport = page.viewport_size
        assert viewport is not None
        for _ in range(50):
            box = heading.bounding_box()
            if box and 0 <= box["y"] < viewport["height"]:
                break
            page.wait_for_timeout(100)
        else:
            self.fail("heading-20 never scrolled into the viewport")

    def test_markdown_links_to_other_files(self) -> None:
        """Relative links resolve against the file's dir → /files/<rel>.

        External and pure-hash hrefs pass through untouched; clicking the
        inter-file link navigates to the other file's page.
        """
        page = self.page
        self._goto_sample_md()
        rendered = page.locator(".files-markdown")
        self.assertEqual(
            rendered.get_by_role("link", name="another file").get_attribute("href"),
            "/files/main/djangoapp/tests/filefixtures/other.md",
        )
        self.assertEqual(
            rendered.get_by_role("link", name="subdir link").get_attribute("href"),
            "/files/main/djangoapp/tests/filefixtures/sub/other.md",
        )
        # Leading-/ resolves against the file's worktree root (main/), not
        # the browse root.
        self.assertEqual(
            rendered.get_by_role("link", name="root-anchored link").get_attribute("href"),
            "/files/main/djangoapp/tests/filefixtures/other.md",
        )
        # Dot segments stay in the produced URL verbatim — the backend's
        # resolve-and-confine (PathWrapper) is the boundary for what arrives.
        self.assertEqual(
            rendered.get_by_role("link", name="dot-segment link").get_attribute("href"),
            "/files/main/djangoapp/tests/filefixtures/sub/../other.md",
        )
        # Climbing hrefs are still only ever /files/-prefixed paths.
        self.assertEqual(
            rendered.get_by_role("link", name="workroot-climbing link").get_attribute("href"),
            "/files/main/djangoapp/tests/filefixtures/../../../other.md",
        )
        self.assertEqual(
            rendered.get_by_role("link", name="escape link").get_attribute("href"),
            "/files/main/djangoapp/tests/filefixtures/../../../../../users/list",
        )
        self.assertEqual(
            rendered.get_by_role("link", name="external site").get_attribute("href"),
            "https://example.com",
        )
        self.assertEqual(
            rendered.get_by_role("link", name="hash link").get_attribute("href"),
            "#section-two",
        )
        # The rewritten link navigates to the other file's viewer page (full
        # load — v-html anchors aren't Inertia links); wait for the async
        # markdown render before reading content (slow VM exposed the race).
        rendered.get_by_role("link", name="another file").click()
        page.wait_for_url("**/filefixtures/other.md")
        page.wait_for_selector('[data-files-state="rendered"]')
        self.assertIn("Other file", page.locator(".files-markdown").inner_text())

    def test_no_mermaid_requests_without_diagrams(self) -> None:
        """A page without diagrams downloads no mermaid chunk.

        Mermaid is one lazy bundle (vite.config.js) whose only entry point is
        the dynamic import on first diagram render — the entry must never
        statically import it (that once made every page fetch 3+ MB). A
        chunk-graph regression shows up here as mermaid requests on this
        mermaid-free page, so this is the tripwire for the bundle staying
        lazy. Resource entries are read after the render completes — a
        diagram-free page never triggers the import, so there is nothing to
        wait for.
        """
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/other.md"))
        page.wait_for_selector('[data-files-state="rendered"]')
        mermaid_resources = page.evaluate(
            "performance.getEntriesByType('resource')"
            ".map(e => e.name).filter(n => n.includes('/mermaid-'))"
        )
        self.assertEqual(mermaid_resources, [])

    def test_markdown_mermaid_fence_renders(self) -> None:
        """A ```mermaid fenced block renders as an SVG diagram, not a code block."""
        page = self.page
        self._goto_sample_md()
        svg = page.locator(".files-markdown .rich-diagram svg")
        # Documented exception (the only timeout override in the suite): the
        # lazy mermaid chunk (~900 KB gzipped) + parse can exceed the 2s
        # default on the test VM.
        svg.wait_for(state="visible", timeout=15000)
        self.assertEqual(page.locator(".files-markdown .rich-diagram-error").count(), 0)
        # The fence is no longer a code block (the <pre> was swapped out).
        self.assertEqual(page.locator(".files-markdown pre > code.language-mermaid").count(), 0)

    def test_markdown_heading_ids_dedupe(self) -> None:
        """Heading ids dedupe over ASSIGNED ids, not per-base counts.

        dedupe.md's "Foo", "Foo 2" (slugs to foo-2), "Foo" must yield foo,
        foo-2, foo-3 — a per-base counter would re-emit foo-2 for the second
        "Foo". The literal "Section 1" heading must not collide with the
        section-N fallback either: the symbol-only heading's fallback base
        section-1 bumps to section-1-2, same as any other taken id.
        """
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/dedupe.md"))
        page.wait_for_selector('[data-files-state="rendered"]')
        rendered = page.locator(".files-markdown")
        self.assertEqual(rendered.locator("h2").count(), 5)
        self.assertEqual(rendered.locator("h2#foo").count(), 1)
        self.assertEqual(rendered.locator("h2#foo-2").count(), 1)
        self.assertEqual(rendered.locator("h2#foo-3").count(), 1)
        self.assertEqual(rendered.locator("h2#section-1").count(), 1)
        self.assertEqual(rendered.locator("h2#section-1-2").count(), 1)

    def test_markdown_mermaid_error_fallback(self) -> None:
        """An invalid mermaid fence shows the raw source in the error style."""
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/dedupe.md"))
        page.wait_for_selector('[data-files-state="rendered"]')
        error = page.locator(".files-markdown .rich-diagram-error")
        # Same mermaid chunk-load exception as the fence test above.
        error.wait_for(state="visible", timeout=15000)
        self.assertIn("this is not valid mermaid", error.inner_text())
