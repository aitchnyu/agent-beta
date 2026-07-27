# test module loaded by the runner, not a package
"""Tests for the ``/git`` viewer — the real stack (real GitPython + real views).

Against a throwaway temp repo. No mocks: ``setUp`` builds a known git history
(3 commits incl. a root commit and a deletion, plus uncommitted changes) and
patches the apps-root to it. Each test hits the view via ``self.client`` and
asserts the Inertia props / 404.
"""

from __future__ import annotations

import tempfile
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import git
from inertia.test import InertiaTestCase

from djangoapp.models import User


class GitRealTests(InertiaTestCase):
    """``/git`` views against a real temp inner repo (no mocks).

    Repo history (newest first):
      C — deletes file2.md
      B — modifies file1.py, adds file2.md
      A — root: adds file1.py
    Uncommitted: file1.py modified, file3.txt untracked.

    test_uncommitted_list — /git lists modified + untracked files
    test_uncommitted_diff_tracked — diff of a modified file shows the new line
    test_uncommitted_diff_untracked — diff of an untracked file shows all-added
    test_uncommitted_diff_unknown — unknown path → 404
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
    test_uncommitted_path_confinement — .. escape → 404
    test_commit_file_diff_confinement — .. escape on commit route → 404
    test_anon_404 — anonymous → 404
    test_missing_repo_404 — missing/non-git apps dir → 404
    test_empty_repo_uncommitted — no HEAD → only untracked
    test_empty_repo_commits — no HEAD → empty list + zero pager
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(
            username="root", password="p", is_staff=True, is_superuser=True
        )
        self.client.force_login(self.user)

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        repo = git.Repo.init(root)
        repo.git.config("user.email", "t@example.com")
        repo.git.config("user.name", "Tester")

        # commit A (root): add file1.py
        (root / "file1.py").write_text("a = 1\n")
        repo.index.add(["file1.py"])
        self.commit_a = repo.index.commit("commit A")

        # commit B: modify file1.py + add file2.md
        (root / "file1.py").write_text("a = 1\nb = 2\n")
        (root / "file2.md").write_text("# hi\n")
        repo.index.add(["file1.py", "file2.md"])
        self.commit_b = repo.index.commit("commit B")

        # commit C: delete file2.md
        repo.index.remove(["file2.md"])
        (root / "file2.md").unlink()
        self.commit_c = repo.index.commit("commit C")

        # uncommitted: modify file1.py + add untracked file3.txt
        (root / "file1.py").write_text("a = 1\nb = 2\nc = 3\n")
        (root / "file3.txt").write_text("new1\nnew2\n")

        self.short_a = self.commit_a.hexsha[:7]
        self.short_b = self.commit_b.hexsha[:7]
        self.short_c = self.commit_c.hexsha[:7]

        self._patch = patch("djangoapp.apps.dynamic_module._APPS_ROOT", root)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_uncommitted_list(self) -> None:
        """``/git`` lists the modified file + the untracked file."""
        self.client.get("/git")
        self.assertComponentUsed("GitUncommitted")
        by_path = {f["path"]: f["status"] for f in self.props()["props"]["files"]}
        self.assertEqual(by_path.get("file1.py"), "modified")
        self.assertEqual(by_path.get("file3.txt"), "untracked")

    def test_uncommitted_diff_tracked(self) -> None:
        """``/git/uncommitted/file1.py`` serves the diff with the new line."""
        self.client.get("/git/uncommitted/file1.py")
        self.assertComponentUsed("GitDiff")
        self.assertIn("+c = 3", self.props()["props"]["diff"])

    def test_uncommitted_diff_untracked(self) -> None:
        """``/git/uncommitted/file3.txt`` serves the whole-file-added diff."""
        self.client.get("/git/uncommitted/file3.txt")
        self.assertComponentUsed("GitDiff")
        self.assertIn("+new1", self.props()["props"]["diff"])

    def test_uncommitted_diff_unknown(self) -> None:
        """An uncommitted diff for a path that isn't uncommitted → 404."""
        self.assertEqual(
            self.client.get("/git/uncommitted/nope.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_commit_list(self) -> None:
        """``/git/commits`` lists 3 commits newest-first with pagination."""
        self.client.get("/git/commits")
        self.assertComponentUsed("GitCommitList")
        props = self.props()["props"]
        self.assertEqual(
            [c["subject"] for c in props["commits"]],
            ["commit C", "commit B", "commit A"],
        )
        self.assertEqual(props["pagination"]["page"], 1)
        self.assertEqual(props["pagination"]["total_pages"], 1)
        self.assertEqual(props["pagination"]["total_count"], 3)

    def test_commit_list_fields(self) -> None:
        """Each commit summary has all expected fields with correct types."""
        self.client.get("/git/commits")
        first = self.props()["props"]["commits"][0]
        self.assertEqual(first["subject"], "commit C")
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
        self.assertEqual(props["commit"]["subject"], "commit B")
        by_path = {f["path"]: f["status"] for f in props["files"]}
        self.assertEqual(by_path.get("file1.py"), "modified")
        self.assertEqual(by_path.get("file2.md"), "added")

    def test_commit_files_root(self) -> None:
        """The root commit (no parent) shows all files as 'added'."""
        self.client.get(f"/git/commits/{self.short_a}")
        props = self.props()["props"]
        self.assertEqual(props["commit"]["subject"], "commit A")
        by_path = {f["path"]: f["status"] for f in props["files"]}
        self.assertEqual(by_path.get("file1.py"), "added")

    def test_commit_files_deleted(self) -> None:
        """A commit that deletes a file shows status='deleted'."""
        self.client.get(f"/git/commits/{self.short_c}")
        by_path = {f["path"]: f["status"] for f in self.props()["props"]["files"]}
        self.assertEqual(by_path.get("file2.md"), "deleted")

    def test_commit_files_unknown(self) -> None:
        """An unknown commit id → 404."""
        self.assertEqual(
            self.client.get("/git/commits/deadbeef").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_commit_file_diff(self) -> None:
        """``/git/commits/<sha>/<path>`` serves that file's diff in the commit."""
        self.client.get(f"/git/commits/{self.short_b}/file1.py")
        self.assertComponentUsed("GitDiff")
        self.assertIn("+b = 2", self.props()["props"]["diff"])

    def test_commit_file_diff_deleted(self) -> None:
        """A diff for a file deleted in the commit shows the deletion."""
        self.client.get(f"/git/commits/{self.short_c}/file2.md")
        self.assertComponentUsed("GitDiff")
        self.assertIn("-# hi", self.props()["props"]["diff"])

    def test_commit_file_diff_unknown_path(self) -> None:
        """A diff for a path not in the commit → 404."""
        self.assertEqual(
            self.client.get(f"/git/commits/{self.short_b}/nope.py").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_uncommitted_path_confinement(self) -> None:
        """A ``..`` escape in an uncommitted-diff path → 404."""
        self.assertEqual(
            self.client.get("/git/uncommitted/../../etc/passwd").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_commit_file_diff_confinement(self) -> None:
        """A ``..`` escape in a commit-file-diff path → 404."""
        self.assertEqual(
            self.client.get(f"/git/commits/{self.short_b}/../../etc/passwd").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_anon_404(self) -> None:
        """An anonymous viewer → 404."""
        self.client.logout()
        self.assertEqual(self.client.get("/git").status_code, HTTPStatus.NOT_FOUND)

    def test_missing_repo_404(self) -> None:
        """A missing/non-git apps dir → 404, not a 500 traceback."""
        with patch("djangoapp.apps.dynamic_module._APPS_ROOT", Path("/nonexistent/git/path")):
            self.assertEqual(
                self.client.get("/git").status_code, HTTPStatus.NOT_FOUND
            )

    def test_empty_repo_uncommitted(self) -> None:
        """A repo with no HEAD shows only untracked files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git.Repo.init(root)
            (root / "orphan.py").write_text("x = 1\n")
            with patch("djangoapp.apps.dynamic_module._APPS_ROOT", root):
                self.client.get("/git")
            files = self.props()["props"]["files"]
            self.assertEqual([f["path"] for f in files], ["orphan.py"])
            self.assertEqual(files[0]["status"], "untracked")

    def test_empty_repo_commits(self) -> None:
        """A repo with no HEAD returns an empty commit list + zero-count pager."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git.Repo.init(root)
            with patch("djangoapp.apps.dynamic_module._APPS_ROOT", root):
                self.client.get("/git/commits")
            props = self.props()["props"]
            self.assertEqual(props["commits"], [])
            self.assertEqual(props["pagination"]["total_count"], 0)
