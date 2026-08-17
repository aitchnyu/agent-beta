from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, cast
from unittest.mock import Mock, patch

import httpx

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase, BaseTestCase
from djangoapp.views import opencode

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.http import HttpResponse


def _fake_stream(_request: object, _session_id: str | None, _message: str) -> Iterator[bytes]:
    """Stand-in for the httpx-backed stream so the view wiring is unit-testable.

    Yields the synthetic ``session`` event the real stream emits first.
    """
    yield b'data: {"type":"session","properties":{"session_id":"ses_x"}}\n\n'


class _FakeStreamCM:
    """Stand-in for ``httpx.Client(...).stream("GET", "/event")``.

    The real call opens a streaming HTTP response whose ``iter_lines()`` yields
    the SSE lines. Tests inject the lines they want ``_iter_sse`` to see.
    """

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def __enter__(self) -> Mock:
        resp = Mock()
        resp.iter_lines = Mock(return_value=iter(self._lines))
        return resp

    def __exit__(self, *_exc: object) -> None:
        return None


def _stream_client(lines: list[str]) -> Mock:
    """Build a fake ``httpx.Client`` whose ``/event`` stream yields ``lines``."""
    client = Mock()
    client.stream = Mock(return_value=_FakeStreamCM(lines))
    client.close = Mock()
    return client


def _sse_line(event: dict[str, Any]) -> str:
    """Build one ``data: <json>`` SSE line (mirrors opencode's wire format)."""
    return f"data: {json.dumps(event)}"


def _frames(chunks: bytes) -> list[dict[str, Any]]:
    """Parse the SSE bytes our view emits back into event dicts."""
    out: list[dict[str, Any]] = []
    for frame in chunks.split(b"\n\n"):
        if not frame:
            continue
        line = frame.split(b"\n", 1)[0]
        assert line.startswith(b"data: ")
        out.append(json.loads(line[6:]))
    return out


class OpencodePageTests(BaseInertiaTestCase):
    """Superuser-only chat page at /agent/.

    - test_anonymous_404, unauthenticated visitor gets 404 (never the page)
    - test_non_superuser_404, signed-in non-superuser gets 404
    - test_superuser_200, superuser gets the Inertia page (component pinned)
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_anonymous_404(self) -> None:
        """Anonymous visitor learns nothing — the gate 404s before rendering."""
        response = self.client.get("/agent/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_non_superuser_404(self) -> None:
        """A signed-in non-superuser is also 404'd, matching the management-route rule."""
        self.client.force_login(self.plain)
        response = self.client.get("/agent/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_superuser_200(self) -> None:
        """Superuser gets the rendered OpencodeChat Inertia page."""
        self.client.force_login(self.superuser)
        response = self.client.get("/agent/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertComponentUsed("OpencodeChat")


class OpencodePromptTests(BaseTestCase):
    """Streaming prompt endpoint POST /agent/api/prompt/.

    No Inertia features are exercised (the streaming response isn't an Inertia
    response), so this uses plain ``TestCase`` to skip the Inertia/DB overhead.

    - test_anonymous_post_404, unauthenticated POST is 404
    - test_anonymous_get_405, unauthenticated GET is 405 (ninja dispatches the
      method before the op's auth check runs)
    - test_invalid_body_422, a body missing ``message`` is rejected with 422
    - test_streams_for_superuser, superuser POST returns an SSE stream whose
      first frame carries the session id (httpx stream stubbed out)
    """

    superuser: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)

    def test_anonymous_post_404(self) -> None:
        """Unauthenticated POST (valid body) is gated before any opencode call.

        ninja validates the body before the op runs, so the body must be valid
        to reach the auth gate — an invalid body would 422 first.
        """
        response = self.client.post(
            "/agent/api/prompt/", {"message": "hi"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_anonymous_get_405(self) -> None:
        """Unauthenticated GET is 405 — ninja checks the method before the op runs."""
        response = self.client.get("/agent/api/prompt/")
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_invalid_body_422(self) -> None:
        """A body without ``message`` fails pydantic validation with 422."""
        self.client.force_login(self.superuser)
        response = self.client.post("/agent/api/prompt/", {}, content_type="application/json")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_streams_for_superuser(self) -> None:
        """Superuser POST returns an SSE stream; session frame first, SSE headers set."""
        self.client.force_login(self.superuser)
        with patch.object(opencode, "_event_stream", _fake_stream):
            response = self.client.post(
                "/agent/api/prompt/",
                {"message": "hi", "session_id": "ses_x"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        # Load-bearing for SSE through nginx/dev-server buffering.
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        body = b"".join(response.streaming_content)  # type: ignore[attr-defined]
        frames = _frames(body)
        self.assertEqual(frames[0], {"type": "session", "properties": {"session_id": "ses_x"}})


class _OpencodeProxyMixin:
    """Shared safety net for the opencode proxy endpoints (superuser-only POST).

    Each proxy forwards to opencode and returns ``{ok}`` (200) or 502.
    Subclasses set ``endpoint`` (the proxy URL) and ``body`` (a valid request
    body); the mixin supplies the non-superuser-404, wrong-method-405 and
    transport-error-502 tests so every endpoint gets the same coverage without
    copy-paste. ``superuser`` and ``plain`` come from each subclass's
    ``setUpTestData``. Not itself a TestCase, so the runner never collects it.
    """

    endpoint: ClassVar[str]
    body: ClassVar[dict[str, Any]]
    superuser: ClassVar[User]
    plain: ClassVar[User]

    def _post(self) -> HttpResponse:
        resp = self.client.post(  # type: ignore[attr-defined]
            self.endpoint, self.body, content_type="application/json"
        )
        return cast("HttpResponse", resp)

    def test_non_superuser_404(self) -> None:
        """A signed-in non-superuser is gated exactly like an anonymous user."""
        self.client.force_login(self.plain)  # type: ignore[attr-defined]
        self.assertEqual(self._post().status_code, HTTPStatus.NOT_FOUND)  # type: ignore[attr-defined]

    def test_wrong_method_405(self) -> None:
        """A superuser using the wrong verb gets 405 (not 404)."""
        self.client.force_login(self.superuser)  # type: ignore[attr-defined]
        response = self.client.get(self.endpoint)  # type: ignore[attr-defined]
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)  # type: ignore[attr-defined]

    def test_transport_error_returns_502(self) -> None:
        """A daemon transport failure (conn refused/DNS/timeout) -> 502, not 500."""
        self.client.force_login(self.superuser)  # type: ignore[attr-defined]
        with patch(
            "djangoapp.views.opencode.httpx.request",
            side_effect=httpx.HTTPError("conn refused"),
        ):
            self.assertEqual(self._post().status_code, HTTPStatus.BAD_GATEWAY)  # type: ignore[attr-defined]


class OpencodePermissionTests(_OpencodeProxyMixin, BaseTestCase):
    """Permission proxy POST /agent/api/permission/<sid>/<permid>/.

    No Inertia features are exercised; uses plain ``TestCase``.

    - test_anonymous_404, unauthenticated POST is 404
    - test_invalid_response_422, a response outside once/always/reject is 422
    - test_proxies_to_opencode, a valid decision is forwarded verbatim to opencode
    - test_proxies_opencode_failure_returns_502, opencode rejection → 502
    - inherited: non-superuser-404, wrong-method-405, transport-error-502
    """

    endpoint = "/agent/api/permission/ses_x/per_x/"
    body: ClassVar[dict[str, Any]] = {"response": "once"}
    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_anonymous_404(self) -> None:
        """Unauthenticated POST never reaches the opencode permission endpoint."""
        response = self.client.post(
            "/agent/api/permission/ses_x/per_x/",
            {"response": "once"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_invalid_response_422(self) -> None:
        """A response other than once/always/reject is rejected with 422."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            "/agent/api/permission/ses_x/per_x/",
            {"response": "maybe"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_proxies_to_opencode(self) -> None:
        """A valid decision is forwarded to opencode with the same body, no extra fields."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.request", return_value=Mock(is_success=True)
        ) as posted:
            response = self.client.post(
                "/agent/api/permission/ses_x/per_x/",
                {"response": "always"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        posted.assert_called_once_with(
            "POST",
            f"{opencode._OPENCODE_BASE}/session/ses_x/permissions/per_x",
            json={"response": "always"},
            timeout=opencode._OPENCODE_TIMEOUT,
        )

    def test_proxies_opencode_failure_returns_502(self) -> None:
        """Opencode rejection surfaces as 502, not 200 with ``ok:false``."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.request",
            return_value=Mock(is_success=False, text="no such permission"),
        ) as posted:
            response = self.client.post(
                "/agent/api/permission/ses_x/per_x/",
                {"response": "once"},
                content_type="application/json",
            )
        # The mock must actually intercept (and be the rejection, not a transport
        # error): assert the exact call + detail-from-body so a drifted patch
        # target can't let a real httpx call raise HTTPError and still pass 502.
        posted.assert_called_once_with(
            "POST",
            f"{opencode._OPENCODE_BASE}/session/ses_x/permissions/per_x",
            json={"response": "once"},
            timeout=opencode._OPENCODE_TIMEOUT,
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(response.json(), {"ok": False, "detail": "no such permission"})


class OpencodeAbortTests(_OpencodeProxyMixin, BaseTestCase):
    """Abort endpoint POST /agent/api/abort/<sid>/.

    - test_anonymous_404, unauthenticated POST is 404
    - test_proxies_to_opencode, superuser POST forwards to opencode's session abort
    - inherited: non-superuser-404, wrong-method-405, transport-error-502
    """

    endpoint = "/agent/api/abort/ses_x/"
    body: ClassVar[dict[str, Any]] = {}
    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_anonymous_404(self) -> None:
        """Unauthenticated POST never reaches the opencode abort endpoint."""
        response = self.client.post("/agent/api/abort/ses_x/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_proxies_to_opencode(self) -> None:
        """A superuser stop is forwarded to opencode's session abort."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.request", return_value=Mock(is_success=True)
        ) as posted:
            response = self.client.post("/agent/api/abort/ses_x/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        posted.assert_called_once_with(
            "POST",
            f"{opencode._OPENCODE_BASE}/session/ses_x/abort",
            timeout=opencode._OPENCODE_TIMEOUT,
        )


class OpencodeDeleteSessionTests(_OpencodeProxyMixin, BaseTestCase):
    """Session-delete endpoint POST /agent/api/delete/<sid>/.

    The proxy stays POST (CSRF/HTTP-client consistency) and translates to opencode's
    ``DELETE /session/:id``. Inherits non-superuser-404, wrong-method-405,
    transport-error-502 from the mixin.

    - test_anonymous_404, unauthenticated POST is 404
    - test_proxies_to_opencode_as_delete, a superuser POST is forwarded as DELETE
    - test_proxies_opencode_failure_returns_502, opencode rejection -> 502
    """

    endpoint = "/agent/api/delete/ses_x/"
    body: ClassVar[dict[str, Any]] = {}
    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_anonymous_404(self) -> None:
        """Unauthenticated POST never reaches the opencode delete endpoint."""
        response = self.client.post("/agent/api/delete/ses_x/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_proxies_to_opencode_as_delete(self) -> None:
        """The POST proxy is forwarded to opencode as ``DELETE /session/:id``."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.request", return_value=Mock(is_success=True)
        ) as posted:
            response = self.client.post("/agent/api/delete/ses_x/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        posted.assert_called_once_with(
            "DELETE",
            f"{opencode._OPENCODE_BASE}/session/ses_x",
            timeout=opencode._OPENCODE_TIMEOUT,
        )

    def test_proxies_opencode_failure_returns_502(self) -> None:
        """An opencode rejection (e.g. unknown session) surfaces as 502."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.request",
            return_value=Mock(is_success=False, text="no such session"),
        ):
            response = self.client.post("/agent/api/delete/ses_x/")
        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(response.json()["ok"], False)


class OpencodeStreamCoreTests(BaseTestCase):
    r"""Pure helpers behind the SSE proxy — no DB, no network.

    - test_iter_sse_joins_multiline_data, several ``data:`` lines for one event join and parse
    - test_iter_sse_strips_one_leading_space, the SSE single-space rule (not lstrip)
    - test_iter_sse_skips_non_data_lines, comments and ``event:``/``id:`` lines are ignored
    - test_iter_sse_skips_invalid_json, a malformed frame is dropped, the next frame still yields
    - test_iter_sse_flushes_trailing_frame_without_blank_line, unterminated final frame still yields
    - test_is_relevant_filters_unrelated_types, noise types are dropped even on the right session
    - test_is_relevant_filters_other_sessions, a relevant type for another session is dropped
    - test_is_relevant_accepts_relevant_for_session, relevant type + matching session passes
    - test_is_relevant_passes_error_events_for_session, ``error`` events now pass for the session
    - test_is_idle_only_on_status_idle, ``session.status`` ``type:idle`` is the sole idle marker
    - test_sse_framing, an event is emitted as one ``data: <json>\\n\\n`` frame
    """

    def test_iter_sse_joins_multiline_data(self) -> None:
        """Multi-line ``data:`` payloads are joined with newlines before parsing.

        Input lines (one event split across three ``data:`` lines):
            data: {
            data: "type": "a",
            data: "properties": {"x": 1}}
            <blank>
        Yields one event: ``{"type": "a", "properties": {"x": 1}}``.
        """
        resp = _FakeStreamCM(
            [
                "data: {",
                'data: "type": "a",',
                'data: "properties": {"x": 1}}',
                "",
            ]
        )
        events = list(opencode._iter_sse(resp.__enter__()))
        self.assertEqual(events, [{"type": "a", "properties": {"x": 1}}])

    def test_iter_sse_strips_exactly_one_leading_space(self) -> None:
        r"""The SSE spec strips exactly one leading space after ``data:``.

        Input: ``data:   {"type": "a"}`` (three spaces after ``data:``).
        Spec strips one → ``json.loads`` receives ``'  {"type": "a"}'``
        (two spaces). ``lstrip(" ")`` would have stripped all three.

        JSON parsing ignores leading whitespace, so this can't be observed in
        the parsed output — verify by capturing the raw payload handed to
        ``json.loads``.
        """
        captured: list[str] = []
        real_loads = json.loads

        def spy(payload: str) -> object:
            captured.append(payload)
            return real_loads(payload)

        resp = _FakeStreamCM(
            [
                'data:   {"type": "a"}',  # three leading spaces
                "",
            ]
        )
        with patch.object(json, "loads", side_effect=spy):
            list(opencode._iter_sse(resp.__enter__()))
        # strip-one leaves two leading spaces; strip-all would leave none.
        self.assertEqual(captured, ['  {"type": "a"}'])

    def test_iter_sse_skips_non_data_lines(self) -> None:
        """Comments (``:``), ``event:``, and ``id:`` lines don't pollute the payload."""
        resp = _FakeStreamCM(
            [
                ": heartbeat",
                "event: message",
                "id: 42",
                'data: {"type": "a"}',
                "",
            ]
        )
        events = list(opencode._iter_sse(resp.__enter__()))
        self.assertEqual(events, [{"type": "a"}])

    def test_iter_sse_skips_invalid_json(self) -> None:
        """One malformed frame must not kill the rest of the stream."""
        resp = _FakeStreamCM(
            [
                "data: not-json",
                "",
                'data: {"type": "ok"}',
                "",
            ]
        )
        events = list(opencode._iter_sse(resp.__enter__()))
        self.assertEqual(events, [{"type": "ok"}])

    def test_iter_sse_flushes_trailing_frame_without_blank_line(self) -> None:
        r"""A trailing frame lacking a blank-line terminator still yields.

        Without this, a daemon whose last write before close is ``data: {idle}
        \\n`` (no second newline) loses the idle marker — the most common
        trigger for the spurious "stream ended without idle" error.
        """
        resp = _FakeStreamCM(
            [
                'data: {"type": "session.status", "properties": {"status": {"type": "idle"}}}',
            ]
        )
        events = list(opencode._iter_sse(resp.__enter__()))
        self.assertEqual(
            events,
            [{"type": "session.status", "properties": {"status": {"type": "idle"}}}],
        )

    def test_is_relevant_filters_unrelated_types(self) -> None:
        """Noise types (server.connected, session.updated, …) are dropped."""
        for noise in ("server.connected", "session.updated", "server.heartbeat"):
            self.assertFalse(
                opencode._is_relevant(
                    {"type": noise, "properties": {"sessionID": "ses_x"}},
                    "ses_x",
                )
            )

    def test_is_relevant_filters_other_sessions(self) -> None:
        """A relevant event for a different session is dropped (/event is global)."""
        self.assertFalse(
            opencode._is_relevant(
                {"type": "message.part.delta", "properties": {"sessionID": "ses_other"}},
                "ses_x",
            )
        )

    def test_is_relevant_accepts_relevant_for_session(self) -> None:
        """A relevant event on the right session passes the filter."""
        self.assertTrue(
            opencode._is_relevant(
                {"type": "permission.asked", "properties": {"sessionID": "ses_x"}},
                "ses_x",
            )
        )

    def test_is_relevant_passes_error_events_for_session(self) -> None:
        """opencode-emitted ``error`` events tagged with this session reach the client."""
        self.assertTrue(
            opencode._is_relevant(
                {"type": "error", "properties": {"sessionID": "ses_x", "message": "tool failed"}},
                "ses_x",
            )
        )

    def test_is_idle_only_on_status_idle(self) -> None:
        """Only ``session.status`` → ``status.type == "idle"`` ends a turn."""
        self.assertTrue(
            opencode._is_idle(
                {"type": "session.status", "properties": {"status": {"type": "idle"}}}
            )
        )
        self.assertFalse(
            opencode._is_idle(
                {"type": "session.status", "properties": {"status": {"type": "busy"}}}
            )
        )
        self.assertFalse(opencode._is_idle({"type": "message.part.updated", "properties": {}}))

    def test_sse_framing(self) -> None:
        r"""``_sse`` serialises a typed synthetic event to ``data: <json>\\n\\n``."""
        self.assertEqual(
            opencode._sse(opencode._SseError(properties=opencode._SseErrorProps(message="x"))),
            b'data: {"type": "error", "properties": {"message": "x"}}\n\n',
        )

    def test_encode_path_segment_quotes_unsafe_chars(self) -> None:
        """``_encode_path_segment`` URL-encodes so /, ?, or # can't rewrite the upstream URL."""
        self.assertEqual(opencode._encode_path_segment("a/b"), "a%2Fb")
        self.assertEqual(opencode._encode_path_segment("a?b"), "a%3Fb")
        self.assertEqual(opencode._encode_path_segment("a#b"), "a%23b")
        self.assertEqual(opencode._encode_path_segment("safe"), "safe")

    def test_is_relevant_passes_unscoped_error(self) -> None:
        """An ``error`` with no sessionID still reaches the client (auth/rate-limit)."""
        self.assertTrue(
            opencode._is_relevant({"type": "error", "properties": {"message": "boom"}}, "ses_x")
        )

    def test_is_relevant_drops_other_session_error(self) -> None:
        """An ``error`` tagged to another session is still dropped (not broadcast)."""
        self.assertFalse(
            opencode._is_relevant(
                {"type": "error", "properties": {"sessionID": "ses_other", "message": "boom"}},
                "ses_x",
            )
        )

    def test_client_disconnected_handles_wsgi_request(self) -> None:
        """A WSGI request has no ``is_closed()`` — degrade to False, don't raise.

        Regression guard: calling ``request.is_closed()`` directly raised
        ``AttributeError`` under the dev server (WSGI), which surfaced mid-stream
        as an SSE error.
        """
        wsgi_request = Mock(spec=[])  # no is_closed attribute, like WSGIRequest
        self.assertFalse(opencode._client_disconnected(wsgi_request))
        self.assertFalse(opencode._client_disconnected(None))

    def test_client_disconnected_detects_asgi_close(self) -> None:
        """An ASGI request reporting ``is_closed()`` → True."""
        asgi_request = Mock()
        asgi_request.is_closed = Mock(return_value=True)
        self.assertTrue(opencode._client_disconnected(asgi_request))


class OpencodeEventStreamTests(BaseTestCase):
    """End-to-end behaviour of ``_event_stream`` with httpx mocked out.

    - test_emits_session_frame_first, the synthetic session event leads the stream
    - test_create_session_failure_emits_error, daemon-down at session create surfaces an error
    - test_prompt_async_failure_emits_error, a non-2xx prompt_async surfaces an error and ends
    - test_stream_end_without_idle_emits_error, a daemon drop surfaces an error
    - test_idle_closes_cleanly, an idle marker ends the stream with no trailing error
    """

    def _run(
        self,
        lines: list[str],
        *,
        prompt_ok: bool = True,
        session_id: str | None = "ses_x",
    ) -> tuple[list[dict[str, Any]], Mock]:
        """Drive ``_event_stream`` with httpx mocked out; return (frames, post_mock).

        ``request`` is passed as ``None`` (no client-disconnect detection in
        tests). ``post_mock`` is the ``httpx.post`` mock so callers can assert
        on the prompt_async / abort call shape.
        """
        client = _stream_client(lines)
        prompt_resp = Mock(
            is_success=prompt_ok,
            status_code=200 if prompt_ok else 400,
            text="bad",
        )
        post_mock = Mock(return_value=prompt_resp)
        with (
            patch("djangoapp.views.opencode.httpx.Client", return_value=client),
            patch("djangoapp.views.opencode.httpx.post", post_mock),
        ):
            chunks = b"".join(opencode._event_stream(None, session_id, "hi"))
        return _frames(chunks), post_mock

    def test_emits_session_frame_first(self) -> None:
        """The client always learns its session id before any opencode event."""
        events, _ = self._run(
            [
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                "",
            ]
        )
        self.assertTrue(events)
        self.assertEqual(events[0], {"type": "session", "properties": {"session_id": "ses_x"}})

    def test_create_session_failure_emits_error(self) -> None:
        """A daemon-down failure at session creation surfaces as an SSE error."""
        with patch(
            "djangoapp.views.opencode._create_session",
            side_effect=httpx.HTTPError("connection refused"),
        ):
            chunks = b"".join(opencode._event_stream(None, None, "hi"))
        events = _frames(chunks)
        self.assertEqual([e["type"] for e in events], ["error"])
        self.assertIn("session", events[-1]["properties"]["message"])

    def test_prompt_async_failure_emits_error(self) -> None:
        """A rejected prompt_async surfaces an error and the stream ends (no idle hang)."""
        events, _ = self._run([], prompt_ok=False)
        types = [e["type"] for e in events]
        self.assertIn("error", types)
        # No idle-driven close, no trailing "stream ended without idle" — the
        # prompt_async error is the only thing after the session frame.
        self.assertEqual(types, ["session", "error"])
        self.assertIn("prompt_async", events[-1]["properties"]["message"])

    def test_stream_end_without_idle_emits_error(self) -> None:
        """If the daemon drops mid-turn, the client learns instead of clearing silently."""
        events, _ = self._run(
            [
                _sse_line(
                    {
                        "type": "message.part.delta",
                        "properties": {"sessionID": "ses_x", "delta": "hi"},
                    }
                ),
                "",
            ]
        )
        types = [e["type"] for e in events]
        self.assertEqual(types[-1], "error")
        self.assertIn("idle", events[-1]["properties"]["message"])

    def test_idle_closes_cleanly(self) -> None:
        """An idle marker ends the stream with no trailing error."""
        events, _ = self._run(
            [
                _sse_line(
                    {
                        "type": "message.part.delta",
                        "properties": {"sessionID": "ses_x", "delta": "hi"},
                    }
                ),
                "",
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                "",
            ]
        )
        types = [e["type"] for e in events]
        self.assertNotIn("error", types)
        self.assertEqual(types[-2:], ["message.part.delta", "session.status"])

    def test_idle_marker_without_trailing_blank_line_still_closes_cleanly(self) -> None:
        """A trailing-frame flush must not turn a clean idle into a "no idle" error.

        Regression guard for ``_iter_sse``'s end-of-stream flush: a daemon that
        emits the idle marker without a trailing blank line still ends the
        stream cleanly (no spurious "stream ended without idle").
        """
        events, _ = self._run(
            [
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                # No trailing blank line — _iter_sse must still flush and yield.
            ]
        )
        types = [e["type"] for e in events]
        self.assertNotIn("error", types)
        self.assertEqual(types, ["session", "session.status"])

    def test_create_session_happy_path_propagates_new_id(self) -> None:
        """An absent session_id: the daemon creates one and it propagates.

        Covers the most common flow (first prompt) — the new id must reach both
        the synthetic ``session`` frame and ``_is_relevant``'s filter.
        """
        with patch(
            "djangoapp.views.opencode._create_session",
            return_value=opencode._SessionCreated(id="ses_new"),
        ):
            events, _ = self._run(
                [
                    _sse_line(
                        {
                            "type": "message.part.delta",
                            "properties": {"sessionID": "ses_new", "delta": "hi"},
                        }
                    ),
                    "",
                    _sse_line(
                        {
                            "type": "session.status",
                            "properties": {
                                "sessionID": "ses_new",
                                "status": {"type": "idle"},
                            },
                        }
                    ),
                    "",
                ],
                session_id=None,
            )
        self.assertEqual(events[0], {"type": "session", "properties": {"session_id": "ses_new"}})
        # The filter adopted the new id — an event tagged ses_new passes through.
        self.assertEqual(events[1]["type"], "message.part.delta")

    def test_prompt_async_shape(self) -> None:
        """prompt_async is fired with the model, a text part, and the timeout."""
        _events, post_mock = self._run(
            [
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                "",
            ]
        )
        post_mock.assert_any_call(
            f"{opencode._OPENCODE_BASE}/session/ses_x/prompt_async",
            json={
                "model": opencode._MODEL,
                "parts": [{"type": "text", "text": "hi"}],
            },
            timeout=opencode._OPENCODE_TIMEOUT,
        )

    def test_stream_client_closed(self) -> None:
        """The /event httpx client is closed when the stream ends (no pool leak)."""
        client = _stream_client(
            [
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                "",
            ]
        )
        prompt_resp = Mock(is_success=True, status_code=200, text="ok")
        with (
            patch("djangoapp.views.opencode.httpx.Client", return_value=client),
            patch("djangoapp.views.opencode.httpx.post", return_value=prompt_resp),
        ):
            b"".join(opencode._event_stream(None, "ses_x", "hi"))
        client.close.assert_called_once()

    def test_permission_asked_then_replied_round_trip(self) -> None:
        """The id<->requestID contract round-trips through the proxy.

        asked.id and replied.requestID are both forwarded unchanged; the FE
        correlates requestID to id, so this equality is load-bearing.
        """
        events, _ = self._run(
            [
                _sse_line(
                    {
                        "type": "permission.asked",
                        "properties": {
                            "sessionID": "ses_x",
                            "id": "per_42",
                            "permission": "bash",
                            "metadata": {"command": "ls"},
                            "always": [],
                        },
                    }
                ),
                "",
                _sse_line(
                    {
                        "type": "permission.replied",
                        "properties": {
                            "sessionID": "ses_x",
                            "requestID": "per_42",
                            "reply": "once",
                        },
                    }
                ),
                "",
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                "",
            ]
        )
        asked = next(e for e in events if e["type"] == "permission.asked")
        replied = next(e for e in events if e["type"] == "permission.replied")
        self.assertEqual(asked["properties"]["id"], "per_42")
        self.assertEqual(replied["properties"]["requestID"], "per_42")

    def test_permission_asked_is_forwarded(self) -> None:
        """Forward a permission.asked normally (exercises the cap reset on a touchpoint)."""
        events, _ = self._run(
            [
                _sse_line(
                    {
                        "type": "permission.asked",
                        "properties": {
                            "sessionID": "ses_x",
                            "id": "per_1",
                            "permission": "bash",
                        },
                    }
                ),
                "",
                _sse_line(
                    {
                        "type": "session.status",
                        "properties": {"sessionID": "ses_x", "status": {"type": "idle"}},
                    }
                ),
                "",
            ]
        )
        types = [e["type"] for e in events]
        self.assertIn("permission.asked", types)
        self.assertNotIn("error", types)


class OpencodeTranscriptTests(BaseTestCase):
    """Transcript endpoint GET /agent/api/session/<sid>/transcript/.

    Returns the daemon's persisted transcript verbatim so the client can
    reconcile after a dropped stream (dev-server reload, daemon bounce). No
    Inertia features are exercised; plain ``TestCase``.

    - test_proxies_transcript_verbatim, superuser GET returns the daemon body unchanged
    - test_proxies_opencode_failure_returns_502, daemon rejection -> 502
    - test_transport_error_returns_502, daemon unreachable -> 502
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_proxies_transcript_verbatim(self) -> None:
        """The daemon's persisted transcript is returned unchanged, as JSON."""
        self.client.force_login(self.superuser)
        body = '[{"info":{"role":"user"},"parts":[{"id":"prt_1","type":"text","text":"hi"}]}]'
        with patch(
            "djangoapp.views.opencode.httpx.get",
            return_value=Mock(is_success=True, content=body.encode()),
        ) as got:
            response = self.client.get("/agent/api/session/ses_x/transcript/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("application/json", response.headers["Content-Type"])
        # Verbatim passthrough — the client validates the shape with zod.
        self.assertEqual(response.content, body.encode())
        got.assert_called_once_with(
            f"{opencode._OPENCODE_BASE}/session/ses_x/message",
            timeout=opencode._OPENCODE_TIMEOUT,
        )

    def test_proxies_opencode_failure_returns_502(self) -> None:
        """A daemon rejection (e.g. unknown session) surfaces as 502."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.get",
            return_value=Mock(is_success=False, text="no such session"),
        ):
            response = self.client.get("/agent/api/session/ses_x/transcript/")
        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(response.json(), {"ok": False, "detail": "no such session"})

    def test_transport_error_returns_502(self) -> None:
        """A daemon transport failure (conn refused) -> 502, not 500."""
        self.client.force_login(self.superuser)
        with patch(
            "djangoapp.views.opencode.httpx.get",
            side_effect=httpx.HTTPError("conn refused"),
        ):
            response = self.client.get("/agent/api/session/ses_x/transcript/")
        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
