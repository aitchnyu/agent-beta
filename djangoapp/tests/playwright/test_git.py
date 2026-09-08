from __future__ import annotations

from djangoapp.models import User
from djangoapp.tests._git_fixtures import GitRepoMixin
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class GitViewerE2e(GitRepoMixin, BasePlaywrightTestCase):
    """E2E for the superuser ``/git`` viewer (headless firefox) against real repos.

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
        body = page.inner_text("body")
        for name in (
            "app.py",
            "notes.md",
            "idea.md",
            "x.md",
            "scratch_only.py",
            "scratch_notes.md",
        ):
            self.assertIn(name, body)

        # -- folder rows: main's Docs/ + TodoApp/ (+ nested TodoApp/Docs/),
        #    then scratch's TodoApp/ — selected by full-dir-path attribute,
        #    scoped to each worktree's section container --
        main = page.locator('[data-tree-section="main"]')
        scratch = page.locator('[data-tree-section="scratch"]')
        self.assertEqual(page.locator("[data-tree-folder]").count(), 4)
        # text_content (not inner_text): the caret/name/count spans sit on
        # one button; inner_text would split them by layout. Attribute values
        # are full dir paths — the DISPLAY text is the bare segment, so the
        # nested TodoApp/Docs/ shows "Docs/ (1)" like its root sibling; the
        # attribute is what disambiguates them.
        self.assertIn("Docs/ (1)", main.locator('[data-tree-toggle="Docs"]').text_content() or "")
        self.assertIn(
            "TodoApp/ (3)",
            main.locator('[data-tree-toggle="TodoApp"]').text_content() or "",
        )
        self.assertIn(
            "Docs/ (1)",
            main.locator('[data-tree-toggle="TodoApp/Docs"]').text_content() or "",
        )
        self.assertIn(
            "TodoApp/ (2)",
            scratch.locator('[data-tree-toggle="TodoApp"]').text_content() or "",
        )
        # app.py's link lives INSIDE main's TodoApp folder li (nesting).
        self.assertEqual(
            main.locator(
                '[data-tree-folder="TodoApp"] a[href="/git/uncommitted/main/TodoApp/app.py"]'
            ).count(),
            1,
        )

        # -- file (diff) links keep the worktree in the path --
        self.assertEqual(
            page.get_by_role("link", name="app.py").get_attribute("href"),
            "/git/uncommitted/main/TodoApp/app.py",
        )
        self.assertEqual(
            page.get_by_role("link", name="scratch_only.py").get_attribute("href"),
            "/git/uncommitted/scratch/TodoApp/scratch_only.py",
        )

        # -- secondary links point at the file url (browse root = repo parent) --
        self.assertEqual(
            page.locator('a[href="/files/main/TodoApp/app.py"]').count(),
            1,
        )
        self.assertEqual(
            page.locator('a[href="/files/scratch/TodoApp/scratch_only.py"]').count(),
            1,
        )

        # -- status words new/mod with their color classes (4 untracked → new,
        #    2 modified → mod across the two worktrees) --
        words = page.locator(".git-status").all_inner_texts()
        self.assertIn("new", words)
        self.assertIn("mod", words)
        self.assertEqual(page.locator(".git-status.text-success").count(), 4)
        self.assertEqual(page.locator(".git-status.text-warning").count(), 2)

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
        self.assertEqual(docs_toggle.get_attribute("aria-expanded"), "true")
        controls = docs_toggle.get_attribute("aria-controls")
        self.assertTrue(controls and page.locator(f"#{controls}").count() == 1)

        # -- fold Docs/ --
        docs_toggle.click()
        self.assertEqual(docs_toggle.get_attribute("aria-expanded"), "false")
        self.assertFalse(idea_link.is_visible())
        # SIBLING folder unaffected — the bug folded every sibling together.
        self.assertEqual(todoapp_toggle.get_attribute("aria-expanded"), "true")
        self.assertTrue(app_link.is_visible())
        # NESTED same-named folder unaffected — per-LEVEL scoping.
        self.assertEqual(nested_toggle.get_attribute("aria-expanded"), "true")
        self.assertTrue(nested_link.is_visible())

        # -- unfold Docs/ --
        docs_toggle.click()
        self.assertEqual(docs_toggle.get_attribute("aria-expanded"), "true")
        self.assertTrue(idea_link.is_visible())

    def test_commit_list_renders(self) -> None:
        """``/git/commits`` shows the 3 subjects (newest first) + a commit count."""
        page = self.page
        page.goto(f"{self.live_server_url}/git/commits")
        page.get_by_role("link", name=self.short_b).wait_for(state="visible")
        body = page.inner_text("body")
        self.assertIn("Add delete endpoint", body)
        self.assertIn("Add create endpoint", body)
        self.assertIn("Initial TodoApp", body)
        self.assertIn("3 commits", body)

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
        self.assertGreater(diff.locator(".d2h-ins").count(), 0)
        self.assertGreater(diff.locator(".d2h-del").count(), 0)
        self.assertIn("TodoApp/app.py", diff.text_content() or "")
        self.assertIn("final", diff.text_content() or "")

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
        self.assertTrue(side.is_visible())
        # diff2html's side-by-side: one wrapper, two side panes.
        self.assertEqual(side.locator(".d2h-file-side-diff").count(), 2)
        self.assertFalse(page.locator("[data-sd-unified]").is_visible())
        # Narrow: the line-by-line container shows, side-by-side hides.
        page.set_viewport_size({"width": 375, "height": 800})
        self.assertTrue(page.locator("[data-sd-unified]").is_visible())
        self.assertFalse(side.is_visible())
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
        self.assertGreater(diff.locator(".d2h-ins").count(), 0)
        self.assertIn("ADDED", diff.text_content() or "")

    def test_commit_navigation(self) -> None:
        """The commits → files → diff link chain works end-to-end.

        Each step navigates via ``goto`` and verifies the expected links exist,
        then waits for the diff to render.
        """
        page = self.page
        # Commit list has a link to each commit.
        page.goto(f"{self.live_server_url}/git/commits")
        page.get_by_role("link", name=self.short_b).wait_for(state="visible")
        self.assertIn("Add create endpoint", page.inner_text("body"))
        # The commit page links to each changed file.
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}")
        page.get_by_role("link", name="endpoints.py").wait_for(state="visible")
        self.assertIn("Add create endpoint", page.inner_text("body"))
        # The file's diff renders (insert rows + the ADDED tag for a new file).
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}/TodoApp/endpoints.py")
        page.wait_for_selector("[data-split-diff] .d2h-ins")
        diff_text = page.locator("[data-split-diff]").text_content() or ""
        self.assertIn("ADDED", diff_text)
        self.assertIn("TodoApp/endpoints.py", diff_text)

    def test_non_superuser_404(self) -> None:
        """An anonymous viewer of the git viewer gets a 404 (the gate holds over HTTP)."""
        with self.anon_page() as page:
            response = page.goto(f"{self.live_server_url}/git/uncommitted/")
            assert response is not None
            self.assertEqual(response.status, 404)
