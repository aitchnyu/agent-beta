"""Tests for the facts models (``Topic``, ``Fact``)."""

from django.test import TestCase

from ourapp.models import Fact, Topic


class FactModelTests(TestCase):
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
        "Topic __str__ is the name; get_absolute_url is /facts/<slug>."
        self.assertEqual(str(self.cars), "cars")
        self.assertEqual(self.cars.get_absolute_url(), "/facts/cars")

    def test_random_fact_returns_a_fact(self) -> None:
        "Topic.random_fact returns one of the topic's facts."
        fact = self.cars.random_fact()
        self.assertIsNotNone(fact)
        self.assertEqual(fact, self.f1)

    def test_random_fact_none_when_empty(self) -> None:
        "Topic.random_fact is None when the topic has no facts."
        empty = Topic.objects.create(name="empty", slug="empty")
        self.assertIsNone(empty.random_fact())

    def test_fact_objects_random_scoped(self) -> None:
        "Fact.objects.random(topic=…) only picks facts in that topic."
        for _ in range(10):
            fact = Fact.objects.random(topic=self.cars)
            self.assertEqual(fact, self.f1)

    def test_fact_objects_random_any(self) -> None:
        "Fact.objects.random() can return a fact from any topic (unscoped)."
        # Over enough draws both topics' facts appear (random() is not topic-scoped).
        picks = {Fact.objects.random() for _ in range(40)}
        self.assertEqual(picks, {self.f1, self.f2})
