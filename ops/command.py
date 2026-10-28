"""The Command base classes every ops.cli subcommand implements.

A command is its name plus its docstring (the help text); build_parser()
makes the argparse parser and run() executes the parsed command. The
classes live beside their code (ops/scratch.py, ops/testsuite.py) —
ops/cli.py only collects and dispatches them.
"""

from __future__ import annotations

import argparse


class Command:
    """One subcommand: a name, a parser, a run."""

    name: str

    def build_parser(self) -> argparse.ArgumentParser:
        """Build the command's parser — override to add arguments."""
        return argparse.ArgumentParser(prog=f"ops.cli {self.name}", description=self.__doc__)

    @staticmethod
    def run(args: argparse.Namespace, extra: list[str]) -> None:
        """Execute the parsed command (args + pass-through extra)."""


class LabelsCommand(Command):
    """A command that also takes test labels (handed to manage.py test)."""

    labels_help = "test labels for manage.py test"

    def build_parser(self) -> argparse.ArgumentParser:
        """Build the command's parser plus the labels positional."""
        parser = super().build_parser()
        parser.add_argument("labels", nargs="*", metavar="label", help=self.labels_help)
        return parser
