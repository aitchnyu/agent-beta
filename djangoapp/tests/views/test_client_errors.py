"""Tests for POST /client-errors — the frontend error capture sink."""

from __future__ import annotations

import io
import json
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

import redis
from django.test import TestCase

from djangoapp.logging import json_formatter
from djangoapp.models import User
from djangoapp.views import client_errors

if TYPE_CHECKING:
    from collections.abc import Generator


# Real redis on an isolated DB (not the app's DB 0), so the 429 test exercises the
# actual INCR/EXPIRE/count path with no hand-rolled fake. Redis is always present.
_TEST_REDIS_URL = "redis://127.0.0.1:6379/2"


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "message": "boom at render",
        "stack": "Error: boom\n    at foo (app.js:1:10)",
        "filename": "http://app/static/djangoapp/main.js",
        "lineno": 42,
        "colno": 7,
        "url": "http://app/some/page",
        "userAgent": "Mozilla/5.0 (test)",
        "vueInfo": "render",
        "public_id": "ignored-client-value",
    }
    base.update(overrides)
    return base


@contextmanager
def _capture_json() -> Generator[io.StringIO]:
    buf: io.StringIO = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(json_formatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield buf
    finally:
        root.removeHandler(handler)


def _ndjson(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


class ClientErrorViewTests(TestCase):
    """Server-side behaviour of POST /client-errors (no browser involved).

    These POST directly (``self.client.post``) and assert on the resulting
    ``client error`` log record + status — i.e. what the *backend* does with a
    report: authoritative identity from ``request.user`` (not the body),
    anonymous accepted, Redis rate limiting. The *frontend* half — capturing an
    uncaught browser error and building the request payload (lineno/colno/url/
    public_id) — is owned by the Playwright ``ClientErrorReportingE2e`` suite.

    - test_authed_report_logs_client_error, authed POST → 204; source=client + row/col + user
    - test_anon_report_accepted, anonymous POST → 204 with user None
    - test_rate_limit_returns_429_over_budget, over cap → 429 (real redis)
    - test_redis_failure_fails_closed, dead redis → 500 (fail closed)
    - test_client_body_cannot_forge_log_fields, stray keys → 422 (extra=forbid)
    - test_stack_truncated_to_cap, over-cap stack truncated before logging

    Tests assert on the rendered NDJSON log record (via _capture_json) and the
    response status; identity always comes from request.user, never the body.
    """

    def test_authed_report_logs_client_error(self) -> None:
        """Authed POST → 204 with source=client + row/col/url + the user."""
        user = User.objects.create_user(username="alice", password="x", first_name="Alice")
        self.client.force_login(user)
        with _capture_json() as buf:
            response = self.client.post(
                "/client-errors", data=_payload(), content_type="application/json"
            )
        self.assertEqual(response.status_code, 204)
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "client error")
        self.assertEqual(rec["source"], "client")
        self.assertEqual(rec["logger"], "client")
        self.assertEqual(rec["client_lineno"], 42)
        self.assertEqual(rec["client_colno"], 7)
        self.assertEqual(rec["url"], "http://app/some/page")
        self.assertEqual(rec["client_filename"], "http://app/static/djangoapp/main.js")
        # Authoritative identity comes from request.user, NOT the client body.
        self.assertEqual(rec["user"], {"public_id": user.public_id, "username": "alice"})
        self.assertNotEqual(rec["user"], {"public_id": "ignored-client-value"})

    def test_anon_report_accepted(self) -> None:
        """Anonymous POST → 204 with user=None."""
        with _capture_json() as buf:
            response = self.client.post(
                "/client-errors", data=_payload(), content_type="application/json"
            )
        self.assertEqual(response.status_code, 204)
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "client error")
        self.assertIsNone(rec["user"])

    def test_rate_limit_returns_429_over_budget(self) -> None:
        """Over the per-identity cap, the (N+1)th report is 429 (real redis)."""
        test_redis = redis.Redis.from_url(_TEST_REDIS_URL, decode_responses=True)
        test_redis.flushdb()
        original = client_errors._redis_client
        client_errors._redis_client = test_redis
        original_limit = client_errors._RATE_LIMIT
        client_errors._RATE_LIMIT = 2
        try:
            self.client.force_login(User.objects.create_user(username="alice", password="x"))
            statuses = [
                self.client.post(
                    "/client-errors", data=_payload(), content_type="application/json"
                ).status_code
                for _ in range(4)
            ]
        finally:
            client_errors._redis_client = original
            client_errors._RATE_LIMIT = original_limit
            test_redis.flushdb()
        # 2 within budget → 204, then 429.
        self.assertEqual(statuses, [204, 204, 429, 429])

    def test_redis_failure_fails_closed(self) -> None:
        """A dead-redis endpoint → 500 (fail closed; report not accepted).

        ``_rate_limited`` lets the redis error propagate to ninja's global
        handler. Points redis-py at a dead port so ``execute()`` raises a real
        ``ConnectionError`` — no fake needed.
        """
        dead = redis.Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.25)
        original = client_errors._redis_client
        client_errors._redis_client = dead
        try:
            response = self.client.post(
                "/client-errors", data=_payload(), content_type="application/json"
            )
        finally:
            client_errors._redis_client = original
        self.assertEqual(response.status_code, 500)

    def test_client_body_cannot_forge_log_fields(self) -> None:
        """Stray top-level keys are rejected, not merged into the log record.

        source/user_public_id/level/logger sent in the body → 422
        (extra=forbid), so a client can't forge log fields.
        """
        forged = _payload(source="server", user_public_id="forged", level="error", logger="x")
        response = self.client.post("/client-errors", data=forged, content_type="application/json")
        self.assertEqual(response.status_code, 422)

    def test_stack_truncated_to_cap(self) -> None:
        """An over-log-cap stack (within the model cap) is truncated before logging.

        Model accepts up to _MAX_STACK_INPUT; the log line keeps _MAX_STACK_CHARS.
        """
        original = client_errors._MAX_STACK_CHARS
        client_errors._MAX_STACK_CHARS = 10
        try:
            with _capture_json() as buf:
                self.client.post(
                    "/client-errors",
                    # 100 chars: under the model's _MAX_STACK_INPUT, over the
                    # runtime log cap of 10 → exercises the view's truncation.
                    data=_payload(stack="x" * 100),
                    content_type="application/json",
                )
        finally:
            client_errors._MAX_STACK_CHARS = original
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "client error")
        self.assertEqual(len(rec["client_stack"]), 10)  # type: ignore[arg-type]
