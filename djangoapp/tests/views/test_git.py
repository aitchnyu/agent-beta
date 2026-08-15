# test module loaded by the runner, not a package
"""Tests for the ``/git`` viewer — the real stack (real GitPython + real views).

Against throwaway temp repos. No mocks: the class mixes in ``GitRepoMixin``
(``djangoapp/tests/_git_fixtures.py``, shared with the Playwright suite), whose
``setUpClass`` builds a known git history (3 commits incl. a root commit and a
deletion, plus uncommitted changes) in a ``main`` worktree and a baseline +
uncommitted changes in a sibling ``scratch`` worktree, and patches the repo
root to ``main``. Each test hits the view via ``self.client`` and asserts the
Inertia props / 404.
"""

from __future__ import annotations

import tempfile
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import git

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase
from djangoapp.tests._git_fixtures import GitRepoMixin


class GitRealTests(GitRepoMixin, BaseInertiaTestCase):
    """``/git`` views against real temp inner repos (no mocks).

    ``GitRepoMixin.setUpClass`` (also the Playwright suite's base) builds the
    ``parent/main`` + ``parent/scratch`` fixture and its commit history — see the
    mixin's docstring for that history; this class adds superuser auth and
    asserts the Inertia props / 404s over ``self.client``.

    test_uncommitted_list — /git/uncommitted/ lists every worktree (main, scratch)
    test_uncommitted_unknown_worktree — unknown worktree → 404 (list + diff)
    test_uncommitted_diff_tracked — diff of a modified file shows the new line
    test_uncommitted_diff_untracked — diff of an untracked file shows all-added
    test_uncommitted_diff_unknown — unknown path → 404
    test_uncommitted_scratch_diff — a diff resolves against the scratch worktree
    test_commit_list — /git/commits lists 3 commits with pagination
    test_commit_list_fields — commit summary fields (sha, author, date type)
    test_commit_list_page_clamped — ?page=999 clamps to last page
    test_commit_list_bad_page — ?page=abc clamps to 1
    test_commit_files — commit meta + changed files with statuses
    test_commit_files_root — root commit shows all files as added
    test_commit_files_deleted — deleted file shows status=deleted
    test_commit_files_unknown — unknown commit → 404
    test_commit_file_diff — file diff in a commit shows the change
    test_commit_file_diff_deleted — diff of a deleted file shows the deletion
    test_commit_file_diff_unknown_path — unknown path → 404
    test_uncommitted_path_confinement — .. escape on the main worktree → 404
    test_uncommitted_scratch_confinement — .. escape on the scratch worktree → 404
    test_commit_file_diff_confinement — .. escape on commit route → 404
    test_anon_404 — anonymous → 404
    test_missing_repo_diff_404 — a diff in a missing repo → 404
    test_uncommitted_missing_scratch — a missing worktree is omitted from the list
    test_empty_repo_uncommitted — no HEAD → only untracked
    test_empty_repo_commits — no HEAD → empty list + zero pager
    """

    def setUp(self) -> None:
        super().setUp()  # auth only — the repo fixture is class-scoped
        self.user = User.objects.create_user(
            username="root", password="p", is_staff=True, is_superuser=True
        )
        self.client.force_login(self.user)

    def test_uncommitted_list(self) -> None:
        """``/git/uncommitted/`` lists main's + scratch's pending files."""
        self.client.get("/git/uncommitted/")
        self.assertComponentUsed("GitUncommitted")
        props = self.props()["props"]
        main = {f["path"]: f["status"] for f in props["main_files"]}
        scratch = {f["path"]: f["status"] for f in props["scratch_files"]}
        self.assertEqual(main.get("TodoApp/app.py"), "modified")
        self.assertEqual(main.get("TodoApp/notes.md"), "untracked")
        self.assertEqual(scratch.get("TodoApp/scratch_only.py"), "modified")
        self.assertEqual(scratch.get("TodoApp/scratch_notes.md"), "untracked")
        self.assertNotIn("TodoApp/app.py", scratch)

    def test_uncommitted_unknown_worktree(self) -> None:
        """An unknown worktree name → 404 (list + diff routes)."""
        self.assertEqual(
            self.client.get("/git/uncommitted/other").status_code,
            HTTPStatus.NOT_FOUND,
        )
        self.assertEqual(
            self.client.get("/git/uncommitted/other/foo.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_uncommitted_diff_tracked(self) -> None:
        """``/git/uncommitted/main/TodoApp/app.py`` serves the diff with the new line."""
        self.client.get("/git/uncommitted/main/TodoApp/app.py")
        self.assertComponentUsed("GitDiff")
        props = self.props()["props"]
        self.assertIn('+    print("final")', props["diff"])
        self.assertEqual(props["title"], "Uncommitted (main): TodoApp/app.py")

    def test_uncommitted_diff_untracked(self) -> None:
        """``/git/uncommitted/main/TodoApp/notes.md`` serves the whole-file-added diff."""
        self.client.get("/git/uncommitted/main/TodoApp/notes.md")
        self.assertComponentUsed("GitDiff")
        self.assertIn("+todo", self.props()["props"]["diff"])

    def test_uncommitted_diff_unknown(self) -> None:
        """An uncommitted diff for a path that isn't uncommitted → 404."""
        self.assertEqual(
            self.client.get("/git/uncommitted/main/nope.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_uncommitted_scratch_diff(self) -> None:
        """``/git/uncommitted/scratch/TodoApp/scratch_only.py`` serves the scratch-repo diff."""
        self.client.get("/git/uncommitted/scratch/TodoApp/scratch_only.py")
        self.assertComponentUsed("GitDiff")
        props = self.props()["props"]
        self.assertIn("+x = 1", props["diff"])
        self.assertEqual(props["title"], "Uncommitted (scratch): TodoApp/scratch_only.py")

    def test_commit_list(self) -> None:
        """``/git/commits`` lists 3 commits newest-first with pagination."""
        self.client.get("/git/commits")
        self.assertComponentUsed("GitCommitList")
        props = self.props()["props"]
        self.assertEqual(
            [c["subject"] for c in props["commits"]],
            ["Add delete endpoint", "Add create endpoint", "Initial TodoApp"],
        )
        self.assertEqual(props["pagination"]["page"], 1)
        self.assertEqual(props["pagination"]["total_pages"], 1)
        self.assertEqual(props["pagination"]["total_count"], 3)

    def test_commit_list_fields(self) -> None:
        """Each commit summary has all expected fields with correct types."""
        self.client.get("/git/commits")
        first = self.props()["props"]["commits"][0]
        self.assertEqual(first["subject"], "Add delete endpoint")
        self.assertEqual(first["short_sha"], self.short_c)
        self.assertEqual(first["sha"], self.commit_c.hexsha)
        self.assertEqual(first["author"], "Tester <t@example.com>")
        self.assertIsInstance(first["date"], int)

    def test_commit_list_page_clamped(self) -> None:
        """``?page=999`` clamps to the last page (1 here), not an impossible number."""
        self.client.get("/git/commits?page=999")
        props = self.props()["props"]
        self.assertEqual(props["pagination"]["page"], 1)
        self.assertEqual(len(props["commits"]), 3)

    def test_commit_list_bad_page(self) -> None:
        """A non-int ``?page=`` clamps to 1 (200), not an error."""
        self.client.get("/git/commits?page=abc")
        self.assertComponentUsed("GitCommitList")
        self.assertEqual(len(self.props()["props"]["commits"]), 3)

    def test_commit_files(self) -> None:
        """``/git/commits/<sha>`` shows the commit meta + changed files with statuses."""
        self.client.get(f"/git/commits/{self.short_b}")
        props = self.props()["props"]
        self.assertEqual(props["commit"]["subject"], "Add create endpoint")
        by_path = {f["path"]: f["status"] for f in props["files"]}
        self.assertEqual(by_path.get("TodoApp/app.py"), "modified")
        self.assertEqual(by_path.get("TodoApp/endpoints.py"), "added")

    def test_commit_files_root(self) -> None:
        """The root commit (no parent) shows all files as 'added'."""
        self.client.get(f"/git/commits/{self.short_a}")
        props = self.props()["props"]
        self.assertEqual(props["commit"]["subject"], "Initial TodoApp")
        by_path = {f["path"]: f["status"] for f in props["files"]}
        self.assertEqual(by_path.get("TodoApp/app.py"), "added")

    def test_commit_files_deleted(self) -> None:
        """A commit that deletes a file shows status='deleted'."""
        self.client.get(f"/git/commits/{self.short_c}")
        by_path = {f["path"]: f["status"] for f in self.props()["props"]["files"]}
        self.assertEqual(by_path.get("TodoApp/endpoints.py"), "deleted")

    def test_commit_files_unknown(self) -> None:
        """An unknown commit id → 404."""
        self.assertEqual(
            self.client.get("/git/commits/0123456789abcdef").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_commit_file_diff(self) -> None:
        """``/git/commits/<sha>/<path>`` serves that file's diff in the commit."""
        self.client.get(f"/git/commits/{self.short_b}/TodoApp/app.py")
        self.assertComponentUsed("GitDiff")
        self.assertIn("+    return x", self.props()["props"]["diff"])

    def test_commit_file_diff_deleted(self) -> None:
        """A diff for a file deleted in the commit shows the deletion."""
        self.client.get(f"/git/commits/{self.short_c}/TodoApp/endpoints.py")
        self.assertComponentUsed("GitDiff")
        self.assertIn("-def greet(name):", self.props()["props"]["diff"])

    def test_commit_file_diff_unknown_path(self) -> None:
        """A diff for a path not in the commit → 404."""
        self.assertEqual(
            self.client.get(f"/git/commits/{self.short_b}/nope.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_uncommitted_path_confinement(self) -> None:
        """A ``..`` escape from the main worktree root → 404."""
        self.assertEqual(
            self.client.get("/git/uncommitted/main/../../etc/passwd").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_uncommitted_scratch_confinement(self) -> None:
        """A ``..`` escape from the scratch worktree root (into main/) → 404."""
        self.assertEqual(
            self.client.get("/git/uncommitted/scratch/../main/TodoApp/app.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_commit_file_diff_confinement(self) -> None:
        """A ``..`` escape in a commit-file-diff path → 404."""
        self.assertEqual(
            self.client.get(f"/git/commits/{self.short_b}/../../etc/passwd").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_anon_404(self) -> None:
        """An anonymous viewer → 404 on the uncommitted list + a diff."""
        self.client.logout()
        self.assertEqual(
            self.client.get("/git/uncommitted/").status_code,
            HTTPStatus.NOT_FOUND,
        )
        self.assertEqual(
            self.client.get("/git/uncommitted/main/TodoApp/app.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_missing_repo_diff_404(self) -> None:
        """A diff for a file in a missing repo → 404, not a 500 traceback."""
        with patch("djangoapp.views.git_data._REPO_ROOT", Path("/nonexistent/git/path")):
            self.assertEqual(
                self.client.get("/git/uncommitted/main/foo.py").status_code,
                HTTPStatus.NOT_FOUND,
            )

    def test_uncommitted_missing_scratch(self) -> None:
        """A missing ``scratch/`` → ``scratch_files`` is None (its section is omitted)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "main"
            repo = git.Repo.init(root)
            repo.git.config("user.email", "t@example.com")
            repo.git.config("user.name", "Tester")
            (root / "a.py").write_text("x = 1\n")  # untracked
            with patch("djangoapp.views.git_data._REPO_ROOT", root):
                self.client.get("/git/uncommitted/")
            props = self.props()["props"]
            self.assertIsNone(props["scratch_files"])  # scratch/ not on disk → omitted
            self.assertEqual([f["path"] for f in props["main_files"]], ["a.py"])

    def test_empty_repo_uncommitted(self) -> None:
        """A repo with no HEAD shows only untracked files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "main"
            git.Repo.init(root)
            (root / "orphan.py").write_text("x = 1\n")
            with patch("djangoapp.views.git_data._REPO_ROOT", root):
                self.client.get("/git/uncommitted/")
            props = self.props()["props"]
            self.assertIsNone(props["scratch_files"])  # no scratch/ sibling
            files = props["main_files"]
            self.assertEqual([f["path"] for f in files], ["orphan.py"])
            self.assertEqual(files[0]["status"], "untracked")

    def test_empty_repo_commits(self) -> None:
        """A repo with no HEAD returns an empty commit list + zero-count pager."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "main"
            git.Repo.init(root)
            with patch("djangoapp.views.git_data._REPO_ROOT", root):
                self.client.get("/git/commits")
            props = self.props()["props"]
            self.assertEqual(props["commits"], [])
            self.assertEqual(props["pagination"]["total_count"], 0)
