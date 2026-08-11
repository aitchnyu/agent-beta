"""Facts feature models — ``Topic``, ``Fact``, and the daily ``FactOfTheDay`` pick.

- ``Topic`` groups facts (cars, science, …); ``Topic.random_fact()`` /
  ``Fact.objects.random()`` carry the random-pick domain logic (views stay thin).
- ``FactOfTheDay`` is a **singleton** — the single current pick (one row max,
  enforced at the DB level by a unique constant sentinel). Its ``fact`` is
  rotated daily by the Huey cron (see ``ourapp/tasks/``); its ``last_updated_at``
  is "the date this pick was set". ``current()`` is the read-only accessor views
  use (a GET never creates/mutates a row); ``choose_for_today()`` is the only
  mutator (the scheduled picker). ``fact`` is SET_NULL so re-seeding facts (which
  deletes them) never blocks or wipes the singleton.

``Fact.topic`` is a ForeignKey to ``Topic`` (a BaseModel → BaseModel link, so in
the models-management UI the cell links to the topic's detail page via its
``get_absolute_url()``).
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


class FactOfTheDay(BaseModel):
    """The single, current Fact of the Day — rotated daily by a Huey cron task.

    A **singleton**: exactly one row can ever exist, enforced at the DB level by
    a unique constant ``singleton`` sentinel. ``current()`` reads it (a GET never
    writes); ``choose_for_today()`` is the cron's mutator.
    """

    fact = models.ForeignKey(
        Fact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_picks",
    )
    # Singleton sentinel: always 1. The UniqueConstraint on it is what makes this table single-row
    singleton = models.SmallIntegerField(default=1, editable=False)

    class Meta:
        ordering: ClassVar[list[str]] = ["-last_updated_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["singleton"],
                name="factoftheday_singleton_row",
            ),
        ]

    def __str__(self) -> str:
        """Return '<when set>: <fact summary>'."""
        summary = self.fact.text[:60] if self.fact else "—"
        when = f"{self.last_updated_at:%Y-%m-%d}" if self.last_updated_at else "—"
        return f"{when}: {summary}"

    @classmethod
    def current(cls) -> FactOfTheDay | None:
        """The current pick (read-only); None until the cron has run once.

        Never creates a row: ``GET /`` only displays whatever the cron last set, or
        None (empty state) before the first run / when the fact pool was empty.
        """
        return cls.objects.select_related("fact").first()

    @classmethod
    def choose_for_today(cls) -> FactOfTheDay | None:
        """Pick one random fact and upsert the singleton. None if the pool is empty.

        The only mutator. The unique ``singleton`` sentinel enforces "one row" at
        the DB level. Writes go through ``save_with_logs(user=None)``.
        """
        fact = Fact.objects.random()
        if fact is None:
            return None
        row = cls.objects.first()
        if row is None:
            row = cls(fact=fact)
        else:
            row.fact = fact
        row.save_with_logs(user=None)
        return row
