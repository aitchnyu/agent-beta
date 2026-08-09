"""Facts feature models — a ``Topic`` and the ``Fact`` rows grouped under it.

``Fact.topic`` is a ForeignKey to ``Topic`` (a BaseModel → BaseModel link, so in
the models-management UI the cell links to the topic's detail page via its
``get_absolute_url()``). ``Topic.random_fact()`` / ``Fact.objects.random()``
carry the random-pick domain logic, keeping views thin.
"""

from __future__ import annotations

from typing import ClassVar, override

from django.db import models

from djangoapp.models import BaseModel


class Topic(BaseModel):
    """A category that groups facts (e.g. cars, science, animals)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self) -> str:
        """Return the topic's name."""
        return self.name

    @override
    def get_absolute_url(self) -> str:
        """URL of the topic's random-fact page (``/facts/<slug>``)."""
        return f"/facts/{self.slug}"

    def random_fact(self) -> Fact | None:
        """One random fact in this topic, or None when the topic is empty."""
        return Fact.objects.random(topic=self)


class FactManager(models.Manager["Fact"]):
    """Manager for ``Fact``; carries the random-pick query."""

    def random(self, *, topic: Topic | None = None) -> Fact | None:
        """Return one random fact, optionally scoped to a topic, or None.

        Uses ``ORDER BY RANDOM()`` (Postgres) so the pick is unbiased and need
        not load every row. An empty table/topic yields None rather than raising.
        """
        qs = self.get_queryset()
        if topic is not None:
            qs = qs.filter(topic=topic)
        return qs.order_by("?").first()


class Fact(BaseModel):
    """A single piece of trivia, filed under a ``Topic``."""

    text = models.TextField()
    topic = models.ForeignKey(
        Topic,
        on_delete=models.RESTRICT,
        related_name="facts",
    )

    objects = FactManager()

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """Return the fact's text."""
        return self.text
