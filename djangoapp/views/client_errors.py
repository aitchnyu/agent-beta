"""POST /client-errors — capture uncaught frontend errors server-side.

The frontend's global handlers (frontend/src/main.ts) POST here with the error
message, stack, source location (filename/lineno/colno), page url and browser
context. This view logs it once on the ``client`` logger and returns 204. The
authoritative identity is read from ``request.user`` (never trusted from the
body); anonymous reports are accepted (``user`` is ``None``).

CSRF: django-ninja exempts all of its views from Django's ``CsrfViewMiddleware``
and only re-runs its own CSRF check for cookie-auth endpoints; this one declares
no ``auth``, so anonymous POSTs and the ``navigator.sendBeacon`` fallback
(pagehide, no X-CSRFTOKEN header) land without a csrftoken cookie. That's
acceptable because the endpoint is stateless (log-only) — the only abuse vector
is log spam, bounded by the Redis rate limit: an hourly budget per
authenticated user, with all anonymous reporters sharing one bucket.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import redis
from django.http import HttpRequest, HttpResponse
from ninja import Router
from pydantic import BaseModel, ConfigDict, Field

from djangoapp.logging import get_logger
from djangoapp.ninja_api import make_ninja_api
from djangoapp.shortcuts import maybe_user

if TYPE_CHECKING:
    from djangoapp.models import User

logger = get_logger("client")

# Redis is required (rate limiting is mandatory, not best-effort). Defaults to
# the local redis; redis-py connects lazily, so constructing at import is safe.
_REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
_redis_client: redis.Redis = redis.Redis.from_url(_REDIS_URL, decode_responses=True)
# Max reports per hour per authenticated user; all anonymous reporters
# share ONE bucket combined. Mandatory — no silent default: the anonymous,
# CSRF-exempt sink's only abuse bound must be present, a valid int, and
# above 0 (mirrors settings' SESSION_IDLE_DAYS contract).
_RATE_LIMIT = int(os.environ["CLIENT_ERROR_RATE_LIMIT"])
if (
    _RATE_LIMIT <= 0
):  # pragma: no cover -- import-time contract guard; only a fresh process can hit it
    msg = "CLIENT_ERROR_RATE_LIMIT must be an integer above 0"
    raise ValueError(msg)
_WINDOW_SECS = 3600
# Parse cap (pydantic) vs. log cap. The model accepts more than we keep, so the
# view's truncation is meaningful: a client can send up to _MAX_STACK_INPUT, but
# only _MAX_STACK_CHARS reaches the log line. The frontend caps to this too
# (frontend/src/utils/clientError.ts MAX_STACK_CHARS) so a long browser stack
# doesn't 422.
_MAX_STACK_CHARS = 500
_MAX_STACK_INPUT = 5000


class ClientErrorBody(BaseModel):
    """A single frontend-reported error."""

    # extra="forbid" makes the no-injection guarantee explicit: a client can't
    # sneak `source`/`level`/`logger` past the model —
    # stray keys 422 instead of being silently dropped.
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    message: str = Field(default="", max_length=2000)
    stack: str = Field(default="", max_length=_MAX_STACK_INPUT)
    filename: str = Field(default="", max_length=500)
    lineno: int | None = None
    colno: int | None = None
    url: str = Field(default="", max_length=2000)
    # Frontend sends camelCase keys; alias so the model stays PEP 8.
    user_agent: str = Field(default="", alias="userAgent", max_length=500)
    vue_info: str = Field(
        default="",
        alias="vueInfo",
        max_length=200,
        description="Vue's lifecycle hint from app.config.errorHandler (e.g. "
        "'render', 'setup function') — categorizes where the error blew up.",
    )
    public_id: str | None = None


client_errors_router = Router()


def _rate_limited(user: User | None) -> bool:
    """Return True when the reporter's hourly budget is exhausted.

    Two bucket shapes: one per authenticated user (``client-errors:user:<pk>``)
    and a single shared bucket for every anonymous reporter
    (``client-errors:anon``) — anon budget is collective, not per IP, so a
    spoofed/spoofing crowd can't buy fresh budget per request.

    Raises ``RedisError`` if redis is unreachable — the caller lets it propagate
    to the global exception handler (fail closed: 500, report not accepted).
    """
    bucket = "client-errors:anon" if user is None else f"client-errors:user:{user.pk}"
    pipe = _redis_client.pipeline()
    pipe.incr(bucket)
    pipe.expire(bucket, _WINDOW_SECS, nx=True)
    result = pipe.execute()  # raises RedisError if redis is down
    return bool(result) and result[0] > _RATE_LIMIT


@client_errors_router.post("/client-errors", response={204: None, 429: None})
def submit(request: HttpRequest, body: ClientErrorBody) -> HttpResponse:
    user = maybe_user(request)
    if _rate_limited(user):
        return HttpResponse(status=429)
    logger.warning(
        "client error",
        source="client",
        client_message=body.message,
        client_stack=body.stack[:_MAX_STACK_CHARS],
        # Browser source location. Prefixed `client_*` to avoid clashing with
        # CallsiteParameterAdder's `filename`/`lineno` (the *server* call site).
        client_filename=body.filename,
        client_lineno=body.lineno,
        client_colno=body.colno,
        url=body.url,
        user_agent=body.user_agent,
        vue_info=body.vue_info,
        # method/path + user_public_id/username come from the bound
        # context (LoggingContextMiddleware); echoed here as a flat object
        # so a client error record is self-describing.
        user=(
            {"public_id": user.public_id, "username": user.username} if user is not None else None
        ),
    )
    return HttpResponse(status=204)


# Mount at the project root so the route is POST /client-errors.
# csrf=False: tokenless anonymous POSTs (sendBeacon on pagehide) are the
# point of this sink — no csrf_guard — and the Redis rate limit
# bounds the abuse vector to log spam.
client_errors_api = make_ninja_api("clienterrors", client_errors_router, prefix="", csrf=False)
