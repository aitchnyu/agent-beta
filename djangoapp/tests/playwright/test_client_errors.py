from __future__ import annotations

import json

from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class ClientErrorReportingE2e(BasePlaywrightTestCase):
    """Frontend half of the client-error pipeline (browser → request payload).

    Complement to the unit ``ClientErrorViewTests`` (djangoapp/tests/views),
    which owns the *server* side (POST → ``client_error`` log record, identity,
    rate limiting). This suite owns the *browser* side: a genuinely uncaught
    error must be captured and POSTed with the right body — it asserts on the
    request, not the log, so the two layers don't overlap.

    The harness logs in a plain user, so the home page is rendered (Inertia
    shares ``user.public_id``). We trigger a real uncaught error via
    ``setTimeout`` (so ``window.onerror`` fires with ``lineno``/``colno`` and the
    handler POSTs), then assert on the captured request body: it must carry the
    source location, the page url, and the reporter's ``public_id``. The base
    ``tearDown`` fails on console errors by default; this test calls
    ``expect_console_errors()`` because the handler legitimately logs the error
    to the console before reporting it.

    - test_uncaught_error_posts_client_location_and_user: window error → POST
      with lineno/colno/url/public_id
    - test_promise_rejection_posts_message: unhandledrejection → POST with a message
    - test_anonymous_report_omits_public_id: an anonymous viewer's report carries
      no public_id (user info reflects auth state)
    """

    def setUp(self) -> None:
        super().setUp()
        self.expect_console_errors()
        # Home route shares the viewer profile (public_id) on every Inertia page.
        # Plain goto suffices: handlers are wired at app boot and the tests
        # await the error POST via expect_request (networkidle here cost ~0.8s
        # per test for no correctness).
        self.page.goto(f"{self.live_server_url}/")

    def test_uncaught_error_posts_client_location_and_user(self) -> None:
        """A thrown window error POSTs row/col/url + the reporter's public_id."""
        page = self.page
        # A throw inside setTimeout is genuinely uncaught → window.onerror with
        # lineno/colno. page.evaluate returns before the throw fires, so the
        # error reaches our handler (and the POST), not Playwright's catcher.
        with page.expect_request(
            lambda req: req.method == "POST" and "/client-errors" in req.url
        ) as req_info:
            page.evaluate(
                "() => setTimeout(() => { throw new Error('client-errors e2e boom') }, 0)"
            )
        request = req_info.value
        self.assertIn("/client-errors", request.url)
        body = json.loads(request.post_data or "{}")
        self.assertEqual(body["message"], "client-errors e2e boom")
        # Source location captured from the ErrorEvent as real ints (present
        # even when minified — resolvable against the emitted sourcemap).
        self.assertIsInstance(body["lineno"], int)
        self.assertIsInstance(body["colno"], int)
        self.assertGreater(body["lineno"], 0)
        self.assertGreater(body["colno"], 0)
        self.assertIsInstance(body["filename"], str)
        # url is the page URL, sent verbatim (nothing sensitive is put in
        # URLs) — the home route has no query, so it equals page.url.
        self.assertEqual(body["url"], page.url)
        # Reporter identity, read from the Inertia shared prop — matches the
        # logged-in test user (backend re-derives it from request.user too).
        self.assertEqual(body["public_id"], self.user.public_id)

    def test_promise_rejection_posts_message(self) -> None:
        """An unhandled promise rejection POSTs a message (no line/col)."""
        page = self.page
        with page.expect_request(
            lambda req: req.method == "POST" and "/client-errors" in req.url
        ) as req_info:
            # Reject a promise nobody awaits → unhandledrejection event.
            page.evaluate("() => { Promise.reject(new Error('rejected boom')) }")
        body = json.loads(req_info.value.post_data or "{}")
        self.assertEqual(body["message"], "rejected boom")

    def test_anonymous_report_omits_public_id(self) -> None:
        """An anonymous viewer's report carries no public_id (user info = auth)."""
        with self.anon_page() as page:
            page.goto(f"{self.live_server_url}/")
            with page.expect_request(
                lambda req: req.method == "POST" and "/client-errors" in req.url
            ) as req_info:
                page.evaluate("() => setTimeout(() => { throw new Error('anon boom') }, 0)")
            body = json.loads(req_info.value.post_data or "{}")
            self.assertIsNone(body["public_id"])
