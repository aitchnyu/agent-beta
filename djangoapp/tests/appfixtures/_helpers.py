"""Shared helpers for the appfixtures tests.

``patched_app_root`` centralises the repeated ``patch.object(dynamic_module, "_APPS_ROOT", …)``
so the fixture-tree path lives in one place and both idioms work off one helper:

- as a context manager (per-block, variable path): ``with patched_app_root(root):``
- started/stopped (whole-test scope, default fixture tree):
  ``patcher = patched_app_root(); patcher.start(); self.addCleanup(patcher.stop)``
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import _patch, patch

from django.conf import settings

from djangoapp.apps import dynamic_module

# The shared fixture tree: ``<app>/app.py`` under ``djangoapp/tests/appfixtures/``.
APPS_ROOT = Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures"


def patched_app_root(path: Path | str = APPS_ROOT) -> _patch[Any]:
    """Patch ``dynamic_module._APPS_ROOT`` to ``path`` (default: the fixture tree).

    Returns the ``patch.object`` object, so it works both as a context manager
    (``with patched_app_root(root):``) and via ``.start()`` / ``.stop()``.
    """
    return patch.object(dynamic_module, "_APPS_ROOT", Path(path))
