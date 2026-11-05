"""Django-level error views (the ninja handlers cover JSON ops only).

``handler404`` renders the same friendly ``404.html`` the API-side
handler uses, with the message a ``NotFound`` carries (or the fixed
leak-free text). Everything else about page errors is Django's own
behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from djangoapp.ninja_api import NOT_FOUND_TEXT

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    """handler404: the friendly 404 page for plain page views."""
    message = getattr(exception, "msg", None) or NOT_FOUND_TEXT
    return render(request, "404.html", {"message": message}, status=404)
