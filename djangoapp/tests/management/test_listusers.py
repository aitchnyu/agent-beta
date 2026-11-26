import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase


class ListUsersCommandTests(BaseTestCase):
    """``listusers`` emits one JSON line: message + page/pages/total/users.

    - test_rows_list_every_column, first/last/email/staff/super all ride
      the users rows
    - test_staff_and_superuser_markers, flags render as yes, absences as -
    - test_pagination_pages_and_past_last, fixed 100/page; a page past
      the last refuses
    - test_exclude_omits_matching_emails, --exclude drops matching
      users from the rows and the total
    - test_superusers_flag_lists_superusers_only, --superusers keeps
      superusers only, oldest first, in the same row shape
    - test_rows_come_in_creation_order, rows are ordered by pk, so the
      first-created user comes first
    - test_page_past_last_refuses, a page beyond the last is a CommandError
    - test_page_zero_refuses, --page is 1-based
    - test_empty_table_still_reports, zero users → empty rows, page 1/1
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

    def test_rows_list_every_column(self) -> None:
        out = StringIO()
        call_command("listusers", stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["message"], "page 1/1 · 2 users")
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["pages"], 1)
        self.assertEqual(payload["total"], 2)
        root_row = next(row for row in payload["users"] if row["email"] == "root@example.com")
        self.assertEqual(set(root_row), {"first", "last", "email", "staff", "super"})

    def test_staff_and_superuser_markers(self) -> None:
        out = StringIO()
        call_command("listusers", stdout=out)
        rows = json.loads(out.getvalue())["users"]
        root_row = next(row for row in rows if row["email"] == "root@example.com")
        plain_row = next(row for row in rows if row["email"] == "plain@example.com")
        self.assertEqual((root_row["staff"], root_row["super"]), ("yes", "yes"))
        self.assertEqual((plain_row["staff"], plain_row["super"]), ("-", "-"))

    def test_pagination_pages_and_past_last(self) -> None:
        """One page for a small table; a page past the last refuses.

        Fixed 100 rows/page with 2 users means page 1/1 holds everyone.
        """
        first_page = StringIO()
        call_command("listusers", stdout=first_page)
        payload = json.loads(first_page.getvalue())
        self.assertEqual(
            sorted(row["email"] for row in payload["users"]),
            ["plain@example.com", "root@example.com"],
        )
        self.assertEqual(payload["message"], "page 1/1 · 2 users")
        with self.assertRaisesRegex(CommandError, r"^page 2 is past the last page \(1\)$"):
            call_command("listusers", "--page", "2", stdout=StringIO())

    def test_exclude_omits_matching_emails(self) -> None:
        """--exclude drops matching users from the table and the total."""
        out = StringIO()
        call_command("listusers", "--exclude", r"^(root@example\.com|.*@gate\.test)$", stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual([row["email"] for row in payload["users"]], ["plain@example.com"])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["message"], "page 1/1 · 1 users")

    def test_superusers_flag_lists_superusers_only(self) -> None:
        """--superusers keeps superusers only, oldest first.

        - the plain user is gone from the rows and the total
        - a superuser created later comes after root, though its email sorts first
        - the row shape is unchanged
        """
        User.objects.create_user(
            username="ada", password="x", email="ada@example.com", is_superuser=True
        )
        out = StringIO()
        call_command("listusers", "--superusers", stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(
            [row["email"] for row in payload["users"]], ["root@example.com", "ada@example.com"]
        )
        self.assertEqual(payload["total"], 2)
        self.assertEqual(set(payload["users"][0]), {"first", "last", "email", "staff", "super"})

    def test_rows_come_in_creation_order(self) -> None:
        """Rows come in creation order, oldest first.

        - root comes before plain, although "plain" sorts first as text
        - the plain listing keeps every user
        """
        out = StringIO()
        call_command("listusers", stdout=out)
        rows = json.loads(out.getvalue())["users"]
        self.assertEqual([row["email"] for row in rows], ["root@example.com", "plain@example.com"])

    def test_page_past_last_refuses(self) -> None:
        with self.assertRaisesRegex(CommandError, r"^page 3 is past the last page"):
            call_command("listusers", "--page", "3", stdout=StringIO())

    def test_page_zero_refuses(self) -> None:
        with self.assertRaisesRegex(CommandError, r"^--page is 1-based$"):
            call_command("listusers", "--page", "0", stdout=StringIO())

    def test_empty_table_still_reports(self) -> None:
        User.objects.all().delete()
        out = StringIO()
        call_command("listusers", stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["users"], [])
        self.assertEqual(payload["message"], "page 1/1 · 0 users")
