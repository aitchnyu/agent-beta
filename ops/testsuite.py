"""The ``./run test`` / ``playwrighttest`` / ``screenshots`` commands.

``./run`` calls ``uv run python -m ops.cli <command> …`` after ``setenv``,
so the app environment is inherited. Every Django suite runs on the
isolated test redis (DB 2, never the live DB 0).

``test`` is built for the agent's edit-check loop: quiet logs, stop at
the first failure, and reuse the test database while no migration
changed. ``test --full`` is the slow, safe run: full logs, no early
stop, database rebuilt from scratch — the gates use that.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from ops import scratch, shell

if TYPE_CHECKING:
    from collections.abc import Sequence

# The executing tree's migration trees (main/ or scratch/ — whichever's
# ./run dispatched) — same trees the Django runner will migrate.
_MIGRATION_TREES = (
    scratch.MAIN_DIR / "djangoapp" / "migrations",
    scratch.MAIN_DIR / "ourapp" / "migrations",
)
_MARKER = Path("/tmp/desmo/test-migrations.sha")


def _hash_migration_trees(trees: Sequence[Path], *, relative_to: Path) -> str:
    """Hash the given migration trees (file paths + contents), sorted.

    Any new, edited, renamed, or deleted migration changes the hash.
    """
    digest = hashlib.sha256()
    for tree in trees:
        for path in sorted(tree.glob("*.py")):
            digest.update(str(path.relative_to(relative_to)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _migrations_hash() -> str:
    """Hash both of this tree's migration trees."""
    return _hash_migration_trees(_MIGRATION_TREES, relative_to=scratch.MAIN_DIR)


def test(labels: Sequence[str], extra: Sequence[str], *, is_full: bool) -> None:
    """Run the Django unit suite (playwright tests excluded).

    ``is_full`` selects the full, safe run (see the module docstring);
    ``extra`` flags pass through to manage.py test.
    """
    env = scratch.test_redis_env()
    flags: list[str] = ["--exclude-tag", "playwright", "--noinput"]
    digest = ""
    if not is_full:
        env["LOG_LEVEL"] = "WARNING"
        digest = _migrations_hash()
        keepdb = _MARKER.is_file() and _MARKER.read_text(encoding="utf-8").strip() == digest
        flags.append("--failfast")
        if keepdb:
            flags.append("--keepdb")
    shell.run(
        "uv", "run", "manage.py", "test", *scratch.DJANGO_NO_COLOR, *flags, *labels, *extra, env=env
    )
    if not is_full:
        _MARKER.parent.mkdir(parents=True, exist_ok=True)
        _MARKER.write_text(digest + "\n", encoding="utf-8")


def _built_frontend() -> None:
    """Rebuild the frontend bundle the browser suites test against."""
    shell.run("npm", "run", "build", cwd=scratch.MAIN_DIR / "frontend")


def playwrighttest(labels: Sequence[str], extra: Sequence[str] = ()) -> None:
    """Run the Playwright e2e suite (builds the frontend first).

    A test label runs just that module; no label runs the whole suite.
    """
    _built_frontend()
    shell.run(
        "uv",
        "run",
        "manage.py",
        "test",
        *scratch.DJANGO_NO_COLOR,
        "--tag",
        "playwright",
        "--noinput",
        *labels,
        *extra,
        env=scratch.test_redis_env(),
    )


def screenshots(labels: Sequence[str], extra: Sequence[str] = ()) -> None:
    """Regenerate the README PNGs in docs/screenshots/.

    The models-management shots also need the testapp overlay — see
    docs/screenshots/README.md.
    """
    env = scratch.test_redis_env()
    env["GENERATE_SCREENSHOTS"] = "1"
    _built_frontend()
    shell.run(
        "uv",
        "run",
        "manage.py",
        "test",
        *scratch.DJANGO_NO_COLOR,
        "--tag",
        "screenshots",
        "--noinput",
        *labels,
        *extra,
        env=env,
    )
