"""Unit tests for the ``hashed_entry`` template filter (djangoapp.templatetags.app_static).

The filter resolves the page's entry JS/CSS to their content-hashed build
names from Vite's ``.vite/manifest.json`` — the pipeline that replaced the
mtime query-string buster (a query on the ES-module entry URL made the
browser execute main.js twice; see frontend/vite.config.js). These tests pin
each resolution path against a synthetic manifest so they don't depend on
the repo's built artifacts: ``finders.find`` is patched to the fixture
(otherwise the app-static finder would resolve the repo's real manifest).
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings

from djangoapp.templatetags import app_static

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

_VALID_MANIFEST: dict[str, dict[str, object]] = {
    "src/main.ts": {
        "file": "main-abc123.js",
        "name": "main",
        "src": "src/main.ts",
        "isEntry": True,
        "imports": ["_rolldown-runtime-x.js"],
        "dynamicImports": ["src/utils/filePreview.ts"],
        "css": ["assets/main-css456.css"],
    },
    "_rolldown-runtime-x.js": {
        "file": "assets/rolldown-runtime-x.js",
        "name": "rolldown-runtime",
    },
    "src/utils/filePreview.ts": {
        "file": "assets/filePreview-y.js",
        "name": "filePreview",
        "src": "src/utils/filePreview.ts",
        "isDynamicEntry": True,
    },
}


def _render(url: str) -> str:
    template = Template('{% load app_static %}{{ "' + url + '"|hashed_entry }}')
    return template.render(Context())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class HashedEntryTests(SimpleTestCase):
    """Resolution, fallback, and cache paths of the hashed_entry filter."""

    def setUp(self) -> None:
        super().setUp()
        # Fresh manifest cache per test: the filter memoizes by (path, mtime).
        app_static._manifest_cache.clear()

    def _patch_find(self, manifest: str | None) -> AbstractContextManager[str]:
        """Point finders.find at a temp manifest file (None → not found)."""
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.json"
        if manifest is not None:
            path.write_text(manifest, encoding="utf-8")
        return patch(
            "djangoapp.templatetags.app_static.finders.find",
            return_value=str(path) if manifest is not None else None,
        )

    def test_resolves_hashed_js_and_css(self) -> None:
        with self._patch_find(json.dumps(_VALID_MANIFEST)):
            self.assertEqual(
                _render("/static/djangoapp/main.js"),
                "/static/djangoapp/main-abc123.js",
            )
            self.assertEqual(
                _render("/static/djangoapp/main.css"),
                "/static/djangoapp/assets/main-css456.css",
            )

    def test_missing_manifest_falls_back_to_plain_url(self) -> None:
        with self._patch_find(None):
            self.assertEqual(_render("/static/djangoapp/main.js"), "/static/djangoapp/main.js")

    def test_invalid_manifest_falls_back_to_plain_url(self) -> None:
        with self._patch_find("{not json"):
            self.assertEqual(_render("/static/djangoapp/main.js"), "/static/djangoapp/main.js")

    def test_missing_entry_record_falls_back_to_plain_url(self) -> None:
        # Chunk records only — the 'src/main.ts' entry alias finds nothing.
        chunks_only = {
            "_chunk.js": {"file": "assets/chunk.js", "name": "chunk"},
        }
        with self._patch_find(json.dumps(chunks_only)):
            self.assertEqual(_render("/static/djangoapp/main.js"), "/static/djangoapp/main.js")

    def test_entry_without_css_falls_back_to_plain_css_url(self) -> None:
        manifest = {
            **_VALID_MANIFEST,
            "src/main.ts": {**_VALID_MANIFEST["src/main.ts"], "css": []},
        }
        with self._patch_find(json.dumps(manifest)):
            self.assertEqual(_render("/static/djangoapp/main.css"), "/static/djangoapp/main.css")

    def test_manifest_reread_after_rebuild(self) -> None:
        """The mtime-keyed cache re-reads the manifest after a build rewrites it."""
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.json"
        path.write_text(json.dumps(_VALID_MANIFEST), encoding="utf-8")
        with patch("djangoapp.templatetags.app_static.finders.find", return_value=str(path)):
            self.assertEqual(
                _render("/static/djangoapp/main.js"), "/static/djangoapp/main-abc123.js"
            )
            rebuilt = {
                **_VALID_MANIFEST,
                "src/main.ts": {
                    **_VALID_MANIFEST["src/main.ts"],
                    "file": "main-new789.js",
                },
            }
            path.write_text(json.dumps(rebuilt), encoding="utf-8")
            self.assertEqual(
                _render("/static/djangoapp/main.js"), "/static/djangoapp/main-new789.js"
            )
