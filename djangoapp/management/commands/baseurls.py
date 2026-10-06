from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Print the deployed origins (BASE_URLS), comma-separated.

    Lets the agent (and the operator) build shareable absolute URLs
    without reading the credentials env — steer.md's linking rule consumes
    this output. The origins are ``BASE_URLS`` (scheme + host [+ port]);
    the FIRST is the link base — use it verbatim.
    """

    help = "Print the deployed origins (BASE_URLS), comma-separated."

    def handle(self, *args: object, **options: object) -> None:  # noqa: ARG002 # Django's handle signature
        self.stdout.write(",".join(url for url in settings.BASE_URLS if url))
