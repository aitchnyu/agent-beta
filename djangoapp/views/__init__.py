from __future__ import annotations

from django.http import Http404, HttpRequest


def require_superuser(request: HttpRequest) -> None:
    """Gate a view to a superuser, else 404 (never 403).

    Shared by the superuser-only read views (``/manage/models``,
    ``/files/...``). A 404 (not 403) keeps the page's existence hidden from
    unauthenticated / non-superuser viewers.
    """
    viewer = request.user
    if not (viewer.is_authenticated and viewer.is_superuser):
        raise Http404
