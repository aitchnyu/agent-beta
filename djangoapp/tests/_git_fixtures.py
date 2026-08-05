"""Shared git-repo fixture for the ``/git`` viewer tests.

Both the Django-test-client suite (``tests/views/test_git.py``) and the
Playwright suite (``tests/playwright/test_git.py``) stand up the **same** real
``parent/main`` + ``parent/scratch`` temp repos and patch
``djangoapp.views.git_data._REPO_ROOT`` to ``main`` — mirroring the real layout
(``main/`` = the dev-server repo, ``scratch/`` = the scratch sibling
``./run createscratch`` builds). :class:`GitRepoMixin` does that build in its
``setUp`` (cooperatively chained before the real TestCase base), so the two
suites share one fixture; each test class keeps only its harness-specific auth.

Main history (newest last): root commit → modify+add → modify+delete, plus
uncommitted changes (a ``-``/``+`` modification + an untracked file). Scratch: a
baseline commit + an uncommitted modification + an untracked file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import patch

import git

if TYPE_CHECKING:
    from typing import Any


def _write(root: Path, rel: str, text: str) -> None:
    """Write ``root/rel`` (creating parent dirs) — for nested repo paths."""
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)


def _init_repo(root: Path, *, email: str, name: str) -> git.Repo:
    """``git init`` at ``root`` and set the committer identity. Returns the Repo."""
    repo = git.Repo.init(root)
    repo.git.config("user.email", email)
    repo.git.config("user.name", name)
    return repo


def _worktree_roots(test: TestCase) -> tuple[Path, Path]:
    """Create a temp ``parent/main`` + ``parent/scratch``; patch ``_REPO_ROOT``→main.

    Returns ``(main_root, scratch_root)`` — both empty (no identity, no
    commits); callers :func:`_init_repo` each and build history. The temp dir is
    removed and the patch undone on test exit (registered via ``test.addCleanup``).
    """
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    main_root = Path(tmp.name) / "main"
    scratch_root = Path(tmp.name) / "scratch"
    patcher = patch("djangoapp.views.git_data._REPO_ROOT", main_root)
    patcher.start()
    test.addCleanup(patcher.stop)
    return main_root, scratch_root


def _commit(repo: git.Repo, root: Path, files: dict[str, str], message: str) -> Any:  # noqa: ANN401 -- git.Repo.index.commit() has no first-class stub; Any is honest
    """Stage ``files`` (overwriting existing) and commit. ``files``: ``{rel: text}```."""
    for rel, text in files.items():
        _write(root, rel, text)
    repo.index.add(list(files))
    return repo.index.commit(message)


class GitRepoMixin(TestCase):
    """Cooperative mixin: builds the shared main+scratch repo fixture + ``_REPO_ROOT`` patch.

    Mix **first**, before the real TestCase base — ``InertiaTestCase`` for the
    views suite, ``BasePlaywrightTestCase`` for the browser suite. ``setUp``
    cooperatively calls ``super().setUp()`` (the real base's), then builds the
    fixture and exposes the three main commits + their short shas; the temp dir
    + patch are undone via ``addCleanup``. Subclasses keep doing their own auth
    in their own ``setUp`` (after ``super().setUp()``).

    History (the single source both suites assert against):
    - Main commits (newest first):
      - C — modifies TodoApp/app.py, deletes TodoApp/endpoints.py
      - B — modifies TodoApp/app.py, adds TodoApp/endpoints.py
      - A — root commit: adds TodoApp/app.py
    - Main uncommitted: TodoApp/app.py modified, TodoApp/notes.md untracked
    - Scratch uncommitted: TodoApp/scratch_only.py modified, TodoApp/scratch_notes.md untracked
    """

    commit_a: Any  # git.Commit — the root commit (all files "added")
    commit_b: Any
    commit_c: Any
    short_a: str
    short_b: str
    short_c: str

    def setUp(self) -> None:
        super().setUp()
        main_root, scratch_root = _worktree_roots(self)
        main = _init_repo(main_root, email="t@example.com", name="Tester")

        self.commit_a = _commit(
            main,
            main_root,
            {"TodoApp/app.py": 'def main():\n    print("hello")\n'},
            "Initial TodoApp",
        )
        self.commit_b = _commit(
            main,
            main_root,
            {
                "TodoApp/app.py": 'def main():\n    print("hi")\n    return x\n',
                "TodoApp/endpoints.py": 'def greet(name):\n    return f"Hello, {name}"\n',
            },
            "Add create endpoint",
        )
        # commit C: modify app.py + delete endpoints.py (a modify+delete commit).
        main.index.remove(["TodoApp/endpoints.py"])
        (main_root / "TodoApp/endpoints.py").unlink()
        self.commit_c = _commit(
            main,
            main_root,
            {"TodoApp/app.py": 'def main():\n    print("bye")\n    return x\n'},
            "Add delete endpoint",
        )
        # uncommitted: modify app.py (bye→final: one `-` and one `+` line) + add
        # untracked notes.md.
        _write(main_root, "TodoApp/app.py", 'def main():\n    print("final")\n    return x\n')
        _write(main_root, "TodoApp/notes.md", "todo\n")

        # scratch worktree — baseline commit + uncommitted changes.
        scratch = _init_repo(scratch_root, email="scratch@example.com", name="Scratch")
        _commit(scratch, scratch_root, {"TodoApp/scratch_only.py": "x = 0\n"}, "scratch baseline")
        _write(scratch_root, "TodoApp/scratch_only.py", "x = 0\nx = 1\n")
        _write(scratch_root, "TodoApp/scratch_notes.md", "wip\n")

        self.short_a = self.commit_a.hexsha[:7]
        self.short_b = self.commit_b.hexsha[:7]
        self.short_c = self.commit_c.hexsha[:7]
