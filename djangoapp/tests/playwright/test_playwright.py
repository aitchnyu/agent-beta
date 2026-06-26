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


@tag("playwright")
@override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None)
class BasePlaywrightTestCase(StaticLiveServerTestCase):
    """Playwright E2E harness.

    Launches a headless firefox browser once per test class and gives each
    test a pre-authenticated page. Authentication bypasses Google OAuth via
    the DEBUG-only ``/login-for-test/<pk>`` view, mirroring the prevproject
    harness. ``tearDown`` fails the test on any browser console error so
    regressions surface loudly.

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
        self.logged_in_page.on("console", self._handle_console)
        login_url = f"{self.live_server_url}/login-for-test/{self.user.pk}"
        self.logged_in_page.goto(login_url, wait_until="domcontentloaded")
        self.assertEqual(
            self.logged_in_page.text_content("body"),
            f"Logged in as {self.user.username}",
        )
        return super().setUp()

    def _handle_console(self, msg: object) -> None:
        assert isinstance(msg, ConsoleMessage)
        if msg.type == "error":
            self.console_errors.append(msg.text)

    def tearDown(self) -> None:
        if self.console_errors:
            self.fail(f"Console errors detected: {self.console_errors}")
        self.logged_in_page.close()
        return super().tearDown()

    @contextmanager
    def anon_page(self) -> Iterator[Page]:
        """Yield a fresh unauthenticated page in its own browser context.

        The context is closed on exit so anonymous sessions never leak into
        the authenticated class-level context.
        """
        anon_context = self.browser.new_context()
        page = anon_context.new_page()
        page.set_default_timeout(1000)
        try:
            yield page
        finally:
            anon_context.close()
