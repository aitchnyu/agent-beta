"""Superuser-only read-only git viewer at ``/git/...`` over the project repo.

Mirrors ``/files``: superuser-only (404 otherwise), path-confined to the repo
root. Reads via :mod:`djangoapp.views.git_data` (GitPython); tests patch those
functions. Routes in :mod:`djangoapp.urls`.
"""

from __future__ import annotations

import re

from django.http import Http404, HttpRequest, HttpResponseBase
from inertia import InertiaResponse
from pydantic import BaseModel

from djangoapp.views import git_data, require_superuser

# Commit ids are full-or-short hex shas (4..40 chars); validated before use.
_HEX_RE = re.compile(r"^[0-9a-f]{4,40}$", re.IGNORECASE)


def _confined_to_repo(rel: str) -> str:
    """Return ``rel`` normalized if it stays inside the repo root, else raise Http404.

    Unlike :class:`PathWrapper`, existence is *not* required — a diff path may be
    a deleted/added file, so only the escape check (resolve + ``is_relative_to``)
    runs.
    """
    root = git_data._REPO_ROOT.resolve()  # noqa: SLF001 # shared repo-root constant
    normalized = (rel or "").strip().lstrip("/")  # git paths are posix, repo-relative
    resolved = (root / normalized).resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise Http404
    return normalized


class GitUncommittedProps(BaseModel):
    files: list[git_data.UncommittedFile]


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
    except TypeError, ValueError:
        return 1


def git_uncommitted_list(request: HttpRequest) -> HttpResponseBase:
    """``GET /git`` — uncommitted files in the repo."""
    require_superuser(request)
    props = GitUncommittedProps(files=git_data.uncommitted())
    return InertiaResponse(
        request,
        "GitUncommitted",
        {"props": props.model_dump(mode="json")},
    )


def git_uncommitted_diff(request: HttpRequest, rel: str) -> HttpResponseBase:
    """``GET /git/uncommitted/<path>`` — the unified diff of one uncommitted file."""
    require_superuser(request)
    path = _confined_to_repo(rel)
    diff = git_data.diff_uncommitted(path)
    if diff is None:
        raise Http404
    props = GitDiffProps(title=f"Uncommitted: {path}", diff=diff)
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
    path = _confined_to_repo(rel)
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
