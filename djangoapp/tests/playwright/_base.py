"""Shared Playwright E2E base for the framework and ``ourapp``.

Lives in the test package (it's test infrastructure). Import it directly:
``from djangoapp.tests.playwright._base import BasePlaywrightTestCase``. It is
NOT re-exported from ``djangoapp.shortcuts`` — re-exporting it would pull the
playwright dependency into production code.
"""

from __future__ import annotations

import os
import typing
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from importlib import import_module

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.http import HttpRequest
from django.test import override_settings, tag
from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
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


@dataclass
class _ConsoleSink:
    """Where the suite-wide console/pageerror handlers write.

    It is MODULE-level because the handlers outlive every test instance —
    they are attached exactly once to the shared page/context. setUp clears
    the sink in place (never rebinds: handlers hold the reference), so each
    test sees exactly its own errors.
    """

    errors: list[str] = field(default_factory=list)
    expect: bool = False


_console = _ConsoleSink()


def _on_console(msg: ConsoleMessage) -> None:
    if msg.type == "error":
        # Args were already stringified by the init script, so msg.text()
        # carries the real Error stack/message.
        _console.errors.append(msg.text)


def _on_pageerror(err: object) -> None:
    # Uncaught page errors arrive with their full message + stack as text.
    _console.errors.append(f"pageerror: {err}")


# ONE playwright/firefox/context/page per test process, created lazily on the
# first playwright class. Sharing the browser skips per-class cold launches;
# sharing ONE context + page (instead of per class/test) keeps a single HTTP
# cache and a warm page across the whole run — per-test contexts/pages were
# seconds of pure overhead, and auth isolation doesn't need them: setUp wipes
# the context's cookies and injects this test's session (``login_as``). Tests
# needing a genuinely separate viewer use ``anon_page`` (its own context).
# Never explicitly closed — the runner is a one-shot process and playwright's
# driver exits when the interpreter does (stdin EOF), taking firefox with it;
# refcounted teardown was tried and only added failure modes.
class _SharedBrowser:
    """Lazily created process-wide playwright + firefox + context + page."""

    def __init__(self) -> None:
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def ensure(self) -> tuple[Browser, BrowserContext, Page]:
        """Create everything on first use; return the (browser, context, page)."""
        if self.browser is None:
            self.browser = sync_playwright().start().firefox.launch(headless=True)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            # Init script + handlers ONCE here — page.on stacks, so per-test
            # attachment on the shared page would pile up N copies (and dead
            # test-instance bindings). They route into the module-level sink.
            self.context.add_init_script(script=_STRINGIFY_CONSOLE_ERROR)
            assert self.page is not None
            self.page.set_default_timeout(1000)
            self.page.on("console", _on_console)
            self.page.on("pageerror", _on_pageerror)
        assert self.browser is not None
        assert self.context is not None
        assert self.page is not None
        return self.browser, self.context, self.page


_SHARED_BROWSER = _SharedBrowser()


@tag("playwright")
@override_settings(
    DEBUG=True,
    SECURE_CSP_REPORT_ONLY=None,
    # Fast test hasher (see djangoapp/tests/_base.py): e2e setUp creates
    # password-bearing users per test and never authenticates by password
    # (login is in-process cookie injection), so PBKDF2 is pure runtime here.
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class BasePlaywrightTestCase(StaticLiveServerTestCase):
    """Playwright E2E harness.

    Shares one headless firefox + one browser context + one page across the
    whole run (see the module globals). ``self.page`` is that shared page;
    per-test isolation comes from wiping the context's cookies in setUp and
    injecting this test's session (``login_as``) — no login navigation, no
    per-test page. Tests that need a genuinely separate viewer use
    ``anon_page`` (its own context). ``tearDown`` fails the test on any
    browser console error so regressions surface loudly.

    Subclasses set up their own model fixtures in ``setUp`` and may re-auth
    via ``login_as`` (it replaces the session cookie) — e.g. superuser-only
    suites log in their admin that way.

    Isolation note: cookies and the document are reset per test (clear_cookies
    + the about:blank navigation in tearDown) but localStorage is NOT — it is
    origin-scoped and shared with the suite context. Nothing uses it today;
    the first e2e that does must clear it in its own setUp.
    """

    if typing.TYPE_CHECKING:
        browser: typing.ClassVar[Browser]
        context: typing.ClassVar[BrowserContext]
        page: Page
        user: User
        console_errors: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.browser, cls.context, _ = _SHARED_BROWSER.ensure()

    def login_as(self, user: User) -> None:
        """Authenticate the shared context as ``user`` — no HTTP round trip.

        In-process ``login(request, user, backend=ModelBackend)``: a fresh
        session store, ``auth_login`` fills/rotates it, one save, then the session cookie is
        injected straight into the browser context. The next navigation (any
        test goto) is already authenticated. A second call with a different
        user REPLACES the cookie (same name); setUp clears cookies first so
        each test starts with exactly its own user's session.
        """
        engine = import_module(settings.SESSION_ENGINE)
        request = HttpRequest()
        request.session = engine.SessionStore()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.save()
        assert request.session.session_key is not None
        self.context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": request.session.session_key,
                    "url": self.live_server_url,
                }
            ]
        )

    def setUp(self) -> None:
        # Fresh console capture FIRST (the shared page's handlers write into
        # the module sink; clear in place, never rebind) — then hand this test
        # the shared page + its own session cookie.
        _console.errors.clear()
        _console.expect = False
        self.console_errors = _console.errors
        self.page = _SHARED_BROWSER.ensure()[2]
        # Reset the shared page's timeout per test: subclass setUps may raise
        # it for their own tests, and without this the raise leaks to every
        # LATER class via execution order (the shared page outlives classes).
        self.page.set_default_timeout(1000)
        self.context.clear_cookies()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.login_as(self.user)
        return super().setUp()

    def expect_console_errors(self) -> None:
        """Mark this test as expecting console/page errors (skip tearDown fail).

        The default tearDown fails on ANY console.error / pageerror, which is
        the right default for regression-hunting. Tests that deliberately raise
        an uncaught error (e.g. to exercise the client-error reporting path and
        assert on the network call instead) call this in setUp to opt out.
        """
        _console.expect = True

    def tearDown(self) -> None:
        # The shared page is deliberately NOT closed — the next test reuses it.
        # Pump playwright's event queue first: the sync API dispatches queued
        # console/pageerror callbacks only while a playwright call runs on the
        # main thread, so an async error fired after a test's last call (e.g.
        # client-errors' setTimeout throw) would otherwise be attributed to
        # the NEXT test's freshly cleared sink. One no-op round trip (~1ms)
        # while this test still owns the sink makes attribution exact; the
        # suppress keeps a dead page from masking the test's own failure.
        with suppress(Exception):
            self.page.wait_for_timeout(0)
        if _console.errors and not _console.expect:
            self.fail(f"Console errors detected: {_console.errors}")
        return super().tearDown()

    @classmethod
    def tearDownClass(cls) -> None:
        # Kill the last test's document BEFORE the live server thread dies (in
        # super().tearDownClass): a stale document left alive across a class
        # boundary — its timers, idle-time fetches — would fetch from the
        # previous class's now-dead server port and report the unhandled
        # rejections against the NEXT class's tests. Within a class this can't
        # happen (the server stays alive), so only classes pay this navigation.
        # suppress: a dead page must not mask real failures.
        page = _SHARED_BROWSER.page
        if page is not None:
            with suppress(Exception):
                page.goto("about:blank")
        super().tearDownClass()

    @contextmanager
    def anon_page(self) -> Iterator[Page]:
        """Yield a fresh unauthenticated page in its own browser context.

        The context is closed on exit so anonymous sessions never leak into
        the shared suite context. Its console/pageerror handlers feed the
        current test's sink (same failure-on-error semantics).
        """
        anon_context = self.browser.new_context()
        # Init script BEFORE the page exists so even a pre-navigation evaluate
        # sees the stringifier (init scripts also run on existing pages' next
        # navigation, but ordering keeps the guarantee obvious).
        anon_context.add_init_script(script=_STRINGIFY_CONSOLE_ERROR)
        page = anon_context.new_page()
        page.set_default_timeout(1000)
        page.on("console", _on_console)
        page.on("pageerror", _on_pageerror)
        try:
            yield page
        finally:
            anon_context.close()
