"""Shared Playwright E2E base for the framework and ``ourapp``.

Lives in the test package (it's test infrastructure). Import it directly:
``from djangoapp.tests.playwright._base import BasePlaywrightTestCase``. It is
NOT re-exported from ``djangoapp.shortcuts`` — re-exporting it would pull the
playwright dependency into production code.
"""

from __future__ import annotations

import os
import typing
from contextlib import contextmanager

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings, tag
from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Playwright,
    sync_playwright,
)

from djangoapp.models import User

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

# Injected before page scripts: stringify the args of console.error so a logged
# Error (e.g. a Vue render error caught and logged by the app) reports its
# stack/message instead of Playwright's opaque "JSHandle@object". Without this a
# failing render surfaces as a useless string and the test author has to debug
# blind (see the Instant.html transcript).
_STRINGIFY_CONSOLE_ERROR = """
(() => {
  const orig = console.error.bind(console);
  console.error = (...args) =>
    orig(
      ...args.map((a) =>
        a && typeof a === "object" && (a.stack || a.message)
          ? a.stack || a.message
          : a,
      ),
    );
})();
"""


@tag("playwright")
@override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None)
class BasePlaywrightTestCase(StaticLiveServerTestCase):
    """Playwright E2E harness.

    Launches a headless firefox browser once per test class and gives each
    test a pre-authenticated page. Authentication bypasses Google OAuth via
    the DEBUG-only ``/login-for-test/<pk>`` view. ``tearDown`` fails the test
    on any browser console error so regressions surface loudly.

    Subclasses set up their own model fixtures in ``setUp``.
    """

    if typing.TYPE_CHECKING:
        playwright: typing.ClassVar[Playwright]
        browser: typing.ClassVar[Browser]
        context: typing.ClassVar[BrowserContext]

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.firefox.launch(headless=True)
        cls.context = cls.browser.new_context()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.logged_in_page: Page = self.context.new_page()
        self.logged_in_page.set_default_timeout(1000)
        self.console_errors: list[str] = []
        self._expect_console_errors = False
        # Attach the console.error-stringifier at the CONTEXT level so every page
        # in the shared context (incl. logged_in_page) gets it; anon_page wires
        # its own (separate) context. Capture uncaught page errors too — both
        # feed console_errors so tearDown reports the real message/stack, not
        # "JSHandle@object".
        self.context.add_init_script(script=_STRINGIFY_CONSOLE_ERROR)
        self.logged_in_page.on("console", self._handle_console)
        self.logged_in_page.on("pageerror", self._handle_pageerror)
        login_url = f"{self.live_server_url}/login-for-test/{self.user.pk}"
        self.logged_in_page.goto(login_url, wait_until="domcontentloaded")
        self.assertEqual(
            self.logged_in_page.text_content("body"),
            f"Logged in as {self.user.username}",
        )
        return super().setUp()

    def expect_console_errors(self) -> None:
        """Mark this test as expecting console/page errors (skip tearDown fail).

        The default tearDown fails on ANY console.error / pageerror, which is
        the right default for regression-hunting. Tests that deliberately raise
        an uncaught error (e.g. to exercise the client-error reporting path and
        assert on the network call instead) call this in setUp to opt out.
        """
        self._expect_console_errors = True

    def _handle_console(self, msg: object) -> None:
        assert isinstance(msg, ConsoleMessage)
        if msg.type == "error":
            # Args were already stringified by the init script, so msg.text()
            # carries the real Error stack/message.
            self.console_errors.append(msg.text)

    def _handle_pageerror(self, err: object) -> None:
        # Uncaught page errors arrive with their full message + stack as text.
        self.console_errors.append(f"pageerror: {err}")

    def tearDown(self) -> None:
        if self.console_errors and not self._expect_console_errors:
            self.fail(f"Console errors detected: {self.console_errors}")
        self.logged_in_page.close()
        return super().tearDown()

    @contextmanager
    def anon_page(self) -> Iterator[Page]:
        """Yield a fresh unauthenticated page in its own browser context.

        The context is closed on exit so anonymous sessions never leak into
        the authenticated class-level context.
        """
        # Separate context gets its own init script + console/pageerror handlers
        # so anon e2e also surfaces render errors (not just the logged-in page).
        anon_context = self.browser.new_context()
        anon_context.add_init_script(script=_STRINGIFY_CONSOLE_ERROR)
        page = anon_context.new_page()
        page.set_default_timeout(1000)
        page.on("console", self._handle_console)
        page.on("pageerror", self._handle_pageerror)
        try:
            yield page
        finally:
            anon_context.close()
