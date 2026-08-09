"""Test-app API — a django-ninja API serving the landing page + a ``ours/`` list page.

Serves ``/`` (the app-owned landing page) and ``/books`` (an ``ours/`` list page)
so the project tests (which hit ``/``) keep working after the framework's own
home view was removed.
"""

from __future__ import annotations

from django.http import HttpRequest
from inertia import InertiaResponse
from ninja import NinjaAPI

from djangoapp.shortcuts import maybe_user
from ourapp.models import Book

api = NinjaAPI(urls_namespace="ourapp-http")


@api.get("/", response=None)
def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``ours/Home``), login-state only.

    The component name is irrelevant to the server-side project tests; this view
    exists so ``GET /`` resolves to an Inertia page (the framework no longer owns
    a home route).
    """
    user = maybe_user(request)
    if user is None:
        props = {
            "is_authenticated": False,
            "display_name": "",
            "public_id": "",
        }
    else:
        props = {
            "is_authenticated": True,
            "display_name": user.display_name,
            "public_id": user.public_id,
        }
    return InertiaResponse(request, "ours/Home", {"props": props})


@api.get("/books", response=None)
def books_page(request: HttpRequest) -> InertiaResponse:
    """Render the books list as an Inertia page (component ``ours/BooksPage``)."""
    books = [
        {
            "public_id": b.public_id,
            "title": b.title,
            "author": b.author.name,
        }
        for b in Book.objects.select_related("author").order_by("-created_at")
    ]
    return InertiaResponse(request, "ours/BooksPage", {"props": {"books": books}})
