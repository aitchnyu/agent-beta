"""Utility functions for the djangoapp."""

from __future__ import annotations

import html
import re
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
    """Sanitize HTML content by allowing only whitelisted tags and attributes.

    Also strips BOM characters used by Quill for cursor positioning.
    """
    sanitized = nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    return sanitized.replace(_BOM, "")


def human_size(num_bytes: int) -> str:
    kb = 1024
    mb = kb * kb
    if num_bytes < kb:
        return f"{num_bytes}B"
    if num_bytes < mb:
        return f"{num_bytes / kb:.1f}KB"
    return f"{num_bytes / mb:.1f}MB"


_BLOCK_RE = re.compile(r"</(p|h[1-6]|li|tr|div|table|ul|ol|thead|tbody|br)\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(raw_html: str) -> str:
    text = _BLOCK_RE.sub(" ", raw_html)
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()
