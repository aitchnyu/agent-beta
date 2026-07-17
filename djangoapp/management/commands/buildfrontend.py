"""Build an app's frontend, then verify it in a browser before completing.

Usage: ``./run djangomanage buildfrontend <collection>/<app>``

Resolves the app, locates its ``frontend/`` dir (``application.frontend_dir()``),
and runs ``npm run build -- --emptyOutDir --outDir <static_folder>`` so vite
writes ``main.js``/``main.css`` to the app's derived static folder
(``application.static_folder()``). Constant asset path; cache-busting is via the
``?cache_buster=<generation>`` the inertia view appends (no hashed filenames).

After the build, the app's ``@playwright_test`` funcs are driven in a headless
browser against a short-lived live server (see :func:`_drive_playwright_tests`)
so a green buildfrontend means the built bundle actually mounts and interacts. This
drives the app's *own* funcs against the current DB install (the app must be
installed first via ``setup``), so it works for real apps in ``apps/`` as well
as fixtures under tests. An app with no ``@playwright_test`` skips the browser
phase. ``--skip-playwright`` builds only — used by the playwright harness itself
(which drives the browser on its own) and for fast dev-loop rebuilds.

Exits non-zero (CommandError) when the app or its frontend is missing, the build
fails, or any ``@playwright_test`` fails.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import traceback
from typing import TYPE_CHECKING, Any

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings
from django.test.testcases import LiveServerThread
from django.test.utils import modify_settings

from djangoapp.models.applications import Application, AppsGeneration

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path


class Command(BaseCommand):
    """``djangomanage buildfrontend <collection/app>`` — build + browser-smoke an app."""

    help = "Build an app's Vue frontend, then run its @playwright_test suite."

    def add_arguments(self, parser: Any) -> None:  # noqa: ANN401 # Django parser is untyped
        parser.add_argument(
            "app",
            help="App identity as '<collection>/<app>' (e.g. Demo/Page).",
        )
        parser.add_argument(
            "--skip-playwright",
            action="store_true",
            default=False,
            help="Build only; don't run the app's @playwright_test browser suite.",
        )

    def handle(self, *_args: Any, **options: Any) -> None:  # noqa: ANN401 # Django options is untyped
        identity: str = options["app"]
        skip_playwright: bool = options["skip_playwright"]
        if "/" not in identity:
            msg = f"Expected '<collection>/<app>', got {identity!r}."
            raise CommandError(msg)
        collection_name, app_name = identity.split("/", 1)

        try:
            application = Application.get_by_names(collection_name, app_name)
        except Application.DoesNotExist as exc:
            msg_0 = f"No app '{identity}'."
            raise CommandError(msg_0) from exc

        frontend_dir = application.frontend_dir()
        if not (frontend_dir / "package.json").exists():
            msg = (
                f"No frontend at {frontend_dir} (expected package.json next to "
                f"{application.script_path()})."
            )
            raise CommandError(msg)

        # frontend_dir/static_folder/app_bundle are pure path derivations exposed
        # as methods (no @property, per the Application convention).
        static_folder = application.static_folder()
        # Ensure the app's deps are installed (idempotent — a no-op once
        # node_modules exists) so ``buildfrontend <app>`` is self-sufficient and the
        # test harnesses don't each replicate an npm-install step.
        if not (frontend_dir / "node_modules").exists():
            self.stdout.write(f"Installing deps for {identity}…")
            _run_npm(["install"], cwd=frontend_dir, identity=identity)
        self.stdout.write(f"Building {identity} → {static_folder}")
        _run_npm(
            ["run", "build", "--", "--emptyOutDir", "--outDir", str(static_folder)],
            cwd=frontend_dir,
            identity=identity,
        )

        if not (static_folder / "main.js").exists():
            msg = f"Build finished but {static_folder / 'main.js'} is missing."
            raise CommandError(msg)
        # Bump the apps generation so running server workers invalidate their
        # caches and browsers refetch the rebuilt bundle (cache-bust value).
        AppsGeneration.bump()
        self.stdout.write(self.style.SUCCESS(f"Built {identity}."))

        if skip_playwright:
            return
        self._run_playwright_suite(identity, application)

    def _run_playwright_suite(self, identity: str, application: Application) -> None:
        """Drive the app's ``@playwright_test`` funcs; fail buildfrontend on the first failure.

        Skips cleanly when the app declares no ``@playwright_test``. The funcs run
        against the current DB install (the app must already be set up) and the
        just-built bundle, so this verifies the build end to end. The first
        failing test halts the run (the driver prints its traceback).
        """
        module = application.module()
        if not module.playwright_tests:
            self.stdout.write(f"{identity} declares no @playwright_test; skipping browser phase.")
            return

        self.stdout.write(f"Running @playwright_test suite for {identity}...")
        try:
            _drive_playwright_tests(module.playwright_tests, err_write=self.stderr.write)
        except Exception as exc:
            msg = f"@playwright_test suite for {identity} failed: {exc}"
            raise CommandError(msg) from exc
        self.stdout.write(self.style.SUCCESS(f"@playwright_test suite for {identity} passed."))


def _run_npm(
    args: Sequence[str],
    *,
    cwd: Path,
    identity: str,
) -> None:
    """Run ``npm <args>`` in ``cwd``; raise ``CommandError`` if npm is missing or it fails.

    ``shutil.which("npm")`` lives here (not at each call site) so callers don't
    repeat the missing-npm check; the failure message is built from ``args``.
    """
    npm = shutil.which("npm")
    if npm is None:
        msg = "npm not found on PATH."
        raise CommandError(msg)
    try:
        subprocess.run(  # noqa: S603 # argv fixed; cwd is an app frontend dir
            [npm, *args],
            cwd=cwd,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = f"npm {' '.join(args)} for {identity} failed (exit {exc.returncode})."
        raise CommandError(msg) from exc


class RollbackEveryRequestMiddleware:
    """Per-request rolled-back atomic; reverts every live-server DB write.

    Installed only during ``_drive_playwright_tests`` (prepended onto
    ``MIDDLEWARE`` via ``modify_settings``), so it never runs in normal server
    operation. The live server runs on its own connection, so this is independent
    of the drive's in-process rolled-back atomic — together they revert both
    HTTP-triggered (browser) and in-process writes.

    Sharing the server's connection + one rolled-back atomic is blocked:
    ``close_old_connections`` (fired per request) force-closes any connection
    whose autocommit differs from the setting, and inside ``atomic`` autocommit
    is off. Containing the atomic to a single request dodges that — autocommit is
    back on before ``request_finished`` fires. A write is therefore visible only
    for the lifetime of the request that makes it.
    """

    def __init__(self, get_response: Callable[..., object]) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:  # noqa: ANN401 # Django request/response are untyped
        with transaction.atomic():
            response = self.get_response(request)
            transaction.set_rollback(True)
        return response


def _drive_playwright_tests(
    tests: Sequence[Callable[..., object]],
    *,
    err_write: Callable[[str], object],
    host: str = "localhost",
) -> None:
    """Run each ``@playwright_test(context, base_url)`` in a headless browser.

    Starts a short-lived, static-aware live server on a free port (its *own* DB
    connection — not shared with this command), then hands each func a fresh
    ``BrowserContext`` + ``base_url`` and lets it build its own pages, users, and
    login. **Stops on the first failure**: its name + traceback are written via
    ``err_write`` and the exception re-raised so the caller can fail the build.

    Two rollback layers keep the drive from touching the DB (no per-test cleanup):

    - **In-process** — the whole test loop runs in one ``transaction.atomic`` on
      this command's connection, each ``@playwright_test`` in its own
      ``savepoint`` (rolled back in ``finally``), the atomic marked
      ``set_rollback(True)`` so writes a test body makes never commit.
    - **Browser** — :class:`RollbackEveryRequestMiddleware` (prepended onto ``MIDDLEWARE``
      for the drive only) wraps each live-server request in its own rolled-back
      ``atomic`` on the server's connection, so writes a ``@playwright_test``
      triggers over HTTP revert per request.

    The server keeps its own connection (sharing it + one rolled-back atomic is
    blocked — see :class:`RollbackEveryRequestMiddleware`). So a write is visible only for
    the **request** that makes it: per-request, not per-test — a write in one
    request is gone by the next.

    ``sync_playwright`` runs an asyncio loop in this thread, which would trip
    Django's ``async_unsafe`` guard on the rolled-back atomic + per-test
    savepoints (and any in-test ORM) — the ORM calls here are synchronous, not
    actually concurrent with the loop, so the guard's caution doesn't apply.
    ``DJANGO_ALLOW_ASYNC_UNSAFE`` is set for the drive only and restored after
    (same workaround the playwright test runner applies globally).
    """
    # Set before anything else so the env var covers the whole drive (the
    # atomic below, the per-test savepoints, and any in-test ORM), then
    # restore the prior value (or unset) in the server-cleanup finally.
    saved_allow_async_unsafe = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    # port=0 lets the OS pick; LiveServerThread publishes the chosen port after
    # is_ready. daemon=True so a crashed command can't strand the server thread.
    server = LiveServerThread(host, StaticFilesHandler, port=0)
    server.daemon = True
    try:
        with (
            modify_settings(
                ALLOWED_HOSTS={"append": host},
                # Prepend (index 0 = outermost) so the atomic wraps every other
                # middleware's writes too — notably SessionMiddleware's
                # response-phase save. Scoped to this drive by the context
                # manager; the chain is cached into the LiveServerThread's own
                # WSGIHandler, which dies with the server at drive end.
                MIDDLEWARE={"prepend": f"{__name__}.RollbackEveryRequestMiddleware"},
            ),
            override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None),
        ):
            server.start()
            server.is_ready.wait()
            if server.error is not None:
                raise server.error
            base_url = f"http://{host}:{server.port}"
            # Imported lazily so importing buildfrontend never needs playwright
            # (a test/dev dep; --skip-playwright builds must not require it).
            from playwright.sync_api import sync_playwright  # noqa: PLC0415

            with sync_playwright() as pw:
                browser = pw.firefox.launch(headless=True)
                # Two rollback layers keep the drive from touching the DB:
                # 1. in-process — one atomic on this command's connection, each
                #    @playwright_test in its own savepoint (rolled back in
                #    finally), the atomic marked set_rollback(True) so a test
                #    body's writes never commit.
                # 2. browser — RollbackEveryRequestMiddleware (prepended onto MIDDLEWARE
                #    above) wraps each live-server request in a rolled-back
                #    atomic on the server's own connection, so HTTP-triggered
                #    writes revert per request (a write is visible only within
                #    the request that makes it — per-request, not per-test).
                # Each test also gets a fresh BrowserContext (closed in finally),
                # so no session/storage leaks between tests — matching the
                # per-test savepoint isolation.
                # set_rollback(True) is the LAST statement in the block: it
                # poisons further queries (validate_no_broken_transaction),
                # mirroring TestCase._rollback_atomics.
                with transaction.atomic():
                    for test_function in tests:
                        sid = transaction.savepoint()
                        context = browser.new_context()
                        try:
                            try:
                                test_function(context=context, base_url=base_url)
                            except Exception:
                                # Stop on the first failure; show which test +
                                # its traceback before the server/browser tear
                                # down.
                                err_write(f"@playwright_test {test_function.__name__} failed:")
                                err_write(traceback.format_exc())
                                raise
                        finally:
                            context.close()
                            transaction.savepoint_rollback(sid)
                            transaction.savepoint_commit(sid)
                    transaction.set_rollback(True)
                browser.close()
    finally:
        if saved_allow_async_unsafe is None:
            os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        else:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = saved_allow_async_unsafe
        if server.is_alive():
            server.terminate()
