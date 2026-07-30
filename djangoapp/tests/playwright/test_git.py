from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from djangoapp.models import User
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase
from djangoapp.views.git_data import CommitFile, CommitSummary, GitPagination, UncommittedFile

# ── Inlined mock data ──────────────────────────────────────────────────────
# Deterministic canned data so these E2E tests don't depend on live git state.
# The git_data functions are patched (same-process live server → visible to its
# requests) with these. Defined here, not in a separate module, so the test is
# self-contained.

_UNCOMMITTED = [
    UncommittedFile(path="TodoApp/app.py", status="modified"),
    UncommittedFile(path="TodoApp/notes.md", status="untracked"),
]

_COMMITS = [
    CommitSummary(
        sha="c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8",
        short_sha="c3d2e1f",
        author="Alice <alice@example.com>",
        date=int(datetime(2026, 7, 27, 18, 15, tzinfo=UTC).timestamp() * 1000),
        subject="Add delete endpoint",
    ),
    CommitSummary(
        sha="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        short_sha="b2c3d4e",
        author="Bob <bob@example.com>",
        date=int(datetime(2026, 7, 27, 17, 0, tzinfo=UTC).timestamp() * 1000),
        subject="Add create endpoint",
    ),
    CommitSummary(
        sha="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        short_sha="a1b2c3d",
        author="Alice <alice@example.com>",
        date=int(datetime(2026, 7, 26, 9, 30, tzinfo=UTC).timestamp() * 1000),
        subject="Initial TodoApp",
    ),
]

_COMMIT_FILES = {
    "c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8": [CommitFile(path="TodoApp/app.py", status="modified")],
    "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7": [
        CommitFile(path="TodoApp/app.py", status="modified"),
        CommitFile(path="TodoApp/endpoints.py", status="added"),
    ],
    "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6": [CommitFile(path="TodoApp/app.py", status="added")],
}

_PAGE_SIZE = 25


def _mock_uncommitted() -> list[UncommittedFile]:
    return list(_UNCOMMITTED)


def _mock_commits(page: int) -> tuple[list[CommitSummary], GitPagination]:
    total = len(_COMMITS)
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(max(1, page), total_pages)
    start = (page - 1) * _PAGE_SIZE
    return _COMMITS[start : start + _PAGE_SIZE], GitPagination(
        page=page, total_pages=total_pages, total_count=total
    )


def _mock_commit(commit_id: str) -> tuple[CommitSummary, list[CommitFile]] | None:
    c = next(
        (c for c in _COMMITS if commit_id in (c.sha, c.short_sha) or c.sha.startswith(commit_id)),
        None,
    )
    return (c, list(_COMMIT_FILES.get(c.sha, []))) if c else None


def _mock_diff_uncommitted(path: str) -> str | None:
    if not any(f.path == path for f in _UNCOMMITTED):
        return None
    return f"""\
diff --git a/{path} b/{path}
index 1234567..89abcde 100644
--- a/{path}
+++ b/{path}
@@ -10,3 +10,6 @@ def main():
     print("hello")
-print("old line")
+
+x = 42
+print(x)
+return x
"""


def _mock_diff_commit(commit_id: str, path: str) -> str | None:
    found = _mock_commit(commit_id)
    if found is None or not any(f.path == path for f in found[1]):
        return None
    return f"""\
diff --git a/{path} b/{path}
new file mode 100644
index 0000000..abcdef1
--- /dev/null
+++ b/{path}
@@ -0,0 +1,3 @@
+def greet(name):
+    return f"Hello, {{name}}"
+
"""


class GitViewerE2e(BasePlaywrightTestCase):
    """E2E for the superuser ``/git`` viewer (headless firefox).

    The base harness logs in a plain user; ``/git`` is superuser-only (404
    otherwise), so ``setUp`` re-auths as a superuser. The ``git_data``
    functions are patched with the inlined canned data (the live server is
    in-process, so the patch is visible to its requests). ``tearDown`` fails on
    any browser console error.

    - test_uncommitted_renders, the /git list mounts with 2 files → diff links
    - test_commit_list_renders, /git/commits shows 3 subjects + a commit count
    - test_diff_highlighted, a diff renders .hljs-addition/.hljs-deletion spans
    - test_commit_navigation, the commits → files → diff link chain works
    - test_non_superuser_404, an anonymous viewer of /git gets 404
    """

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(
            username="gitadmin", password="x", is_staff=True, is_superuser=True
        )
        self.page = self.logged_in_page
        self.page.goto(
            f"{self.live_server_url}/login-for-test/{self.admin.pk}",
            wait_until="networkidle",
        )
        self._m1 = patch("djangoapp.views.git_data.uncommitted", _mock_uncommitted)
        self._m1.start()
        self.addCleanup(self._m1.stop)

        self._m2 = patch("djangoapp.views.git_data.commits", _mock_commits)
        self._m2.start()
        self.addCleanup(self._m2.stop)

        self._m3 = patch("djangoapp.views.git_data.commit", _mock_commit)
        self._m3.start()
        self.addCleanup(self._m3.stop)

        self._m4 = patch("djangoapp.views.git_data.diff_uncommitted", _mock_diff_uncommitted)
        self._m4.start()
        self.addCleanup(self._m4.stop)

        self._m5 = patch("djangoapp.views.git_data.diff_commit", _mock_diff_commit)
        self._m5.start()
        self.addCleanup(self._m5.stop)

    def _url(self, rel: str = "") -> str:
        return f"{self.live_server_url}/git/{rel}".rstrip("/")

    def test_uncommitted_renders(self) -> None:
        """``/git`` lists the 2 uncommitted files, each linking to its diff."""
        page = self.page
        page.goto(self._url(), wait_until="networkidle")
        page.get_by_role("link", name="TodoApp/app.py").wait_for(state="visible")
        body = page.inner_text("body")
        self.assertIn("TodoApp/app.py", body)
        self.assertIn("TodoApp/notes.md", body)
        link = page.get_by_role("link", name="TodoApp/app.py")
        self.assertEqual(link.get_attribute("href"), "/git/uncommitted/TodoApp/app.py")

    def test_commit_list_renders(self) -> None:
        """``/git/commits`` shows the 3 subjects (newest first) + a commit count."""
        page = self.page
        page.goto(self._url("commits"), wait_until="networkidle")
        page.get_by_role("link", name="c3d2e1f").wait_for(state="visible")
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
        page.goto(self._url("uncommitted/TodoApp/app.py"), wait_until="networkidle")
        page.wait_for_function(
            "() => document.querySelectorAll('.git-diff .hljs-addition').length > 0"
            " && document.querySelectorAll('.git-diff .hljs-deletion').length > 0"
        )
        diff = page.locator(".git-diff")
        self.assertGreater(diff.locator(".hljs-addition").count(), 0)
        self.assertGreater(diff.locator(".hljs-deletion").count(), 0)
        self.assertIn("TodoApp/app.py", diff.text_content() or "")

    def test_commit_navigation(self) -> None:
        """The commits → files → diff link chain works end-to-end.

        Each step navigates via ``goto`` and verifies the expected links exist,
        then waits for the diff to render.
        """
        page = self.page
        # Commit list has a link to each commit.
        page.goto(self._url("commits"), wait_until="networkidle")
        page.get_by_role("link", name="b2c3d4e").wait_for(state="visible")
        self.assertIn("Add create endpoint", page.inner_text("body"))
        # The commit page links to each changed file.
        page.goto(f"{self.live_server_url}/git/commits/b2c3d4e", wait_until="networkidle")
        page.get_by_role("link", name="TodoApp/endpoints.py").wait_for(state="visible")
        self.assertIn("Add create endpoint", page.inner_text("body"))
        # The file's diff renders.
        page.goto(
            f"{self.live_server_url}/git/commits/b2c3d4e/TodoApp/endpoints.py",
            wait_until="networkidle",
        )
        page.wait_for_function(
            "() => (document.querySelector('.git-diff')?.textContent || '')"
            ".includes('new file mode')"
        )
        diff_text = page.locator(".git-diff").text_content() or ""
        self.assertIn("new file mode", diff_text)
        self.assertIn("TodoApp/endpoints.py", diff_text)

    def test_non_superuser_404(self) -> None:
        """An anonymous viewer of ``/git`` gets a 404 (the gate holds over HTTP)."""
        with self.anon_page() as page:
            response = page.goto(self._url())
            assert response is not None
            self.assertEqual(response.status, 404)
