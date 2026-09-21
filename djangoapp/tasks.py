"""Framework Huey tasks.

Auto-discovered: djhuey imports each installed app's ``tasks`` module and
``djangoapp`` is one. App-level tasks live in the apps' own ``tasks``
modules — this module holds the framework's only task, Web Push delivery,
so no request path ever waits on push-service HTTP.

Models import ``deliver_push`` at TOP level (the dependency arrow points
task → models); the models import stays function-local here because
importing it at module level would be circular.
"""

from __future__ import annotations

from huey.contrib.djhuey import db_task


@db_task()
def deliver_push(user_pk: int, payload: dict[str, str]) -> None:
    """Fan a serialized payload out to the user's live-session subscriptions.

    Thin wrapper by repo convention (fat model, thin task):
    ``djangoapp.models.notify_sessions`` owns the logic — VAPID gating,
    pruning, failure containment. Enqueued by ``Notification.record``'s
    on_commit and by ``push_test`` (views never run the fan-out inline —
    push-service HTTP is slow and capped by a 10s timeout per
    subscription). The user crosses the queue as a pk, not an instance:
    task args serialize, and a stale instance would push stale data.
    A missing user raises (huey logs the failure) — honest signal that
    the user was deleted between commit and delivery; their
    subscriptions are CASCADE-gone anyway.
    """
    from djangoapp.models import User, notify_sessions  # noqa: PLC0415

    notify_sessions(User.objects.get(pk=user_pk), payload)
