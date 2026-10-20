from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from djangoapp.models import User, UserHistory
from djangoapp.tests._base import BaseTestCase


class CreateUserCommandTests(BaseTestCase):
    """``createuser`` makes the user row (no signup flow exists).

    setUp seeds the mandatory first superuser; later users may be plain.

    - test_creates_user_with_names, email + names land on the row
    - test_superuser_flags_land_in_created_audit, --superuser sets the flags
      on the row and the "created" entry carries them
    - test_plain_create_records_created, plain createuser audits one
      "created" entry (no is_superuser)
    - test_duplicate_email_refuses, a second account for the same email
      (iexact) raises
    - test_output_mentions_login_link, stdout points at makeloginlink
    - test_first_user_must_be_superuser, plain createuser on an empty
      table raises with the --superuser instruction
    - test_first_user_with_superuser_flag_allowed, --superuser on an
      empty table creates
    """

    def setUp(self) -> None:
        User.objects.create_user(username="root", password="x", email="root@example.com")

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

    def test_superuser_flags_land_in_created_audit(self) -> None:
        """--superuser sets the flags on the row; one "created" entry carries them."""
        call_command(
            "createuser",
            "root2@example.com",
            "--superuser",
            stdout=StringIO(),
        )
        user = User.objects.get(email="root2@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        entry = UserHistory.objects.get(target_user=user)
        self.assertEqual(entry.action, "created")
        self.assertEqual(entry.user, user)  # CLI actor: the user itself
        self.assertIs(entry._changes["is_superuser"]["new"], True)  # noqa: FBT003
        self.assertIs(entry._changes["is_staff"]["new"], True)  # noqa: FBT003

    def test_plain_create_records_created(self) -> None:
        """Creation alone is audited: one "created" entry, no flags."""
        call_command("createuser", "plain@example.com", stdout=StringIO())
        user = User.objects.get(email="plain@example.com")
        entry = UserHistory.objects.get(target_user=user)
        self.assertEqual(entry.action, "created")
        self.assertEqual(entry.user, user)  # CLI actor: the user itself
        self.assertIs(entry._changes["is_superuser"]["new"], False)  # noqa: FBT003

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

    def test_first_user_must_be_superuser(self) -> None:
        """A plain first user would lock everyone out — refuse with the fix."""
        User.objects.all().delete()  # setUp's seed — the guard is empty-table only
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "createuser",
                "first@example.com",
                "--first-name",
                "First",
                stdout=StringIO(),
            )
        msg = str(ctx.exception)
        self.assertIn("first user", msg)
        self.assertIn("superuser", msg)
        self.assertEqual(User.objects.count(), 0)

    def test_first_user_with_superuser_flag_allowed(self) -> None:
        """--superuser on the empty table is exactly the intended first user."""
        User.objects.all().delete()  # setUp's seed — recreate as the first user
        call_command("createuser", "first@example.com", "--superuser", stdout=StringIO())
        user = User.objects.get(email="first@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
