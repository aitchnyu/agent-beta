from io import StringIO

from django.core.management import call_command
from django.test import override_settings

from djangoapp.tests._base import BaseTestCase


class BaseUrlsCommandTests(BaseTestCase):
    """``baseurls`` prints the deployed origins (BASE_URLS), comma-separated.

    steer.md's linking rule makes this command the sole source for the
    absolute base URL — empty output would push the agent to guess an
    origin, exactly what the rule forbids.

    - test_prints_origins_comma_separated, multiple origins join with commas, first stays first
    - test_single_origin, one origin prints bare — scheme and port intact
    - test_empty_entries_filtered, empty strings drop out
    """

    def _run(self) -> str:
        out = StringIO()
        call_command("baseurls", stdout=out)
        return out.getvalue()

    def test_prints_origins_comma_separated(self) -> None:
        """Multiple origins join with commas; order preserved (first = link base)."""
        with override_settings(BASE_URLS=["https://app.local", "https://www.app.local"]):
            self.assertEqual(self._run(), "https://app.local,https://www.app.local\n")

    def test_single_origin(self) -> None:
        """A single origin prints bare — scheme and port intact."""
        with override_settings(BASE_URLS=["https://localhost:8000"]):
            self.assertEqual(self._run(), "https://localhost:8000\n")

    def test_empty_entries_filtered(self) -> None:
        """Empty strings drop out of the output."""
        with override_settings(BASE_URLS=["", "https://app.local"]):
            self.assertEqual(self._run(), "https://app.local\n")
