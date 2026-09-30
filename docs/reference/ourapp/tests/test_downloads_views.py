"""Tests for the downloads views (page, upload, replace, delete, anonymous serve)."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from djangoapp.models import User
from djangoapp.tests._base import BaseTestCase

from ourapp.models import Download


class DownloadsViewTests(BaseTestCase):
    """The /downloads manager + the anonymous serve route.

    - test_page_404_anonymous_and_non_superuser, the manager hides from anon
      and plain users
    - test_page_lists_downloads, superuser sees rows (pk-free)
    - test_upload_stores_and_returns, multipart create → schema body, file on disk
    - test_upload_custom_expiry, the expiry picker value is honoured
    - test_upload_past_expiry_404, a past pick is 404 (no dead-on-arrival links)
    - test_upload_bad_expiry_404, an unparseable expiry is 404
    - test_upload_truncates_long_original_name, a 300-char filename stores
      truncated by the field's max_length (never an OS error), never a 500
    - test_upload_non_superuser_404, non-superuser upload is 404
    - test_replace_non_superuser_404, non-superuser replace is 404
    - test_delete_non_superuser_404, non-superuser delete is 404
    - test_replace_deletes_old_file, replace marks old bytes, new survive, version bumps
    - test_replace_stale_version_404, a stale expected_row_version is 404
    - test_delete_removes_row_and_bytes, delete → row + history gone, bytes gone
      (lean tombstone remains)
    - test_serve_anonymous_live_download, anyone with the name downloads the bytes
      under the ORIGINAL filename
    - test_serve_expired_404, past expires_at the same URL is 404
    - test_serve_unknown_404, an unknown name is 404
    """

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()  # noqa: SIM115 # test-scoped, cleaned up below
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(MEDIA_ROOT=Path(self._tmp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.admin = User.objects.create_user(username="admin", is_superuser=True)
        self.plain = User.objects.create_user(username="plain")
        self.client = Client()
        self.client.force_login(self.admin)

    def _upload(
        self, name: str = "report.pdf", content: bytes = b"pdf-bytes", expires_at: str = ""
    ) -> object:
        """The app action: the admin uploads a file through the form."""
        return self.client.post(
            "/downloads/upload",
            data={"file": SimpleUploadedFile(name, content), "expires_at": expires_at},
        )

    def test_page_404_anonymous_and_non_superuser(self) -> None:
        """The manager hides from anonymous and non-superuser viewers."""
        self.assertEqual(Client().get("/downloads").status_code, 404)
        plain = Client()
        plain.force_login(self.plain)
        self.assertEqual(plain.get("/downloads").status_code, 404)

    def test_page_lists_downloads(self) -> None:
        """Superuser GET /downloads renders the rows (pk-free)."""
        resp = self._upload()
        self.assertEqual(resp.status_code, 200)
        props = self.client.get("/downloads", HTTP_X_INERTIA="true").json()["props"]["props"]
        self.assertEqual(len(props["downloads"]), 1)
        for key in props["downloads"][0]:
            self.assertNotIn(key, ("id", "pk"))

    def test_upload_stores_and_returns(self) -> None:
        """Multipart create returns the schema body and stores the bytes."""
        resp = self._upload()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["public_id"])
        self.assertEqual(body["original_name"], "report.pdf")
        self.assertEqual(body["row_version"], 0)
        self.assertFalse(body["is_expired"])
        self.assertNotIn("id", body)
        self.assertTrue(default_storage.exists(body["stored_name"]))
        self.assertEqual(Download.objects.count(), 1)

    def test_upload_custom_expiry(self) -> None:
        """The expiry picker value is honoured (naive input → local tz)."""
        resp = self._upload(expires_at="2030-01-01T12:00")
        self.assertEqual(resp.status_code, 200)
        got = datetime.fromisoformat(resp.json()["expires_at"])
        # The stored value is the picker's wall-clock time, tz-aware in the
        # server's local timezone (datetime-local sends no offset).
        self.assertIsNotNone(got.tzinfo)
        self.assertEqual(
            timezone.localtime(got).replace(tzinfo=None),
            datetime(2030, 1, 1, 12, 0),
        )

    def test_upload_past_expiry_404(self) -> None:
        """A past expiry pick is 404 — no dead-on-arrival links."""
        past = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.assertEqual(self._upload(expires_at=past).status_code, 404)
        self.assertEqual(Download.objects.count(), 0)

    def test_upload_bad_expiry_404(self) -> None:
        """An unparseable expiry is 404 (bad client state ≈ a miss)."""
        self.assertEqual(self._upload(expires_at="not-a-date").status_code, 404)
        self.assertEqual(Download.objects.count(), 0)

    def test_upload_truncates_long_original_name(self) -> None:
        """A 300-char upload filename stores truncated by the field's
        ``max_length`` (Django truncates + adds a random suffix — the OS
        never sees an over-long name, so no 500)."""
        resp = self._upload(name="x" * 300 + ".txt")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertLessEqual(len(body["stored_name"]), 255)
        self.assertLessEqual(len(body["original_name"]), 255)

    def test_upload_non_superuser_404(self) -> None:
        """A non-superuser upload is 404."""
        plain = Client()
        plain.force_login(self.plain)
        resp = plain.post("/downloads/upload", data={"file": SimpleUploadedFile("report.pdf", b"pdf-bytes"), "expires_at": ""})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Download.objects.count(), 0)

    def test_replace_non_superuser_404(self) -> None:
        """A non-superuser replace is 404 (the gate is not page-only)."""
        created = self._upload().json()
        plain = Client()
        plain.force_login(self.plain)
        resp = plain.post(
            f"/downloads/{created['public_id']}/replace",
            data={"file": SimpleUploadedFile("v2.pdf", b"v2-bytes"), "expected_row_version": 0},
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_non_superuser_404(self) -> None:
        """A non-superuser delete is 404 (the gate is not page-only)."""
        created = self._upload().json()
        plain = Client()
        plain.force_login(self.plain)
        resp = plain.post(f"/downloads/{created['public_id']}/delete")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Download.objects.count(), 1)

    def test_replace_deletes_old_file(self) -> None:
        """Replace: old bytes go post-commit, new survive, version bumps."""
        created = self._upload().json()
        old_name = created["stored_name"]
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                f"/downloads/{created['public_id']}/replace",
                data={
                    "file": SimpleUploadedFile("v2.pdf", b"v2-bytes"),
                    "expected_row_version": created["row_version"],
                },
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["original_name"], "v2.pdf")
        self.assertEqual(body["row_version"], 1)
        self.assertFalse(default_storage.exists(old_name))
        self.assertTrue(default_storage.exists(body["stored_name"]))

    def test_replace_stale_version_404(self) -> None:
        """A stale expected_row_version on replace is 404 (old file kept)."""
        created = self._upload().json()
        old_name = created["stored_name"]
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                f"/downloads/{created['public_id']}/replace",
                data={"file": SimpleUploadedFile("v2.pdf", b"v2-bytes"), "expected_row_version": 42},
            )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(default_storage.exists(old_name))

    def test_delete_removes_row_and_bytes(self) -> None:
        """Delete → JSON body; row, history, and bytes gone (tombstone stays)."""
        created = self._upload().json()
        stored_name = created["stored_name"]
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(f"/downloads/{created['public_id']}/delete")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"deleted": created["public_id"]})
        self.assertEqual(Download.objects.count(), 0)
        self.assertFalse(default_storage.exists(stored_name))

    def test_serve_anonymous_live_download(self) -> None:
        """Anyone with the storage name gets the bytes under the ORIGINAL name."""
        created = self._upload().json()
        resp = Client().get(f"/downloads/{created['stored_name']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), b"pdf-bytes")
        self.assertIn("report.pdf", resp.headers["Content-Disposition"])
        self.assertNotIn(created["stored_name"], resp.headers["Content-Disposition"])

    def test_serve_expired_404(self) -> None:
        """Past expires_at the same URL is 404 (sweep or not)."""
        download = Download(
            file=SimpleUploadedFile("report.pdf", b"pdf-bytes"),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        download.save_plus(actor=self.admin, expected_row_version=0)
        self.assertEqual(Client().get(f"/downloads/{download.file.name}").status_code, 404)

    def test_serve_unknown_404(self) -> None:
        """An unknown name is 404."""
        self.assertEqual(Client().get("/downloads/deadbeef.bin").status_code, 404)
