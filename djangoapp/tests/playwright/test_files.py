from __future__ import annotations

import re

from playwright.sync_api import expect

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
    - test_humanized_time_toggles_to_absolute, file listings start absolute;
      clicking swaps to the relative label
    - test_markdown_renders_with_image, a linked image resolves to /files/raw and renders
    - test_markdown_outline_renders_and_expands, the heading outline shows and its
      >600px cap expands via the toggle
    - test_no_d2_requests_without_diagrams, a diagram-free page fetches no
      d2 chunk (the lazy-bundle tripwire)
    - test_markdown_hash_link_scrolls, an outline link scrolls its heading into view
    - test_markdown_links_to_other_files, relative links resolve to /files/<rel>;
      external and pure-hash links pass through
    - test_markdown_d2_fence_renders, a ```d2 fence renders an SVG
    - test_markdown_heading_ids_dedupe, ids dedupe over taken ids (Foo/Foo 2/Foo,
      Section 1 vs the anonymous fallback)
    - test_markdown_d2_error_fallback, an invalid fence shows raw source
      in .rich-diagram-error (30s waits — the lazy d2 WASM chunk is slow on VMs)
    - test_markdown_source_toggle, Source mode shows the markdown source
      alone (client state — URL unchanged); switching back works
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
        expect(page.locator("body")).to_contain_text(_ENTRY_DIR)
        expect(page.locator("body")).to_contain_text("urls.py")
        crumb = page.locator(".files-breadcrumb")
        expect(crumb.get_by_role("link", name="root")).to_be_visible()
        expect(crumb.get_by_role("link", name=_LEAF)).to_be_visible()

    def test_clicking_directory_entry_navigates(self) -> None:
        """Clicking a directory entry navigates into it (Inertia SPA nav)."""
        page = self.page
        page.goto(self._files(_DIR))
        page.get_by_role("link", name=_ENTRY_DIR).click()
        page.wait_for_url(lambda url: f"/files/{_DIR}/{_ENTRY_DIR}" in url)
        expect(page).to_have_url(re.compile(re.escape(f"/files/{_DIR}/{_ENTRY_DIR}")))

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
        expect(preview).to_contain_text("BaseModel")
        expect(preview).to_contain_text("models-management")

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
        expect(preview).to_contain_text("<template>")
        # A v-html regression would parse the file's tags into live elements.
        expect(page.locator(".files-code script")).to_have_count(0)
        expect(page.locator(".files-code template")).to_have_count(0)
        expect(page.locator(".files-code div")).to_have_count(0)

    def test_humanized_time_toggles_to_absolute(self) -> None:
        """File listings start absolute; clicking swaps to the relative label."""
        page = self.page
        page.goto(self._files(_DIR))
        timestamp = page.locator(".humanized-time").first
        # The value span is unconditional — assert the state within it.
        value = timestamp.locator(".humanized-time-value")
        # Absolute view: the clock rides along in a deemphasized small.
        expect(value.locator("small.humanized-time-time")).to_be_visible()
        absolute_label = value.text_content() or ""
        timestamp.click()
        # Relative view: plain text, no smalls.
        expect(value).not_to_have_text(absolute_label)
        expect(value.locator("small")).to_have_count(0)

    def test_markdown_renders_with_image(self) -> None:
        """Markdown renders prose + the rewritten image, behind the toolbar.

        The Rendered/Source toggle sits above the rendered HTML; rendered
        mode is the default.
        """
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/sample.md"))
        # Both the rendered view and the raw fill asynchronously — wait
        # on the component state flip, not their (already-visible) elements.
        page.wait_for_selector('[data-files-state="rendered"]')
        rendered = page.locator(".files-markdown")
        expect(rendered).to_contain_text("Sample markdown")
        img = rendered.locator("img")
        expect(img).to_be_visible()
        expect(img).to_have_attribute(
            "src", "/files/raw/main/djangoapp/tests/filefixtures/diagram.svg"
        )
        # Rendered mode is the default: outline + rendered HTML, no source.
        expect(page.locator(".markdown-outline")).to_be_visible()
        expect(page.locator(".files-raw-source")).to_have_count(0)

    def test_markdown_source_toggle(self) -> None:
        """Source mode shows the markdown source alone; switching back works.

        The toggle is client state — the URL never changes. Source mode
        shows the literal `![…](…)` syntax (not an <img> element) and hides
        the outline and rendered HTML.
        """
        page = self.page
        self._goto_sample_md()
        page.locator(".files-mode-button", has_text="Source").click()
        expect(page).to_have_url(re.compile(r"/files/main/.*sample\.md$"))
        raw = page.locator(".files-raw-source")
        expect(raw).to_be_visible()
        expect(raw).to_contain_text("# Sample markdown")
        expect(raw).to_contain_text("![A blue square](diagram.svg)")
        expect(raw.locator("img")).to_have_count(0)

        # Rendered-mode furniture is gone — no rendered HTML, no outline.
        expect(page.locator(".files-markdown")).to_have_count(0)
        expect(page.locator(".markdown-outline")).to_have_count(0)

        # And back: rendered HTML returns, the source block goes.
        page.locator(".files-mode-button", has_text="Rendered").click()
        expect(page.locator(".files-markdown")).to_contain_text("Sample markdown")
        expect(page.locator(".files-raw-source")).to_have_count(0)

    def _goto_sample_md(self) -> None:
        """Open the markdown fixture and wait for the async preview to render."""
        self.page.goto(self._files("main/djangoapp/tests/filefixtures/sample.md"))
        self.page.wait_for_selector('[data-files-state="rendered"]')

    def test_markdown_outline_renders_and_expands(self) -> None:
        """The heading outline shows at the top and expands past its 600px cap.

        sample.md has 40 headings, so the collapsed list is taller than the
        600px cap: the toggle must appear, start collapsed (capped class), and
        remove the cap on click.
        """
        page = self.page
        self._goto_sample_md()
        outline = page.locator("[data-outline]")
        outline.wait_for(state="visible")
        # Outline entries mirror the page's headings.
        links = outline.locator("a")
        self.assertGreater(links.count(), 20)
        expect(outline.get_by_role("link", name="Section one")).to_have_attribute(
            "href", "#section-one"
        )
        # The outline precedes the rendered markdown.
        outline_box = outline.bounding_box()
        markdown_box = page.locator(".files-markdown").bounding_box()
        assert outline_box is not None
        assert markdown_box is not None
        self.assertLess(outline_box["y"], markdown_box["y"])
        # Over the 600px cap → toggle visible, collapsed first, expands on click.
        toggle = page.locator("[data-outline-toggle]")
        toggle.wait_for(state="visible")
        listing = page.locator(".markdown-outline-list")
        expect(listing).to_have_class(re.compile(r"markdown-outline-collapsed"))
        expect(toggle).to_have_attribute("aria-expanded", "false")
        toggle.click()
        expect(toggle).to_have_attribute("aria-expanded", "true")
        expect(listing).not_to_have_class(re.compile(r"markdown-outline-collapsed"))

    def test_markdown_hash_link_scrolls(self) -> None:
        """Clicking an outline link scrolls its heading into view (hash nav)."""
        page = self.page
        self._goto_sample_md()
        page.locator("[data-outline]").get_by_role("link", name="Heading 20").click()
        expect(page).to_have_url(re.compile(re.escape("#heading-20")))
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
        expect(rendered.get_by_role("link", name="another file")).to_have_attribute(
            "href", "/files/main/djangoapp/tests/filefixtures/other.md"
        )
        expect(rendered.get_by_role("link", name="subdir link")).to_have_attribute(
            "href", "/files/main/djangoapp/tests/filefixtures/sub/other.md"
        )
        # Leading-/ resolves against the file's worktree root (main/), not
        # the browse root.
        expect(rendered.get_by_role("link", name="root-anchored link")).to_have_attribute(
            "href", "/files/main/djangoapp/tests/filefixtures/other.md"
        )
        # Dot segments stay in the produced URL verbatim — the backend's
        # resolve-and-confine (PathWrapper) is the boundary for what arrives.
        expect(rendered.get_by_role("link", name="dot-segment link")).to_have_attribute(
            "href", "/files/main/djangoapp/tests/filefixtures/sub/../other.md"
        )
        # Climbing hrefs are still only ever /files/-prefixed paths.
        expect(rendered.get_by_role("link", name="workroot-climbing link")).to_have_attribute(
            "href", "/files/main/djangoapp/tests/filefixtures/../../../other.md"
        )
        expect(rendered.get_by_role("link", name="escape link")).to_have_attribute(
            "href", "/files/main/djangoapp/tests/filefixtures/../../../../../users/list"
        )
        expect(rendered.get_by_role("link", name="external site")).to_have_attribute(
            "href", "https://example.com"
        )
        expect(rendered.get_by_role("link", name="hash link")).to_have_attribute(
            "href", "#section-two"
        )
        # The rewritten link navigates to the other file's viewer page (full
        # load — v-html anchors aren't Inertia links); wait for the async
        # markdown render before reading content (slow VM exposed the race).
        rendered.get_by_role("link", name="another file").click()
        page.wait_for_url("**/filefixtures/other.md")
        page.wait_for_selector('[data-files-state="rendered"]')
        expect(page.locator(".files-markdown")).to_contain_text("Other file")

    def test_no_d2_requests_without_diagrams(self) -> None:
        """A page without diagrams downloads no d2 chunk.

        - d2 is one lazy bundle (vite.config.js); its only entry point is
          the dynamic import on first diagram render
        - the entry must never statically import it — that would make
          every page fetch ~11.5 MB of WASM
        - a chunk-graph regression shows up as d2 requests on this
          diagram-free page: the tripwire for the bundle staying lazy
        - resource entries are read after the render completes — a
          diagram-free page never triggers the import, so there is
          nothing to wait for
        """
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/other.md"))
        page.wait_for_selector('[data-files-state="rendered"]')
        d2_resources = page.evaluate(
            "performance.getEntriesByType('resource')"
            ".map(e => e.name).filter(n => n.includes('/d2-'))"
        )
        self.assertEqual(d2_resources, [])

    def test_markdown_d2_fence_renders(self) -> None:
        """A ```d2 fenced block renders as an SVG diagram, not a code block."""
        page = self.page
        self._goto_sample_md()
        # d2 output nests an inner svg — "> svg" pins the outer wrapper
        # (the zoom target) so strict-mode sees exactly one element.
        svg = page.locator(".files-markdown .rich-diagram > svg")
        # Documented exception (the only timeout override in the suite): the
        # lazy d2 chunk (WASM, ~8.6 MB gzipped) + compile can exceed the 2s
        # default on the test VM.
        svg.wait_for(state="visible", timeout=30000)
        expect(page.locator(".files-markdown .rich-diagram-error")).to_have_count(0)
        # The fence is no longer a code block (the <pre> was swapped out).
        expect(page.locator(".files-markdown pre > code.language-d2")).to_have_count(0)
        # The files viewer wires zoom controls onto every rendered diagram.
        expect(page.locator(".files-markdown .rich-diagram-zoom")).to_have_count(3)
        # zoomIn is exponential (scale x e^step, step 0.3 -> x1.3499) so equal
        # clicks compound equally in log space; reset returns to exactly 1.
        page.locator(".files-markdown .rich-diagram-zoom-in").click()
        expect(svg).to_have_attribute("style", re.compile(r"scale\(1\.34"))
        page.locator(".files-markdown .rich-diagram-zoom-reset").click()
        expect(svg).to_have_attribute("style", re.compile(r"scale\(1\)"))

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
        expect(rendered.locator("h2")).to_have_count(5)
        expect(rendered.locator("h2#foo")).to_have_count(1)
        expect(rendered.locator("h2#foo-2")).to_have_count(1)
        expect(rendered.locator("h2#foo-3")).to_have_count(1)
        expect(rendered.locator("h2#section-1")).to_have_count(1)
        expect(rendered.locator("h2#section-1-2")).to_have_count(1)

    def test_markdown_d2_error_fallback(self) -> None:
        """An invalid d2 fence shows the raw source in the error style."""
        page = self.page
        page.goto(self._files("main/djangoapp/tests/filefixtures/dedupe.md"))
        page.wait_for_selector('[data-files-state="rendered"]')
        error = page.locator(".files-markdown .rich-diagram-error")
        # Same d2 chunk-load exception as the fence test above.
        error.wait_for(state="visible", timeout=30000)
        expect(error).to_contain_text("a -> -> b")
