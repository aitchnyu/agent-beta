"""desmo-ops — the Python home of the scratch-lifecycle and test commands.

``./run`` wraps this module (``uv run python -m ops.cli <command> [args…]``);
checkframework1 builds its stage-3/4 scratch copies through the same CLI.
Each command owns its parser; main() dispatches by the COMMANDS dict only.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from ops import scratch, testsuite

if TYPE_CHECKING:
    from collections.abc import Callable


def _plain_parser(command: str, description: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=f"ops.cli {command}", description=description)


def _labels_parser(command: str, description: str, labels_help: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"ops.cli {command}", description=description)
    parser.add_argument("labels", nargs="*", metavar="label", help=labels_help)
    return parser


_test_parser = _labels_parser(
    "test",
    "Django unit suite (playwright tests excluded).",
    "test labels for manage.py test",
)
_test_parser.add_argument(
    "--full", action="store_true", help="full run: fresh DB, full logs, no failfast"
)

COMMANDS: dict[str, tuple[argparse.ArgumentParser, Callable[[argparse.Namespace, list[str]], None]]] = {
    "createscratch": (
        _plain_parser("createscratch", "Fresh scratch/ of main/ for editing + diffing."),
        lambda _args, _extra: scratch.createscratch(),
    ),
    "deployscratch": (
        _plain_parser("deployscratch", "Run the check battery in scratch, then deploy to main/."),
        lambda _args, _extra: scratch.deployscratch(),
    ),
    "cleanscratch": (
        _plain_parser("cleanscratch", "Remove scratch/ and its /tmp/desmo contents."),
        lambda _args, _extra: scratch.cleanscratch(),
    ),
    "test": (
        _test_parser,
        lambda args, extra: testsuite.test(args.labels, extra, is_full=args.full),
    ),
    "playwrighttest": (
        _labels_parser(
            "playwrighttest",
            "Playwright e2e suite (builds the frontend first).",
            "test labels; none = full suite",
        ),
        lambda args, extra: testsuite.playwrighttest(args.labels, extra),
    ),
    "screenshots": (
        _labels_parser(
            "screenshots",
            "Regenerate the README PNGs in docs/screenshots/.",
            "test labels for manage.py test",
        ),
        lambda args, extra: testsuite.screenshots(args.labels, extra),
    ),
}


def main(argv: list[str]) -> None:
    """Dispatch: the first word names the command; its parser owns the rest.

    Flags the per-command parser doesn't know pass through to the tool it
    wraps (manage.py test) — parse_known_args, not a closed grammar.
    """
    scratch.configure_output()
    if len(argv) < 1 or argv[0] not in COMMANDS:
        names = "|".join(COMMANDS)
        print(f"usage: python -m ops.cli <{names}> (run delegates automatically)", file=sys.stderr)
        raise SystemExit(1)
    parser, run = COMMANDS[argv[0]]
    args, extra = parser.parse_known_args(argv[1:])
    run(args, extra)


if __name__ == "__main__":
    main(sys.argv[1:])
