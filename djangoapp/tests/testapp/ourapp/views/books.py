"""Books feature — the ``GET /books`` list page.

Renders the books list as the Inertia page ``ours/BooksPage``; data is pk-free
(only ``public_id``).
"""

from __future__ import annotations

from django.http import HttpRequest
from inertia import InertiaResponse
from ninja import Router

from ourapp.models import Book

router = Router()


@router.get("/books", response=None)
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
