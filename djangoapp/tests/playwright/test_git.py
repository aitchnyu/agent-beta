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
      (main then scratch) with U/M status letters; each file links to its worktree diff
    - test_commit_list_renders — /git/commits shows 3 subjects + a commit count
    - test_diff_highlighted — an uncommitted diff renders .hljs-add/del spans
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
        """``/git/uncommitted/`` lists both worktrees' files with U/M status letters."""
        page = self.page
        page.goto(f"{self.live_server_url}/git/uncommitted/")
        page.get_by_role("link", name="TodoApp/app.py").wait_for(state="visible")
        page.get_by_role("link", name="TodoApp/scratch_only.py").wait_for(state="visible")
        body = page.inner_text("body")
        # main then scratch, shown together on one page.
        self.assertIn("TodoApp/app.py", body)
        self.assertIn("TodoApp/notes.md", body)
        self.assertIn("TodoApp/scratch_only.py", body)
        self.assertIn("TodoApp/scratch_notes.md", body)
        # File (diff) links keep the worktree in the path.
        self.assertEqual(
            page.get_by_role("link", name="TodoApp/app.py").get_attribute("href"),
            "/git/uncommitted/main/TodoApp/app.py",
        )
        self.assertEqual(
            page.get_by_role("link", name="TodoApp/scratch_only.py").get_attribute("href"),
            "/git/uncommitted/scratch/TodoApp/scratch_only.py",
        )
        # Status letters U/M, and untracked rows greyed (2 untracked files).
        letters = page.locator(".git-letter").all_inner_texts()
        self.assertIn("M", letters)
        self.assertIn("U", letters)
        self.assertEqual(page.locator("li.text-muted").count(), 2)

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
        """An uncommitted diff renders with the hljs diff grammar's spans.

        The `diff` grammar colours `+` lines as ``.hljs-addition`` and `-`
        lines as ``.hljs-deletion`` — asserting both proves the lazy
        ``filePreview`` chunk highlighted the diff (not raw text).
        """
        page = self.page
        page.goto(f"{self.live_server_url}/git/uncommitted/main/TodoApp/app.py")
        # wait_for_selector, not wait_for_function (per INSTRUCTIONS.md): the diff
        # grammar emits .hljs-addition/.hljs-deletion once the highlighter runs, so
        # the addition selector proves the chunk rendered before the asserts below.
        page.wait_for_selector(".code-diff .hljs-addition")
        diff = page.locator(".code-diff")
        self.assertGreater(diff.locator(".hljs-addition").count(), 0)
        self.assertGreater(diff.locator(".hljs-deletion").count(), 0)
        self.assertIn("TodoApp/app.py", diff.text_content() or "")
        self.assertIn("final", diff.text_content() or "")

    def test_diff_opens_via_click(self) -> None:
        """A file-diff link opened by a click (Inertia client-side swap) renders.

        Context: opening a commit's file-diff page broke twice, both times only
        on the client-side navigation path (a link click), never on a hard load:

        1. GitDiff highlighted its diff via a dynamic ``import()`` inside
           ``onMounted``. Firing a dynamic import during an Inertia v2 swap made
           Inertia silently roll the navigation back — the URL reverted to the
           commit page and the diff never showed (no console error, so it was
           invisible to the goto-based tests).
        2. Making GitDiff a lazy page chunk then caused ``page.props`` to be
           transiently undefined during Inertia's async component resolution, so
           Layout's shared-prop parse (and the slot render) threw.

        The other diff tests use ``goto`` (a hard load), which never exercises
        the swap, so neither regression was caught. This test clicks the link
        instead: the URL must advance to the diff page (not roll back), the
        highlighted diff must render, and tearDown's console-error check guards
        the transient-prop crashes.
        """
        page = self.page
        # Land on the commit's file list (loads the Inertia app + main.js).
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}")
        page.get_by_role("link", name="TodoApp/endpoints.py").wait_for(state="visible")
        # Click the file link — a client-side Inertia swap to GitDiff.
        page.get_by_role("link", name="TodoApp/endpoints.py").click()
        # A rollback would leave the URL on the commit page; assert it advanced.
        page.wait_for_url(f"**/git/commits/{self.short_b}/TodoApp/endpoints.py")
        # The diff renders highlighted (hljs spans), not raw text.
        page.wait_for_selector(".code-diff .hljs-addition")
        diff = page.locator(".code-diff")
        self.assertGreater(diff.locator(".hljs-addition").count(), 0)
        self.assertIn("new file mode", diff.text_content() or "")

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
        page.get_by_role("link", name="TodoApp/endpoints.py").wait_for(state="visible")
        self.assertIn("Add create endpoint", page.inner_text("body"))
        # The file's diff renders.
        page.goto(f"{self.live_server_url}/git/commits/{self.short_b}/TodoApp/endpoints.py")
        page.wait_for_selector(".code-diff .hljs-addition")
        diff_text = page.locator(".code-diff").text_content() or ""
        self.assertIn("new file mode", diff_text)
        self.assertIn("TodoApp/endpoints.py", diff_text)

    def test_non_superuser_404(self) -> None:
        """An anonymous viewer of the git viewer gets a 404 (the gate holds over HTTP)."""
        with self.anon_page() as page:
            response = page.goto(f"{self.live_server_url}/git/uncommitted/")
            assert response is not None
            self.assertEqual(response.status, 404)
