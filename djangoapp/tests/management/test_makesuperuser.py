from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from djangoapp.models import User, UserHistory
from djangoapp.tests._base import BaseTestCase


class MakeSuperuserCommandTests(BaseTestCase):
    """``makesuperuser`` promotes an existing user (by email) to superuser+staff.

    Uses ``User.update`` so each promotion is audited as a ``UserHistory``
    "edited" entry. Verifies case-insensitive email lookup, the recorded audit
    entry, idempotency, and the 0/>1 match guards (User.email is not unique).

    - test_promotes_matching_user, matching email sets is_superuser + is_staff
    - test_promotion_records_history, promotion writes an edited UserHistory row
    - test_email_match_is_case_insensitive, different-case email still matches
    - test_unknown_email_raises, no match -> CommandError
    - test_already_superuser_is_noop, already-superuser reports nothing-to-do
    """

    def test_promotes_matching_user(self) -> None:
        """Matching email sets is_superuser + is_staff."""
        User.objects.create_user(username="alice", password="x", email="alice@example.com")
        call_command("makesuperuser", "alice@example.com", stdout=StringIO())
        user = User.objects.get(username="alice")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_promotion_records_history(self) -> None:
        """Promotion writes an edited UserHistory row with the flag diff."""
        User.objects.create_user(username="alice", password="x", email="alice@example.com")
        call_command("makesuperuser", "alice@example.com", stdout=StringIO())
        user = User.objects.get(username="alice")
        entry = UserHistory.objects.get(target_user=user)
        self.assertEqual(entry.action, "edited")
        self.assertEqual(entry._changes["is_staff"], {"old": False, "new": True})
        self.assertEqual(entry._changes["is_superuser"], {"old": False, "new": True})
        # No other fields were touched.
        self.assertIsNone(entry._changes["first_name"])

    def test_email_match_is_case_insensitive(self) -> None:
        """Different-case email still matches."""
        User.objects.create_user(username="bob", password="x", email="bob@example.com")
        call_command("makesuperuser", "BOB@example.com", stdout=StringIO())
        user = User.objects.get(username="bob")
        self.assertTrue(user.is_superuser)

    def test_unknown_email_raises(self) -> None:
        """No match -> CommandError."""
        with self.assertRaises(CommandError):
            call_command("makesuperuser", "nobody@example.com", stdout=StringIO())

    def test_already_superuser_is_noop(self) -> None:
        """Already-superuser reports nothing-to-do without error or history."""
        User.objects.create_user(
            username="root",
            password="x",
            email="root@example.com",
            is_superuser=True,
            is_staff=True,
        )
        call_command("makesuperuser", "root@example.com", stdout=StringIO())
        user = User.objects.get(username="root")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(UserHistory.objects.filter(target_user=user).count(), 0)
