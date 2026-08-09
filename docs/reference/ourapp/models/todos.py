"""Todos feature models — a ``Todo`` owned by a user.

Demonstrates a ForeignKey to the project ``User`` (in the models-management UI
such a cell links to the owner's profile). ``TodoManager.active_for`` carries
the per-user query, and ``Todo.toggle()`` flips completion, keeping views thin.
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models

from djangoapp.models import BaseModel, User


class TodoManager(models.Manager["Todo"]):
    """Manager for ``Todo``; carries the per-user active query."""

    def active_for(self, user: User) -> models.QuerySet["Todo"]:
        """Return a user's todos, newest first (used by the ``/todos`` page)."""
        return self.get_queryset().filter(owner=user).order_by("-created_at")


class Todo(BaseModel):
    """A single to-do item owned by a user."""

    text = models.CharField(max_length=500)
    completed = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="todos",
    )

    objects = TodoManager()

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """Return the todo's text."""
        return self.text

    def toggle(self) -> None:
        """Flip completion state (caller persists via ``save_with_logs``)."""
        self.completed = not self.completed
