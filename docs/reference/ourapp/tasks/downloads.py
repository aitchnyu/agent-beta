"""Expired-download sweep (daily) — bytes post-commit, rows audited.

The body is a one-line wrapper over ``Download.delete_expired()`` so it can
be exercised without a consumer (``delete_expired_downloads.call_local()``
runs the wrapped function immediately, bypassing the queue). The time was
picked off midnight (``facts`` owns 00:00) so the two crons never share a
wake-up.
"""

from __future__ import annotations

from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from ourapp.models import Download


@db_periodic_task(crontab(hour=3, minute=0))
def delete_expired_downloads() -> None:
    """Daily cron: remove every expired download (row + file bytes)."""
    Download.delete_expired()
