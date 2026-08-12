"""Structured logging setup (structlog) + the stdlib bridge.

Every log line is exactly one JSON object (NDJSON) with stable top-level keys so
the stream can be sliced with jq::

    jq 'select(.level=="error")'
    jq 'select(.logger=="client")'          # frontend-reported errors
    jq 'select(.source=="server")'           # any server-side record

Per-request fields (``method``, ``path``, ``user_public_id``, ``username``)
are bound into contextvars by
``LoggingContextMiddleware`` and merged into every record. Because Django and its
ecosystem (``django.request``/``django.security``, allauth, httpx, ninja, ...)
emit through stdlib ``logging``, those records flow through the same
``ProcessorFormatter`` and come out as the same JSON shape as our own structlog
loggers — one uniform stream, no bridge quirks.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import structlog
from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Mapping

    from structlog.typing import EventDict, FilteringBoundLogger, WrappedLogger

__all__ = [
    "bind_log_context",
    "clear_log_context",
    "configure_logging",
    "get_logger",
    "json_formatter",
]


def _default_source(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Tag every record with a ``source`` so server vs. client logs are jq-able.

    Defaults to ``"server"``; ``client``-reported errors set ``source="client"``
    explicitly (setdefault leaves an existing key untouched).
    """
    event_dict.setdefault("source", "server")
    return event_dict


# Chain applied to EVERY record (structlog loggers AND bridged stdlib records)
# before the final JSON render. ``merge_contextvars`` pulls in the per-request
# fields bound by LoggingContextMiddleware; the traceback renderer turns
# ``exc_info`` into a structured ``exception`` field (a list of trace dicts)
# instead of a trailing multi-line string.
# show_locals=False is deliberate: an exception in a view could otherwise dump
# request bodies, tokens, or ORM rows (the locals) into the log stream.
_DICT_TRACEBACKS = structlog.processors.ExceptionRenderer(
    structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
)
_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    _default_source,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.CallsiteParameterAdder(
        parameters=[
            structlog.processors.CallsiteParameter.MODULE,
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.LINENO,
        ],
    ),
    structlog.processors.StackInfoRenderer(),
    _DICT_TRACEBACKS,
]


def get_logger(name: str = __name__) -> FilteringBoundLogger:
    """Return a structlog logger named ``name``.

    Always use this instead of importing structlog directly, so the structlog
    dependency lives in this one module and logger construction can be tuned
    here (processors, bind defaults, naming) without touching call sites.
    """
    return cast("FilteringBoundLogger", structlog.get_logger(name))


def bind_log_context(**fields: object) -> Mapping[str, Any]:
    """Bind per-context fields (e.g. user_public_id, method) onto every log line.

    Thin wrapper over ``structlog.contextvars.bind_contextvars`` so call sites
    (LoggingContextMiddleware) don't import structlog directly. Returns the token
    map — pass it to ``reset_log_context`` to restore the prior state (avoids
    ``clear_contextvars`` clobbering any other in-process structlog user).
    """
    return structlog.contextvars.bind_contextvars(**fields)


def clear_log_context(tokens: Mapping[str, Any]) -> None:
    """Reset only the fields ``bind_log_context`` bound (token-scoped)."""
    structlog.contextvars.reset_contextvars(**tokens)


def configure_logging() -> None:
    """Configure structured logging once at import (called from ``settings.py``).

    Our loggers run the shared chain then hand the record to the handler's
    ``ProcessorFormatter`` via ``wrap_for_formatter`` (the mandatory final
    processor). Foreign stdlib loggers skip this chain entirely and are
    pre-processed by ``foreign_pre_chain`` on the formatter instead — both land
    in the same JSON renderer.
    """
    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_level()),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def json_formatter() -> logging.Formatter:
    """Render both structlog and foreign records as one JSON object per line.

    Returns a stdlib ``logging.Formatter`` (the structlog ``ProcessorFormatter``)
    so Django/framework records and our own structlog loggers emit the same
    NDJSON shape.
    """
    return structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=_SHARED_PROCESSORS,
    )


def _level() -> int:
    """Return DEBUG in dev, INFO otherwise.

    Matches the stdlib root logger level set in ``LOGGING`` so the two
    filtering layers (structlog bound logger + stdlib root) stay aligned.
    """
    return logging.DEBUG if settings.DEBUG else logging.INFO
