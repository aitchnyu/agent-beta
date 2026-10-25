"""The one redis accessor.

``settings.REDIS_URL`` is the single URL source — env for the live app,
overridden by test runs (run's export or ``override_settings``). Clients
are cached per URL; redis-py connects lazily, construction is cheap.
"""

from __future__ import annotations

import os

import redis
from django.conf import settings

# One client per URL, cached: the live app reuses a single connection pool
# across requests, while an override (override_settings / run's test-redis
# export) gets its own client for the override's URL instead of mutating
# the live one.
_clients: dict[str, redis.Redis] = {}


def redis_client() -> redis.Redis:
    """Return a client for the current ``settings.REDIS_URL`` (cached per URL)."""
    url = settings.REDIS_URL
    client = _clients.get(url)
    if client is None:
        client = _clients[url] = redis.Redis.from_url(
            url,
            decode_responses=True,
            # Local redis connects in milliseconds; this is only a ceiling
            # so a dead endpoint (the fail-closed test's dead port) can
            # never hang on the OS connect timeout.
            socket_connect_timeout=2,
        )
    return client


def clear_redis() -> None:
    """Flush the CURRENT settings redis.

    Test runs point it at an isolated DB — run's ``_with_test_redis`` also
    exports ``DESMO_TEST_REDIS=1``, which this requires, so a bare
    ``manage.py test`` (live DB 0) refuses loudly instead of wiping it.
    Never call from request paths.
    """
    if not os.environ.get("DESMO_TEST_REDIS"):
        msg = "clear_redis refused: not a run-wrapped test process (live redis would be wiped)"
        raise RuntimeError(msg)
    redis_client().flushdb()
