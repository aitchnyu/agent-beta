"""The one redis accessor.

``settings.REDIS_URL`` is the single URL source — env for the live app,
overridden by test runs (``test_redis_env`` or ``override_settings``).
Clients are cached per URL; redis-py connects lazily, construction is
cheap.
"""

from __future__ import annotations

import re

import redis
from django.conf import settings

# One client per URL, cached: the live app reuses a single connection pool
# across requests, while an override (override_settings / test runs) gets
# its own client for the override's URL instead of mutating the live one.
_clients: dict[str, redis.Redis] = {}

# A test redis is a bare "redis://host[:port]/N" with N ≥ 1 — the live
# stack (sessions, huey) sits on DB 0, where suffix-less URLs default
# too. Nothing else flushes: redis-py strips ALL slashes from the path
# and silently defaults to DB 0 on an unparseable remainder ("…/x/2"
# resolves DB 0), so the authority and path stay strict.
_TEST_REDIS = re.compile(r"^rediss?://[^/]+/[1-9][0-9]*$")


def redis_client() -> redis.Redis:
    """Return a client for the current ``settings.REDIS_URL`` (cached per URL)."""
    url = settings.REDIS_URL
    client = _clients.get(url)
    if client is None:
        client = _clients[url] = redis.Redis.from_url(
            url,
            decode_responses=True,
            # Local redis connects in milliseconds; this is only a ceiling
            # so a dead endpoint can never hang on the OS connect timeout.
            socket_connect_timeout=2,
        )
    return client


def clear_redis() -> None:
    """Flush the CURRENT settings redis — test DBs only.

    Only a bare nonzero-DB URL flushes (see _TEST_REDIS); DB 0 — the
    default, and the live stack's home — refuses loudly instead of
    being wiped. Never call from request paths.
    """
    url = settings.REDIS_URL
    if not _TEST_REDIS.match(url):
        message = f"clear_redis refused: {url} is not a test redis (nonzero DB)"
        raise RuntimeError(message)
    redis_client().flushdb()
