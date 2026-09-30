from io import StringIO

from django.core.management import call_command

from djangoapp.models import BackupMarker
from djangoapp.tests._base import BaseTestCase


class BackupMarkerTests(BaseTestCase):
    def test_set_next_yields_distinct_values_and_latest_value_tracks_newest(self) -> None:
        first = BackupMarker.set_next()
        BackupMarker.set_next()
        newest = BackupMarker.set_next()

        self.assertNotEqual(first, newest)
        self.assertEqual(BackupMarker.objects.count(), 3)
        self.assertEqual(BackupMarker.latest_value(), newest)


class BackupMarkerCommandTests(BaseTestCase):
    def test_set_prints_created_value_and_latest_prints_it_again(self) -> None:
        set_out = StringIO()
        call_command("backupmarker", "set", stdout=set_out)

        latest_out = StringIO()
        call_command("backupmarker", "latest", stdout=latest_out)

        self.assertEqual(set_out.getvalue().strip(), latest_out.getvalue().strip())
        self.assertEqual(set_out.getvalue().strip(), BackupMarker.latest_value())
