"""Build an app's frontend, then verify it in a browser before completing.

Usage: ``./run djangomanage buildapp <collection>/<app>``

Resolves the app, locates its ``frontend/`` dir (``application.frontend_dir``),
and runs ``npm run build -- --emptyOutDir --outDir <static_folder>`` so vite
writes ``main.js``/``main.css`` to the app's derived static folder
(``application.static_folder``). Constant asset path; cache-busting is via the
``?cache_buster=<generation>`` the inertia view appends (no hashed filenames).

After the build, the app's ``@playwright_test`` funcs are driven in a headless
browser against a short-lived live server (see :func:`_drive_playwright_tests`)
so a green buildapp means the built bundle actually mounts and interacts. This
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
from django.test import override_settings
from django.test.testcases import LiveServerThread
from django.test.utils import modify_settings

from djangoapp.models import User
from djangoapp.models.applications import Application, AppsGeneration

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class Command(BaseCommand):
    """``djangomanage buildapp <collection/app>`` — build + browser-smoke an app."""

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

        frontend_dir = application.frontend_dir
        if not (frontend_dir / "package.json").exists():
            msg = (
                f"No frontend at {frontend_dir} (expected package.json next to "
                f"{application.script_path})."
            )
            raise CommandError(msg)

        # static_folder is a property (a pure path derivation, like frontend_dir
        # and app_bundle); .module() is a method because it does import work.
        # aihere dont keep as property, it should be .static_folder() for clarity
        static_folder = application.static_folder
        npm = shutil.which("npm")
        if npm is None:
            msg_1 = "npm not found on PATH."
            raise CommandError(msg_1)
        self.stdout.write(f"Building {identity} → {static_folder}")
        try:
            subprocess.run(  # noqa: S603 # argv fixed; cwd is the app frontend
                [
                    npm,
                    "run",
                    "build",
                    "--",
                    "--emptyOutDir",
                    "--outDir",
                    str(static_folder),
                ],
                cwd=frontend_dir,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            msg_0 = f"vite build for {identity} failed (exit {exc.returncode})."
            raise CommandError(msg_0) from exc

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
        """Drive the app's ``@playwright_test`` funcs; fail buildapp on the first failure.

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


def _drive_playwright_tests(
    tests: Sequence[Callable[..., object]],
    *,
    err_write: Callable[[str], object],
    host: str = "localhost",
) -> None:
    """Run each ``@playwright_test(page, base_url)`` in a headless browser.

    Starts a short-lived, static-aware live server on a free port, authenticates
    a throwaway user via the DEBUG-only ``/login-for-test`` view, then runs each
    func against that server. **Stops on the first failure**: its name + traceback
    are written via ``err_write`` and the exception re-raises so the caller can
    fail the build. Mirrors the playwright harness in ``tests/playwright`` but is
    command-callable: no ``TestCase`` base, and it serves the *current* default
    database, so callers must ensure the app is installed and its data committed
    (run under a ``TransactionTestCase``/real DB — a plain ``TestCase``'s
    savepoint isn't visible to the server thread).
    """
    # port=0 lets the OS pick; LiveServerThread publishes the chosen port after
    # is_ready. daemon=True so a crashed command can't strand the server thread.
    server = LiveServerThread(host, StaticFilesHandler, port=0)
    server.daemon = True
    # Per-run username (pid-suffixed) so a leaked row from a hard-killed prior
    # run can't block the next create_user on the unique constraint.
    user = User.objects.create_user(username=f"buildapp-smoke-{os.getpid()}", password="pw")
    try:
        with (
            modify_settings(ALLOWED_HOSTS={"append": host}),
            override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None),
        ):
            server.start()
            server.is_ready.wait()
            if server.error is not None:
                raise server.error
            base_url = f"http://{host}:{server.port}"
            # Imported lazily so importing buildapp never needs playwright
            # (a test/dev dep; --skip-playwright builds must not require it).
            from playwright.sync_api import sync_playwright  # noqa: PLC0415

            with sync_playwright() as pw:
                browser = pw.firefox.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(5000)
                page.goto(f"{base_url}/login-for-test/{user.pk}")
                # aihere each test will run in savepoint
                for fn in tests:
                    try:
                        # aihere pass context to browser instead of page, let user
                        # create page and users and login explicitly
                        fn(page=page, base_url=base_url)
                    except Exception:
                        # Stop on the first failure; show which test + its
                        # traceback before the server/browser tear down.
                        err_write(f"@playwright_test {fn.__name__} failed:")
                        err_write(traceback.format_exc())
                        raise
                page.close()
                context.close()
                browser.close()
    finally:
        if server.is_alive():
            server.terminate()
        user.delete()
