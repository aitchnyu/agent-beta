from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from djangoapp.models import User, UserHistory
from djangoapp.tests._base import BaseTestCase


class CreateUserCommandTests(BaseTestCase):
    """``createuser`` makes the user row (no signup flow exists).

    - test_creates_user_with_names, email + names land on the row
    - test_superuser_flag_grants_and_audits, --superuser sets flags via
      User.update (UserHistory "edited" entry)
    - test_plain_create_records_no_history, no flags -> no history row
    - test_duplicate_email_refuses, a second account for the same email
      (iexact) raises
    - test_output_mentions_login_link, stdout points at makeloginlink
    """

    def test_creates_user_with_names(self) -> None:
        """Email + names land on the row; username derives from the local part."""
        call_command(
            "createuser",
            "jane@example.com",
            "--first-name",
            "Jane",
            "--last-name",
            "Doe",
            stdout=StringIO(),
        )
        user = User.objects.get(email="jane@example.com")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.username, "jane")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_superuser_flag_grants_and_audits(self) -> None:
        """--superuser sets is_staff + is_superuser and audits the grant."""
        call_command(
            "createuser",
            "root@example.com",
            "--superuser",
            stdout=StringIO(),
        )
        user = User.objects.get(email="root@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        entry = UserHistory.objects.get(target_user=user)
        self.assertEqual(entry.action, "edited")
        self.assertEqual(entry._changes["is_superuser"], {"old": False, "new": True})

    def test_plain_create_records_no_history(self) -> None:
        """Without flags nothing is audited (creation alone isn't a User.update)."""
        call_command("createuser", "plain@example.com", stdout=StringIO())
        user = User.objects.get(email="plain@example.com")
        self.assertEqual(UserHistory.objects.filter(target_user=user).count(), 0)

    def test_duplicate_email_refuses(self) -> None:
        """A second account for the same email (iexact) raises instead of doubling."""
        User.objects.create_user(username="dup", email="dup@example.com")
        with self.assertRaises(CommandError):
            call_command("createuser", "DUP@example.com", stdout=StringIO())

    def test_output_mentions_login_link(self) -> None:
        """Stdout points the operator at makeloginlink for signing in."""
        out = StringIO()
        call_command("createuser", "hint@example.com", stdout=out)
        self.assertIn("makeloginlink hint@example.com", out.getvalue())
