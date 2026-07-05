from __future__ import annotations

import os
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings, tag

from djangoapp.apps import dynamic_module
from djangoapp.apps.dynamic_module import app_modules, apps_root
from djangoapp.management.commands.installorupdate import install_or_update
from djangoapp.models import Application
from djangoapp.models.dynamic import dynamic_models
from djangoapp.tests.playwright.test_playwright import BasePlaywrightTestCase

# Which fixture app's @playwright_test funcs this case runs. Override with the
# APP_IDENTITY env var ("Collection/App") to verify a different app in a browser.
# Reading it at import time lets the test runner pick it up; format is validated
# in setUp so a bad value surfaces as a clear skip, not an import crash.
# aihere remove this IDENTITY thing, since we have a better way to test apps
IDENTITY = os.environ.get("APP_IDENTITY", "Tests/Page")
_DEFAULT_APPS_ROOT = Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures"

_APPS_ROOT_PATCH = patch.object(dynamic_module, "_APPS_ROOT", _DEFAULT_APPS_ROOT)


class AppPlaywrightTests(BasePlaywrightTestCase):
    """Run a specified fixture app's ``@playwright_test`` funcs in a browser.

    Phase 5 second phase of the app workflow (after ``installorupdate`` installs +
    seeds and ``buildapp`` builds the frontend): the app is installed and its
    frontend built in ``setUp`` (TransactionTestCase flushes between tests, so
    each test re-installs), then every ``@playwright_test(page, base_url)`` the
    app declares is driven against the live server. Green = the app is verified
    installed end to end. The target app is selected by the ``APP_IDENTITY``
    env var ("Collection/App", default ``Tests/Page``); an app with no
    ``@playwright_test`` is skipped. Dynamic tables are dropped in ``tearDown``
    so the TransactionTestCase flush doesn't choke on their FKs.

    - test_run_playwright_tests, runs every @playwright_test on the APP_IDENTITY app
    """

    def setUp(self) -> None:
        # Clear the in-memory dynamic-model registry: TransactionTestCase flushes
        # the DB between tests but not this process-wide singleton, so stale model
        # classes from a prior install would clash with the fresh one.
        # aihere can you use the sync_app_cache method instead of .reset() throughout the codebase
        dynamic_models.reset()
        _APPS_ROOT_PATCH.start()
        self.addCleanup(_APPS_ROOT_PATCH.stop)
        if "/" not in IDENTITY:
            msg = f"APP_IDENTITY must be '<Collection>/<App>', got {IDENTITY!r}."
            self.skipTest(msg)
        self.collection, self.app_name = IDENTITY.split("/", 1)

        # Load the module first so we can skip apps that declare no browser
        # tests without paying for the install + frontend build (or launching a
        # browser page in super().setUp()).
        script_path = (apps_root() / self.collection / self.app_name / "app.py").resolve()
        self.dm = app_modules.load(script_path, force_reload=True)
        if not self.dm.playwright_tests:
            self.skipTest(f"{IDENTITY} declares no @playwright_test funcs.")

        super().setUp()
        install_or_update(IDENTITY)
        self.app = Application.get_by_names(self.collection, self.app_name)
        self._build_frontend()

    def tearDown(self) -> None:
        # Drop the installed app's physical tables before the TransactionTestCase
        # flush (dynamic zz_* tables FK auth_user and would block it).
        app = Application.objects.filter(
            name=self.app_name,
            application_collection__name=self.collection,
        ).first()
        if app is not None:
            dynamic_models.delete_application(app)
        dynamic_models.reset()
        super().tearDown()

    # aihere dry this method with the buildapp folder
    def _build_frontend(self) -> None:
        """Install deps (if missing) and build this one app's frontend via buildapp.

        ``skip_playwright=True`` so buildapp builds only — this harness drives the
        browser itself; buildapp's own browser phase is for standalone use.
        """
        frontend_dir = apps_root() / self.collection / self.app_name / "frontend"
        npm = shutil.which("npm")
        if npm is None:
            msg = "npm not found on PATH."
            raise RuntimeError(msg)
        if not (frontend_dir / "node_modules").exists():
            subprocess.run(  # noqa: S603 # argv fixed; cwd is the app frontend
                [npm, "install"],
                cwd=frontend_dir,
                check=True,
            )
        call_command("buildapp", IDENTITY, skip_playwright=True, stdout=StringIO())

    def test_run_playwright_tests(self) -> None:
        """Run every @playwright_test(page, base_url) declared by the app."""
        page = self.context.new_page()
        page.set_default_timeout(5000)
        try:
            for fn in self.dm.playwright_tests:
                with self.subTest(test=fn.__name__):
                    fn(page=page, base_url=self.live_server_url)
        finally:
            page.close()


@tag("playwright")
@override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None)
class BuildappDrivesPlaywrightTests(TransactionTestCase):
    """``buildapp`` builds the frontend then drives ``@playwright_test`` for real.

    Distinct from ``AppPlaywrightTests``: here the browser phase is triggered by
    ``buildapp`` itself (no ``--skip-playwright``), exercising buildapp's own
    live-server + playwright drive (``_drive_playwright_tests``) rather than the
    ``StaticLiveServerTestCase`` harness. ``TransactionTestCase`` so the installed
    app's seeded row is committed and visible to the drive's server thread.

    - test_buildapp_drives_demo_page, buildapp builds + drives @playwright_test on the live install
    """

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        _APPS_ROOT_PATCH.start()
        self.addCleanup(_APPS_ROOT_PATCH.stop)
        install_or_update(IDENTITY)
        # buildapp runs `npm run build`, not `install`; ensure node_modules first.
        frontend_dir = apps_root() / "Tests" / "Page" / "frontend"
        npm = shutil.which("npm")
        if npm is not None and not (frontend_dir / "node_modules").exists():
            subprocess.run(  # noqa: S603 # argv fixed; cwd is the app frontend
                [npm, "install"],
                cwd=frontend_dir,
                check=True,
            )

    def tearDown(self) -> None:
        # Drop the installed app's tables before the TransactionTestCase flush.
        app = Application.objects.filter(name="Page", application_collection__name="Tests").first()
        if app is not None:
            dynamic_models.delete_application(app)
        dynamic_models.reset()
        super().tearDown()

    def test_buildapp_drives_demo_page(self) -> None:
        """Tests/Page: buildapp (no --skip-playwright) builds + drives @playwright_test."""
        out = StringIO()
        call_command("buildapp", IDENTITY, stdout=out)
        self.assertIn("passed", out.getvalue())
