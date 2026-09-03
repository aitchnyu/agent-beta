from io import StringIO

from django.core.management import call_command
from django.test import override_settings

from djangoapp.tests._base import BaseTestCase


class HostnamesCommandTests(BaseTestCase):
    """``hostnames`` prints the deployed hostnames, comma-separated.

    steer.md's linking rule makes this command the sole source for the
    absolute base URL (``https://<first hostname>``) — empty output would
    push the agent to guess a hostname, exactly what the rule forbids.

    - test_prints_hostnames_comma_separated, multiple hosts join with commas, first stays first
    - test_single_hostname, one host prints bare
    - test_empty_and_wildcard_entries_filtered, "" and "*" drop out
    - test_no_usable_hosts_prints_empty, degenerate config prints an empty line (honest no-output)
    """

    def _run(self) -> str:
        out = StringIO()
        call_command("hostnames", stdout=out)
        return out.getvalue()

    def test_prints_hostnames_comma_separated(self) -> None:
        """Multiple hosts join with commas; order preserved (first = URL base)."""
        with override_settings(ALLOWED_HOSTS=["app.local", "192.168.1.5"]):
            self.assertEqual(self._run(), "app.local,192.168.1.5\n")

    def test_single_hostname(self) -> None:
        """A single host prints bare."""
        with override_settings(ALLOWED_HOSTS=["app.local"]):
            self.assertEqual(self._run(), "app.local\n")

    def test_empty_and_wildcard_entries_filtered(self) -> None:
        """Empty strings and the catch-all "*" drop out of the output."""
        with override_settings(ALLOWED_HOSTS=["*", "app.local", ""]):
            self.assertEqual(self._run(), "app.local\n")

    def test_no_usable_hosts_prints_empty(self) -> None:
        """Degenerate config (only "*" / empties) prints an empty line, no error."""
        with override_settings(ALLOWED_HOSTS=["*", ""]):
            self.assertEqual(self._run(), "\n")
