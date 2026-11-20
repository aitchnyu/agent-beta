from __future__ import annotations

from unittest import mock

import redis
from django.test import override_settings

from djangoapp import redis_client
from djangoapp.redis_client import clear_redis
from djangoapp.tests._base import BaseTestCase


class ClearRedisGuardTests(BaseTestCase):
    """``clear_redis`` flushes test DBs only — any nonzero DB is a test DB.

    - test_live_db0_refuses, an explicit /0 URL raises instead of flushing
    - test_suffix_less_url_refuses, a URL with no DB part defaults to
      DB 0 (the live stack's home) and refuses too
    - test_nonzero_db_flushes, a nonzero-DB URL is a test DB and the
      flush goes to that URL's client — never to any other
    """

    def test_live_db0_refuses(self) -> None:
        """An explicit DB 0 URL raises instead of flushing.

        - the refusal names the URL and the rule (nonzero DB), matched by
          its message
        - no redis client is ever constructed for the refused URL
        """
        with (
            override_settings(REDIS_URL="redis://127.0.0.1:6379/0"),
            mock.patch.object(redis.Redis, "from_url") as from_url,
            self.assertRaisesRegex(
                RuntimeError, r"^clear_redis refused: .*/0 is not a test redis \(nonzero DB\)$"
            ),
        ):
            clear_redis()
        from_url.assert_not_called()

    def test_suffix_less_url_refuses(self) -> None:
        """A URL without a DB part reads as the live DB and refuses.

        - redis defaults a suffix-less URL to DB 0, so the guard treats
          it as live even though no /0 appears in the URL
        - the refusal message carries the exact URL
        """
        with (
            override_settings(REDIS_URL="redis://127.0.0.1:6379"),
            self.assertRaisesRegex(
                RuntimeError,
                r"^clear_redis refused: redis://127\.0\.0\.1:6379 is not a test redis \(nonzero DB\)$",
            ),
        ):
            clear_redis()

    def test_nonzero_db_flushes(self) -> None:
        """A nonzero-DB URL is a test DB and flushes that URL only.

        - the flushdb call rides the client built from the configured
          test URL
        - no other URL's client is touched (the cache holds one entry)
        """
        client = mock.MagicMock()
        self.addCleanup(redis_client._clients.pop, "redis://127.0.0.1:6379/2", None)
        with (
            override_settings(REDIS_URL="redis://127.0.0.1:6379/2"),
            mock.patch.object(redis.Redis, "from_url", return_value=client) as from_url,
        ):
            clear_redis()
        from_url.assert_called_once_with(
            "redis://127.0.0.1:6379/2",
            decode_responses=True,
            socket_connect_timeout=2,
        )
        client.flushdb.assert_called_once_with()
