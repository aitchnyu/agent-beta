"""Superuser-only read-only file browser over the project tree at ``/files/...``.

Directories list their entries (folders first); files preview as text or render
as images; any file can be downloaded (``/files/download/...``) or served raw
(``/files/raw/...``, used for ``<img>``). The browse root is ``BASE_DIR.parent``
(the folder holding both ``main/`` and ``scratch/``); the "Files" nav button lands
at ``main/ourapp/`` and you can navigate up to that parent (to browse ``scratch/``)
but no further. Path traversal (``..``, absolute paths, symlink escapes) is
confined in :class:`PathWrapper` (resolve + ``is_relative_to`` → 404).

Served by a django-ninja ``NinjaAPI`` (the same shape as ``/git`` and
``/manage``): each op returns an Inertia page or a ``FileResponse`` with
``response=None``, and raises ``Http404`` for misses (mapped to a consistent
JSON body by the registered error handlers). Mounted in :mod:`djangoapp.urls`.
"""

from __future__ import annotations

import mimetypes
import stat
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponseBase
from django.urls import register_converter
from inertia import InertiaResponse
from ninja import Router
from pydantic import BaseModel

from djangoapp.ninja_api import make_ninja_api
from djangoapp.views import require_superuser

if TYPE_CHECKING:
    import os
    from typing import IO

_REPO_ROOT = Path(str(settings.BASE_DIR)).resolve().parent
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
_MARKDOWN_EXT = ".md"
# Default-hidden from listings: heavy or generated dirs (toggle with ?hidden=true).
_HIDDEN_DIRECTORIES = {".venv", "node_modules", ".git", "__pycache__"}
_TEXT_MAX_SIZE = 1_000_000  # ~1 MB: larger text files aren't previewed inline
_TEXT_SNIFF_BYTES = 8192  # first 8 KB checked for a NUL byte (binary heuristic)
_UNKNOWN_MIME = "application/octet-stream"
# Value of the ?hidden flag that reveals excluded dirs.
_HIDDEN_TRUE = "true"


class BreadcrumbSegment(BaseModel):
    """A breadcrumb segment: display label + the repo-root-relative path to it."""

    label: str
    rel: str


class FileEntry(BaseModel):
    name: str
    is_dir: bool
    is_image: bool
    size: int
    mtime: int  # epoch milliseconds; the client formats it in the local timezone


class FileBrowserProps(BaseModel):
    rel: str  # current dir, repo-root-relative ("" = root)
    breadcrumb: list[BreadcrumbSegment]
    parent: str | None  # rel of the parent dir; None at the repo root
    entries: list[FileEntry]
    contains_hidden_entries: bool  # whether hidden dirs are currently shown


class FileViewerProps(BaseModel):
    rel: str
    breadcrumb: list[BreadcrumbSegment]
    parent: str | None  # rel of the parent dir; None only if rel is the repo root
    name: str
    size: int
    mtime: int
    kind: str  # "markdown" | "image" | "text" | "binary"
    text: str = ""


class PathWrapper:
    """A path under ``_REPO_ROOT`` resolved from a repo-root-relative ``rel``.

    Raises :class:`Http404` if ``rel`` escapes the repo root or doesn't exist
    (``resolve()`` collapses ``..`` and follows symlinks; ``is_relative_to``
    rejects anything outside the root). Exposes the bits the view needs —
    breadcrumbs, parent, stats, entry listing, classification, and byte serving
    — so the view stays thin.
    """

    __slots__ = ("path", "rel")

    def __init__(self, rel: str) -> None:
        normalized = (rel or "").strip().rstrip("/")
        path = (_REPO_ROOT / normalized).resolve()
        if path != _REPO_ROOT and not path.is_relative_to(_REPO_ROOT):
            raise Http404
        if not path.exists():
            raise Http404
        self.rel = normalized
        self.path = path

    @property
    def name(self) -> str:
        return self.path.name or "root"

    @property
    def is_dir(self) -> bool:
        return self.path.is_dir()

    @property
    def is_file(self) -> bool:
        return self.path.is_file()

    def stat(self) -> os.stat_result:
        return self.path.stat()

    def breadcrumbs(self) -> list[BreadcrumbSegment]:
        parts = PurePosixPath(self.rel).parts
        return [
            BreadcrumbSegment(label="root", rel=""),
            *(
                BreadcrumbSegment(label=parts[i - 1], rel="/".join(parts[:i]))
                for i in range(1, len(parts) + 1)
            ),
        ]

    def parent(self) -> str | None:
        """Return the rel of the parent dir, or None at the repo root."""
        if not self.rel:
            return None
        parent = PurePosixPath(self.rel).parent
        return "" if str(parent) == "." else str(parent)

    def is_image(self) -> bool:
        return self.path.suffix.lower() in _IMAGE_EXTENSIONS

    def is_markdown(self) -> bool:
        return self.path.suffix.lower() == _MARKDOWN_EXT

    def looks_like_text(self) -> bool:
        """Treat the file as text when its first chunk has no NUL byte (heuristic).

        Misclassifies UTF-16/UTF-32 (which carry NUL bytes) as binary — acceptable
        for a dev preview tool.
        """
        with self.path.open("rb") as fh:
            chunk = fh.read(_TEXT_SNIFF_BYTES)
        return b"\x00" not in chunk

    def read_text(self) -> str:
        return self.path.read_text(errors="replace")

    def open_bytes(self) -> IO[bytes]:
        """Open the raw bytes for streaming (FileResponse closes it)."""
        return self.path.open("rb")

    def mime(self) -> str:
        return mimetypes.guess_type(self.path.name, strict=False)[0] or _UNKNOWN_MIME

    def list_entries(self, *, include_hidden: bool) -> list[FileEntry]:
        entries: list[FileEntry] = []
        for child in self.path.iterdir():
            if not include_hidden and child.name in _HIDDEN_DIRECTORIES:
                continue
            st = child.stat()
            entries.append(
                FileEntry(
                    name=child.name,
                    is_dir=stat.S_ISDIR(st.st_mode),
                    is_image=child.suffix.lower() in _IMAGE_EXTENSIONS,
                    size=st.st_size,
                    mtime=int(st.st_mtime * 1000),
                )
            )
        # Folders first, then files; alphabetical, case-insensitive.
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries


class _RelPathConverter:
    """Django path converter matching zero or more segments (``.*``).

    The built-in ``path`` converter requires ≥1 char (``.+``), so it can't serve
    the browse root (``/files/``, ``rel=""``). Matching ``.*`` lets one
    ``/{relpath:rel}`` route serve both the root and subpaths — no dedicated
    trailing-slash route. Registered globally below (Django converters are
    process-wide by design); this module is imported by the URLconf.
    """

    regex = r".*"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value


# "relpath" — a path that may be empty (repo root). See _RelPathConverter.
register_converter(_RelPathConverter, "relpath")

files_router = Router()


def _serve(target: PathWrapper, *, attachment: bool, content_type: str) -> FileResponse:
    """Stream a file's bytes — as a download (attachment) or inline (raw)."""
    if not target.is_file:
        raise Http404
    return FileResponse(
        target.open_bytes(),
        as_attachment=attachment,
        filename=target.name,
        content_type=content_type,
    )


# Byte-serving routes are registered before the browse catch-all so /files/raw/...
# and /files/download/... win over /files/{path:rel} (which would otherwise grab
# "raw/<rest>" / "download/<rest>" as a browse path).
@files_router.get("/raw/{path:rel}", response=None)
def file_raw(request: HttpRequest, rel: str) -> FileResponse:
    """Serve a file's bytes inline with its real Content-Type (``/files/raw/...``).

    Used by ``<img>`` (and other media). Inline, not an attachment. Restricted to
    images: this endpoint serves bytes in the app's authenticated origin, so a
    non-image (e.g. ``evil.html`` → ``text/html``) would be a same-origin
    stored-XSS sink. The image-only gate — not CSP — is the boundary.
    """
    require_superuser(request)
    target = PathWrapper(rel)
    if not target.is_image():
        raise Http404
    return _serve(target, attachment=False, content_type=target.mime())


@files_router.get("/download/{path:rel}", response=None)
def file_download(request: HttpRequest, rel: str) -> FileResponse:
    """Serve a file's bytes as a download attachment (``/files/download/...``)."""
    require_superuser(request)
    return _serve(PathWrapper(rel), attachment=True, content_type=_UNKNOWN_MIME)


def _browse(request: HttpRequest, rel: str) -> HttpResponseBase:
    """Render a directory listing or a file preview (shared by the /files routes).

    Byte serving lives on its own endpoints (:func:`file_raw`, :func:`file_download`)
    — this only renders Inertia pages.
    """
    require_superuser(request)
    target = PathWrapper(rel)

    if target.is_dir:
        include_hidden = request.GET.get("hidden", "").lower() == _HIDDEN_TRUE
        props = FileBrowserProps(
            rel=target.rel,
            breadcrumb=target.breadcrumbs(),
            parent=target.parent(),
            entries=target.list_entries(include_hidden=include_hidden),
            contains_hidden_entries=include_hidden,
        )
        return InertiaResponse(
            request,
            "FileBrowser",
            {"props": props.model_dump()},
        )

    # File preview: images render via /files/raw; text is inlined; else binary.
    st = target.stat()
    file_viewer = FileViewerProps(
        rel=target.rel,
        breadcrumb=target.breadcrumbs(),
        parent=target.parent(),
        name=target.name,
        size=st.st_size,
        mtime=int(st.st_mtime * 1000),
        kind="binary",
    )
    if target.is_image():
        # The <img> fetches bytes via /files/raw/..., so nothing is inlined here.
        file_viewer.kind = "image"
    elif st.st_size <= _TEXT_MAX_SIZE and target.looks_like_text():
        # Text-like: markdown renders via marked; everything else is plain text
        # (the frontend decides which text files get syntax highlighting).
        file_viewer.text = target.read_text()
        file_viewer.kind = "markdown" if target.is_markdown() else "text"
    return InertiaResponse(
        request,
        "FileViewer",
        {"props": file_viewer.model_dump()},
    )


# ``/files`` (no slash) needs its own route — a Django pattern can't make the
# leading slash optional. ``/files/`` (the root, rel="") and every subpath share
# the one catch-all below: ``{relpath:rel}`` uses _RelPathConverter (matches
# zero-or-more segments), so the empty-root case lands on the same route.
@files_router.get("", response=None)
def file_browser(request: HttpRequest) -> HttpResponseBase:
    """``GET /files`` — browse the repo root (BASE_DIR.parent)."""
    return _browse(request, "")


@files_router.get("/{relpath:rel}", response=None)
def file_browser_path(request: HttpRequest, rel: str) -> HttpResponseBase:
    """``GET /files/`` (root) and ``GET /files/<path>`` — browse a dir or preview a file."""
    return _browse(request, rel)


files_api = make_ninja_api("files", files_router)
