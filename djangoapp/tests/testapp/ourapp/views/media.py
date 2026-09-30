"""Media feature — the checkframework2 gate's upload/serve endpoints.

Superuser-only pair exercising the framework media primitives over the real
HTTPS stack (``deploy/vm.sh`` gate, assert 10): a multipart POST stores a
file under ``MEDIA_ROOT`` with an unguessable uuid name; the GET streams it
back through ``djangoapp.media.serve_file`` — including its traversal-safe
404s. No model, no list page: this is the gate's substrate, not a second
file feature (``docs/reference/ourapp`` owns the full illustration).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.core.files.storage import default_storage
from ninja import File, Router, Schema, UploadedFile

from djangoapp.media import serve_file
from djangoapp.views import require_superuser

if TYPE_CHECKING:
    from django.http import FileResponse, HttpRequest, HttpResponse

router = Router()


class MediaOutSchema(Schema):
    """pk-free reply: the storage name to fetch the file back with."""

    name: str


@router.post("/media/upload", response=MediaOutSchema)
def media_upload(request: HttpRequest, file: File[UploadedFile]) -> MediaOutSchema:
    """Store an uploaded file under a fresh uuid name → ``{name}``."""
    require_superuser(request)
    original = file.name or ""
    suffix = f".{original.rsplit('.', 1)[-1].lower()}" if "." in original else ""
    name = default_storage.save(f"{uuid.uuid4().hex}{suffix}", file)
    return MediaOutSchema(name=name)


@router.get("/media/{name}", response=None)
def media_serve(request: HttpRequest, name: str) -> FileResponse | HttpResponse:
    """Stream a stored file back via ``serve_file`` (traversal-safe 404s)."""
    require_superuser(request)
    return serve_file(request, name)
