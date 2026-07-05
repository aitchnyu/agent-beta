from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError, OutputWrapper
from django.test import SimpleTestCase, TestCase

from djangoapp.apps import dynamic_module
from djangoapp.management.commands.buildapp import Command
from djangoapp.management.commands.installorupdate import install_or_update
from djangoapp.models import Application, ApplicationCollection, ApplicationTable, AppsGeneration
from djangoapp.models.dynamic import dynamic_models

# Point the apps machinery at the fixture tree so <collection>/<app>/app.py resolves.
_APPS_ROOT_PATCH = patch.object(
    dynamic_module,
    "_APPS_ROOT",
    Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures",
)


class SetupRunnerTests(TestCase):
    """The ``installorupdate`` command installs + self-tests an app.

    Each test installs one of the fixture apps under ``djangoapp/tests/appfixtures/``
    (laid out as ``<collection>/<app>/app.py``; apps_root is patched to that
    tree) and asserts the outcome. The fixtures (all under the ``Tests``
    collection):

    - ``Tests/Page`` — the happy path: a seeded ``items`` table, ``current_code``
      + ``random_code`` ``@get_endpoint``s, an ``@inertia_endpoint`` page, and
      backend tests (incl. one proving a backend_test's writes roll back).
    - ``Tests/AllTypes`` — a table spanning every ``Column`` class, so the
      framework exercises each type end-to-end.
    - ``Tests/Mock`` — an endpoint that calls an external HTTP API via a helper
      its ``@backend_test`` patches (no real network).
    - ``Tests/FailsTest`` — a valid install whose ``@backend_test`` raises.
    - ``Tests/FailsSetup`` — ``@setup`` itself raises (a bad
      ``CharColumn(max_length=0)``).

    The first three cover the success path; the last two cover the rollback
    guarantee — a failing ``@backend_test`` or ``@setup`` leaves nothing behind
    (no collection/app/table/physical table, registry cache reset).

    - test_install_demo_page, demo app installs: app + table + physical table; script_path resolves
    - test_backend_test_writes_roll_back, a backend_test's writes don't persist (savepoint)
    - test_install_alltypes, every column class materialises a physical column
    - test_install_http_mock, HTTP-calling endpoint's backend_test patches the helper (no network)
    - test_fails_backend_test_rolls_back, a failing backend test reverts the whole install
    - test_fails_setup_rolls_back, a failing setup reverts the whole install
    - test_successful_setup_bumps_generation, success bumps AppsGeneration; failure does not
    - test_buildapp_rejects_bad_identity, buildapp errors without a collection/app slash
    - test_buildapp_unknown_app_errors, buildapp errors when the app is not installed
    - test_buildapp_missing_frontend_errors, buildapp errors when the app has no frontend/
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

    def test_install_demo_page(self) -> None:
        """Demo app installs: app + table + physical table; script_path resolves."""
        self._run("Tests/Page")
        app = Application.get_by_names("Tests", "Page")
        self.assertTrue(app.script_path.exists())
        table = app.tables.get(name="items")
        self.assertTrue(table.does_physical_table_exist())
        # The seed ran: the seeded codes are present.
        self.assertEqual(cast("Any", table.as_model()).objects.count(), 3)

    def test_backend_test_writes_roll_back(self) -> None:
        """A @backend_test's writes don't persist into the installed app.

        Tests/Page has a backend_test that inserts a row; after install the table
        must hold only the 3 seeded rows — proving the test ran in a rolled-back
        savepoint.
        """
        self._run("Tests/Page")
        table = Application.get_by_names("Tests", "Page").tables.get(name="items")
        self.assertEqual(cast("Any", table.as_model()).objects.count(), 3)

    def test_install_alltypes(self) -> None:
        """Every column class materialises a physical column."""
        self._run("Tests/AllTypes")
        table = ApplicationTable.objects.get(
            application__name="AllTypes", application__application_collection__name="Tests"
        )
        physical = set(table.physical_columns())
        for name in ["code", "note", "qty", "active", "price", "due", "owner_id"]:
            with self.subTest(col=name):
                self.assertIn(name, physical)

    def test_install_http_mock(self) -> None:
        """The HTTP-mock app installs: its backend_test patched the helper (no network)."""
        self._run("Tests/Mock")
        app = Application.get_by_names("Tests", "Mock")
        # The fallback row seeded in setup is present.
        self.assertEqual(cast("Any", app.tables.get(name="facts").as_model()).objects.count(), 1)

    def test_fails_backend_test_rolls_back(self) -> None:
        """A failing backend test reverts the whole install (nothing left)."""
        with self.assertRaises(CommandError):
            self._run("Tests/FailsTest")
        self.assertFalse(ApplicationCollection.objects.filter(name="Tests").exists())
        self.assertFalse(Application.objects.filter(name="FailsTest").exists())
        self.assertFalse(ApplicationTable.objects.filter(name="things").exists())

    def test_fails_setup_rolls_back(self) -> None:
        """A failing setup reverts the whole install (nothing left)."""
        with self.assertRaises(CommandError):
            self._run("Tests/FailsSetup")
        self.assertFalse(ApplicationCollection.objects.filter(name="Tests").exists())
        self.assertFalse(Application.objects.filter(name="FailsSetup").exists())

    def test_successful_setup_bumps_generation(self) -> None:
        """A successful install bumps AppsGeneration; a failed one does not."""
        before = AppsGeneration.current()
        self._run("Tests/Page")
        self.assertEqual(AppsGeneration.current(), before + 1)
        # A failed setup must not bump (it rolled back).
        before = AppsGeneration.current()
        with self.assertRaises(CommandError):
            self._run("Tests/FailsTest")
        self.assertEqual(AppsGeneration.current(), before)

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
    browser mechanics are proven by ``AppPlaywrightTests`` (same login/playwright
    path), and the real build by the ``buildapp`` error-path tests above. Here the
    drive helper + module loader are mocked so no DB/browser/vite runs.

    - test_phase_skips_when_no_playwright_tests, no @playwright_test → drive not launched
    - test_phase_passes_when_suite_clean, clean drive → funcs passed through, success reported
    - test_phase_raises_commanderror_on_failure, drive raises → CommandError raised
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
            self._command()._run_playwright_suite("Tests/Page", self._app([]))
            mock_drive.assert_not_called()

    def test_phase_passes_when_suite_clean(self) -> None:
        """Clean drive (no raise): funcs passed through, buildapp reports success."""
        with patch("djangoapp.management.commands.buildapp._drive_playwright_tests") as mock_drive:
            fn = MagicMock()
            mock_drive.return_value = None
            self._command()._run_playwright_suite("Tests/Page", self._app([fn]))
            mock_drive.assert_called_once()
            self.assertEqual(mock_drive.call_args.args[0], [fn])
            self.assertIn("err_write", mock_drive.call_args.kwargs)

    def test_phase_raises_commanderror_on_failure(self) -> None:
        """A failing @playwright_test fails the whole build (CommandError)."""
        with patch("djangoapp.management.commands.buildapp._drive_playwright_tests") as mock_drive:
            mock_drive.side_effect = RuntimeError("boom")
            with self.assertRaises(CommandError):
                self._command()._run_playwright_suite("Tests/Page", self._app([MagicMock()]))
