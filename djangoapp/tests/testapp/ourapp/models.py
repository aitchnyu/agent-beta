"""Test-app models — exercise every models-management path.

Two concrete ``BaseModel`` subclasses covering each field kind plus both FK
types: ``Book.author`` → ``Author`` (FK to a BaseModel → links via
``get_absolute_url``) and ``Book.reviewer`` → ``User`` (FK to User → links to the
profile). Seeded by the project tests with enough rows for pagination/sort.

Overlaid onto ``scratch/ourapp/`` by ``checkproject``; not installed in ``main/``.
"""

from django.conf import settings
from django.db import models

from djangoapp.models import BaseModel


class Author(BaseModel):
    """An author of books."""

    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True, default="")
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        """Return the author's name."""
        return self.name


class Book(BaseModel):
    """A book — char/text/integer/decimal/datetime/boolean + both FK kinds."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    pages = models.IntegerField(null=True, blank=True)
    published = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        Author,
        on_delete=models.RESTRICT,
        related_name="books",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="reviewed_books",
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        """Return the book's title."""
        return self.title
