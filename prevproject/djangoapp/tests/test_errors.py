import json

from django.http import Http404
from django.test import RequestFactory, TestCase
from ninja import NinjaAPI

from djangoapp.errors import ApiError, register_api_error_handlers


class ApiErrorHandlersTest(TestCase):
    """Tests for register_api_error_handlers response shapes.

    ApiError renders its payload dict verbatim, or ``{"detail": message}`` when
    no payload is given. The Http404 handler surfaces the exception's message
    instead of discarding it (ninja's default returned a bare "Not Found").

    Common characteristics. One line per method in correct order.
    - test_api_error_string_message, body is {detail: message} with the error's status
    - test_api_error_payload_replaces_body, payload dict replaces the body verbatim
    - test_api_error_payload_none_keeps_detail, no payload keeps {detail: message} and logs message
    - test_http_404_with_message_propagates, Http404("msg") surfaces msg
    - test_bare_http_404_falls_back, bare Http404 returns generic "Not Found"
    """

    def setUp(self) -> None:
        """Build a NinjaAPI with the handlers registered and a GET request."""
        self.api = NinjaAPI(urls_namespace="test-errors-api")
        register_api_error_handlers(self.api)
        self.request = RequestFactory().get("/")

    def test_api_error_string_message(self) -> None:
        """Body is {detail: message} with the error's status."""
        response = self.api.on_exception(self.request, ApiError(404, "Article not found"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content), {"detail": "Article not found"})

    def test_api_error_payload_replaces_body(self) -> None:
        """Payload dict replaces the body verbatim; message is kept only for str()."""
        exc = ApiError(400, "duplicate", payload={"code": "dup", "message": "Tag exists"})
        self.assertEqual(str(exc), "duplicate")
        response = self.api.on_exception(self.request, exc)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content), {"code": "dup", "message": "Tag exists"})

    def test_api_error_payload_none_keeps_detail(self) -> None:
        """No payload keeps {detail: message}."""
        response = self.api.on_exception(self.request, ApiError(400, "Bad request"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content), {"detail": "Bad request"})

    def test_http_404_with_message_propagates(self) -> None:
        """Http404("msg") surfaces the message rather than discarding it."""
        response = self.api.on_exception(self.request, Http404("Article not found"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content), {"detail": "Article not found"})

    def test_bare_http_404_falls_back(self) -> None:
        """Bare Http404 returns the generic Not Found."""
        response = self.api.on_exception(self.request, Http404())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content), {"detail": "Not Found"})
