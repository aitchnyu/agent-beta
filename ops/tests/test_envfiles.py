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


def _mandatory_settings_keys() -> set[str]:
    """Return the keys settings.py reads with ``os.environ[...]`` — the hard-required set."""
    source = (_REPO / "djangoproject" / "settings.py").read_text(encoding="utf-8")
    return set(re.findall(r'os\.environ\["([A-Z][A-Z0-9_]*)"\]', source))


class EnvParityTests(unittest.TestCase):
    """The two env templates.

    - test_dev_and_vm_templates_share_the_same_key_set, no key may exist in only one file
    - test_settings_mandatory_keys_are_in_both_templates, every os.environ[...] key settings reads is staged
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

    def test_settings_mandatory_keys_are_in_both_templates(self) -> None:
        required = _mandatory_settings_keys()
        self.assertTrue(required, "no os.environ[...] reads found — the regex went stale")
        for name, template in (("dev", _DEV_TEMPLATE), ("vm", _VM_TEMPLATE)):
            with self.subTest(template=name):
                missing = required - _keys(template)
                self.assertFalse(
                    missing, f"settings requires but template lacks: {sorted(missing)}"
                )

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
