"""deploy/gen-vapid.py — the provision-time VAPID mint, validated.

Every case runs the script exactly as both callers do — as a script,
capturing stdout — so the tests pin the real surface: exit 0, empty
stderr, one line, the base64url unpadded P-256 scalar pywebpush derives
a key from (the same acceptance path djangoapp.models.notifications
uses).

No import-by-path: importing deploy/ tooling would grow a __pycache__
dir there.

sys.executable is NEITHER real invocation (uv --no-project pre-venv on
dev, system python3 on the VM) — those stay dev/VM-only by
construction.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

_REPO = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO / "deploy" / "gen-vapid.py"


def _run_mint() -> subprocess.CompletedProcess[str]:
    """Execute the mint script once; check=True turns failure into a test error."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT)], capture_output=True, text=True, check=True
    )


class MintVapidScalarTests(unittest.TestCase):
    """The mint script's stdout contract.

    - test_stdout_is_exactly_one_valid_line, nothing pollutes the captured value
    - test_each_mint_is_fresh, no constant or replayed output
    - test_scalar_is_a_valid_p256_private_key, derive_private_key's range check
    """

    def test_stdout_is_exactly_one_valid_line(self) -> None:
        completed = _run_mint()
        self.assertEqual(completed.stderr, "")
        self.assertRegex(completed.stdout, r"\A[A-Za-z0-9_-]{43}\n\Z")

    def test_each_mint_is_fresh(self) -> None:
        self.assertNotEqual(_run_mint().stdout, _run_mint().stdout)

    def test_scalar_is_a_valid_p256_private_key(self) -> None:
        scalar = _run_mint().stdout.strip()
        padded = scalar + "=" * (-len(scalar) % 4)
        raw = base64.urlsafe_b64decode(padded.encode())
        self.assertEqual(len(raw), 32)
        # derive_private_key raises unless 0 < scalar < curve order — the
        # exact acceptance pywebpush applies to settings' VAPID_PRIVATE_KEY.
        ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
