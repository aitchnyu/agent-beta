"""Downloads feature — admin-uploaded files, anonymously downloadable till expiry.

Endpoints (one Inertia page ``ours/DownloadsPage`` + the anonymous serve route):
- GET  /downloads                        — superuser page: list + upload form
- POST /downloads/upload                 — superuser multipart create → DownloadOutSchema
- POST /downloads/{public_id}/replace    — superuser multipart replace (just reassign
                                            + save_plus — the old file dies post-commit) → DownloadOutSchema
- POST /downloads/{public_id}/delete     — superuser removal (delete_plus: row +
                                            history purge + file; lean tombstone) → {"deleted": public_id}
- GET  /downloads/{path:storage_name}    — ANONYMOUS serve: expiry gate → serve_file

The serve route is the expiry gate: a live row streams via
``djangoapp.media.serve_file`` under its original name; an expired or unknown
name is 404 (the daily sweep — ``tasks/downloads.py`` — deletes row + file
soon after). Storage names are the original filenames (guessable), so the
expiry date — not URL secrecy — is what guards a download. Mutating payloads
echo ``expected_row_version`` like every tracked write.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.http import Http404
from django.utils import timezone
from inertia import InertiaResponse
from ninja import File, Form, Router, Schema, UploadedFile

from djangoapp.media import serve_file
from djangoapp.models import SKIP_ROW_VERSION_CHECK
from djangoapp.shortcuts import maybe_user
from djangoapp.views import require_superuser
from ourapp.models import DEFAULT_DOWNLOAD_WINDOW, Download

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router()


class DownloadOutSchema(Schema):
    """pk-free serialisation of a download (``stored_name`` — the storage
    path — is public: it IS the anonymous download URL; the integer pk
    never leaves)."""

    public_id: str
    original_name: str
    stored_name: str
    expires_at: datetime
    is_expired: bool
    row_version: int


class DownloadDeletedSchema(Schema):
    """Delete reply — a body, not a bare 204, so JSON clients parse cleanly."""

    deleted: str


def _download_out(download: Download) -> DownloadOutSchema:
    return DownloadOutSchema(
        public_id=download.public_id,
        original_name=download.basename,
        stored_name=download.file.name,
        expires_at=download.expires_at,
        is_expired=download.is_expired,
        row_version=download.row_version,
    )


def _parse_expiry(raw: str | None) -> datetime:
    """Parse the optional expiry picker value, or default one week out.

    Unparseable or PAST input is 404 (house shape: bad client state looks
    like a miss — the form widget sends ``datetime-local`` strings, and a
    past pick would birth a link that 404s immediately). A naive value
    (``datetime-local`` sends no tz) is made aware — the column is
    UTC-aware and ``is_expired`` compares against ``timezone.now()``.
    """
    if not raw:
        return timezone.now() + DEFAULT_DOWNLOAD_WINDOW
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise Http404 from exc
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed)
    if parsed <= timezone.now():
        raise Http404
    return parsed


@router.get("/downloads", response=None)
def downloads_page(request: HttpRequest) -> InertiaResponse:
    """Render the superuser download manager (component ``ours/DownloadsPage``)."""
    require_superuser(request)
    downloads = Download.objects.all()
    return InertiaResponse(
        request,
        "ours/DownloadsPage",
        {"props": {"downloads": [_download_out(d).model_dump() for d in downloads]}},
    )


@router.post("/downloads/upload", response=DownloadOutSchema)
def upload_download(
    request: HttpRequest,
    file: File[UploadedFile],
    expires_at: Form[str | None] = None,
) -> DownloadOutSchema:
    """Store an uploaded file as a new download; return the row (pk-free).

    Over-long filenames are the field's business: its ``max_length``
    truncates (with a random suffix) instead of the OS rejecting the write.
    The save uses the sentinel (the server is the only writer at create
    time; there is no client echo to check against).
    """
    require_superuser(request)
    download = Download(
        file=file,
        expires_at=_parse_expiry(expires_at),
    )
    download.save_plus(
        actor=maybe_user(request), expected_row_version=SKIP_ROW_VERSION_CHECK
    )
    return _download_out(download)


@router.post("/downloads/{public_id}/replace", response=DownloadOutSchema)
def replace_download(
    request: HttpRequest,
    public_id: str,
    file: File[UploadedFile],
    expected_row_version: Form[int],
) -> DownloadOutSchema:
    """Swap a download's file — THE replacement illustration.

    Just reassign and ``save_plus``: the tracked save reads the row's
    pre-edit file name under lock, and on commit the OLD bytes go while
    the new survive (a rollback keeps both the edit and the old file).
    No separate cleanup call exists to remember or forget.
    """
    require_superuser(request)
    download = Download.objects.filter(public_id=public_id).first()
    if download is None:
        raise Http404
    download.file = file
    download.save_plus(
        actor=maybe_user(request),
        expected_row_version=expected_row_version,
    )
    return _download_out(download)


@router.post("/downloads/{public_id}/delete", response=DownloadDeletedSchema)
def delete_download(
    request: HttpRequest, public_id: str
) -> DownloadDeletedSchema:
    """Remove a download — row, history purge, file, and a tombstone.

    Deletes carry no optimistic lock (``delete_plus`` takes none — a
    delete is idempotent); a missing row is simply already-gone → 404. The
    reply is a body (``{"deleted": public_id}``), not a bare 204, so JSON
    clients parse cleanly.
    """
    require_superuser(request)
    download = Download.objects.filter(public_id=public_id).first()
    if download is None:
        raise Http404
    download.delete_plus(actor=maybe_user(request))
    return DownloadDeletedSchema(deleted=download.public_id)


@router.get("/downloads/{path:storage_name}", response=None)
def serve_download(request: HttpRequest, storage_name: str):
    """ANONYMOUS: stream a live download under its original name.

    The expiry gate: an expired row (sweep hasn't caught it yet) 404s exactly
    like a missing one. ``serve_file`` confines the name under ``MEDIA_ROOT``
    (traversal → 404) and the disposition carries the original name.
    """
    download = Download.objects.filter(file=storage_name).first()
    if download is None or download.is_expired:
        raise Http404
    return serve_file(request, download.file.name, download_name=download.basename)
