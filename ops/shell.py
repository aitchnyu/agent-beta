"""The subprocess touchpoint for ops/ commands.

Children inherit stdio — a check step's output streams as it runs — and
exit codes are checked: on failure the command's own output has already
printed, and the process exits with its code. Captured output comes
back stripped. ``die`` is the guard idiom; ``run_step`` prints the re-run
hint on failure. The exact message strings are load-bearing — the VM
gate asserts them.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def die(msg: str) -> NoReturn:
    """Print msg to stderr and exit 1 — the ``Refusing:`` guard idiom."""
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def run(
    *cmd: str,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    quiet_stderr: bool = False,
) -> None:
    """Run cmd with inherited stdio; on failure exit with its code.

    check=False leaves failure handling to the caller.
    """
    process = subprocess.run(
        cmd,
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else dict(env),
        stderr=subprocess.DEVNULL if quiet_stderr else None,
        check=False,
    )
    if check and process.returncode != 0:
        raise SystemExit(process.returncode)


def capture(*cmd: str, cwd: Path | None = None, quiet_stderr: bool = True) -> tuple[int, str]:
    """Run cmd and return ``(returncode, stripped stdout)``.

    Use when stdout is needed; the caller owns the failure message.
    """
    process = subprocess.run(
        cmd,
        cwd=None if cwd is None else str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if quiet_stderr else None,
        check=False,
    )
    return process.returncode, (process.stdout or "").strip()


def run_step(
    retry: str,
    *cmd: str,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Run one check-battery step; on failure print the re-run hint, exit 1.

    ``retry`` is the command the agent re-runs in scratch to iterate on
    just that step.
    """
    process = subprocess.run(
        cmd,
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else dict(env),
        check=False,
    )
    if process.returncode != 0:
        print(file=sys.stderr)
        print(f"Step failed: {retry}", file=sys.stderr)
        print(
            "Iterate to fix it and run only that step, not the time-consuming deployscratch.",
            file=sys.stderr,
        )
        print("then re-run: ./run deployscratch (from main/)", file=sys.stderr)
        raise SystemExit(1)
