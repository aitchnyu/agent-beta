"""Tests for the structured (NDJSON) logging pipeline.

Validates the real rendered output — one JSON object per line with the stable
top-level keys the prompt contract promises — by attaching a temporary handler
that renders through the same ``ProcessorFormatter`` the live app uses. This
catches regressions in the structlog config, the contextvar binding, the
stdlib bridge, and ``dict_tracebacks`` exception structuring.
"""

from __future__ import annotations

import io
import json
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.test import TestCase

from djangoapp.logging import get_logger, json_formatter
from djangoapp.models import User

if TYPE_CHECKING:
    from collections.abc import Generator


def _ndjson(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


@contextmanager
def _capture_json() -> Generator[io.StringIO]:
    """Render every root-bound log record as NDJSON into a StringIO."""
    buf: io.StringIO = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(json_formatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield buf
    finally:
        root.removeHandler(handler)


class StructuredLoggingTests(TestCase):
    """The NDJSON contract: flat keys, levels, tracebacks, request context.

    - test_stdlib_logger_renders_as_json: a bridged stdlib log → one flat JSON object
    - test_exception_is_structured: exc_info → a structured exception field (not a string)
    - test_request_log_carries_viewer_identity: the request line carries
      public_id + username (never the integer pk)
    - test_anonymous_request_has_null_identity: an anonymous request binds
      user_public_id None
    - test_client_source_default: server records default to source=server
    """

    def test_stdlib_logger_renders_as_json(self) -> None:
        """A plain stdlib logger comes out as one flat JSON object per line."""
        with _capture_json() as buf:
            logging.getLogger("djangoapp.tests.extern").warning("hello %s", "world")
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("logger") == "djangoapp.tests.extern")
        self.assertEqual(rec["level"], "warning")
        self.assertEqual(rec["event"], "hello world")
        self.assertEqual(rec["source"], "server")
        self.assertIn("timestamp", rec)

    def test_exception_is_structured(self) -> None:
        """exc_info renders as a structured ``exception`` field, not a string."""
        with _capture_json() as buf:
            try:
                msg = "boom"
                raise ValueError(msg)  # noqa: TRY301
            except ValueError:
                get_logger("djangoapp.tests.ex").error("failed", exc_info=True)
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "failed")
        # dict_tracebacks yields a non-empty list of trace dicts (structured),
        # never a trailing multi-line string; each trace carries exc_type + frames.
        exception = rec.get("exception")
        self.assertIsInstance(exception, list)
        assert isinstance(exception, list)
        self.assertTrue(exception, "traceback must be present")
        trace = exception[0]
        self.assertIsInstance(trace, dict)
        self.assertEqual(trace.get("exc_type"), "ValueError")
        frames = trace.get("frames")
        self.assertIsInstance(frames, list)
        assert isinstance(frames, list)
        self.assertTrue(frames)
        self.assertIn("filename", frames[0])
        # show_locals=False: locals (which could hold request bodies/tokens) must
        # not be dumped into the log.
        self.assertNotIn("locals", frames[0])

    def test_request_log_carries_viewer_identity(self) -> None:
        """An authed request's http request line carries the viewer identity.

        The integer pk is never logged — only public_id + username.
        """
        user = User.objects.create_user(username="alice", password="x")
        self.client.force_login(user)
        with _capture_json() as buf:
            self.client.get("/")
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "http request")
        self.assertNotIn("user_id", rec)  # the integer pk must never be logged
        self.assertEqual(rec["user_public_id"], user.public_id)
        self.assertEqual(rec["username"], "alice")
        self.assertEqual(rec["method"], "GET")
        self.assertEqual(rec["path"], "/")

    def test_anonymous_request_has_null_identity(self) -> None:
        """An anonymous request binds user_public_id None."""
        with _capture_json() as buf:
            self.client.get("/")
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "http request")
        self.assertIsNone(rec["user_public_id"])

    def test_client_source_default(self) -> None:
        """Server records default to source=server (jq 'select(.source=="server")')."""
        with _capture_json() as buf:
            get_logger("djangoapp.tests.src").info("ping")
        records = _ndjson(buf)
        rec = next(r for r in records if r.get("event") == "ping")
        self.assertEqual(rec["source"], "server")
