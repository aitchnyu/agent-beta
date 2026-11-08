"""The feature close-out audit — steer.md stage [5] as a command.

One PASS/FAIL line per checklist item: clean tree, migrations applied,
scratch gone. The agent runs it at the
close-out, fixes anything red, then writes the one-sentence report.
Pure reads — it never mutates anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ops import scratch, shell
from ops.command import Command
from ops.scratch import MAIN_DIR, SCRATCH_DIR, _load_env, porcelain_paths

if TYPE_CHECKING:
    import argparse


def _audit_lines() -> list[tuple[bool, str]]:
    """Run every checklist check and return (ok, label) pairs, in order."""
    results: list[tuple[bool, str]] = []

    # 1. Clean tree — ignored runtime state never appears in porcelain,
    #    so anything listed here is real drift.
    exit_code, status = shell.capture(
        "git",
        "-c",
        "core.quotePath=false",
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
        cwd=MAIN_DIR,
    )
    if exit_code != 0:
        results.append((False, f"tree: git status failed in {MAIN_DIR}"))
    else:
        files = porcelain_paths(status)
        results.append(
            (not files, "tree clean" if not files else f"tree dirty: {', '.join(files)}")
        )

    # 2. Migrations applied to the live DB (migrate --check exits nonzero
    #    when migrations are pending). --no-sync matches the deploy tail:
    #    the audit goes green/red for the right reason, never a sync stall.
    exit_code, _ = shell.capture(
        "uv",
        "run",
        "--no-sync",
        "python",
        "manage.py",
        "migrate",
        "--check",
        "--noinput",
        *scratch.DJANGO_NO_COLOR,
        cwd=MAIN_DIR,
    )
    results.append(
        (
            exit_code == 0,
            "migrations applied"
            if exit_code == 0
            else "pending migrations — run ./run djangomanage migrate",
        )
    )

    # 3. Scratch gone (./run cleanscratch discards it).
    gone = not SCRATCH_DIR.is_dir()
    results.append(
        (
            gone,
            "scratch gone" if gone else "scratch still present: ./run cleanscratch",
        )
    )
    return results


class Postdeploychecks(Command):
    """Audit the feature close-out: clean tree, migrations applied, scratch gone.

    Prints one PASS/FAIL line per checklist item and exits nonzero on
    any FAIL. Pure reads — never mutates anything.
    """

    name = "postdeploychecks"

    @staticmethod
    def run(_args: argparse.Namespace, _extra: list[str]) -> None:
        _load_env()
        results = _audit_lines()
        for ok, label in results:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failures = sum(1 for ok, _ in results if not ok)
        print(f"postdeploychecks: {len(results) - failures}/{len(results)} green")
        if failures:
            raise SystemExit(1)
