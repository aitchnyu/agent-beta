from __future__ import annotations

import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from django.http import Http404
from django.test import SimpleTestCase, override_settings

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase
from djangoapp.views import files as files_view
from djangoapp.views.files import PathWrapper

# A tracked text file in the user app — stable target for the preview/download
# integration tests below. main/-prefixed because the browse root is the project
# parent (BASE_DIR.parent), so main/ holds the repo. The user app splits models
# into a package, so point at the package's __init__ (which documents BaseModel).
_TEXT_FILE = "main/ourapp/models/__init__.py"


class FilesViewTests(BaseInertiaTestCase):
    """Superuser-only ``/files/...`` browser — HTTP view (gate, listing, preview, serving).

    Uses the Inertia test case (``self.props`` / ``assertComponentUsed``) against
    the real repo tree (``ourapp/`` and its ``models/`` package). Non-superusers
    and anonymous viewers get 404 (never 403); byte serving lives on its own
    endpoints (``/files/download`` / ``/files/raw``).

    - test_non_superuser_404 / test_anonymous_404, access gate → 404
    - test_root_without_trailing_slash / test_root_with_trailing_slash, rel=None/"" → root
    - test_hidden_dirs_filtered_by_default, .venv/node_modules/.git/__pycache__ excluded
    - test_missing_path_404, unknown path → 404
    - test_ourapp_listing_and_breadcrumb, entries + breadcrumb + parent
    - test_text_file_preview, text content present (escaped)
    - test_download_returns_attachment, /files/download → attachment, octet-stream
    - test_download_traversal_404 / test_download_non_superuser_404, download gating
    - test_raw_serves_image_inline_with_content_type, /files/raw → inline, image Content-Type
    - test_raw_non_image_404 / test_raw_traversal_404, raw is <img>-only (non-image/escape → 404)
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_non_superuser_404(self) -> None:
        """non-superuser gets 404 on /files."""
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get("/files/ourapp").status_code, HTTPStatus.NOT_FOUND)

    def test_anonymous_404(self) -> None:
        """Anonymous viewer gets 404 on /files."""
        self.assertEqual(self.client.get("/files/ourapp").status_code, HTTPStatus.NOT_FOUND)

    def test_root_without_trailing_slash(self) -> None:
        """/files (rel=None) serves the browse-root listing (BASE_DIR.parent)."""
        self.client.force_login(self.superuser)
        self.client.get("/files")
        self.assertComponentUsed("FileBrowser")
        props = self.props()["props"]
        names = {e["name"] for e in props["entries"]}
        self.assertIn("main", names)  # the repo dir (BASE_DIR.name)
        self.assertIsNone(props["parent"])  # can't go above the browse root

    def test_root_with_trailing_slash(self) -> None:
        """/files/ (rel="") serves the same browse-root listing."""
        self.client.force_login(self.superuser)
        self.client.get("/files/")
        props = self.props()["props"]
        self.assertIn("main", {e["name"] for e in props["entries"]})

    def test_hidden_dirs_filtered_by_default(self) -> None:
        """Default listing excludes .venv/node_modules/.git/__pycache__."""
        self.client.force_login(self.superuser)
        self.client.get("/files/")
        names = {e["name"] for e in self.props()["props"]["entries"]}
        for hidden in (".venv", "node_modules", ".git", "__pycache__"):
            self.assertNotIn(hidden, names)

    def test_missing_path_404(self) -> None:
        """Missing path resolves to 404."""
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get("/files/does-not-exist-xyz").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_ourapp_listing_and_breadcrumb(self) -> None:
        """main/ourapp/ listing carries entries + a root/main/ourapp breadcrumb."""
        self.client.force_login(self.superuser)
        self.client.get("/files/main/ourapp")
        props = self.props()["props"]
        # The user app splits models/views into packages (one module per feature).
        names = {e["name"] for e in props["entries"]}
        self.assertIn("models", names)
        self.assertIn("views", names)
        self.assertEqual([c["label"] for c in props["breadcrumb"]], ["root", "main", "ourapp"])
        self.assertEqual(props["parent"], "main")  # parent is the repo dir

    def test_text_file_preview(self) -> None:
        """Text file returns kind=text with content inlined."""
        self.client.force_login(self.superuser)
        self.client.get(f"/files/{_TEXT_FILE}")
        self.assertComponentUsed("FileViewer")
        props = self.props()["props"]
        self.assertEqual(props["kind"], "text")
        self.assertIn("BaseModel", props["text"])
        self.assertEqual(props["parent"], "main/ourapp/models")

    def test_download_returns_attachment(self) -> None:
        """/files/download returns bytes as an attachment (octet-stream)."""
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/files/download/{_TEXT_FILE}")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))
        self.assertEqual(resp.headers.get("Content-Type"), "application/octet-stream")

    def test_download_traversal_404(self) -> None:
        """Traversal on /files/download resolves to 404."""
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get("/files/download/../etc/passwd").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_download_non_superuser_404(self) -> None:
        """non-superuser gets 404 on /files/download."""
        self.client.force_login(self.plain)
        self.assertEqual(
            self.client.get(f"/files/download/{_TEXT_FILE}").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_raw_serves_image_inline_with_content_type(self) -> None:
        """/files/raw serves an image inline with its real Content-Type.

        No image is tracked in the repo, so patch _REPO_ROOT to a tempdir with a
        PNG and hit the endpoint through the real route.
        """
        self.client.force_login(self.superuser)
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(files_view, "_REPO_ROOT", Path(d).resolve()),
        ):
            (Path(d) / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            resp = self.client.get("/files/raw/pic.png")
            self.assertEqual(resp.status_code, HTTPStatus.OK)
            self.assertNotIn("attachment", resp.headers.get("Content-Disposition", ""))
            self.assertEqual(resp.headers.get("Content-Type"), "image/png")

    def test_raw_non_image_404(self) -> None:
        """/files/raw 404s for non-image files (raw is <img>-only)."""
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get(f"/files/raw/{_TEXT_FILE}").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_raw_traversal_404(self) -> None:
        """Traversal on /files/raw resolves to 404."""
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get("/files/raw/../etc/passwd").status_code, HTTPStatus.NOT_FOUND
        )

    def test_code_file_is_text_kind(self) -> None:
        """A .py file returns kind=text (language detection is frontend-side)."""
        self.client.force_login(self.superuser)
        self.client.get("/files/main/djangoapp/views/files.py")
        props = self.props()["props"]
        self.assertEqual(props["kind"], "text")
        self.assertNotIn("language", props)
        self.assertIn("def file_browser", props["text"])

    def test_markdown_file_classified(self) -> None:
        """A .md file returns kind=markdown with its content inlined."""
        self.client.force_login(self.superuser)
        self.client.get("/files/main/djangoapp/tests/filefixtures/sample.md")
        props = self.props()["props"]
        self.assertEqual(props["kind"], "markdown")
        self.assertIn("linked image", props["text"])


# SimpleTestCase because these are pure-unit tests (tempdir + patched
# _REPO_ROOT, no DB) inside the Django suite
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PathWrapperTests(SimpleTestCase):
    """``PathWrapper`` confinement + classification, unit-tested on a tempdir.

    Patches ``_REPO_ROOT`` to a tempdir so the wrapper resolves throwaway
    files/dirs (no view or HTTP layer).

    - test_confines_traversal, .. / absolute / missing → 404; a valid rel resolves under the root
    - test_normalizes_rel, None/"" → root; a trailing slash is stripped
    - test_file_classification, text/image/binary by ext + NUL-sniff, with a guessed MIME
    - test_list_entries_sorts_and_hides, folders-first sort + hidden-dir filter
    """

    def test_confines_traversal(self) -> None:
        """PathWrapper raises Http404 for escaping/missing rel; valid ones resolve under root."""
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(files_view, "_REPO_ROOT", Path(d).resolve()),
        ):
            for escaping in ("../etc", "/etc/passwd", "../..", "nope/missing"):
                with self.assertRaises(Http404):
                    PathWrapper(escaping)
            (Path(d) / "apps").mkdir()
            t = PathWrapper("apps")
            self.assertTrue(t.is_dir)
            self.assertEqual(t.parent(), "")  # top-level dir → parent is root
            self.assertEqual([c.label for c in t.breadcrumbs()], ["root", "apps"])

    def test_normalizes_rel(self) -> None:
        """PathWrapper normalizes None/"" to the root and strips a trailing slash from rel."""
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(files_view, "_REPO_ROOT", Path(d).resolve()),
        ):
            PathWrapper("")  # repo root
            (Path(d) / "apps").mkdir()
            t = PathWrapper("apps/")  # trailing slash stripped
            self.assertEqual(t.rel, "apps")

    def test_file_classification(self) -> None:
        """PathWrapper classifies a file as text/image/binary and guesses its MIME."""
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(files_view, "_REPO_ROOT", Path(d).resolve()),
        ):
            root = Path(d)
            (root / "a.txt").write_text("hello world")
            (root / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (root / "c.bin").write_bytes(b"\x00\x01\x02\xff")

            txt = PathWrapper("a.txt")
            self.assertTrue(txt.looks_like_text())
            self.assertFalse(txt.is_image())
            self.assertEqual(txt.mime(), "text/plain")
            self.assertEqual(txt.parent(), "")  # file at root → parent is root

            img = PathWrapper("b.png")
            self.assertTrue(img.is_image())
            self.assertEqual(img.mime(), "image/png")

            binf = PathWrapper("c.bin")
            self.assertFalse(binf.looks_like_text())  # NUL byte → binary

    def test_list_entries_sorts_and_hides(self) -> None:
        """list_entries sorts folders first and hides excluded dirs unless include_hidden."""
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(files_view, "_REPO_ROOT", Path(d).resolve()),
        ):
            root = Path(d)
            (root / "zfile.txt").write_text("x")
            (root / "adir").mkdir()
            (root / ".git").mkdir()  # hidden
            t = PathWrapper("")
            visible = t.list_entries(include_hidden=False)
            self.assertEqual([e.name for e in visible], ["adir", "zfile.txt"])  # dirs first
            self.assertNotIn(".git", {e.name for e in visible})
            hidden = t.list_entries(include_hidden=True)
            self.assertIn(".git", {e.name for e in hidden})
