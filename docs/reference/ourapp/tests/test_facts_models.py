"""Tests for the facts models (``Topic``, ``Fact``, ``FactOfTheDay``)."""

from django.db import IntegrityError, transaction
from djangoapp.tests._base import BaseTestCase

from ourapp.models import Fact, FactOfTheDay, Topic


class FactModelTests(BaseTestCase):
    """Topic/Fact behaviour: __str__, URLs, random pick (scoped and unscoped).

    - test_topic_str_and_url, __str__ is the name; get_absolute_url is /facts/<slug>
    - test_random_fact_returns_a_fact, Topic.random_fact returns a fact in the topic
    - test_random_fact_none_when_empty, Topic.random_fact is None when no facts exist
    - test_fact_objects_random_scoped, Fact.objects.random(topic=…) stays in the topic
    - test_fact_objects_random_any, Fact.objects.random() can pick across topics
    """

    def setUp(self) -> None:
        self.cars = Topic.objects.create(name="cars", slug="cars")
        self.science = Topic.objects.create(name="science", slug="science")
        self.f1 = Fact.objects.create(text="VW Beetle ran 65 years.", topic=self.cars)
        self.f2 = Fact.objects.create(text="Water expands when frozen.", topic=self.science)

    def test_topic_str_and_url(self) -> None:
        """Topic __str__ is the name; get_absolute_url is /facts/<slug>."""
        self.assertEqual(str(self.cars), "cars")
        self.assertEqual(self.cars.get_absolute_url(), "/facts/cars")

    def test_random_fact_returns_a_fact(self) -> None:
        """Topic.random_fact returns one of the topic's facts."""
        fact = self.cars.random_fact()
        self.assertIsNotNone(fact)
        self.assertEqual(fact, self.f1)

    def test_random_fact_none_when_empty(self) -> None:
        """Topic.random_fact is None when the topic has no facts."""
        empty = Topic.objects.create(name="empty", slug="empty")
        self.assertIsNone(empty.random_fact())

    def test_fact_objects_random_scoped(self) -> None:
        """Fact.objects.random(topic=…) only picks facts in that topic."""
        for _ in range(10):
            fact = Fact.objects.random(topic=self.cars)
            self.assertEqual(fact, self.f1)

    def test_fact_objects_random_any(self) -> None:
        """Fact.objects.random() can return a fact from any topic (unscoped)."""
        # Over enough draws both topics' facts appear (random() is not topic-scoped).
        picks = {Fact.objects.random() for _ in range(40)}
        self.assertEqual(picks, {self.f1, self.f2})


class FactOfTheDayModelTests(BaseTestCase):
    """FactOfTheDay singleton behaviour: read-only current(), single-row upsert.

    - test_current_is_none_until_chosen, current() is None and writes no row before the cron runs
    - test_current_does_not_create, current() is read-only (never inserts a row)
    - test_choose_for_today_creates_singleton, choose_for_today creates the one row pointing at a Fact
    - test_choose_for_today_is_singleton, two picks on one day = one row (upsert)
    - test_choose_for_today_rotates_fact_and_stamp, a later pick updates fact + last_updated_at on the same row
    - test_choose_for_today_none_when_pool_empty, choose_for_today is None when no facts exist (no row written)
    - test_save_rejects_second_row, a hand-rolled second insert is blocked at the DB level (IntegrityError)
    """

    def setUp(self) -> None:
        self.topic = Topic.objects.create(name="cars", slug="cars")
        self.f1 = Fact.objects.create(text="VW Beetle ran 65 years.", topic=self.topic)
        self.f2 = Fact.objects.create(text="The Corolla sells the most.", topic=self.topic)

    def test_current_is_none_until_chosen(self) -> None:
        """current() is None and writes no row before the cron has run."""
        self.assertIsNone(FactOfTheDay.current())
        self.assertEqual(FactOfTheDay.objects.count(), 0)

    def test_current_does_not_create(self) -> None:
        """current() is read-only: calling it never inserts a row."""
        FactOfTheDay.choose_for_today()
        FactOfTheDay.current()
        FactOfTheDay.current()
        self.assertEqual(FactOfTheDay.objects.count(), 1)

    def test_choose_for_today_creates_singleton(self) -> None:
        """choose_for_today creates the single row, pointing at a real Fact."""
        daily = FactOfTheDay.choose_for_today()
        assert daily is not None  # narrowing for mypy
        self.assertIn(daily.fact, {self.f1, self.f2})
        self.assertEqual(FactOfTheDay.objects.count(), 1)

    def test_choose_for_today_is_singleton(self) -> None:
        """Two choose_for_today calls upsert — still a single row."""
        FactOfTheDay.choose_for_today()
        FactOfTheDay.choose_for_today()
        self.assertEqual(FactOfTheDay.objects.count(), 1)

    def test_choose_for_today_rotates_fact_and_stamp(self) -> None:
        """A later pick updates fact + last_updated_at on the same row."""
        first = FactOfTheDay.choose_for_today()
        second = FactOfTheDay.choose_for_today()
        assert first is not None
        assert second is not None
        self.assertEqual(first.public_id, second.public_id)  # same row
        self.assertGreaterEqual(second.last_updated_at, first.last_updated_at)

    def test_choose_for_today_none_when_pool_empty(self) -> None:
        """choose_for_today is None when no facts exist (no row written)."""
        Fact.objects.all().delete()
        self.assertIsNone(FactOfTheDay.choose_for_today())
        self.assertEqual(FactOfTheDay.objects.count(), 0)

    def test_save_rejects_second_row(self) -> None:
        """The unique singleton sentinel blocks a second row at the DB level."""
        FactOfTheDay.choose_for_today()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactOfTheDay.objects.create(fact=self.f1)
