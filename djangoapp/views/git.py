"""Superuser-only read-only git viewer at ``/git/...`` over the project worktrees.

Mirrors ``/files``: superuser-only (404 otherwise), path-confined to the
worktree root. Reads via :mod:`djangoapp.views.git_data` (GitPython); tests
patch the repo root. The uncommitted *list* (``/git/uncommitted/``) shows every
worktree's pending files together (main, then scratch); an uncommitted *diff*
takes a ``worktree`` segment (``main``/``scratch``). Commit views read ``main``
only. Routes in :mod:`djangoapp.urls`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.http import Http404, HttpRequest, HttpResponseBase
from inertia import InertiaResponse
from pydantic import BaseModel

from djangoapp.views import git_data, require_superuser

if TYPE_CHECKING:
    from pathlib import Path

# Commit ids are full-or-short hex shas (4..40 chars); validated before use.
_HEX_RE = re.compile(r"^[0-9a-f]{4,40}$", re.IGNORECASE)

# Worktree names the uncommitted routes accept (the <worktree> URL segment).
# "main" = the dev-server repo (BASE_DIR); "scratch" = the scratch sibling
# `./run createscratch` builds. git_data.worktree_root() resolves each to its
# on-disk repo; unknown names → 404 (see _worktree_or_404).
WORKTREES = ("main", "scratch")


def _worktree_or_404(worktree: str) -> str:
    """Return ``worktree`` if it's one the viewer knows, else raise Http404."""
    if worktree not in WORKTREES:
        raise Http404
    return worktree


def _confined_to_repo(rel: str, root: Path) -> str:
    """Return ``rel`` normalized if it stays inside ``root``, else raise Http404.

    Unlike :class:`PathWrapper`, existence is *not* required — a diff path may be
    a deleted/added file, so only the escape check (resolve + ``is_relative_to``)
    runs.
    """
    normalized = (rel or "").strip().lstrip("/")  # git paths are posix, repo-relative
    resolved = (root / normalized).resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise Http404
    return normalized


class GitUncommittedProps(BaseModel):
    main_files: list[git_data.UncommittedFile]
    scratch_files: list[git_data.UncommittedFile] | None  # None when scratch/ isn't on disk yet


class GitDiffProps(BaseModel):
    title: str
    diff: str


class GitCommitListProps(BaseModel):
    commits: list[git_data.CommitSummary]
    pagination: git_data.GitPagination


class GitCommitProps(BaseModel):
    commit: git_data.CommitSummary
    files: list[git_data.CommitFile]


def _parse_page(request: HttpRequest) -> int:
    """``?page=`` as an int ≥ 1 (invalid/missing → 1)."""
    raw = request.GET.get("page", "1")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def git_uncommitted_list(request: HttpRequest) -> HttpResponseBase:
    """``GET /git/uncommitted/`` — uncommitted files for ``main`` and ``scratch``.

    ``main`` always exists; ``scratch`` is ``None`` when its repo isn't on disk
    yet (no ``createscratch``), so the page omits that section rather than
    404-ing.
    """
    require_superuser(request)
    props = GitUncommittedProps(
        main_files=git_data.uncommitted("main"),
        scratch_files=(
            git_data.uncommitted("scratch") if git_data.worktree_exists("scratch") else None
        ),
    )
    return InertiaResponse(
        request,
        "GitUncommitted",
        {"props": props.model_dump(mode="json")},
    )


def git_uncommitted_diff(request: HttpRequest, worktree: str, rel: str) -> HttpResponseBase:
    """``GET /git/uncommitted/<worktree>/<path>`` — one uncommitted file's diff."""
    require_superuser(request)
    worktree = _worktree_or_404(worktree)
    root = git_data.worktree_root(worktree)
    if not root.is_dir():
        raise Http404  # worktree repo missing (e.g. no scratch/ yet)
    path = _confined_to_repo(rel, root)
    diff = git_data.diff_uncommitted(path, worktree)
    if diff is None:
        raise Http404
    props = GitDiffProps(title=f"Uncommitted ({worktree}): {path}", diff=diff)
    return InertiaResponse(
        request,
        "GitDiff",
        {"props": props.model_dump(mode="json")},
    )


def git_commit_list(request: HttpRequest) -> HttpResponseBase:
    """``GET /git/commits?page=N`` — paginated commit list (25/page, newest first)."""
    require_superuser(request)
    commits, pagination = git_data.commits(_parse_page(request))
    props = GitCommitListProps(commits=commits, pagination=pagination)
    return InertiaResponse(
        request,
        "GitCommitList",
        {"props": props.model_dump(mode="json")},
    )


def git_commit_file_list(request: HttpRequest, commit_id: str) -> HttpResponseBase:
    """``GET /git/commits/<commit_id>`` — a commit's changed files."""
    require_superuser(request)
    found = _commit_or_404(commit_id)
    summary, files = found
    props = GitCommitProps(commit=summary, files=files)
    return InertiaResponse(
        request,
        "GitCommit",
        {"props": props.model_dump(mode="json")},
    )


def git_commit_file_diff(request: HttpRequest, commit_id: str, rel: str) -> HttpResponseBase:
    """``GET /git/commits/<commit_id>/<path>`` — a file's diff in a commit."""
    require_superuser(request)
    _commit_or_404(commit_id)  # validate + 404 on unknown commit
    path = _confined_to_repo(rel, git_data.worktree_root("main"))
    diff = git_data.diff_commit(commit_id, path)
    if diff is None:
        raise Http404
    props = GitDiffProps(title=f"{commit_id}: {path}", diff=diff)
    return InertiaResponse(
        request,
        "GitDiff",
        {"props": props.model_dump(mode="json")},
    )


def _commit_or_404(commit_id: str) -> tuple[git_data.CommitSummary, list[git_data.CommitFile]]:
    """Validate + resolve a commit id, 404 on a bad/unknown id."""
    if not _HEX_RE.match(commit_id):
        raise Http404
    found = git_data.commit(commit_id)
    if found is None:
        raise Http404
    return found
