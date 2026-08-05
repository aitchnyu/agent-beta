"""Data contract + GitPython-backed read functions for the ``/git`` viewer.

The ``/git`` views (:mod:`djangoapp.views.git`) call these module-level
functions. They read a named **worktree** — ``main`` (the repo at ``BASE_DIR``,
which the dev server runs in) or ``scratch`` (the throwaway scratch sibling that
``./run createscratch`` builds) — so the viewer can show pending files in both
places. Commits/commit diffs read ``main`` only (``scratch`` has no shared
history).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

from django.conf import settings
from pydantic import BaseModel

if TYPE_CHECKING:
    from typing import Any

# The repo the viewer reads: the project's git repo at BASE_DIR. Module-level so
# tests can point it at a throwaway temp repo (see tests/views/test_git.py).
_REPO_ROOT = Path(str(settings.BASE_DIR)).resolve()

_PAGE_SIZE = 25
# Commit ids are full-or-short hex shas (4..40 chars); validated before reaching git.
_HEX_RE = re.compile(r"^[0-9a-f]{4,40}$", re.IGNORECASE)


class UncommittedFile(BaseModel):
    """A working-tree file with uncommitted changes."""

    path: str
    status: str  # "modified" | "added" | "deleted" | "untracked"


class CommitSummary(BaseModel):
    """One row of the paginated commit list (newest first)."""

    sha: str
    short_sha: str
    author: str
    date: int  # epoch ms — the frontend renders via HumanizedTime (matches FileEntry.mtime)
    subject: str


class CommitFile(BaseModel):
    """A file changed by a specific commit."""

    path: str
    status: str  # "added" | "modified" | "deleted"


class GitPagination(BaseModel):
    """Pager state for the commit list (mirrors the users-list pager)."""

    page: int
    total_pages: int
    total_count: int


def worktree_root(name: str) -> Path:
    """Root of a named worktree — ``main`` → ``_REPO_ROOT``, ``scratch`` → its sibling.

    ``scratch`` lives at ``<parent>/scratch`` (same layout ``./run createscratch``
    uses), so it resolves from ``_REPO_ROOT``'s parent. The view validates
    ``name`` against the URL-accepted set (git.py's ``WORKTREES``) first; an
    unknown name here raises ``ValueError`` as a backstop.
    """
    root = _REPO_ROOT.resolve()
    if name == "main":
        return root
    if name == "scratch":
        return root.parent / "scratch"
    msg = f"unknown worktree: {name}"
    raise ValueError(msg)


def worktree_exists(name: str) -> bool:
    """Return whether the named worktree's repo is on disk.

    E.g. ``scratch/`` only after ``createscratch``. Views check this before reading,
    so ``_repo``/``uncommitted`` follow the happy path (no missing-repo handling).
    """
    return worktree_root(name).is_dir()


def _repo(name: str = "main") -> Any:  # noqa: ANN401 -- git.Repo has no first-class stub; Any is the honest type
    import git  # noqa: PLC0415 -- lazy: only the real provider needs GitPython

    # Raises git.NoSuchPathError / git.InvalidGitRepositoryError if the worktree's
    # repo is missing — left for the caller (views map to 404, the list skips).
    return git.Repo(str(worktree_root(name)))


def _change_status(change_type: str) -> str:
    if change_type == "A":
        return "added"
    if change_type == "D":
        return "deleted"
    return "modified"


def _commit_summary(c: Any) -> CommitSummary:  # noqa: ANN401 -- git.Commit has no stubs
    return CommitSummary(
        sha=c.hexsha,
        short_sha=c.hexsha[:7],
        author=f"{c.author.name} <{c.author.email}>",
        date=int(c.committed_datetime.timestamp() * 1000),
        subject=(c.message.strip().splitlines()[:1] or [""])[0],
    )


def _commit_files(c: Any) -> list[CommitFile]:  # noqa: ANN401 -- git.Commit has no stubs
    import git  # noqa: PLC0415

    diffs = c.parents[0].diff(c) if c.parents else c.diff(git.NULL_TREE)
    return [
        CommitFile(path=d.b_path or d.a_path, status=_change_status(d.change_type)) for d in diffs
    ]


def uncommitted(name: str = "main") -> list[UncommittedFile]:
    """Return a worktree's files not yet committed (untracked + tracked changes)."""
    repo = _repo(name)
    out: list[UncommittedFile] = [
        UncommittedFile(path=p, status="untracked") for p in repo.untracked_files
    ]
    if repo.head.is_valid():  # no HEAD → fresh repo, only untracked
        out.extend(
            UncommittedFile(path=d.b_path or d.a_path, status=_change_status(d.change_type))
            for d in repo.head.commit.diff(None)  # HEAD vs working tree (all tracked changes)
        )
    return out


def commits(page: int) -> tuple[list[CommitSummary], GitPagination]:
    """Return a page of commits (newest first) + pager state.

    ``page`` is clamped to ``[1, total_pages]`` so an out-of-range request
    (e.g. ``?page=999``) shows the last page rather than an impossible page
    number with empty results.
    """
    repo = _repo()
    if not repo.head.is_valid():
        return [], GitPagination(page=max(1, page), total_pages=1, total_count=0)
    total = int(repo.git.rev_list("--count", "HEAD"))
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(max(1, page), total_pages)
    skip = (page - 1) * _PAGE_SIZE
    items = [_commit_summary(c) for c in repo.iter_commits(max_count=_PAGE_SIZE, skip=skip)]
    return items, GitPagination(page=page, total_pages=total_pages, total_count=total)


def commit(commit_id: str) -> tuple[CommitSummary, list[CommitFile]] | None:
    """Return a commit's summary + its changed files (None if ``commit_id`` is unknown)."""
    import git  # noqa: PLC0415

    if not _HEX_RE.match(commit_id):
        return None
    repo = _repo()
    try:
        c = repo.commit(commit_id)
    except git.BadName, git.BadObject, git.GitCommandError, ValueError:
        return None
    return _commit_summary(c), _commit_files(c)


def diff_uncommitted(path: str, name: str = "main") -> str | None:
    """Unified diff of a worktree file (None if ``path`` isn't uncommitted)."""
    if not any(f.path == path for f in uncommitted(name)):
        return None
    repo = _repo(name)
    if path in repo.untracked_files:
        # Untracked has no HEAD entry: diff against /dev/null (rc=1 is normal → no raise).
        return cast(
            "str",
            repo.git.diff("--no-index", "--", "/dev/null", path, with_exceptions=False),
        )
    return cast("str", repo.git.diff("HEAD", "--", path))


def diff_commit(commit_id: str, path: str) -> str | None:
    """Unified diff of ``path`` as introduced by commit ``commit_id`` (None if absent).

    Uses ``git diff <parent> <commit> -- <path>`` rather than ``git show``: this
    avoids (a) combined-diff format for merge commits (which emits no
    ``diff --git`` and would return the raw commit header) and (b) the commit
    message header entirely (so a message containing ``diff --git`` can't
    corrupt the slice). Root commits diff against the empty tree.
    """
    import git  # noqa: PLC0415

    if not _HEX_RE.match(commit_id):
        return None
    repo = _repo()
    try:
        c = repo.commit(commit_id)
    except git.BadName, git.BadObject, git.GitCommandError, ValueError:
        return None
    if not any(f.path == path for f in _commit_files(c)):
        return None
    parent = c.parents[0].hexsha if c.parents else git.NULL_TREE
    return cast("str", repo.git.diff(parent, c.hexsha, "--", path))
