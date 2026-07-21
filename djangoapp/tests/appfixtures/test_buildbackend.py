from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import CommandError
from django.test import TestCase

from djangoapp.apps import dynamic_module
from djangoapp.management.commands.buildbackend import build_backend
from djangoapp.models import Application, ApplicationTable, AppsGeneration
from djangoapp.models.dynamic import dynamic_models

# Point the apps machinery at the fixture tree so <app>/app.py resolves.
_APPS_ROOT_PATCH = patch.object(
    dynamic_module,
    "_APPS_ROOT",
    Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures",
)


class BuildBackendTests(TestCase):
    """The ``buildbackend`` command installs + self-tests an app.

    Each test installs one of the fixture apps under ``djangoapp/tests/appfixtures/``
    (laid out as ``<app>/app.py``; apps_root is patched to that tree) and
    asserts the outcome. The fixtures:

    - ``HappyPathApp`` — the happy-path install: a seeded ``items`` table + a
      ``@backend_test`` that writes a row (proving savepoint rollback).
    - ``AllColumns`` — a table spanning every ``Column`` class, so the
      framework exercises each type end-to-end.
    - ``HttpMockApp`` — an endpoint that calls an external HTTP API via a helper
      its ``@backend_test`` patches (no real network).
    - ``FailsTestApp`` — a valid install whose ``@backend_test`` raises.
    - ``FailsSetup`` — ``@setup`` itself raises (a bad
      ``CharColumn(max_length=0)``).

    The first three cover the success path; the last two cover the rollback
    guarantee — a failing ``@backend_test`` or ``@setup`` leaves nothing behind
    (no app/table/physical table, registry cache reset).

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
        self._run("HappyPathApp")
        app = Application.objects.get(name="HappyPathApp")
        self.assertTrue(app.script_path().exists())
        table = app.tables.get(name="items")
        self.assertTrue(table.does_physical_table_exist())
        # The seed ran: the seeded codes are present.
        self.assertEqual(cast("Any", table.as_model()).objects.count(), 3)

    def test_backend_test_writes_roll_back(self) -> None:
        """A @backend_test's writes don't persist into the installed app.

        HappyPathApp has a backend_test that inserts a row; after install the table
        must hold only the 3 seeded rows — proving the test ran in a rolled-back
        savepoint.
        """
        self._run("HappyPathApp")
        table = Application.objects.get(name="HappyPathApp").tables.get(name="items")
        self.assertEqual(cast("Any", table.as_model()).objects.count(), 3)

    def test_fails_backend_test_rolls_back(self) -> None:
        """A failing backend test reverts the whole install (nothing left)."""
        with self.assertRaises(CommandError):
            self._run("FailsTestApp")
        self.assertFalse(Application.objects.filter(name="FailsTestApp").exists())
        self.assertFalse(ApplicationTable.objects.filter(name="things").exists())

    def test_fails_setup_rolls_back(self) -> None:
        """A failing setup reverts the whole install (nothing left)."""
        with self.assertRaises(CommandError):
            self._run("FailsSetup")
        self.assertFalse(Application.objects.filter(name="FailsSetup").exists())

    def test_install_alltypes(self) -> None:
        """Every column class materialises a physical column."""
        self._run("AllColumns")
        table = ApplicationTable.objects.get(
            application__name="AllColumns",
            name="row",
        )
        physical = set(table.physical_columns())
        for name in [
            "code",
            "note",
            "qty",
            "active",
            "price",
            "due",
            "owner_id",
            "category_id",
        ]:
            with self.subTest(col=name):
                self.assertIn(name, physical)

    def test_install_http_mock(self) -> None:
        """The HTTP-mock app installs: its backend_test with a patch works correctly."""
        self._run("HttpMockApp")
        app = Application.objects.get(name="HttpMockApp")
        # The fallback row seeded in setup is present.
        self.assertEqual(cast("Any", app.tables.get(name="facts").as_model()).objects.count(), 1)

    def test_successful_setup_bumps_generation(self) -> None:
        """A successful install bumps AppsGeneration; a failed one does not."""
        before = AppsGeneration.current()
        self._run("HappyPathApp")
        self.assertEqual(AppsGeneration.current(), before + 1)
        # A failed setup must not bump (it rolled back).
        before = AppsGeneration.current()
        with self.assertRaises(CommandError):
            self._run("FailsTestApp")
        self.assertEqual(AppsGeneration.current(), before)

    def test_zero_setup_app_installs_no_row(self) -> None:
        """An app with no @setup installs (tests run + bump) but creates no row.

        ZeroSetupApp has one @backend_test and no @setup: buildbackend succeeds
        (returns the test count), bumps the generation, yet leaves no
        Application row — no setup ran create_application. Proves the ≥1-setup
        guard is gone and the runner handles empty setups.
        """
        before = AppsGeneration.current()
        count = build_backend("ZeroSetupApp")
        self.assertEqual(count, 1)  # the one @backend_test ran
        self.assertEqual(AppsGeneration.current(), before + 1)
        self.assertFalse(Application.objects.filter(name="ZeroSetupApp").exists())


# Root of the multistep fixture trees: <root>/<tree>/MultiStepApp/app.py.
_MULTI_ROOT = Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures"


class BuildBackendResumeTests(TestCase):
    """``buildbackend`` resumes setups from the last completed one (forward-only).

    Two+ fixture trees under ``appfixtures/`` share the app name ``MultiStepApp``:
    ``multistep_step1`` has one ``@setup`` (``setup1``); ``multistep_step2`` has
    ``setup1`` + ``setup2`` (setup1 identical to step1's); ``multistep_renamed``
    renames ``setup2`` → ``setup_two`` (prefix mismatch).

    - test_resume_runs_only_new_step, v1→v2 install runs only setup2 (three proofs)
    - test_downgrade_refuses_resume, fewer setups than executed → CommandError
    - test_prefix_mismatch_refuses_resume, a renamed setup → CommandError
    """

    _APP = "MultiStepApp"

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _install(self, tree: str) -> None:
        """Patch ``_APPS_ROOT`` to ``<appfixtures>/<tree>/`` and run build_backend."""
        root = _MULTI_ROOT / tree
        with patch.object(dynamic_module, "_APPS_ROOT", root):
            build_backend(self._APP)

    def _install_captured(self, tree: str) -> str:
        """Like :meth:`_install` but capture the progress output, returning it."""
        root = _MULTI_ROOT / tree
        captured = io.StringIO()
        with patch.object(dynamic_module, "_APPS_ROOT", root):
            build_backend(self._APP, out_write=captured.write)
        return captured.getvalue()

    def test_resume_runs_only_new_step(self) -> None:
        """step1 install runs setup1; step2 install resumes and runs only setup2.

        Three independent proofs of the skip:
        - the captured progress output lists ``setup2`` but not ``setup1``;
        - ``executed_setups`` grows ``["setup1"]`` → ``["setup1", "setup2"]``;
        - the step2 install succeeds at all — step2's ``setup1`` does
          non-idempotent ``create_application`` work that would
          ``IntegrityError`` if re-run against the existing row.
        """
        # step1 install: fresh, runs setup1.
        self._install("multistep_step1")
        app = Application.objects.get(name=self._APP)
        self.assertEqual(app.executed_setups, ["setup1"])
        alpha = app.tables.get(name="alpha")
        self.assertTrue(alpha.does_physical_table_exist())
        self.assertFalse(app.tables.filter(name="beta").exists())
        alpha_physical_name = alpha.physical_name

        # Reset the in-memory registry between installs (alpha's model is cached
        # from step1; the generation bump from step1 also triggers a clear on
        # step2's load, but reset() is belt-and-suspenders).
        dynamic_models.reset()

        # step2 install: resume — only setup2 runs.
        out = self._install_captured("multistep_step2")

        app.refresh_from_db()
        self.assertEqual(app.executed_setups, ["setup1", "setup2"])
        # beta now exists.
        beta = app.tables.get(name="beta")
        self.assertTrue(beta.does_physical_table_exist())
        # alpha unchanged — same physical_name (setup1 did not re-run / recreate).
        alpha.refresh_from_db()
        self.assertEqual(alpha.physical_name, alpha_physical_name)
        # Captured progress lists only setup2 (robust to exact line format).
        self.assertIn("setup2", out)
        self.assertNotIn("setup1", out)

    def test_downgrade_refuses_resume(self) -> None:
        """A file with fewer setups than already executed → CommandError."""
        self._install("multistep_step2")  # executed_setups = ["setup1", "setup2"]
        with self.assertRaises(CommandError) as cm:
            self._install("multistep_step1")  # file = ["setup1"] — fewer than executed
        msg = str(cm.exception)
        # Fewer-setups branch (not the first-mismatch branch): names both lists,
        # states the resume rule, and reports how many went missing.
        # Example message:
        #   buildbackend MultiStepApp: cannot resume @setup.
        #   The @setup functions that already ran must stay at the top of
        #   app.py — every previous name preserved, in the original order ...
        #     already ran: ['setup1', 'setup2']
        #     app.py now:  ['setup1']
        #   app.py has fewer @setups (1) than already ran (2) — 1 setup(s) went missing.
        self.assertIn("MultiStepApp", msg)
        self.assertIn("already ran", msg)
        self.assertIn("fewer @setups", msg)
        self.assertIn("['setup1']", msg)
        self.assertIn("['setup1', 'setup2']", msg)
        self.assertNotIn("First mismatch", msg)

    def test_prefix_mismatch_refuses_resume(self) -> None:
        """A renamed setup in the new file → CommandError (prefix mismatch)."""
        self._install("multistep_step2")  # executed_setups = ["setup1", "setup2"]
        with self.assertRaises(CommandError) as cm:
            # file = ["setup1", "setup_two"] — same length, but position 1
            # differs from the executed "setup2", so the prefix check fails.
            self._install("multistep_renamed")
        msg = str(cm.exception)
        # First-mismatch branch (not the fewer-setups branch): same length, so
        # the message names the differing position + the two names.
        # Example message:
        #   buildbackend MultiStepApp: cannot resume @setup.
        #   The @setup functions that already ran must stay at the top of
        #   app.py — every previous name preserved, in the original order ...
        #     already ran: ['setup1', 'setup2']
        #     app.py now:  ['setup1', 'setup_two']
        #   First mismatch at position 2: was 'setup2', now 'setup_two'.
        self.assertIn("MultiStepApp", msg)
        self.assertIn("already ran", msg)
        self.assertIn("First mismatch", msg)
        self.assertIn("['setup1', 'setup2']", msg)
        self.assertIn("['setup1', 'setup_two']", msg)
        self.assertNotIn("fewer @setups", msg)
