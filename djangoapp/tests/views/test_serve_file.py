"""Tests for ``djangoapp.media.serve_file`` — safe byte streaming.

``serve_file`` streams ``MEDIA_ROOT / filename`` as an attachment; these
tests pin the content, the Content-Disposition/content-type headers, and —
the security boundary — that every client-generated shape (missing file,
``..`` traversal, absolute path, embedded NUL, directory) is a 404, never a
500 and never a byte from outside ``MEDIA_ROOT``.
"""

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast

from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings

from djangoapp.media import serve_file
from djangoapp.tests._base import BaseTestCase

if TYPE_CHECKING:
    from collections.abc import Iterable


class ServeFileTests(BaseTestCase):
    """serve_file: bytes out, 404 for anything not a file under MEDIA_ROOT.

    - test_serves_file_content, a stored file streams back with its name + type
    - test_subdirectory_served, storage subpaths serve by full name
    - test_download_name_override, download_name replaces the disposition name
    - test_missing_file_404, an unknown name is 404
    - test_traversal_404, ``..`` escapes are 404
    - test_absolute_path_404, an absolute path is 404 (it would replace the join)
    - test_embedded_nul_404, an embedded NUL is 404 (OS-inexpressible shape)
    - test_directory_404, a directory name is 404 (files only)
    - test_symlink_escape_404, a symlink pointing outside MEDIA_ROOT is 404
    - test_proxied_request_emits_x_accel_redirect, X-Forwarded-For present →
      the empty handoff (disposition/type ride along; the same
      404/traversal checks run first)
    - test_head_requests_both_branches, HEAD rides both branches like GET
    - test_accel_header_value_is_quoted_relative_path, the handoff value is
      the RESOLVED path relative to the root, percent-quoted — dot-segments,
      newline names and literal ``%`` can never ride it into a header
    """

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()  # test-scoped, cleaned up below
        self.addCleanup(self._tmp.cleanup)
        self.media = Path(self._tmp.name)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.request: HttpRequest = RequestFactory().get("/")

    def _proxied(self) -> HttpRequest:
        """Build a request that arrived through the reverse proxy.

        Caddy stamps X-Forwarded-For on everything it forwards — that's
        the detection.
        """
        return RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.7")

    def _write(self, rel: str, content: bytes) -> None:
        target = self.media / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def _streamed(self, response: FileResponse | HttpResponse) -> bytes:
        """Drain a FileResponse's streaming body (the accel branch has none)."""
        assert isinstance(response, FileResponse)
        return b"".join(cast("Iterable[bytes]", response.streaming_content))

    def test_serves_file_content(self) -> None:
        """A stored file streams back with its name + guessed content type."""
        self._write("a.txt", b"hello media")
        response = serve_file(self.request, "a.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._streamed(response), b"hello media")
        self.assertEqual(response.headers["Content-Type"], "text/plain")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("a.txt", response.headers["Content-Disposition"])

    def test_subdirectory_served(self) -> None:
        """Storage subpaths (upload_to="downloads/…") serve by full name."""
        storage = FileSystemStorage(location=self.media)
        storage.save("sub/deep.bin", BytesIO(b"\x00\x01"))
        response = serve_file(self.request, "sub/deep.bin")
        self.assertEqual(self._streamed(response), b"\x00\x01")

    def test_download_name_override(self) -> None:
        """download_name replaces the disposition filename (uuid name stays hidden)."""
        self._write("deadbeef.bin", b"x")
        response = serve_file(self.request, "deadbeef.bin", download_name="report.pdf")
        self.assertIn("report.pdf", response.headers["Content-Disposition"])
        self.assertNotIn("deadbeef", response.headers["Content-Disposition"])

    def test_missing_file_404(self) -> None:
        """An unknown name is 404."""
        with self.assertRaises(Http404):
            serve_file(self.request, "nope.txt")

    def test_traversal_404(self) -> None:
        """``..`` escapes are 404 — never bytes from outside MEDIA_ROOT."""
        self._write("inner.txt", b"inner")
        for name in ("../inner.txt", "../../etc/passwd", "sub/../../inner.txt"):
            with self.subTest(name=name), self.assertRaises(Http404):
                serve_file(self.request, name)

    def test_absolute_path_404(self) -> None:
        """An absolute path is 404 (Path join replaces; the guard still holds)."""
        with self.assertRaises(Http404):
            serve_file(self.request, "/etc/passwd")

    def test_embedded_nul_404(self) -> None:
        """An embedded NUL (OS-inexpressible) is 404, not a ValueError 500."""
        with self.assertRaises(Http404):
            serve_file(self.request, "a\x00b.txt")

    def test_directory_404(self) -> None:
        """A directory name is 404 — only files serve."""
        (self.media / "adir").mkdir()
        with self.assertRaises(Http404):
            serve_file(self.request, "adir")

    def test_symlink_escape_404(self) -> None:
        """A symlink inside MEDIA_ROOT pointing outside it is 404."""
        outside = Path(self._tmp.name).parent / "serve-file-outside-secret.txt"
        outside.write_bytes(b"outside bytes")
        self.addCleanup(outside.unlink)
        (self.media / "escape.txt").symlink_to(outside)
        with self.assertRaises(Http404):
            serve_file(self.request, "escape.txt")

    def test_proxied_request_emits_x_accel_redirect(self) -> None:
        """X-Forwarded-For present → the empty X-Accel-Redirect handoff.

        The Caddyfile's reverse_proxy intercepts the header and streams the
        bytes; Content-Disposition/Type (download_name included) ride the
        Django response through the interception. The gate checks still run
        first (missing/traversal names 404 even when proxied — no handoff is
        ever issued for a name that isn't a real file under the root).
        """
        self._write("a.txt", b"hello")
        response = serve_file(self._proxied(), "a.txt", download_name="renamed.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Accel-Redirect"], "/a.txt")
        self.assertIn("renamed.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Content-Type"], "text/plain")
        with self.assertRaises(Http404):
            serve_file(self._proxied(), "nope.txt")
        with self.assertRaises(Http404):
            serve_file(self._proxied(), "../a.txt")

    def test_head_requests_both_branches(self) -> None:
        """HEAD rides both branches like GET (method-agnostic by design)."""
        self._write("a.txt", b"hello")
        direct = serve_file(RequestFactory().head("/"), "a.txt")
        self.assertEqual(direct.status_code, 200)
        proxied = serve_file(
            RequestFactory().head("/", HTTP_X_FORWARDED_FOR="203.0.113.7"),
            "a.txt",
        )
        self.assertEqual(proxied.headers["X-Accel-Redirect"], "/a.txt")

    def test_accel_header_value_is_quoted_relative_path(self) -> None:
        """The handoff value is the resolved, percent-quoted relative path.

        A name with dot-segments resolving INSIDE the root, a stored
        filename with a newline (legal on Unix), or a literal ``%`` (must
        arrive single-encoded as ``%25``) must reach the header as a clean,
        quoted value — never a raw ``..``, a bare newline (which would
        raise BadHeaderError → 500), or a double-decodable path.
        """
        self._write("sub/b.txt", b"b")
        response = serve_file(self._proxied(), "sub/../sub/b.txt")
        self.assertEqual(
            response.headers["X-Accel-Redirect"], "/sub/b.txt"
        )  # dot-segments collapsed to the resolved path
        newline_name = "we\nird.txt"
        self._write(newline_name, b"n")
        response = serve_file(self._proxied(), newline_name)
        self.assertEqual(
            response.headers["X-Accel-Redirect"],
            "/we%0Aird.txt",
        )
        self._write("100%.txt", b"p")
        response = serve_file(self._proxied(), "100%.txt")
        self.assertEqual(response.headers["X-Accel-Redirect"], "/100%25.txt")
