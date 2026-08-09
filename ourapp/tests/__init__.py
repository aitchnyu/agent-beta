"""User app tests — one file per feature + layer, flat under ``tests/``.

Naming: ``test_<feature>_<layer>.py`` where layer is ``models``, ``views``,
``commands``, or ``playwright``. Playwright files subclass
``BasePlaywrightTestCase`` (tagged ``playwright``), so ``./run test`` skips them
and ``./run playwrighttest`` runs them. Seed inside each test (the test DB rolls
back per test); assert state + endpoint return values, pk-free.
"""
