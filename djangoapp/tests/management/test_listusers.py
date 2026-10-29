from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase


class ListUsersCommandTests(BaseTestCase):
    """``listusers`` prints the user table, paginated; ``--exclude`` omits matching emails.

    - test_table_lists_every_column, first/last/email/staff/superuser all render
    - test_staff_and_superuser_markers, flags render as yes, absences as -
    - test_pagination_pages_and_past_last, fixed 100/page; a page past
      the last refuses
    - test_exclude_omits_matching_emails, --exclude drops matching
      users from the table and the total
    - test_page_past_last_refuses, a page beyond the last is a CommandError
    - test_page_zero_refuses, --page is 1-based
    - test_empty_table_still_prints_header, zero users → header + footer, no crash
    """

    def setUp(self) -> None:
        User.objects.create_user(
            username="root",
            password="x",
            email="root@example.com",
            is_staff=True,
            is_superuser=True,
        )
        User.objects.create_user(username="plain", password="x", email="plain@example.com")

    def test_table_lists_every_column(self) -> None:
        out = StringIO()
        call_command("listusers", stdout=out)
        text = out.getvalue()
        for expected in ("first", "last", "email", "staff", "super", "root@example.com"):
            self.assertIn(expected, text)
        self.assertIn("page 1/1 · 2 users", text)

    def test_staff_and_superuser_markers(self) -> None:
        out = StringIO()
        call_command("listusers", stdout=out)
        lines = out.getvalue().splitlines()
        table = "\n".join(lines)
        root_row = next(line for line in lines if "root@example.com" in line)
        plain_row = next(line for line in lines if "plain@example.com" in line)
        self.assertIn("yes", root_row)
        self.assertNotIn("yes", plain_row)
        self.assertEqual(table.count("yes"), 2)  # staff + super on the root row only

    def test_pagination_pages_and_past_last(self) -> None:
        """One page for a small table; a page past the last refuses.

        Fixed 100 rows/page with 2 users means page 1/1 holds everyone.
        """
        first_page = StringIO()
        call_command("listusers", stdout=first_page)
        self.assertIn("plain@example.com", first_page.getvalue())
        self.assertIn("root@example.com", first_page.getvalue())
        self.assertIn("page 1/1 · 2 users", first_page.getvalue())
        with self.assertRaises(CommandError):
            call_command("listusers", "--page", "2", stdout=StringIO())

    def test_exclude_omits_matching_emails(self) -> None:
        """--exclude drops matching users from the table and the total."""
        out = StringIO()
        call_command("listusers", "--exclude", r"^(root@example\.com|.*@gate\.test)$", stdout=out)
        text = out.getvalue()
        self.assertNotIn("root@example.com", text)
        self.assertIn("plain@example.com", text)
        self.assertIn("page 1/1 · 1 users", text)

    def test_page_past_last_refuses(self) -> None:
        with self.assertRaises(CommandError):
            call_command("listusers", "--page", "3", stdout=StringIO())

    def test_page_zero_refuses(self) -> None:
        with self.assertRaises(CommandError):
            call_command("listusers", "--page", "0", stdout=StringIO())

    def test_empty_table_still_prints_header(self) -> None:
        User.objects.all().delete()
        out = StringIO()
        call_command("listusers", stdout=out)
        text = out.getvalue()
        self.assertIn("first", text)
        self.assertIn("page 1/1 · 0 users", text)
