"""checkframework1 — the dev-side gate, dispatched from run's thin shim.

The full gate: lint + types in main/, then FOUR test stages — 1-3 under
coverage, merged into one report:

1. unit suite (main/; project tests self-skip — no RUN_PROJECT_TESTS)
2. Playwright pass (main/; StaticLiveServerTestCase is an in-process
   thread, so plain coverage captures the server code)
3. project tier (scratch + testapp overlay, RUN_PROJECT_TESTS=1) — the
   concrete-BaseModel flows: save_plus/update logs/FileField cleanup/manage
4. reference tier (scratch + docs/reference overlay) — the reference
   app validated FOR ITS OWN SAKE (its own tests over a built bundle);
   NOT under coverage: it must not contribute to the merged report

The bash side (run) keeps the context guards — main/'s ./run only, never
on the VM — plus setenv; everything here runs with the ambient env and
inherits stdio (banners and tool output stream, nothing is captured).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from typing import TYPE_CHECKING

from ops import shell
from ops.command import Command
from ops.scratch import MAIN_DIR, SCRATCH_DIR, Createscratch, step_banner, test_redis_env

if TYPE_CHECKING:
    from pathlib import Path

# The merged report's measured floor. Raise when coverage improves; never
# lower it to make a regression pass.
COVERAGE_RATCHET = "98.70"

FRONTEND_DIR = MAIN_DIR / "frontend"
STAGE_DIR = MAIN_DIR / ".coverage-stage"


def _banner(text: str) -> None:
    print(f"=== {text} ===")


def _tty() -> bool:
    return sys.stdout.isatty()


def _test_env() -> dict[str, str]:
    """Build the test-process environment: ambient + the isolated redis.

    REDIS_URL points at a nonzero DB — a test DB by clear_redis's rule —
    so tests can flush it freely (a bare manage.py test that sees the
    live DB 0 refuses loudly).
    """
    env = dict(os.environ)
    env.update(test_redis_env())
    return env


def _static_checks() -> None:
    ruff_color = "--color=always" if _tty() else "--color=never"
    mypy_color = "--color-output" if _tty() else "--no-color-output"
    django_color = [] if _tty() else ["--no-color"]

    print("Running ruff format --check (formatting drift)")
    shell.run("uv", "run", "ruff", "format", ruff_color, "--check")
    print("Running ruff check (lint)")
    shell.run("uv", "run", "ruff", "check", ruff_color)
    print("Running mypy for type checking")
    shell.run("uv", "run", "mypy", mypy_color, ".")

    print("Running test under coverage (stage 1/4: unit suite)")
    shell.run(
        "uv",
        "run",
        "coverage",
        "run",
        "--parallel-mode",
        "--source=djangoapp,ourapp",
        "manage.py",
        "test",
        *django_color,
        "--exclude-tag",
        "playwright",
        "--noinput",
        env=_test_env(),
    )


def _frontend() -> None:
    print("Running frontend linting")
    shell.run("npm", "run", "lint", cwd=FRONTEND_DIR)
    print("Running frontend build (type-check + vite, bundle for the Playwright pass)")
    shell.run("npm", "run", "build", cwd=FRONTEND_DIR)


def _playwright_stage() -> None:
    django_quiet = [] if _tty() else ["--no-color"]
    print("Running Playwright tests under coverage (stage 2/4)")
    shell.run(
        "uv",
        "run",
        "coverage",
        "run",
        "--parallel-mode",
        "--source=djangoapp,ourapp",
        "manage.py",
        "test",
        *django_quiet,
        "--tag",
        "playwright",
        "--noinput",
        env=_test_env(),
    )


def _overlay_app(source: Path) -> None:
    """Wholesale replace scratch's ourapp/ — same semantics as rsync --delete."""
    shell.run("rsync", "-a", "--delete", f"{source / 'ourapp'}/", f"{SCRATCH_DIR / 'ourapp'}/")


def _stage_fragments() -> None:
    """Move the scratch run's coverage fragments out.

    The next createscratch wipes scratch; only a successful combine
    deletes the staging dir.
    """
    for fragment in SCRATCH_DIR.glob(".coverage.*"):
        shutil.move(str(fragment), STAGE_DIR / fragment.name)


def _project_tier() -> None:
    _banner("stage 3/4: project tests over the test app (scratch copy)")
    # The overlay replaces ourapp/ wholesale with fixture code — measure
    # --source=djangoapp only (never that ourapp/).
    Createscratch.run(argparse.Namespace(), [])
    _overlay_app(MAIN_DIR / "djangoapp" / "tests" / "testapp")
    env = _test_env()
    env["RUN_PROJECT_TESTS"] = "1"
    django_quiet = [] if _tty() else ["--no-color"]
    # typecheck only — lintfix would rewrite files and corrupt the merged
    # line data (main already ran the ruff gates).
    shell.run("./run", "typecheck", cwd=SCRATCH_DIR)
    shell.run(
        "uv",
        "run",
        "coverage",
        "run",
        "--parallel-mode",
        "--source=djangoapp",
        "manage.py",
        "test",
        *django_quiet,
        "--exclude-tag",
        "playwright",
        "--noinput",
        cwd=SCRATCH_DIR,
        env=env,
    )
    _stage_fragments()


def _reference_tier() -> None:
    _banner("stage 4/4: reference app's own tests (scratch copy; not measured)")
    Createscratch.run(argparse.Namespace(), [])
    _overlay_app(MAIN_DIR / "docs" / "reference")
    # The reference app ships its own app-side frontend (pages, components,
    # schemas, styles); overlay them INTO the scratch's app/ tree so its
    # pages are in the built bundle. System files stay the tree's own.
    for name in ("pages", "components", "schemas", "styles"):
        src = MAIN_DIR / "docs" / "reference" / "frontend" / "src" / name
        dst = SCRATCH_DIR / "frontend" / "src" / "app" / name
        shell.run("rsync", "-a", f"{src}/", f"{dst}/")
    shell.run("npm", "run", "build", cwd=SCRATCH_DIR / "frontend")
    shell.run("./run", "test", "--full", "ourapp", cwd=SCRATCH_DIR)
    # Green: drop scratch. On failure the exception aborts earlier, leaving
    # it behind for inspection.
    shutil.rmtree(SCRATCH_DIR)


def _merge_report() -> None:
    print("Merging coverage from all four stages")
    # combine folds the testapp scratch's djangoapp/ onto main's via
    # [tool.coverage.paths] in pyproject.toml.
    shell.run("uv", "run", "coverage", "combine", ".", str(STAGE_DIR))
    # The staged fragments are folded into .coverage now — drop the staging dir.
    shutil.rmtree(STAGE_DIR)
    # Ratchet: the merged report must hold the measured floor.
    shell.run("uv", "run", "coverage", "report", "-m", f"--fail-under={COVERAGE_RATCHET}")
    shell.run("uv", "run", "coverage", "html")
    print("Coverage report: htmlcov/index.html")


def main() -> None:
    # Reset the fragment staging dir (gitignored) — a previous gate run
    # that died before combine leaves it behind. Same for main's own
    # .coverage.* strays: only a successful combine deletes them, and
    # folding stale ones in would corrupt the merged report.
    shutil.rmtree(STAGE_DIR, ignore_errors=True)
    STAGE_DIR.mkdir()
    for stray in MAIN_DIR.glob(".coverage.*"):
        stray.unlink()

    _static_checks()
    step_banner("lint+types+unit")
    _frontend()
    step_banner("frontend")
    _playwright_stage()
    step_banner("playwright")
    _project_tier()
    step_banner("project tier")
    _reference_tier()
    step_banner("reference tier")
    _merge_report()
    step_banner("coverage report")


class Checkframework1(Command):
    """The full dev-side gate — dispatched as an ops.cli verb by run."""

    name = "checkframework1"

    @staticmethod
    def run(_args: argparse.Namespace, _extra: list[str]) -> None:
        main()


if __name__ == "__main__":
    # The old bash body guarded scratch's own ./run copy the same way the
    # shim does — belt and braces here, cheap and loud.
    if MAIN_DIR == SCRATCH_DIR:
        shell.die("Refusing: this is scratch's own tree — run checkframework1 from main/.")
    main()
