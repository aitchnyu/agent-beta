"""desmo-ops — the Python home of the scratch-lifecycle commands.

``./run`` wraps this module for deployscratch/createscratch/cleanscratch
(``uv run python -m ops.cli <command> [args…]``); checkframework1 builds
its stage-3/4 scratch copies through the same CLI.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ops import scratch

if TYPE_CHECKING:
    from collections.abc import Callable

COMMANDS: dict[str, Callable[[], None]] = {
    "createscratch": scratch.createscratch,
    "deployscratch": scratch.deployscratch,
    "cleanscratch": scratch.cleanscratch,
}


def main(argv: list[str]) -> None:
    """Dispatch like run's tail: the first argument names the command.

    Extra arguments are ignored (the trio takes none).
    """
    scratch.configure_output()
    if len(argv) < 1 or argv[0] not in COMMANDS:
        names = "|".join(COMMANDS)
        print(f"usage: python -m ops.cli <{names}> (run delegates automatically)", file=sys.stderr)
        raise SystemExit(1)
    COMMANDS[argv[0]]()


if __name__ == "__main__":
    main(sys.argv[1:])
