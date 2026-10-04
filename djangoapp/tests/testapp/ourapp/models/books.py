"""Books feature models — ``Author``, ``Book`` and ``Shelf``.

Two concrete ``BaseModel`` subclasses covering each field kind plus both FK
types: ``Book.author`` → ``Author`` (FK to a BaseModel → links via
``get_absolute_url``) and ``Book.reviewer`` → ``User`` (FK to User → links to the
profile). ``Book`` also carries the scalar kinds the audit snapshot must
stringify (float, date) and ``Book.shelf`` → ``Shelf`` — a PLAIN model (no
public_id) exercising the degrade-gracefully paths: unlinked FK cells, omitted
log values, detail 404. Seeded by the project tests with enough rows for
pagination/sort.
"""

from django.conf import settings
from django.db import models

from djangoapp.models import BaseModel


class Shelf(models.Model):
    """A plain (non-BaseModel) shelf — no public_id, no audit trail."""

    code = models.CharField(max_length=20)

    def __str__(self) -> str:
        """Return the shelf code."""
        return self.code


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
    """A book — char/text/integer/float/date/datetime/decimal/boolean + all FK kinds."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    pages = models.IntegerField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)
    released = models.DateField(null=True, blank=True)
    published = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        Author,
        on_delete=models.RESTRICT,
        related_name="books",
    )
    # FK to a plain (non-BaseModel, non-User) model — renders unlinked,
    # omits from audit snapshots.
    shelf = models.ForeignKey(
        "Shelf",
        on_delete=models.RESTRICT,
        related_name="books",
        null=True,
        blank=True,
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
