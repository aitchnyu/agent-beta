"""E2e for the downloads page (``/downloads``): upload + replace + delete."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from playwright.sync_api import expect

from djangoapp.models import User
from djangoapp.tests.playwright._base import BasePlaywrightTestCase

from ourapp.models import Download


class DownloadsE2e(BasePlaywrightTestCase):
    """``/downloads`` upload + replace + delete flows.

    - test_upload_lists_download, superuser uploads via the form and the row
      appears (with a download link)
    - test_replace_swaps_file, the Replace action swaps a row's file
    - test_delete_removes_download, the delete action drops the row
    """

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()  # noqa: SIM115 # test-scoped, cleaned up below
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(MEDIA_ROOT=Path(self._tmp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.admin = User.objects.create_user(
            username="dl-admin", password="x", is_superuser=True
        )
        self.login_as(self.admin)
        self.page.set_default_timeout(5000)

    def _pick(self, name: str, content: bytes) -> str:
        """Write a file into tmp media and return its path for the picker."""
        path = Path(self._tmp.name) / name
        path.write_bytes(content)
        return str(path)

    def test_upload_lists_download(self) -> None:
        """Upload via the form; the row renders with its download link."""
        page = self.page
        page.goto(f"{self.live_server_url}/downloads", wait_until="networkidle")
        page.get_by_label("File to share").set_input_files(
            self._pick("e2e-upload.txt", b"e2e download bytes")
        )
        page.get_by_role("button", name="Upload").click()
        expect(page.locator(".ours-downloads-table tbody tr")).to_have_count(1)
        expect(page.locator("body")).to_contain_text("e2e-upload.txt")
        download = Download.objects.get()
        expect(
            page.locator(f'a[href="/downloads/{download.file.name}"]')
        ).to_have_count(1)

    def test_replace_swaps_file(self) -> None:
        """The Replace action swaps a row's file (old bytes marked, new stored)."""
        download = Download(
            file=SimpleUploadedFile("v1.txt", b"v1-bytes"),
        )
        download.save_plus(actor=self.admin, expected_row_version=0)
        old_name = download.file.name
        page = self.page
        page.goto(f"{self.live_server_url}/downloads", wait_until="networkidle")
        expect(page.locator(".ours-downloads-table tbody tr")).to_have_count(1)
        # The hidden shared picker receives the file; the row's Replace
        # button targets it at this row.
        self.page.once("filechooser", lambda chooser: chooser.set_files(
            self._pick("v2.txt", b"v2-bytes")
        ))
        page.get_by_test_id(f"replace-{download.public_id}").click()
        expect(page.locator("tbody")).to_contain_text("v2.txt")
        download.refresh_from_db()
        self.assertNotEqual(download.file.name, old_name)
        self.assertEqual(download.row_version, 1)

    def test_delete_removes_download(self) -> None:
        """The delete action removes the row."""
        download = Download(
            file=SimpleUploadedFile("gone.txt", b"gone-bytes"),
        )
        download.save_plus(actor=self.admin, expected_row_version=0)
        page = self.page
        page.goto(f"{self.live_server_url}/downloads", wait_until="networkidle")
        page.get_by_test_id(f"delete-{download.public_id}").click()
        expect(page.locator(".ours-downloads-table")).to_have_count(0)
        self.assertEqual(Download.objects.count(), 0)
