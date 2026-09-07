"""Template filters for the static asset pipeline."""

from __future__ import annotations

import json
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
    imports: list[str] = []
    # Manifest keys are camelCase (Vite's format); the snake alias keeps
    # ruff's N815 happy at the use site.
    dynamic_imports: list[str] = pydantic.Field(default_factory=list, alias="dynamicImports")


class Manifest(pydantic.BaseModel):
    """The whole ``.vite/manifest.json``, exposing the app's single entry.

    Vite keys each record by its source path (the entry) or hashed chunk
    name; ``main_ts`` aliases the ``"src/main.ts"`` entry record so callers
    read ``manifest.main_ts.file`` / ``.css``. Sibling chunk records land in
    ``chunks`` (same record shape) — the entry's ``imports`` name keys there.
    """

    model_config = pydantic.ConfigDict(extra="ignore", populate_by_name=True)

    main_ts: _ManifestEntry = pydantic.Field(alias="src/main.ts")
    chunks: dict[str, _ManifestEntry] = {}


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


@register.filter
def entry_preloads(url: str) -> list[str]:
    """Static-import chunk URLs of the entry, for ``<link rel=modulepreload>``.

    The entry's static imports (the bundler runtime + the shared chunk) are
    discovered by the browser only AFTER main.js parses and its import
    statements run — a serial round trip per hop. Emitting modulepreload
    links from the HTML starts those fetches in parallel with main.js.
    Chunks reachable only dynamically (mermaid, filePreview, … — including
    transitively, via another chunk's dynamicImports) are deliberately NOT
    preloaded — they stay lazy.

    Usage: ``{% for href in "/static/djangoapp/main.js"|entry_preloads %}``.
    """
    name = url.lstrip("/")
    prefix = (settings.STATIC_URL or "").lstrip("/")
    if prefix and name.startswith(prefix):
        name = name[len(prefix) :]
    static_dir = name.rsplit("/", 1)[0]  # e.g. "djangoapp"
    manifest = _load_manifest(f"{static_dir}/.vite/manifest.json")
    if manifest is None:
        return []
    static_prefix = (settings.STATIC_URL or "/static/").rstrip("/")
    # rolldown's manifest lists dynamic-import chunks in `imports` as well,
    # and laziness is transitive (mermaid-uncommon is the ENTRY's import but
    # mermaid-core's dynamicImport) — exclude the union of dynamicImports
    # across ALL records, or the preload would eagerly fetch lazy chunks.
    dynamic = {
        key
        for record in [manifest.main_ts, *manifest.chunks.values()]
        for key in record.dynamic_imports
    }
    return [
        f"{static_prefix}/{static_dir}/{manifest.chunks[imp].file}"
        for imp in manifest.main_ts.imports
        if imp in manifest.chunks and imp not in dynamic
    ]


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
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        manifest = Manifest.model_validate(
            {
                **data,
                "chunks": {key: record for key, record in data.items() if key != "src/main.ts"},
            }
        )
    except OSError, ValueError, pydantic.ValidationError:
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
