"""Install (or update) an app by running its ``app.py`` setup + self-tests.

Usage: ``./run djangomanage buildbackend <app>``

Resolves the app's ``app.py`` from the apps root
(``<apps_root>/<app>/app.py``), imports it
(``app_modules.load(..., force_reload=True)`` so re-runs pick up edits), runs its
``@setup`` (which calls ``create_application(name=…)``), then runs every
``@backend_test`` in-process. If setup or any test fails, the whole run is
rolled back — the transaction (Postgres transactional DDL) reverts every created
app/table and the dynamic-model registry cache is reset — so a failed install
leaves nothing behind. Exits non-zero on failure so an agent can use it as a
feedback loop.

The core logic lives in :func:`build_backend` (callable directly, e.g. from
tests); :class:`Command` is a thin wrapper that styles output.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from djangoapp.apps.dynamic_module import app_modules, apps_root
from djangoapp.models.applications import AppsGeneration
from djangoapp.models.dynamic import dynamic_models

if TYPE_CHECKING:
    from collections.abc import Callable


def _stderr_line(msg: str) -> None:
    """Default failure line-writer for :func:`build_backend` (plain stderr, no style)."""
    sys.stderr.write(f"{msg}\n")


def build_backend(identity: str, *, err_write: Callable[[str], None] | None = None) -> int:
    """Install ``<app>``: run ``@setup`` + ``@backend_test``s.

    Raises :class:`CommandError` on any failure (after writing the failing
    test's name + traceback via ``err_write``, so the detail isn't lost — Django prints
    only the ``CommandError`` message). Returns the number of ``@backend_test``s
    run. ``err_write`` defaults to :func:`_stderr_line`; the command passes a styled
    writer.
    """
    if err_write is None:
        err_write = _stderr_line
    if "/" in identity:
        msg = f"Expected '<app>' (a single name), got {identity!r}."
        raise CommandError(msg)
    app_name = identity
    # Derived from apps_root + name: no Application row exists yet (the
    # @setup below is what creates it), so Application.script_path() can't be
    # used here — only after install.
    script_path = (apps_root() / app_name / "app.py").resolve()

    # force_reload: even though buildbackend is a fresh CLI process,
    # build_backend() is called in-process by tests, so a second install of
    # the same path must re-import (picks up edits / re-runs @setup registration)
    # rather than reuse the cached module. A missing/empty app.py raises
    # FileNotFoundError/ValueError from load — let those propagate (a clean
    # non-zero exit) instead of wrapping them in CommandError.
    dynamic_module = app_modules.load(script_path, force_reload=True)

    try:
        with transaction.atomic():
            dynamic_module.setup_function()
            for test in dynamic_module.backend_tests:
                # Each @backend_test runs in its own savepoint, rolled back
                # afterwards (success or failure): a test's writes never leak
                # into the installed app or affect the next test.
                sid = transaction.savepoint()
                try:
                    try:
                        test()
                    except Exception as test_exc:
                        # Stop on the first failing @backend_test and name it +
                        # show its traceback — Django prints only the CommandError
                        # message, so the detail would be lost otherwise.
                        err_write(f"buildbackend {identity}: @backend_test {test.__name__} failed")
                        err_write(traceback.format_exc().rstrip())
                        msg_0 = f"buildbackend {identity} failed in @backend_test {test.__name__}"
                        raise CommandError(msg_0) from test_exc
                finally:
                    transaction.savepoint_rollback(sid)
                    transaction.savepoint_commit(sid)
            # Bump the apps generation so running server workers invalidate their
            # dynamic-model/app-module caches (no restart needed).
            AppsGeneration.bump()
    except CommandError:
        # A test failure above (already reported) — just roll back + reset.
        dynamic_models.reset()
        raise
    except Exception as exc:
        # DDL is transactional, so the atomic rollback drops every created
        # physical table; reset the registry so no in-memory model leaks.
        # Wrap any failure (setup error, bad column, assertion) in
        # CommandError so the command exits non-zero with one clear cause.
        dynamic_models.reset()
        msg = f"buildbackend {identity} failed: {exc}"
        raise CommandError(msg) from exc

    return len(dynamic_module.backend_tests)


class Command(BaseCommand):
    """``djangomanage buildbackend <app>`` — install + self-test an app."""

    help = "Install (or update) an app: run its @setup + @backend_test functions."

    def add_arguments(self, parser: Any) -> None:  # noqa: ANN401 # Django parser is untyped
        parser.add_argument(
            "app",
            help="App identity as '<app>' (e.g. HappyPathApp).",
        )

    def handle(self, *_args: Any, **options: Any) -> None:  # noqa: ANN401 # Django options is untyped
        identity: str = options["app"]
        count = build_backend(
            identity, err_write=lambda msg: self.stderr.write(self.style.ERROR(msg))
        )
        self.stdout.write(self.style.SUCCESS(f"Installed {identity}: ran {count} test(s)."))
