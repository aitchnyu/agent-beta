from __future__ import annotations

import os
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError, OutputWrapper
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings, tag

from djangoapp.apps import dynamic_module
from djangoapp.management.commands.buildapp import Command
from djangoapp.management.commands.installorupdate import install_or_update
from djangoapp.models import Application
from djangoapp.models.dynamic import dynamic_models

# Point the apps machinery at the fixture tree so <collection>/<app>/app.py resolves.
_APPS_ROOT_PATCH = patch.object(
    dynamic_module,
    "_APPS_ROOT",
    Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures",
)


class BuildappCommandTests(TestCase):
    """``buildapp`` error paths: bad identity, unknown app, missing frontend.

    Each runs ``buildapp`` with ``--skip-playwright`` (build phase only — the
    browser phase is covered by ``BuildappDrivesPlaywrightTests`` below). All
    three must raise ``CommandError``.

    - test_buildapp_rejects_bad_identity, identity without a collection/app slash -> CommandError
    - test_buildapp_unknown_app_errors, app not installed -> CommandError
    - test_buildapp_missing_frontend_errors, installed app with no frontend/ -> CommandError
    """

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        _APPS_ROOT_PATCH.start()
        self.addCleanup(_APPS_ROOT_PATCH.stop)

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _run(self, identity: str) -> None:
        install_or_update(identity)

    def test_buildapp_rejects_bad_identity(self) -> None:
        """Buildapp errors on an identity without a collection/app slash."""
        with self.assertRaises(CommandError):
            call_command("buildapp", "nope", skip_playwright=True, stdout=StringIO())

    def test_buildapp_unknown_app_errors(self) -> None:
        """Buildapp errors when the app is not installed."""
        with self.assertRaises(CommandError):
            call_command("buildapp", "Tests/Nope", skip_playwright=True, stdout=StringIO())

    def test_buildapp_missing_frontend_errors(self) -> None:
        """Buildapp errors when an installed app has no frontend/ dir."""
        self._run("Tests/AllTypes")
        with self.assertRaises(CommandError):
            call_command("buildapp", "Tests/AllTypes", skip_playwright=True, stdout=StringIO())


class BuildappPlaywrightPhaseTests(SimpleTestCase):
    """``buildapp`` drives the app's ``@playwright_test`` funcs after building.

    Covers the post-build browser phase's control flow only — the live server +
    browser mechanics + real build are proven end to end by
    ``BuildappDrivesPlaywrightTests`` below. Here the drive helper + module
    loader are mocked so no DB/browser/vite runs.

    - test_phase_skips_when_no_playwright_tests, no @playwright_test -> drive not launched
    - test_phase_passes_when_suite_clean, clean drive -> funcs passed through, success reported
    - test_phase_raises_commanderror_on_failure, drive raises -> CommandError raised
    """

    def _command(self) -> Command:
        cmd = Command()
        cmd.stdout = OutputWrapper(StringIO())
        cmd.stderr = OutputWrapper(StringIO())
        return cmd

    def _app(self, playwright_tests: list[object]) -> Application:
        # A stand-in Application whose module() yields a DynamicModule with the
        # given @playwright_test funcs (no DB, no real module load).
        return cast(
            "Application",
            SimpleNamespace(module=lambda: SimpleNamespace(playwright_tests=playwright_tests)),
        )

    def test_phase_skips_when_no_playwright_tests(self) -> None:
        """App with no @playwright_test: the browser drive is never launched."""
        with patch("djangoapp.management.commands.buildapp._drive_playwright_tests") as mock_drive:
            self._command()._run_playwright_suite("Tests/Browser", self._app([]))
            mock_drive.assert_not_called()

    def test_phase_passes_when_suite_clean(self) -> None:
        """Clean drive (no raise): funcs passed through, buildapp reports success."""
        with patch("djangoapp.management.commands.buildapp._drive_playwright_tests") as mock_drive:
            fn = MagicMock()
            mock_drive.return_value = None
            self._command()._run_playwright_suite("Tests/Browser", self._app([fn]))
            mock_drive.assert_called_once()
            self.assertEqual(mock_drive.call_args.args[0], [fn])
            self.assertIn("err_write", mock_drive.call_args.kwargs)

    def test_phase_raises_commanderror_on_failure(self) -> None:
        """A failing @playwright_test fails the whole build (CommandError)."""
        with patch("djangoapp.management.commands.buildapp._drive_playwright_tests") as mock_drive:
            mock_drive.side_effect = RuntimeError("boom")
            with self.assertRaises(CommandError):
                self._command()._run_playwright_suite("Tests/Browser", self._app([MagicMock()]))


@tag("playwright")
@override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None)
class BuildappDrivesPlaywrightTests(TransactionTestCase):
    """``buildapp`` builds the frontend then drives ``@playwright_test`` for real.

    The dedicated sample is ``Tests/Browser`` (a minimal app: one seeded row, an
    ``@inertia_endpoint`` rendered with its own bundle, and a ``@playwright_test``
    asserting it via the browser). The browser phase is triggered by ``buildapp``
    itself (no ``--skip-playwright``), exercising buildapp's own live-server +
    playwright drive (``_drive_playwright_tests``). ``TransactionTestCase`` so the
    installed app's seeded row is committed and visible to the drive's server
    thread.

    - test_buildapp_drives_browser_app, buildapp builds + drives Tests/Browser;
      bundle written; the drive's writes (in-process + browser insert/modify) all
      roll back, leaving only the seed row
    """

    # The dedicated buildapp sample (a minimal app exercised end to end).
    _COLLECTION = "Tests"
    _APP = "Browser"
    _IDENTITY = f"{_COLLECTION}/{_APP}"

    @classmethod
    def setUpClass(cls) -> None:
        # buildapp's drive runs DB ops (the rolled-back atomic) while a
        # sync_playwright event loop is live; the test runner's async-unsafe
        # guard would block that. ``BasePlaywrightTestCase`` sets this too, but
        # this class isn't one — set it itself so it doesn't depend on test
        # ordering (it's now the first playwright-tagged appfixtures test).
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        _APPS_ROOT_PATCH.start()
        self.addCleanup(_APPS_ROOT_PATCH.stop)
        install_or_update(self._IDENTITY)

    def tearDown(self) -> None:
        # Drop the installed app's tables before the TransactionTestCase flush.
        app = Application.objects.filter(
            name=self._APP, application_collection__name=self._COLLECTION
        ).first()
        if app is not None:
            dynamic_models.delete_application(app)
        dynamic_models.reset()
        super().tearDown()

    # aihere explain the corresponding test in app.py
    def test_buildapp_drives_browser_app(self) -> None:
        """Buildapp builds + drives Tests/Browser; bundle written; the DB is unchanged.

        Every DB change the drive causes reverts: the in-process ``smoke`` probe
        (the drive's atomic), the browser insert ``bw1`` (the per-request
        middleware), and the browser modify of the seed to ``modified`` (the
        middleware again). After the drive the ``items`` table is unchanged —
        exactly the one seed row at its original value.
        """
        out = StringIO()
        call_command("buildapp", self._IDENTITY, stdout=out)
        self.assertIn("passed", out.getvalue())
        # The build wrote the app's bundle.
        app = Application.get_by_names(self._COLLECTION, self._APP)
        self.assertTrue((app.static_folder / "main.js").exists())
        # The drive left the DB unchanged: no inserted row, the seed unmodified,
        # and the in-process probe gone.
        items = app.get_table("items")
        self.assertFalse(items.objects.filter(code="smoke").exists())  # in-process write
        self.assertFalse(items.objects.filter(code="bw1").exists())  # browser insert
        self.assertFalse(items.objects.filter(code="modified").exists())  # browser modify
        self.assertEqual(items.objects.count(), 1)  # only the seed
        self.assertTrue(items.objects.filter(code="hi").exists())  # seed unmodified
