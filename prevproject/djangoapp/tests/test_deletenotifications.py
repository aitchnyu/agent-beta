from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from djangoapp.models.base import RowUpdateUserNotification, User


class DeleteNotificationsCommandTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        for i in range(5):
            RowUpdateUserNotification.objects.create(
                modelname="firststuff",
                row_pk=i,
                user=self.user,
                content={"id": i, "action": "created_row"},
            )

    def test_deletes_all_notifications(self) -> None:
        self.assertEqual(RowUpdateUserNotification.objects.count(), 5)
        out = StringIO()
        call_command("deletenotifications", stdout=out)
        self.assertEqual(RowUpdateUserNotification.objects.count(), 0)
        self.assertIn("Deleted 5 notifications", out.getvalue())

    def test_no_notifications(self) -> None:
        RowUpdateUserNotification.objects.all().delete()
        out = StringIO()
        call_command("deletenotifications", stdout=out)
        self.assertEqual(RowUpdateUserNotification.objects.count(), 0)
        self.assertIn("Deleted 0 notifications", out.getvalue())
