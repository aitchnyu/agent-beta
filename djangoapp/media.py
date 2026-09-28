"""Media serving primitive — safe byte streaming from ``MEDIA_ROOT``.

``serve_file(request, filename)`` serves a stored file two ways: a Django
``FileResponse``, or — when the request arrived through the reverse proxy
(detection: Caddy's ``reverse_proxy`` stamps ``X-Forwarded-For`` on
everything it forwards, and granian is bound to 127.0.0.1, so the header
has exactly one possible writer) — an empty response carrying
``X-Accel-Redirect: /<name>``. The Caddyfile intercepts that header
(``@accel`` + ``handle_response``), rewrites to that path and streams the
bytes straight from ``MEDIA_ROOT`` (its root): Django gates the download
but never moves upload bytes. Content-Type and the attachment disposition
are copied onto the served file, so the client still gets the original
filename. A spoofed XFF against an unproxied server yields an empty 200 —
loudly broken, never wrong bytes. The header value is an internal carrier
(it never reaches the client) — not a route; requests for such a path hit
the app's real routes and 404 like any unknown name.

Either way this stays the only serving seam. It is deliberately mounted
NOWHERE by the framework: apps mount their own URL pattern around it with
their own gating first (expiry checks, ownership), because a global open
route would bypass exactly those gates. ``djangoapp.views.files`` (the
superuser file browser) is a different feature: it serves the repo tree,
not uploads.

Path safety mirrors its ``PathWrapper``: resolve + ``is_relative_to`` → 404,
so ``..``, absolute paths, symlink escapes and undecodable shapes (e.g. an
embedded NUL) can never leave ``MEDIA_ROOT`` — a client-generated URL shape
is a 404, never a 500. The checks run before the handoff too, and the
handoff value is built from the RESOLVED path relative to the root
(percent-quoted), so it can never name anything outside it.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils.http import content_disposition_header

if TYPE_CHECKING:
    from django.http import HttpRequest

_UNKNOWN_MIME = "application/octet-stream"  # same fallback as djangoapp.views.files


def _media_file(filename: str) -> tuple[Path, Path]:
    """Resolve ``MEDIA_ROOT / filename`` to (root, file), or raise 404.

    The resolved root is returned alongside the target so callers build
    relative paths against the SAME root that vetted the target (a second
    ``resolve()`` could diverge if ``MEDIA_ROOT`` were a symlink or
    relative path swapped between the two calls).
    """
    root = Path(settings.MEDIA_ROOT).resolve()
    try:
        candidate = (root / filename).resolve()
    except ValueError, OSError:
        # pathlib raises on paths the OS can't express — an embedded NUL
        # (ValueError) or an over-long/looping path (OSError). Still just
        # a 404.
        raise Http404 from None
    # resolve() follows symlinks and collapses ``..`` — if the result left
    # the root, the name was an escape attempt (never serve it).
    if not candidate.is_relative_to(root):
        raise Http404
    # Only files serve — a directory name (or MEDIA_ROOT itself) must 404.
    if not candidate.is_file():
        raise Http404
    return root, candidate


def serve_file(
    request: HttpRequest,
    filename: str,
    *,
    download_name: str | None = None,
) -> FileResponse | HttpResponse:
    """Serve ``MEDIA_ROOT / filename`` as a download (see module docstring)."""
    root, target = _media_file(filename)
    content_type = mimetypes.guess_type(target.name, strict=False)[0] or _UNKNOWN_MIME
    disposition = content_disposition_header(
        as_attachment=True, filename=download_name or target.name
    )
    if request.headers.get("X-Forwarded-For"):
        # Proxied: hand the bytes to the Caddyfile — an empty reply whose
        # X-Accel-Redirect value is the resolved path relative to the root,
        # percent-quoted, so no newline/header-injection or dot-segment
        # shape can ride it. Disposition/type ride along for the
        # Caddyfile's copy_response_headers to forward onto the file.
        accel_path = quote(target.relative_to(root).as_posix(), safe="/")
        response = HttpResponse(content_type=content_type)
        response["Content-Disposition"] = disposition
        response["X-Accel-Redirect"] = f"/{accel_path}"
        return response
    # Direct: stream the bytes ourselves under the same headers.
    return FileResponse(
        target.open("rb"),
        as_attachment=True,
        filename=download_name or target.name,
        content_type=content_type,
    )
