from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase


class ListUsersCommandTests(BaseTestCase):
    """``listusers`` prints the user table, paginated.

    - test_table_lists_every_column, first/last/email/staff/superuser all render
    - test_staff_and_superuser_markers, flags render as yes, absences as -
    - test_page_size_bounds_rows, --page-size slices the table
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

    def test_page_size_bounds_rows(self) -> None:
        """Email-ordered: page 1 holds plain (alphabetically first), page 2 the rest."""
        first_page = StringIO()
        call_command("listusers", "--page-size", "1", stdout=first_page)
        self.assertIn("plain@example.com", first_page.getvalue())
        self.assertNotIn("root@example.com", first_page.getvalue())
        second_page = StringIO()
        call_command("listusers", "--page", "2", "--page-size", "1", stdout=second_page)
        self.assertIn("root@example.com", second_page.getvalue())
        self.assertIn("page 1/2 · 2 users", first_page.getvalue())

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
