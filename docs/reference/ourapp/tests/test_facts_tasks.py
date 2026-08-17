"""Tests for the Huey task (``ourapp.tasks.choose_fact_of_the_day``).

The task body is a one-line wrapper over ``FactOfTheDay.choose_for_today()``, so
these tests call the task via huey's ``call_local()`` (runs the wrapped function
immediately, bypassing the queue) — no consumer process is needed. The periodic
scheduling itself is exercised only when ``./run hueydev`` is running.
"""

from djangoapp.tests._base import BaseTestCase

from ourapp.models import Fact, FactOfTheDay, Topic
from ourapp.tasks import choose_fact_of_the_day


class FactOfTheDayTaskTests(BaseTestCase):
    """The daily cron task creates today's pick via the model classmethod.

    - test_task_creates_today_pick, call_local() creates one FactOfTheDay for today
    - test_task_idempotent_no_duplicate, calling twice leaves a single row
    - test_task_no_op_when_pool_empty, no facts → no row, no error
    """

    def setUp(self) -> None:
        self.topic = Topic.objects.create(name="cars", slug="cars")
        Fact.objects.create(text="VW Beetle ran 65 years.", topic=self.topic)

    def test_task_creates_today_pick(self) -> None:
        """call_local() runs the wrapped fn and creates today's FactOfTheDay row."""
        choose_fact_of_the_day.call_local()
        self.assertEqual(FactOfTheDay.objects.count(), 1)
        daily = FactOfTheDay.objects.get()
        self.assertIsNotNone(daily.fact)

    def test_task_idempotent_no_duplicate(self) -> None:
        """Calling the task twice on one day upserts — still a single row."""
        choose_fact_of_the_day.call_local()
        choose_fact_of_the_day.call_local()
        self.assertEqual(FactOfTheDay.objects.count(), 1)

    def test_task_no_op_when_pool_empty(self) -> None:
        """No facts → the task creates no row and raises nothing."""
        Fact.objects.all().delete()
        choose_fact_of_the_day.call_local()
        self.assertEqual(FactOfTheDay.objects.count(), 0)
