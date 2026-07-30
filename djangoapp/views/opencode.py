"""Proxy to a local ``opencode serve`` daemon, started via ``./run opencode``.

Streams one prompt turn's SSE events for a session to the browser so the Vue
chat page can render reasoning, tool calls, interactive permission prompts and
questions, and forwards the user's answers back to opencode.

All routes require a superuser (404 otherwise): the daemon can read, write and
run shell in the project, so it must not be reachable by unauthenticated users.
The dev ``runserver`` is threaded by default, so the long-lived streaming
request and the short permission POST run on separate threads (the stream waits
on the permission response, so a single-threaded server would deadlock).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

import httpx
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
    StreamingHttpResponse,
)
from inertia import render
from ninja import NinjaAPI, Router
from pydantic import BaseModel

from djangoapp.views import require_superuser

if TYPE_CHECKING:
    from collections.abc import Iterator

# Same host/port the `./run opencode` launcher binds; an explicit
# OPENCODE_BASE_URL still wins for advanced setups.
_OPENCODE_HOST = os.environ.get("OPENCODE_HOSTNAME", "127.0.0.1")
_OPENCODE_PORT = os.environ.get("OPENCODE_PORT", "4196")
# HOST/PORT are read (not inlined into the default) so Django's base URL tracks
# the daemon's bind address when OPENCODE_PORT is customised — without needing
# a separate OPENCODE_BASE_URL. (OPENCODE_BASE_URL still overrides for setups
# where Django and the daemon aren't on the same host:port.)
_OPENCODE_BASE = os.environ.get("OPENCODE_BASE_URL", f"http://{_OPENCODE_HOST}:{_OPENCODE_PORT}")
_OPENCODE_TIMEOUT = 30.0
# Wall-clock cap on agent compute within one turn. Measures time *between*
# human touchpoints (a permission asked/replied resets it — see _HUMAN_TOUCHPOINTS),
# so a slow permission answer doesn't trip it right after the user replies. It
# only fires on *incoming events*, so it catches a noisy runaway (continuous
# output, no idle) but NOT a silent hang (daemon emits nothing — that would need
# an event-independent watchdog, out of scope for a single-admin dev tool).
_STREAM_MAX_SECS = 300
# Cap on how much of an upstream error body is echoed to the client — daemon
# errors can include filesystem paths, config keys, or partial request echo, so
# don't forward the whole thing to the browser.
_MAX_DETAIL_CHARS = 500

logger = logging.getLogger(__name__)
# Provider/model used for every prompt — env-driven so a deployment can swap
# without a code change (single-admin dev tool, so no per-request override).
_PROVIDER = os.environ.get("OPENCODE_PROVIDER", "zai-coding-plan")
_MODEL_ID = os.environ.get("OPENCODE_MODEL", "glm-5.1")
_MODEL = {"providerID": _PROVIDER, "modelID": _MODEL_ID}

# opencode event types that drive the chat UI; everything else is noise.
# `error` is included so opencode-emitted tool/rate-limit errors for this
# session reach the client; Django's own synthetic `error` events (below)
# bypass this filter entirely.
_RELEVANT_TYPES = frozenset(
    {
        "error",
        "message.part.delta",
        "message.part.updated",
        "permission.asked",
        "permission.replied",
        "session.status",
    }
)

# Events that mean a human is now in the loop (a permission is pending, or just
# answered). Each one resets the _STREAM_MAX_SECS clock so the cap measures
# agent compute time, not the wait for the user's decision.
_HUMAN_TOUCHPOINTS = frozenset({"permission.asked", "permission.replied"})


class _PromptBody(BaseModel):
    message: str
    session_id: str | None = None


class _SessionCreated(BaseModel):
    id: str


class _PermissionBody(BaseModel):
    response: Literal["once", "always", "reject"]


opencode_router = Router()


def opencode_page(request: HttpRequest) -> HttpResponse:
    """Render the opencode chat page (superuser-only)."""
    require_superuser(request)
    return render(request, "OpencodeChat", {})


@opencode_router.post("/prompt/", response=None)
def prompt(request: HttpRequest, body: _PromptBody) -> HttpResponseBase:
    """Fire a prompt at opencode and stream its event stream back as SSE.

    ``response=None`` lets the StreamingHttpResponse pass through unchanged
    (ninja otherwise serialises the return into JSON).
    """
    require_superuser(request)
    response = StreamingHttpResponse(
        _event_stream(request, body.session_id, body.message),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@opencode_router.post("/permission/{session_id}/{permission_id}/", response=None)
def permission(
    request: HttpRequest, session_id: str, permission_id: str, body: _PermissionBody
) -> HttpResponse:
    """Forward the user's allow/deny decision to opencode for a tool call."""
    require_superuser(request)
    return _forward(
        f"/session/{_encode_path_segment(session_id)}/permissions/{_encode_path_segment(permission_id)}",
        json_body={"response": body.response},
    )


@opencode_router.post("/abort/{session_id}/", response=None)
def abort(request: HttpRequest, session_id: str) -> HttpResponse:
    """Stop the in-flight opencode turn for a session."""
    require_superuser(request)
    return _forward(f"/session/{_encode_path_segment(session_id)}/abort")


@opencode_router.post("/delete/{session_id}/", response=None)
def delete_session(request: HttpRequest, session_id: str) -> HttpResponse:
    """Delete the opencode session and all its data (history/context).

    The proxy stays POST (CSRF/axios consistency with the other proxies) and
    translates to opencode's ``DELETE /session/:id`` here.
    """
    require_superuser(request)
    return _forward(f"/session/{_encode_path_segment(session_id)}", method="DELETE")


def _encode_path_segment(value: str) -> str:
    """URL-encode a path component.

    A value containing ``/`` would otherwise rewrite the upstream URL.
    """
    return quote(value, safe="")


def _forward(
    path: str, *, json_body: dict[str, Any] | None = None, method: str = "POST"
) -> HttpResponse:
    """Forward a request to opencode at ``path`` and return a JSON status response.

    Success → ``200 {"ok": true}``. Failure → ``502 {"ok": false, "detail"}``
    so HTTP status alone distinguishes transport success from opencode
    rejection (the frontend's axios throws on 502, surfacing a toast).

    ``method`` defaults to POST (permission/abort); the session-delete proxy
    passes ``DELETE`` — opencode's session removal is ``DELETE /session/:id``,
    not POST.
    """
    kwargs: dict[str, Any] = {"timeout": _OPENCODE_TIMEOUT}
    if json_body is not None:
        kwargs["json"] = json_body
    try:
        opencode_resp = httpx.request(method, f"{_OPENCODE_BASE}{path}", **kwargs)
    except httpx.HTTPError as exc:
        detail = str(exc)
        logger.warning("opencode transport error for %s: %s", path, detail)
        return JsonResponse({"ok": False, "detail": detail[:_MAX_DETAIL_CHARS]}, status=502)
    if not opencode_resp.is_success:
        detail = opencode_resp.text
        logger.warning("opencode rejected %s: %s %s", path, opencode_resp.status_code, detail)
        return JsonResponse({"ok": False, "detail": detail[:_MAX_DETAIL_CHARS]}, status=502)
    return JsonResponse({"ok": True})


def _create_session() -> _SessionCreated:
    resp = httpx.post(f"{_OPENCODE_BASE}/session", json={"title": "web"}, timeout=_OPENCODE_TIMEOUT)
    resp.raise_for_status()
    return _SessionCreated.model_validate(resp.json())


def _abort_turn(session_id: str) -> None:
    """Best-effort: tell the daemon to stop the turn (client went away)."""
    with contextlib.suppress(httpx.HTTPError):
        httpx.post(
            f"{_OPENCODE_BASE}/session/{_encode_path_segment(session_id)}/abort",
            timeout=_OPENCODE_TIMEOUT,
        )


def _client_disconnected(request: HttpRequest | None) -> bool:
    """Return whether the browser has closed the connection (ASGI only).

    ``is_closed`` exists on ASGI requests (Django 4.1+) but NOT on
    ``WSGIRequest`` — WSGI doesn't surface client disconnect to the app
    synchronously. Under WSGI (dev server, gunicorn sync workers) this returns
    ``False`` (disconnect-abort is simply unavailable there; Stop + the
    compute-cap still bound a turn). Looked up via ``getattr`` so a WSGI request
    (no such attribute) doesn't raise.
    """
    if request is None:
        return False
    is_closed = getattr(request, "is_closed", None)
    return bool(is_closed()) if callable(is_closed) else False


def _fire_prompt(session_id: str, message: str) -> tuple[bool, bytes | None]:
    """Fire ``prompt_async``. Returns ``(ok, error_frame)``.

    On failure ``error_frame`` is the SSE error to emit before ending the turn
    (without it the /event stream waits for an idle that never arrives).
    """
    prompt_resp = httpx.post(
        f"{_OPENCODE_BASE}/session/{_encode_path_segment(session_id)}/prompt_async",
        json={"model": _MODEL, "parts": [{"type": "text", "text": message}]},
        timeout=_OPENCODE_TIMEOUT,
    )
    if prompt_resp.is_success:
        return True, None
    detail = f"{prompt_resp.status_code} {prompt_resp.text}"[:_MAX_DETAIL_CHARS]
    logger.warning("opencode rejected prompt_async for %s: %s", session_id, detail)
    return False, _sse(
        _SseError(properties=_SseErrorProps(message=f"opencode rejected prompt_async: {detail}"))
    )


def _resolve_session(session_id: str | None) -> tuple[str, bytes | None]:
    """Return ``(session_id, error_frame)``. Creates a session when none was given.

    On a daemon-down failure, ``session_id`` is empty and ``error_frame`` is the
    SSE error to emit instead (so the failure surfaces in-stream, not as a 500).
    """
    if session_id:
        return session_id, None
    try:
        return _create_session().id, None
    except httpx.HTTPError as exc:
        detail = str(exc)[:_MAX_DETAIL_CHARS]
        return "", _sse(
            _SseError(properties=_SseErrorProps(message=f"failed to create session: {detail}"))
        )


def _run_turn(
    client: httpx.Client,
    request: HttpRequest | None,
    session_id: str,
    message: str,
) -> Iterator[bytes]:
    """Drive one turn over an open ``/event`` stream, yielding SSE frames."""
    with client.stream("GET", "/event") as resp:
        # Fire the prompt on a one-shot client so the stream client stays open;
        # events for this session are subscribed before the prompt is sent.
        # A failed prompt_async never produces a turn — emit its error frame
        # and end so the browser spinner doesn't hang waiting for an idle.
        _ok, error_frame = _fire_prompt(session_id, message)
        if error_frame is not None:
            yield error_frame
            return
        yield from _relay_events(resp, request, session_id)


def _relay_events(
    resp: httpx.Response, request: HttpRequest | None, session_id: str
) -> Iterator[bytes]:
    """Relay relevant SSE events until idle / disconnect / cap / end-of-stream.

    The compute-time cap resets on each human touchpoint (permission asked or
    replied) so it measures agent compute, not the wait for the user's decision.
    """
    saw_idle = False
    start = time.monotonic()
    for event in _iter_sse(resp):
        # Disconnect (checked on any event): the browser tab is gone — abort
        # the daemon turn so it doesn't keep running (e.g. on a pending
        # permission).
        if _client_disconnected(request):
            _abort_turn(session_id)
            return
        if not _is_relevant(event, session_id):
            continue
        # Human touchpoint: reset the compute-time clock.
        if event.get("type") in _HUMAN_TOUCHPOINTS:
            start = time.monotonic()
        # Runaway guard: too long since the last touchpoint with no idle.
        if time.monotonic() - start > _STREAM_MAX_SECS:
            yield _sse(
                _SseError(
                    properties=_SseErrorProps(message=f"opencode turn exceeded {_STREAM_MAX_SECS}s")
                )
            )
            return
        # A forwarded daemon event: shape is the daemon's (validated client-side
        # by OpencodeEventSchema), so serialise it verbatim rather than via _sse
        # (which is for the typed synthetic events Django itself emits).
        yield b"data: " + json.dumps(event).encode() + b"\n\n"
        if _is_idle(event):
            saw_idle = True
            return
    # The stream closed without an idle marker (daemon crash, network drop).
    # Tell the client instead of letting the spinner clear silently.
    if not saw_idle:
        yield _sse(
            _SseError(properties=_SseErrorProps(message="opencode stream ended without idle"))
        )


def _event_stream(
    request: HttpRequest | None, session_id: str | None, message: str
) -> Iterator[bytes]:
    # Resolve the session lazily inside the stream so a daemon-down failure
    # surfaces as an SSE error rather than a 500 from the view.
    session_id, error_frame = _resolve_session(session_id)
    if error_frame is not None:
        yield error_frame
        return

    # Tell the client which session this turn belongs to (multi-turn reuse).
    # NOTE: this wrapper event uses snake_case `session_id`; opencode's own
    # events use camelCase `sessionID` (filtered in `_is_relevant`). Both are
    # correct for their source — do not "fix" one to match the other.
    yield _sse(_SseSession(properties=_SseSessionProps(session_id=session_id)))

    # The /event stream is long-lived; a turn can wait indefinitely on a
    # permission, so any fixed timeout would cut the turn short.
    client = httpx.Client(base_url=_OPENCODE_BASE, timeout=None)  # noqa: S113
    try:
        yield from _run_turn(client, request, session_id, message)
    except Exception as exc:  # noqa: BLE001  # last-resort: keep the stream from 500-ing mid-turn
        # Broaden past httpx.HTTPError: _iter_sse/iter_lines() can raise
        # non-httpx exceptions (e.g. UnicodeDecodeError) which would otherwise
        # bubble up as a 500 with a stack trace. Emit a synthetic error instead.
        if not isinstance(exc, httpx.HTTPError):
            logger.warning("opencode stream error", exc_info=True)
        detail = str(exc)[:_MAX_DETAIL_CHARS]
        yield _sse(_SseError(properties=_SseErrorProps(message=detail)))
    finally:
        client.close()


def _iter_sse(resp: httpx.Response) -> Iterator[dict[str, Any]]:
    r"""Yield parsed JSON events from an SSE ``data:`` stream.

    Mirrors the SSE spec: a frame is one or more ``data:`` lines terminated by
    a blank line; multi-line payloads are joined with newlines; exactly one
    leading space after ``data:`` is stripped. A trailing frame without a
    terminator (common when the server closes mid-write) is flushed at
    end-of-stream — without this, a daemon whose last write is ``data: {idle}
    \\n`` (no second newline) loses the idle marker entirely and the client
    gets a spurious "stream ended without idle".

    The frontend re-implements the same protocol in
    ``useOpencodeChat.ts:consume`` — keep the two in sync.
    """
    data_lines: list[str] = []

    def _emit() -> Iterator[dict[str, Any]]:
        if not data_lines:
            return
        payload = "\n".join(data_lines)
        data_lines.clear()
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            return

    for line in resp.iter_lines():
        if line:
            if line.startswith("data:"):
                body = line[5:]
                body = body.removeprefix(" ")
                data_lines.append(body)
            # ignore event:/id:/retry/comment lines
        else:
            yield from _emit()
    yield from _emit()


def _is_relevant(event: dict[str, Any], session_id: str) -> bool:
    etype = event.get("type")
    if etype not in _RELEVANT_TYPES:
        return False
    sid = event.get("properties", {}).get("sessionID")
    if sid is None:
        # An unscoped event (no sessionID) — only `error` is worth surfacing
        # without a session match (e.g. an auth/rate-limit error the daemon
        # emits without tagging). Every other type is session-scoped data and
        # is dropped if we can't match it. An error tagged to another session
        # is still dropped (the sessionID is present but differs).
        return bool(etype == "error")
    return bool(sid == session_id)


def _is_idle(event: dict[str, Any]) -> bool:
    if event.get("type") != "session.status":
        return False
    status = event.get("properties", {}).get("status", {})
    return bool(isinstance(status, dict) and status.get("type") == "idle")


class _SseErrorProps(BaseModel):
    message: str


class _SseError(BaseModel):
    type: Literal["error"] = "error"
    properties: _SseErrorProps


class _SseSessionProps(BaseModel):
    session_id: str


class _SseSession(BaseModel):
    type: Literal["session"] = "session"
    properties: _SseSessionProps


# The synthetic SSE events Django itself emits. Forwarded daemon events arrive
# as already-parsed dicts and pass through `_sse` unchanged (their shape is the
# daemon's, validated client-side by OpencodeEventSchema).
_SseEvent = _SseError | _SseSession


def _sse(event: _SseEvent) -> bytes:
    r"""Serialise one synthetic SSE frame: ``data: <json>\\n\\n``."""
    return b"data: " + json.dumps(event.model_dump()).encode() + b"\n\n"


# Mount the proxy endpoints under /api/opencode/ — ninja gives auto body
# validation (422), method dispatch (405), and an OpenAPI schema (served at
# /api/opencode/docs and /api/opencode/openapi.json). Mounting the API (not just
# the router) at api/opencode/ keeps those docs URLs distinct from the manage API's.
opencode_api = NinjaAPI(urls_namespace="opencode-http")
opencode_api.add_router("", opencode_router)
