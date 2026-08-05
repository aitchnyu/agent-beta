"""Test-app API — a django-ninja API serving an ``ours/`` list page."""

from __future__ import annotations

from django.http import HttpRequest
from inertia import InertiaResponse
from ninja import NinjaAPI

from ourapp.models import Book

api = NinjaAPI(urls_namespace="ourapp-http")


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
