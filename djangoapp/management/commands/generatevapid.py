from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from py_vapid import Vapid

from djangoapp.models.notifications import is_push_enabled, vapid_public_key, vapid_subject

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric import ec


class Command(BaseCommand):
    """Generate a VAPID keypair for Web Push and print the env line.

    Output is copy-paste ready for .env / .env.vm (VAPID_PRIVATE_KEY). The
    private key is a single-token base64url string (env-file and
    systemd-safe — a PEM would span lines); the public key is DERIVED from
    it at call time (djangoapp.models.notifications.vapid_public_key), and
    the RFC 8292 contact subject is derived from the first superuser's
    email (djangoapp.models.notifications.vapid_subject) — so the private
    key is the ONLY value to configure. Run once per deployment; the pair
    identifies this server to the push services.
    """

    help = "Generate a VAPID keypair for Web Push and print the env line."

    def add_arguments(self, parser: Any) -> None:  # noqa: ANN401 # Django passes **options as an untyped command flag bag
        parser.add_argument(
            "--check",
            action="store_true",
            help=(
                "Verify the configured VAPID_PRIVATE_KEY (and print what it "
                "derives to) instead of generating a new pair."
            ),
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as an untyped command flag bag
        if options["check"]:
            self._check()
            return
        vapid = Vapid()
        vapid.generate_keys()
        private_key: ec.EllipticCurvePrivateKey | None = vapid.private_key
        if private_key is None:
            msg = "py_vapid did not produce a keypair."
            raise CommandError(msg)
        # Raw scalar (32-byte big-endian d) as base64url — the exact string
        # pywebpush and vapid_public_key() both accept.
        raw = private_key.private_numbers().private_value.to_bytes(32, "big")
        private_b64 = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        self.stdout.write(
            self.style.SUCCESS(
                "Paste into .env (dev) and .env.vm (VM) — one pair per deployment.\n"
                "The public key and the mailto: subject are derived\n"
                "automatically; nothing else to fill.\n\n"
                f'VAPID_PRIVATE_KEY="{private_b64}"'
            )
        )

    def _check(self) -> None:
        """Report what the current env derives to (or why push is off)."""
        if not settings.VAPID_PRIVATE_KEY:
            self.stdout.write("VAPID_PRIVATE_KEY: unset — browser push off (in-app only).")
            return
        if not is_push_enabled():
            self.stdout.write("VAPID_PRIVATE_KEY: set but sentinel — treat as unset.")
            return
        self.stdout.write(f"VAPID_PRIVATE_KEY: configured (public key {vapid_public_key()[:12]}…)")
        self.stdout.write(
            f"subject (first superuser): {vapid_subject() or '— none with an email; push skipped'}"
        )
