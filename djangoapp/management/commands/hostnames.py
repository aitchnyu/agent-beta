from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Print the deployed hostnames, comma-separated.

    Lets the agent (and the operator) derive the ABSOLUTE base URL for
    shareable links (``https://<first hostname>``) without reading the
    credentials env — steer.md's linking rule consumes this output. The
    hostnames come from ``ALLOWED_HOSTS``; the first entry is the one to
    build URLs with.
    """

    help = "Print the deployed hostnames (ALLOWED_HOSTS), comma-separated."

    def handle(self, *args: object, **options: object) -> None:  # noqa: ARG002 # Django's handle signature
        [h for h in settings.ALLOWED_HOSTS if h and h != "*"]
