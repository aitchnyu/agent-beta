"""The env-file contract tests (see the templates' MAINTAIN-CONSISTENCY note).

.env.example (dev) and deploy/template.env (VM) must carry the same KEY set
— active or commented — and the VM template's assignment lines must stay
bare (systemd EnvironmentFile parses them literally).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_DEV_TEMPLATE = _REPO / ".env.example"
_VM_TEMPLATE = _REPO / "deploy" / "template.env"

# KEY= at line start, optionally commented — the contract counts both.
_KEY_LINE = re.compile(r"^#?\s*([A-Z][A-Z0-9_]*)=")


def _keys(path: Path) -> set[str]:
    return {
        match.group(1)
        for match in (
            _KEY_LINE.match(line) for line in path.read_text(encoding="utf-8").splitlines()
        )
        if match
    }


class EnvParityTests(unittest.TestCase):
    """The two env templates.

    - test_dev_and_vm_templates_share_the_same_key_set, no key may exist in only one file
    - test_known_required_keys_present, the keys settings reads unconditionally are there
    - test_vm_assignment_lines_are_bare, systemd EnvironmentFile parses them literally
    """

    def test_dev_and_vm_templates_share_the_same_key_set(self) -> None:
        dev = _keys(_DEV_TEMPLATE)
        vm = _keys(_VM_TEMPLATE)
        self.assertEqual(
            dev,
            vm,
            f"keys only in dev: {sorted(dev - vm)}; only in vm: {sorted(vm - dev)}",
        )

    def test_known_required_keys_present(self) -> None:
        for required in (
            "LOG_LEVEL",
            "SECRET_KEY",
            "DB_PASSWORD",
            "VAPID_PRIVATE_KEY",
            "REDIS_URL",
        ):
            with self.subTest(key=required):
                self.assertIn(required, _keys(_DEV_TEMPLATE))
                self.assertIn(required, _keys(_VM_TEMPLATE))

    def test_vm_assignment_lines_are_bare(self) -> None:
        assignment = re.compile(r"^[A-Z][A-Z0-9_]*=")
        offenders = [
            line
            for line in _VM_TEMPLATE.read_text(encoding="utf-8").splitlines()
            if assignment.match(line) and " #" in line
        ]
        self.assertEqual(
            offenders, [], "template.env assignment lines must carry no inline comments"
        )
