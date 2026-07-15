from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import CommandError
from django.test import TestCase

from djangoapp.apps import dynamic_module
from djangoapp.management.commands.buildbackend import build_backend
from djangoapp.models import Application, ApplicationCollection, ApplicationTable, AppsGeneration
from djangoapp.models.dynamic import dynamic_models

# Point the apps machinery at the fixture tree so <collection>/<app>/app.py resolves.
_APPS_ROOT_PATCH = patch.object(
    dynamic_module,
    "_APPS_ROOT",
    Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures",
)


class BuildBackendTests(TestCase):
    """The ``buildbackend`` command installs + self-tests an app.

    Each test installs one of the fixture apps under ``djangoapp/tests/appfixtures/``
    (laid out as ``<collection>/<app>/app.py``; apps_root is patched to that
    tree) and asserts the outcome. The fixtures (all under the ``Tests``
    collection):

    - ``Tests/Page`` — the happy-path install: a seeded ``items`` table + a
      ``@backend_test`` that writes a row (proving savepoint rollback).
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
    - test_fails_backend_test_rolls_back, a failing backend test reverts the whole install
    - test_fails_setup_rolls_back, a failing setup reverts the whole install
    - test_install_alltypes, every column class materialises a physical column
    - test_install_http_mock, HTTP-calling endpoint's backend_test patches the helper (no network)
    - test_successful_setup_bumps_generation, success bumps AppsGeneration; failure does not
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
        build_backend(identity)

    def test_install_demo_page(self) -> None:
        """Demo app installs: app + table + physical table; script_path resolves."""
        self._run("Tests/Page")
        app = Application.get_by_names("Tests", "Page")
        self.assertTrue(app.script_path().exists())
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
        """The HTTP-mock app installs: its backend_test with a patch works correctly."""
        self._run("Tests/Mock")
        app = Application.get_by_names("Tests", "Mock")
        # The fallback row seeded in setup is present.
        self.assertEqual(cast("Any", app.tables.get(name="facts").as_model()).objects.count(), 1)

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
