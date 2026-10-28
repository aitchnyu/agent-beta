"""Steer.md's management-command inventory must list every command.

Sessions improvise shell/python when they don't know a command exists
(Oct 28: hand-rolled user listings, each a permission prompt). This
test keeps steer's inventory honest against the commands dir.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_COMMANDS_DIR = _REPO / "djangoapp" / "management" / "commands"
_STEER = (_REPO / "agentconfig" / "steer.md").read_text(encoding="utf-8")


class ManagementCommandInventoryTests(unittest.TestCase):
    """steer.md vs djangoapp/management/commands/.

    - test_every_command_is_in_steer_inventory, no command may be unknown to steer
    - test_inventory_section_exists, the section header itself must be present
    """

    def test_every_command_is_in_steer_inventory(self) -> None:
        commands = sorted(
            path.stem for path in _COMMANDS_DIR.glob("*.py") if path.stem != "__init__"
        )
        self.assertTrue(commands, "no management commands found — the glob went stale")
        missing = [
            name
            for name in commands
            if f"`{name}" not in _STEER  # matches `createuser <first>… style entries
        ]
        self.assertEqual(missing, [], f"commands missing from steer's inventory: {missing}")

    def test_inventory_section_exists(self) -> None:
        self.assertIn("Management commands (synced", _STEER)
