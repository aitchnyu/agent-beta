"""Utility functions for the djangoapp."""

from __future__ import annotations

from typing import Final

import nh3

ALLOWED_TAGS: Final[set[str]] = {
    "p",
    "br",
    "strong",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "a",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "img",
}

ALLOWED_ATTRIBUTES: Final[dict[str, set[str]]] = {
    "a": {"href"},
    "img": {"src"},
}

# Byte Order Mark character inserted by Quill for cursor positioning.
# Must be stripped from stored HTML so it doesn't accumulate on each save.
_BOM = "\ufeff"


def sanitize_html(html: str) -> str:
    """Sanitize HTML by allowing only whitelisted tags/attributes; strip BOM."""
    sanitized = nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    return sanitized.replace(_BOM, "")
