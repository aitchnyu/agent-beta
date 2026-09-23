from __future__ import annotations

from playwright.sync_api import expect

from djangoapp.models import User
from djangoapp.tests._git_fixtures import GitRepoMixin
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class GitViewerE2e(GitRepoMixin, BasePlaywrightTestCase):
    """E2E for the superuser ``/git`` viewer (headless chromium) against real repos.

    No function mocks: the class mixes in ``GitRepoMixin`` (the same real repo
    fixture the views suite uses) — ``main`` (3 commits + uncommitted changes) +
    a sibling ``scratch`` (baseline commit + uncommitted changes), mirroring
    the real ``parent/main`` + ``parent/scratch`` layout, and patches
    ``git_data._REPO_ROOT`` to ``main`` (the in-process live server sees the
    patch). ``/git`` is superuser-only, so ``setUp`` re-auths the shared page
    as a superuser via ``login_as`` (cookie replacement).
    ``tearDown`` fails on any browser console error.

    - test_uncommitted_renders — /git/uncommitted/ lists both worktrees' files
      (main then scratch) as folder trees with new/mod status words + colors;
      each file links to its worktree diff and to the file url
    - test_file_tree_folds — folder rows fold their subtree away and back,
      independently per folder
    - test_commit_list_renders — /git/commits shows the 3 subjects + a commit count
    - test_diff_highlighted — an uncommitted diff renders .d2h-ins/.d2h-del rows
      (diff2html, syntax-highlighted)
    - test_diff_split_and_unified_by_viewport — side-by-side wide, line-by-line narrow
    - test_diff_opens_via_click — a commit file-diff link clicked (Inertia swap) renders
    - test_commit_navigation — the commits → files → diff link chain works
    - test_repo_subnav_highlights_section — the Code sub-nav (Uncommitted /
      Commits / Files) marks the URL's section with aria-current across git
      and files pages
    - test_non_superuser_404 — an anonymous viewer of /git gets 404
    """

    def setUp(self) -> None:
        super().setUp()  # auth only — the repo fixture is class-scoped
        self.admin = User.objects.create_user(
            username="gitadmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(self.admin)

    def test_uncommitted_renders(self) -> None:
        """``/git/uncommitted/`` lists both worktrees' files as a folder tree."""
        page = self.page
        page.goto(f"{self.live_server_url}/git/uncommitted/")
        page.get_by_role("link", name="app.py").wait_for(state="visible")
        page.get_by_role("link", name="scratch_only.py").wait_for(state="visible")

        # -- all files present, grouped under folder rows (bare filenames) --
        for name in (
            "app.py",
            "notes.md",
            "idea.md",
            "x.md",
            "scratch_only.py",
            "scratch_notes.md",
        ):
            expect(page.locator("body")).to_contain_text(name)

        # -- folder rows: main's Docs/ + TodoApp/ (+ nested TodoApp/Docs/),
        #    then scratch's TodoApp/ — selected by full-dir-path attribute,
        #    scoped to each worktree's section container --
        main = page.locator('[data-tree-section="main"]')
        scratch = page.locator('[data-tree-section="scratch"]')
        expect(page.locator("[data-tree-folder]")).to_have_count(4)
        # to_contain_text (not a raw text_content assert): the caret/name/
        # count spans sit on one button and innerText splits them by layout —
        # Playwright normalizes the whitespace, so they match again.
        # Attribute values are full dir paths — the DISPLAY text is the bare
        # segment, so the nested TodoApp/Docs/ shows "Docs/ (1)" like its root
        # sibling; the attribute is what disambiguates them.
        expect(main.locator('[data-tree-toggle="Docs"]')).to_contain_text("Docs/ (1)")
        expect(main.locator('[data-tree-toggle="TodoApp"]')).to_contain_text("TodoApp/ (3)")
        expect(main.locator('[data-tree-toggle="TodoApp/Docs"]')).to_contain_text("Docs/ (1)")
        expect(scratch.locator('[data-tree-toggle="TodoApp"]')).to_contain_text("TodoApp/ (2)")
        # app.py's link lives INSIDE main's TodoApp folder li (nesting).
        expect(
            main.locator(
                '[data-tree-folder="TodoApp"] a[href="/git/uncommitted/main/TodoApp/app.py"]'
            )
        ).to_have_count(1)

        # -- file (diff) links keep the worktree in the path --
        expect(page.get_by_role("link", name="app.py")).to_have_attribute(
            "href", "/git/uncommitted/main/TodoApp/app.py"
        )
        expect(page.get_by_role("link", name="scratch_only.py")).to_have_attribute(
            "href", "/git/uncommitted/scratch/TodoApp/scratch_only.py"
        )

        # -- secondary links point at the file url (browse root = repo parent) --
        expect(page.locator('a[href="/files/main/TodoApp/app.py"]')).to_have_count(1)
        expect(page.locator('a[href="/files/scratch/TodoApp/scratch_only.py"]')).to_have_count(1)

        # -- status words new/mod with their color classes (4 untracked → new,
        #    2 modified → mod across the two worktrees) --
        words = page.locator(".git-status").all_inner_texts()
        self.assertIn("new", words)
        self.assertIn("mod", words)
        expect(page.locator(".git-status.text-success")).to_have_count(4)
        expect(page.locator(".git-status.text-warning")).to_have_count(2)

    def test_file_tree_folds(self) -> None:
        """Folder rows fold their subtrees away and back, independently.

        Two regressions pinned: (1) fold state once lived in a single ref
        per component instance, so folding one folder folded every sibling
        with it; (2) state must also scope per LEVEL — the fixture's main
        worktree nests ``TodoApp/Docs/`` inside ``TodoApp/`` while ``Docs/``
        also exists as a sibling at the root, so a name-keyed GLOBAL set
        would conflate the two and fold the nested one too.
        """
        page = self.page
        page.goto(f"{self.live_server_url}/git/uncommitted/")
        page.wait_for_selector("[data-tree-folder]")
        main = page.locator('[data-tree-section="main"]')

        # -- toggles by full dir path (unique within the section) --
        docs_toggle = main.locator('[data-tree-toggle="Docs"]')
        todoapp_toggle = main.locator('[data-tree-toggle="TodoApp"]')
        nested_toggle = main.locator('[data-tree-toggle="TodoApp/Docs"]')
        idea_link = page.locator('a[href="/git/uncommitted/main/Docs/idea.md"]')
        nested_link = page.locator('a[href="/git/uncommitted/main/TodoApp/Docs/x.md"]')
        app_link = page.locator('a[href="/git/uncommitted/main/TodoApp/app.py"]')

        # -- a11y wiring: expanded by default, toggle names its subtree --
        expect(docs_toggle).to_have_attribute("aria-expanded", "true")
        controls = docs_toggle.get_attribute("aria-controls")
        assert controls is not None
        expect(page.locator(f"#{controls}")).to_have_count(1)

        # -- fold Docs/ --
        docs_toggle.click()
        expect(docs_toggle).to_have_attribute("aria-expanded", "false")
        expect(idea_link).to_be_hidden()
        # SIBLING folder unaffected — the bug folded every sibling together.
        expect(todoapp_toggle).to_have_attribute("aria-expanded", "true")
        expect(app_link).to_be_visible()
        # NESTED same-named folder unaffected — per-LEVEL scoping.
        expect(nested_toggle).to_have_attribute("aria-expanded", "true")
        expect(nested_link).to_be_visible()

        # -- unfold Docs/ --
        docs_toggle.click()
        expect(docs_toggle).to_have_attribute("aria-expanded", "true")
        expect(idea_link).to_be_visible()

    def test_commit_list_renders(self) -> None:
        """``/git/commits`` shows the 3 subjects (newest first) + a commit count."""
        page = self.page
        page.goto(f"{self.live_server_url}/git/commits")
        page.get_by_role("link", name="Add create endpoint").wait_for(state="visible")
        expect(page.locator("body")).to_contain_text("Add delete endpoint")
        expect(page.locator("body")).to_contain_text("Add create endpoint")
        expect(page.locator("body")).to_contain_text("Initial TodoApp")
        expect(page.locator("body")).to_contain_text("3 commits")

    def test_diff_highlighted(self) -> None:
        """An uncommitted diff renders as add/del colored rows (diff2html).

        diff2html colours inserted rows ``.d2h-ins`` and deleted rows
        ``.d2h-del`` — asserting both proves the lazy chunk rendered (not raw
        text or a stuck Loading note).
        """
        page = self.page
        page.goto(f"{self.live_server_url}/git/uncommitted/main/TodoApp/app.py")
        # wait_for_selector, not wait_for_function (per INSTRUCTIONS.md): the
        # row classes exist once the async render lands, so the selector proves
        # the view rendered before the asserts below.
        page.wait_for_selector("[data-split-diff] .d2h-ins")
        diff = page.locator("[data-split-diff]")
        expect(diff.locator(".d2h-ins").first).to_be_visible()
        expect(diff.locator(".d2h-del").first).to_be_visible()
        expect(diff).to_contain_text("TodoApp/app.py")
        expect(diff).to_contain_text("final")

    def test_diff_split_and_unified_by_viewport(self) -> None:
        """The diff shows side-by-side on wide viewports, line-by-line on narrow.

        Both formats render up front (one diff2html container each); a CSS
        media query (768px) picks the visible one — no JS resize handling, so
        the assert is simply which container shows.
        """
        page = self.page
        default_viewport = page.viewport_size or {"width": 1280, "height": 720}
        page.goto(f"{self.live_server_url}/git/uncommitted/main/TodoApp/app.py")
        page.wait_for_selector("[data-split-diff] .d2h-ins")
        # Wide (default 1280x720): the side-by-side container shows (with
        # diff2html's two file panes inside), line-by-line hides.
        side = page.locator("[data-sd-side]")
        expect(side).to_be_visible()
        # diff2html's side-by-side: one wrapper, two side panes.
        expect(side.locator(".d2h-file-side-diff")).to_have_count(2)
        expect(page.locator("[data-sd-unified]")).to_be_hidden()
        # Narrow: the line-by-line container shows, side-by-side hides.
        page.set_viewport_size({"width": 375, "height": 800})
        expect(page.locator("[data-sd-unified]")).to_be_visible()
        expect(side).to_be_hidden()
        page.set_viewport_size(default_viewport)

    def test_diff_opens_via_click(self) -> None:
        """A file-diff link opened by a click (Inertia client-side swap) renders.

        The other diff tests use ``goto`` (a hard load), which never exercises
        the swap — this is the only coverage of the client-side navigation
        path, where module/graph regressions land (e.g. an entry URL mismatch
        double-booting the app and rolling the swap back). Asserts the URL
        advances (no rollback), the diff renders, and tearDown's
        console-error check guards render-time crashes.
        """
        # 2s budget: this test's client-side swap is the one navigation that
        # flaked at the 1s default under VM load.
        self.page.set_default_timeout(2000)
        page = self.page
        # Land on the commit's file list (loads the Inertia app + main.js).
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}")
        page.get_by_role("link", name="endpoints.py").wait_for(state="visible")
        # Click the file link — a client-side Inertia swap to GitDiff.
        page.get_by_role("link", name="endpoints.py").click()
        # The URL advances (no rollback), and the diff renders (insert rows +
        # the ADDED file tag diff2html derives from "new file mode").
        page.wait_for_url(f"**/git/commits/{self.short_b}/TodoApp/endpoints.py")
        page.wait_for_selector("[data-split-diff] .d2h-ins")
        diff = page.locator("[data-split-diff]")
        expect(diff.locator(".d2h-ins").first).to_be_visible()
        expect(diff).to_contain_text("ADDED")

    def test_commit_navigation(self) -> None:
        """The commits → files → diff link chain works end-to-end.

        Each step navigates via ``goto`` and verifies the expected links exist,
        then waits for the diff to render.
        """
        page = self.page
        # Commit list has a link to each commit.
        page.goto(f"{self.live_server_url}/git/commits")
        page.get_by_role("link", name="Add create endpoint").wait_for(state="visible")
        expect(page.locator("body")).to_contain_text("Add delete endpoint")
        # The commit page links to each changed file.
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}")
        page.get_by_role("link", name="endpoints.py").wait_for(state="visible")
        expect(page.locator("body")).to_contain_text("Add create endpoint")
        # The file's diff renders (insert rows + the ADDED tag for a new file).
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}/TodoApp/endpoints.py")
        page.wait_for_selector("[data-split-diff] .d2h-ins")
        diff = page.locator("[data-split-diff]")
        expect(diff).to_contain_text("ADDED")
        expect(diff).to_contain_text("TodoApp/endpoints.py")

    def test_repo_subnav_highlights_section(self) -> None:
        """The Code sub-nav links all three sections and marks the active one.

        Every code-viewer page (git + files) renders the same sub-nav; the
        active tab derives from the URL prefix (uncommitted pages →
        Uncommitted, commit pages → Commits, files pages → Files) and is the
        one link carrying ``aria-current="page"``.
        """
        page = self.page
        subnav = page.get_by_role("navigation", name="Code views")

        def assert_active(label: str) -> None:
            links = subnav.get_by_role("link")
            expect(links).to_have_count(3)
            # One name→aria-current map: exactly `label` carries "page"
            current = {
                (link.text_content() or "").strip(): link.get_attribute("aria-current")
                for link in links.all()
            }
            self.assertEqual(
                current,
                {
                    name: ("page" if name == label else None)
                    for name in ("Uncommitted", "Commits", "Files")
                },
            )

        # The merged navbar entry lands on the default section (Uncommitted).
        page.goto(f"{self.live_server_url}/git/uncommitted/")
        page.get_by_role("link", name="app.py").wait_for(state="visible")
        expect(page.get_by_role("link", name="Code", exact=True)).to_have_attribute(
            "href", "/git/uncommitted/"
        )
        assert_active("Uncommitted")

        # A commit's file-diff page still reads as the Commits section.
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}/TodoApp/endpoints.py")
        page.wait_for_selector("[data-split-diff] .d2h-ins")
        assert_active("Commits")

        # The files browser shares the sub-nav, with Files current.
        page.goto(f"{self.live_server_url}/files/main/ourapp")
        page.get_by_role("link", name="urls.py").wait_for(state="visible")
        assert_active("Files")

    def test_non_superuser_404(self) -> None:
        """An anonymous viewer of the git viewer gets a 404 (the gate holds over HTTP)."""
        with self.anon_page() as page:
            response = page.goto(f"{self.live_server_url}/git/uncommitted/")
            assert response is not None
            self.assertEqual(response.status, 404)
        self.pop_expected_console_error(
            r"Failed to load resource: the server responded with a status of 404"
        )
