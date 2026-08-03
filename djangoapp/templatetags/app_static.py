"""Template filters for the static asset pipeline."""

from __future__ import annotations

import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders

register = template.Library()


@register.filter
def with_cache_buster(url: str) -> str:
    """Append ``?cache_buster=<mtime>`` to a static asset URL.

    Usage in templates: ``{{ "/static/djangoapp/main.js"|with_cache_buster }}``.

    The version is the mtime of the file the staticfiles finder resolves for the
    URL's name. Only the fixed-name ``main.js``/``main.css`` need this. ``os.stat`` is recomputed per render. 
    It is a fast operation that adds negligible delay per request.
    it falls back to ``"0"`` if the file is absent (e.g. before the first build).
    """
    name = url.lstrip("/")
    prefix = (settings.STATIC_URL or "").lstrip("/")
    if prefix and name.startswith(prefix):
        name = name[len(prefix):]
    path = finders.find(name)
    try:
        version = str(int(os.stat(path).st_mtime))
    except (OSError, TypeError):
        version = "0"
    return f"{url}?cache_buster={version}"
