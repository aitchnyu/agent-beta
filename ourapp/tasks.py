"""Background tasks (Huey): session GC for the index/push CASCADE chain.

The chain (Session → UserSessionIndex → PushSubscription) means expired
sessions must actually be DELETED for their subscriptions to die — Django
only does that on ``clearsessions``, so the consumer runs it daily. Hour 3
local: off-peak, and well inside any realistic idle window.
"""

from __future__ import annotations

from django.core.management import call_command
from huey import crontab
from huey.contrib.djhuey import db_periodic_task


@db_periodic_task(crontab(hour=3, minute=0))
def clear_expired_sessions() -> None:
    """Daily cron: delete expired sessions (CASCADE drops index + push rows)."""
    call_command("clearsessions")
