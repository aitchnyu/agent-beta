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
from ops.command import LabelsCommand

if TYPE_CHECKING:
    import argparse

# The executing tree's migration trees (main/ or scratch/ — whichever's
# ./run dispatched) — same trees the Django runner will migrate.
_MIGRATION_TREES = (
    scratch.MAIN_DIR / "djangoapp" / "migrations",
    scratch.MAIN_DIR / "ourapp" / "migrations",
)
_MARKER = Path("/tmp/desmo/test-migrations.sha")


def _migrations_hash() -> str:
    """Hash both migration trees (file paths + contents), sorted.

    Any new, edited, renamed, or deleted migration changes the hash.
    """
    digest = hashlib.sha256()
    for tree in _MIGRATION_TREES:
        for path in sorted(tree.glob("*.py")):
            digest.update(str(path.relative_to(scratch.MAIN_DIR)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _built_frontend() -> None:
    """Rebuild the frontend bundle the browser suites test against."""
    shell.run("npm", "run", "build", cwd=scratch.MAIN_DIR / "frontend")


class Test(LabelsCommand):
    """Django unit suite (playwright tests excluded)."""

    name = "test"

    @staticmethod
    def run(args: argparse.Namespace, extra: list[str]) -> None:
        env = scratch.test_redis_env()
        flags: list[str] = ["--exclude-tag", "playwright", "--noinput"]
        digest = ""
        if not args.full:
            env["LOG_LEVEL"] = "WARNING"
            digest = _migrations_hash()
            keepdb = _MARKER.is_file() and _MARKER.read_text(encoding="utf-8").strip() == digest
            flags.append("--failfast")
            if keepdb:
                flags.append("--keepdb")
        shell.run(
            "uv",
            "run",
            "manage.py",
            "test",
            *scratch.DJANGO_NO_COLOR,
            *flags,
            *args.labels,
            *extra,
            env=env,
        )
        if not args.full:
            _MARKER.parent.mkdir(parents=True, exist_ok=True)
            _MARKER.write_text(digest + "\n", encoding="utf-8")

    def build_parser(self) -> argparse.ArgumentParser:
        """Build the labels parser plus the --full flag."""
        parser = super().build_parser()
        parser.add_argument(
            "--full", action="store_true", help="full run: fresh DB, full logs, no failfast"
        )
        return parser


class Playwrighttest(LabelsCommand):
    """Playwright e2e suite (builds the frontend first).

    A test label runs just that module; no label runs the whole suite.
    """

    name = "playwrighttest"
    labels_help = "test labels; none = full suite"

    @staticmethod
    def run(args: argparse.Namespace, extra: list[str]) -> None:
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
            *args.labels,
            *extra,
            env=scratch.test_redis_env(),
        )


class Screenshots(LabelsCommand):
    """Regenerate the README PNGs in docs/screenshots/.

    The models-management shots also need the testapp overlay — see
    docs/screenshots/README.md.
    """

    name = "screenshots"

    @staticmethod
    def run(args: argparse.Namespace, extra: list[str]) -> None:
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
            *args.labels,
            *extra,
            env=env,
        )
