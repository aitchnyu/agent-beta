"""Fact of the Day cron task (daily local-midnight pick).

The body is a one-line wrapper over ``FactOfTheDay.choose_for_today()`` so it can
be exercised without a consumer (``choose_fact_of_the_day.call_local()`` runs the
wrapped function immediately, bypassing the queue).
"""

from __future__ import annotations

from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from ourapp.models import FactOfTheDay


@db_periodic_task(crontab(hour=0, minute=0))
def choose_fact_of_the_day() -> None:
    """Daily cron (local midnight): rotate the Fact of the Day singleton."""
    FactOfTheDay.choose_for_today()
