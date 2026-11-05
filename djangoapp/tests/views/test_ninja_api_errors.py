"""Tests for the ninja error handlers' browser-negotiation (djangoapp.ninja_api).

``register_api_error_handlers`` renders 404s as the HTML error page (with the
API message + a homepage link) when the client is a browser navigation
(``Accept: text/html`` and no ``X-Inertia`` header), and keeps the JSON
``{"type", "msg", "ctx"}`` contract (ApiError shape) for every API client.
These tests pin both branches and the negotiation guard.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from ninja import NinjaAPI
from ninja.testing import TestClient

from djangoapp.models import User
from djangoapp.ninja_api import register_api_error_handlers
from djangoapp.tests._base import BaseInertiaTestCase, BaseTestCase, assert_page_404

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

_BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


class ErrorSurfaceTests(BaseInertiaTestCase):
    """The surface, not the Accept header, decides a 404's shape.

    Page URLs are plain Django views now: a page 404 always renders
    ``404.html`` (Django's handler404), whatever the client's Accept says.
    JSON ops keep the ninja contract: the {"type", "msg", "ctx"} envelope,
    with the browser-Accept HTML branch still reserved for a navigation.

    - test_page_404_is_html, a page URL → the 404 page
    - test_page_404_is_html_even_for_api_accept, Accept */* on a page URL
      does NOT switch it to JSON (the old negotiation is gone)
    - test_json_op_404_is_json, an API URL → the envelope (custom type kept)
    - test_json_op_404_blanket_accept_is_json, HTML Accept without X-Inertia
      on an API URL still negotiates to the envelope (ninja handlers)
    """

    superuser: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)

    def test_page_404_is_html(self) -> None:
        """A page URL 404 renders the friendly page for a browser navigation."""
        self.client.force_login(self.superuser)
        response = self.client.get("/files/ourapp/does-not-exist.txt", HTTP_ACCEPT=_BROWSER_ACCEPT)
        assert_page_404(self, response)

    def test_page_404_is_html_even_for_api_accept(self) -> None:
        """Accept */* on a page URL still gets the page — pages own that space."""
        self.client.force_login(self.superuser)
        response = self.client.get("/files/ourapp/does-not-exist.txt")
        assert_page_404(self, response)

    def test_json_op_404_is_json(self) -> None:
        """An API URL keeps the envelope, custom type included."""
        self.client.force_login(self.superuser)
        response = self.client.post("/notifications/api/00000000-0000-0000-0000-000000000000/read")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
        body = response.json()
        self.assertEqual(body["type"], "notification_not_found")
        # Unset envelope keys are omitted (ctx rides only when a view sets it).
        self.assertNotIn("ctx", body)

    def test_json_op_404_blanket_accept_is_json(self) -> None:
        """Accept */* on an API URL stays JSON (no browser-only negotiation)."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            "/notifications/api/00000000-0000-0000-0000-000000000000/read",
            HTTP_ACCEPT=_BROWSER_ACCEPT,
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(response.json()["type"], "notification_not_found")


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
        self.assertEqual(
            response.json(),
            {"type": "forbidden", "msg": "You don't have permission to do that."},
        )
