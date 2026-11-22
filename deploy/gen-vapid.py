#!/usr/bin/env python3
"""gen-vapid.py — mint a VAPID private key as the base64url P-256 scalar.

stdout is what settings/pywebpush consume (the public half is derived at
call time — djangoapp.models.notifications.vapid_public_key).

Called by BOTH provisioners: `run init` (repo copy — uv's ephemeral
--no-project --with cryptography env, since the mint runs before
`uv sync`) and inside-vm.sh provision (seeded repo copy — the system
python3 + apt's python3-cryptography; the venv arrives at phase 9).
Fails loudly — callers must refuse to proceed.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric import ec


def mint_vapid_scalar() -> str:
    """Return a fresh P-256 private scalar, base64url-encoded and unpadded."""
    private_value = ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value
    return base64.urlsafe_b64encode(private_value.to_bytes(32, "big")).rstrip(b"=").decode()


if __name__ == "__main__":
    print(mint_vapid_scalar())  # noqa: T201 — stdout IS the product (the mint's scalar)
