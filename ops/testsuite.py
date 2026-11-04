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
_KEEPDB_MARKER = Path("/tmp/desmo/test-migrations.sha")


def _migrations_hash() -> str:
    """Hash both migration trees (file paths + contents), sorted.

    Any new, edited, renamed, or deleted migration changes the hash.
    """
    digest = hashlib.sha256()
    for tree in _MIGRATION_TREES:
        prefix = f"{tree.relative_to(scratch.MAIN_DIR)}/"
        digest.update(scratch.visible_files_hash(tree, prefix=prefix).encode())
    return digest.hexdigest()


def _keepdb_hint() -> bool:
    """True when the marker still matches the migration trees.

    While it matches, suites may pass --keepdb and reuse desmo_db_test
    instead of recreating it + replaying migrations before every run.
    Callers rewrite the marker after their run so the NEXT caller
    inherits the cache.
    """
    return scratch.marker_content_for(_KEEPDB_MARKER) == _migrations_hash()


def _write_keepdb_marker() -> None:
    """Record the current migration hash as the keepdb marker.

    Called after a suite ran against desmo_db_test: the next suite
    (test or playwrighttest) sees a matching hash and may --keepdb.
    """
    scratch.write_marker(_KEEPDB_MARKER, _migrations_hash())


class Test(LabelsCommand):
    """Django unit suite (playwright tests excluded)."""

    name = "test"

    @staticmethod
    def run(args: argparse.Namespace, extra: list[str]) -> None:
        env = scratch.test_redis_env()
        flags: list[str] = ["--exclude-tag", "playwright", "--noinput"]
        if not args.full:
            env["LOG_LEVEL"] = "WARNING"
            flags.append("--failfast")
            if _keepdb_hint():
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
            _write_keepdb_marker()

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
        scratch.built_frontend(scratch.MAIN_DIR / "frontend")
        # Same keepdb-by-marker caching as `test`: while no migration
        # changed, reuse desmo_db_test instead of recreating + replaying
        # migrations before every e2e run (the e2e fix loop pays this
        # boot per invocation otherwise).
        flags = ["--keepdb"] if _keepdb_hint() else []
        shell.run(
            "uv",
            "run",
            "manage.py",
            "test",
            *scratch.DJANGO_NO_COLOR,
            "--tag",
            "playwright",
            "--noinput",
            *flags,
            *args.labels,
            *extra,
            env=scratch.test_redis_env(),
        )
        _write_keepdb_marker()


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
        scratch.built_frontend(scratch.MAIN_DIR / "frontend")
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
