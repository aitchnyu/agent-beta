# ruff: noqa: INP001 # fixture app loaded by file path, not a package
"""Zero-setup fixture: no ``@setup``, just one ``@backend_test``.

Feeds ``BuildBackendTests.test_zero_setup_app_installs_no_row``: an app with no
``@setup`` is valid (DynamicModule no longer requires one). ``buildbackend`` runs
its ``@backend_test``s + bumps the generation, but — with no setup to call
``create_application`` — creates no ``Application`` row. To be servable an app
needs a setup that creates its row; this fixture intentionally has none.
"""

from __future__ import annotations

from djangoapp.apps.shortcuts import backend_test


@backend_test
def test_smoke() -> None:
    """Trivial assertion so the test machinery runs even with no setups."""
    assert True
