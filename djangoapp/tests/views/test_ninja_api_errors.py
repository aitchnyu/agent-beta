"""Tests for the ninja error handlers' browser-negotiation (djangoapp.ninja_api).

``register_api_error_handlers`` renders 404s as the HTML error page (with the
API message + a homepage link) when the client is a browser navigation
(``Accept: text/html`` and no ``X-Inertia`` header), and keeps the JSON
``{"detail": ...}`` contract for every API client. These tests pin both
branches and the negotiation guard.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from ninja import NinjaAPI
from ninja.testing import TestClient

from djangoapp.models import User
from djangoapp.ninja_api import register_api_error_handlers
from djangoapp.tests._base import BaseInertiaTestCase, BaseTestCase

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

_BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


class NinjaErrorHtmlTests(BaseInertiaTestCase):
    """Ninja 404 content negotiation: HTML page for browsers, JSON for API clients.

    - test_browser_navigation_gets_html_404, text/html Accept without X-Inertia
      renders 404.html (message + homepage link)
    - test_api_client_still_gets_json_404, the default Accept (*/*) keeps the
      {"detail": ...} JSON contract
    - test_inertia_visit_gets_json_404, an X-Inertia visit with a browser
      Accept stays on JSON
    """

    superuser: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)

    def test_browser_navigation_gets_html_404(self) -> None:
        """A text/html Accept (no X-Inertia) renders the 404 page, not JSON."""
        self.client.force_login(self.superuser)
        response = self.client.get("/files/ourapp/does-not-exist.txt", HTTP_ACCEPT=_BROWSER_ACCEPT)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        body = response.content.decode()
        self.assertIn("Page not found", body)
        self.assertIn('href="/"', body)

    def test_api_client_still_gets_json_404(self) -> None:
        """The default test-client Accept (*/*) keeps the JSON contract."""
        self.client.force_login(self.superuser)
        response = self.client.get("/files/ourapp/does-not-exist.txt")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("detail", response.json())

    def test_inertia_visit_gets_json_404(self) -> None:
        """An X-Inertia visit with a browser Accept stays on the JSON protocol."""
        self.client.force_login(self.superuser)
        response = self.client.get(
            "/files/ourapp/does-not-exist.txt",
            HTTP_ACCEPT=_BROWSER_ACCEPT,
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("detail", response.json())


class NinjaPermissionDeniedTests(BaseTestCase):
    """A PermissionDenied from any ninja API → the friendly fixed 403 JSON.

    No app endpoint raises PermissionDenied today — this pins the handler's
    contract (status kept, fixed leak-free body) on a scratch API, so a view
    that starts raising it later gets the documented shape for free.

    - test_permission_denied_gets_friendly_403, 403 + the fixed friendly detail
    """

    def test_permission_denied_gets_friendly_403(self) -> None:
        """The handler answers 403 with the fixed permission-denied text."""
        api = NinjaAPI(urls_namespace="perm-denied-tests", auth=None)
        register_api_error_handlers(api)

        @api.get("/boom", response=None)
        def _raise_denied(request: HttpRequest) -> HttpResponse:  # noqa: ARG001
            raise PermissionDenied

        response = TestClient(api).get("/boom")
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        # The literal text, not the private constant — a regression in the
        # message itself must fail this test, not mirror it.
        self.assertEqual(response.json(), {"detail": "You don't have permission to do that."})
