"""Example models for the reference app — copy into ``ourapp/models.py``.

Each concrete model subclasses ``djangoapp.models.BaseModel`` (which adds
``_public_id``, ``_created_by``, ``_created_at``, ``_edited_at`` and
``get_absolute_url()``). The class docstring shows up in the superuser
models-management UI at ``/manage/models``; a foreign-key cell links to the
referenced row via that row's ``get_absolute_url()``.

After adding/changing a model, generate its migration::

    ./run djangomanage makemigrations ourapp
"""

from django.conf import settings
from django.db import models

from djangoapp.models import BaseModel


class Note(BaseModel):
    """A short note owned by a user.

    ``owner`` is a ForeignKey to the project User; in the models-management UI
    such a column links to the owner's profile. A ForeignKey to another
    BaseModel subclass links to that row's detail page instead.
    """

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="notes",
    )

    def __str__(self) -> str:
        """Return the note's title."""
        return self.title
