from __future__ import annotations

from io import StringIO

from django.core.management import call_command

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase


class DbStateCommandTests(BaseTestCase):
    """``dbstate`` read-only snapshot of the app database.

    - test_output_lists_tables_migrations_users, the three sections a
      hand-rolled probe used to answer: tables, applied migrations, users
    - test_user_counts_include_superusers, USERS splits total vs
      superuser counts
    """

    def test_output_lists_tables_migrations_users(self) -> None:
        """A migrated DB with a user renders all three sections.

        - stdout carries the TABLES header, with auth_user among the rows
        - the MIGRATIONS header is followed by a per-app
          "N applied; last = X" line for djangoapp
        - the USERS line counts exactly the one non-superuser created here
        """
        User.objects.create_user(username="snapshot-user", email="snapshot@example.com")
        out = StringIO()
        call_command("dbstate", stdout=out)
        text = out.getvalue()
        self.assertIn("TABLES (approx rows)", text)
        self.assertIn("auth_user", text)
        self.assertIn("MIGRATIONS (ourapp / djangoapp / auth / contenttypes)", text)
        self.assertRegex(text, r"djangoapp: \d+ applied; last = \S+")
        self.assertIn("USERS  1 total, 0 superuser(s)", text)

    def test_user_counts_include_superusers(self) -> None:
        """The USERS line counts total and superuser rows separately.

        - with one plain user and one superuser seeded, USERS reports
          2 total and 1 superuser
        """
        User.objects.create_user(username="plain", email="plain@example.com")
        User.objects.create_superuser(username="root", email="root@example.com")
        out = StringIO()
        call_command("dbstate", stdout=out)
        self.assertIn("USERS  2 total, 1 superuser(s)", out.getvalue())
