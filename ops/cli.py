"""desmo-ops — the CLI front door.

``./run`` wraps this module (``uv run python -m ops.cli <command> [args…]``).
The command classes live beside their code — ops/scratch.py,
ops/testsuite.py; this module only collects them and dispatches by the
COMMANDS dict. argparse owns the arguments: the first word picks the
command, everything after passes to it.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ops import scratch, testsuite

if TYPE_CHECKING:
    from ops.command import Command

COMMANDS: dict[str, Command] = {
    command.name: command
    for command in (
        scratch.Createscratch(),
        scratch.Deployscratch(),
        scratch.Cleanscratch(),
        testsuite.Test(),
        testsuite.Playwrighttest(),
        testsuite.Screenshots(),
    )
}


def main(argv: list[str]) -> None:
    """Dispatch: the first word names the command; its parser owns the rest.

    Flags the command's parser doesn't know pass through to the tool it
    wraps (manage.py test) — parse_known_args, not a closed grammar.
    """
    scratch.configure_output()
    if len(argv) < 1 or argv[0] not in COMMANDS:
        names = "|".join(COMMANDS)
        print(f"usage: python -m ops.cli <{names}> (run delegates automatically)", file=sys.stderr)
        raise SystemExit(1)
    command = COMMANDS[argv[0]]
    args, extra = command.build_parser().parse_known_args(argv[1:])
    command.run(args, extra)


if __name__ == "__main__":
    main(sys.argv[1:])
