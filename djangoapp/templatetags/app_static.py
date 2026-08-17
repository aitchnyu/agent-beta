"""Template filters for the static asset pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

import pydantic
from django import template
from django.conf import settings
from django.contrib.staticfiles import finders

register = template.Library()

logger = logging.getLogger(__name__)


class _ManifestEntry(pydantic.BaseModel):
    """One record of Vite's ``.vite/manifest.json`` (fields we consume).

    Real records carry more keys than we read — e.g. the entry record::

        {"file": "main-51Hqz-kE.js", "name": "main", "src": "src/main.ts",
         "isEntry": true,
         "imports": ["_rolldown-runtime-*.js", "src/main.ts"],
         "dynamicImports": ["src/utils/filePreview.ts", ...],
         "css": ["assets/main-*.css"]}

    and chunk records keyed by hashed chunk name (``"_mermaid-core-*.js"``,
    ``"node_modules/diff/libesm/index.js"``, …) with just
    ``file``/``name``/``imports``. ``extra="ignore"`` makes both shapes (and
    any future keys) validate; only ``file`` is required, ``css`` defaults
    empty for chunk records.
    """

    model_config = pydantic.ConfigDict(extra="ignore")

    file: str
    css: list[str] = []


class Manifest(pydantic.BaseModel):
    """The whole ``.vite/manifest.json``, exposing the app's single entry.

    Vite keys each record by its source path (the entry) or hashed chunk
    name; ``main_ts`` aliases the ``"src/main.ts"`` entry record so callers
    read ``manifest.main_ts.file`` / ``.css``. Sibling chunk records
    validate away under ``extra="ignore"``.
    """

    model_config = pydantic.ConfigDict(extra="ignore", populate_by_name=True)

    main_ts: _ManifestEntry = pydantic.Field(alias="src/main.ts")


@register.filter
def hashed_entry(url: str) -> str:
    """Resolve ``/static/djangoapp/main.js``/``main.css`` to hashed build names.

    Reads ``.vite/manifest.json`` (emitted by the build; see frontend/vite.config.js
    for why the entry must be a stable hashed URL, not a query-busted name).
    Falls back to the plain URL (logged) when the manifest is missing or
    unreadable, e.g. before the first build.

    Usage: ``{{ "/static/djangoapp/main.js"|hashed_entry }}`` (same for main.css).
    """
    name = url.lstrip("/")
    prefix = (settings.STATIC_URL or "").lstrip("/")
    if prefix and name.startswith(prefix):
        name = name[len(prefix) :]
    static_dir = name.rsplit("/", 1)[0]  # e.g. "djangoapp"
    manifest = _load_manifest(f"{static_dir}/.vite/manifest.json")
    if manifest is None:
        return url
    try:
        asset = manifest.main_ts.css[0] if url.endswith(".css") else manifest.main_ts.file
    except IndexError:
        # Entry record without css (all styles moved to async chunks): nothing
        # to link — serve the plain URL rather than 500ing the page.
        logger.warning(
            "hashed_entry: entry record has no css asset for %s — serving the plain URL",
            url,
        )
        return url
    static_prefix = (settings.STATIC_URL or "/static/").rstrip("/")
    return f"{static_prefix}/{static_dir}/{asset}"


# Parsed-manifest cache: keyed by manifest name (resolved path), value
# (mtime, manifest) — an entry is valid only while the mtime matches, and a
# rebuild replaces its entry in place (no unbounded growth). The filter runs
# on every page render (both entry files); this keeps it at one stat() per
# render with a re-read only after a build.
_manifest_cache: dict[str, tuple[float, Manifest | None]] = {}


def _load_manifest(rel_name: str) -> Manifest | None:
    """Read + validate the manifest once per build (mtime-cached), or None."""
    path = finders.find(rel_name)
    if path is None:
        return None
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return None
    cached = _manifest_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        manifest = Manifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except OSError, pydantic.ValidationError:
        logger.warning(
            "hashed_entry: could not parse %s — serving plain URLs (cache-busting "
            "degraded; rebuild the frontend or check the Manifest 'src/main.ts' "
            "alias link)",
            path,
            exc_info=True,
        )
        manifest = None
    _manifest_cache[path] = (mtime, manifest)
    return manifest
