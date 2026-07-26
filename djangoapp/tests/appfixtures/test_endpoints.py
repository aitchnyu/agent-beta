from __future__ import annotations

import types
from http import HTTPStatus
from json import loads as json_loads
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any

from django.test import SimpleTestCase, TestCase
from ninja.errors import ValidationError as NinjaValidationError
from pydantic import BaseModel

from djangoapp.apps.dynamic_module import (
    BaseSchema,
    DynamicModule,
    ExceptionWrapper,
    InertiaPage,
    a_test_request,
    expect_error,
    post_endpoint,
)
from djangoapp.management.commands.buildbackend import build_backend
from djangoapp.models.dynamic import dynamic_models
from djangoapp.tests.appfixtures._helpers import patched_app_root

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest

_APPS_ROOT_PATCH = patched_app_root()


class EndpointViewTests(TestCase):
    """HTTP serving of every endpoint verb at ``.../e/<fn>`` (method-dispatched).

    Each test installs the relevant fixture app (inside the test's transaction),
    then hits the endpoint over HTTP and asserts the JSON shape / values / 404s /
    Inertia page object. ``_APPS_ROOT`` is patched to the fixture tree (via
    ``patched_app_root``) so ``<app>`` resolves. A (method, name) mismatch is a 404,
    not 405.

    - test_demo_random_code_varies, GET returns 200 with a seeded code, and repeats vary
    - test_alltypes_row, GET returns the seed row with every type serialised
    - test_unknown_app_404, an unknown app resolves to 404
    - test_unknown_function_404, an unknown function resolves to 404
    - test_get_endpoint_renders_inertia_page, X-Inertia GET returns the app's component + props
    - test_get_endpoint_loads_app_bundle, first-load HTML loads the app's bundle, not the host's
    - test_default_route_serves_default, GET app root serves `default`; /e/default is identical
    - test_default_route_missing_is_404, app root with no `default` endpoint resolves to 404
    - test_post_put_delete_served, POST/PUT/DELETE dispatch to their decorators and return JSON
    - test_method_mismatch_is_404, POST to a get-only name resolves to 404 (not 405)
    - test_non_get_on_app_root_is_404, POST/PUT/DELETE on the app root resolve to 404 (not 405)
    - test_base_schema_422_over_http, a BaseSchema POST endpoint serves 200 / a structured HTTP 422
    """

    def setUp(self) -> None:
        super().setUp()
        dynamic_models.reset()
        _APPS_ROOT_PATCH.start()
        self.addCleanup(_APPS_ROOT_PATCH.stop)

    def tearDown(self) -> None:
        dynamic_models.reset()
        super().tearDown()

    def _install(self, identity: str) -> None:
        build_backend(identity)

    def test_demo_random_code_varies(self) -> None:
        """GET returns 200 with a seeded code, and repeats vary across calls."""
        self._install("EndpointsApp")
        url = "/apps/EndpointsApp/e/random_code"
        seen: set[str] = set()
        for _ in range(20):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, HTTPStatus.OK)
            code = resp.json()["code"]
            self.assertIn(code, {"A1", "A2", "A3"})
            seen.add(code)
        self.assertGreater(len(seen), 1)

    def test_alltypes_row(self) -> None:
        """GET returns the seed row with every column type serialised."""
        self._install("AllColumns")
        resp = self.client.get("/apps/AllColumns/e/row")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.json()
        self.assertEqual(body["code"], "A1")
        self.assertEqual(body["qty"], 7)
        self.assertTrue(body["active"])
        self.assertEqual(body["price"], "9.99")
        self.assertIsNone(body["due"])

    def test_unknown_app_404(self) -> None:
        """An unknown app resolves to 404."""
        resp = self.client.get("/apps/UnknownApp/e/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_unknown_function_404(self) -> None:
        """An unknown function on an installed app resolves to 404."""
        self._install("EndpointsApp")
        resp = self.client.get("/apps/EndpointsApp/e/nope")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_get_endpoint_renders_inertia_page(self) -> None:
        """An X-Inertia GET returns the page object with the app's component + props."""
        self._install("EndpointsApp")
        resp = self.client.get(
            "/apps/EndpointsApp/e/endpoint_page",
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        page = resp.json()
        self.assertEqual(page["component"], "EndpointPage")
        # Props are nested under "props" (host InertiaResponse convention).
        self.assertEqual(page["props"]["props"]["code"], "A1")

    def test_get_endpoint_loads_app_bundle(self) -> None:
        """A first-load GET renders base.html with the app's bundle URL."""
        self._install("EndpointsApp")
        resp = self.client.get("/apps/EndpointsApp/e/endpoint_page")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.content.decode("utf-8")
        # base.html must load the app's own bundle, not the host's.
        self.assertIn("/static/djangoapp/apps/EndpointsApp/main.js", body)
        self.assertNotIn('src="/static/djangoapp/main.js', body)

    def test_default_route_serves_default(self) -> None:
        """GET app root serves `default`; /e/default serves the same endpoint."""
        self._install("EndpointsApp")
        base = "/apps/EndpointsApp"
        resp = self.client.get(base)
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(resp.json(), {"code": "A1"})
        # The app root and /e/default resolve the same `default` endpoint.
        self.assertEqual(
            self.client.get(base).json(), self.client.get("/apps/EndpointsApp/e/default").json()
        )

    def test_default_route_missing_is_404(self) -> None:
        """GET app root with no `default` endpoint resolves to 404."""
        self._install("AllColumns")
        resp = self.client.get("/apps/AllColumns")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_post_put_delete_served(self) -> None:
        """POST/PUT/DELETE dispatch to their decorators and return JSON."""
        self._install("EndpointsApp")
        post_resp = self.client.post("/apps/EndpointsApp/e/echo")
        self.assertEqual(post_resp.status_code, HTTPStatus.OK)
        self.assertEqual(post_resp.json(), {"created": "echoed"})
        # echo inserted a row: 3 seeds + 1 = 4. rename_first re-titles a row but
        # doesn't change the count.
        put_resp = self.client.put("/apps/EndpointsApp/e/rename_first")
        self.assertEqual(put_resp.status_code, HTTPStatus.OK)
        self.assertEqual(put_resp.json()["count"], 4)
        # drop_first deletes a row: 4 - 1 = 3.
        delete_resp = self.client.delete("/apps/EndpointsApp/e/drop_first")
        self.assertEqual(delete_resp.status_code, HTTPStatus.OK)
        self.assertEqual(delete_resp.json()["count"], 3)

    def test_method_mismatch_is_404(self) -> None:
        """A POST to a get-only name resolves to 404 (not 405)."""
        self._install("EndpointsApp")
        resp = self.client.post("/apps/EndpointsApp/e/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_non_get_on_app_root_is_404(self) -> None:
        """A non-GET on the app root resolves to 404, not 405 (404-everywhere)."""
        self._install("EndpointsApp")
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                resp = getattr(self.client, method)("/apps/EndpointsApp")
                self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_base_schema_422_over_http(self) -> None:
        """A BaseSchema POST endpoint serves 200 valid / a structured HTTP 422 invalid.

        Verifies the ninja handler seam (the in-process raise is covered by
        ``BaseSchemaTests``); here a real HTTP request must come back as 422.
        """
        self._install("SchemaApp")
        ok = self.client.post(
            "/apps/SchemaApp/e/echo", data={"name": "x"}, content_type="application/json"
        )
        self.assertEqual(ok.status_code, HTTPStatus.OK)
        self.assertEqual(ok.json()["name"], "x")
        bad = self.client.post(
            "/apps/SchemaApp/e/echo", data={}, content_type="application/json"
        )
        # Expected 422 body for a missing required field:
        #   {"detail": [{"type": "missing", "loc": ["name"], "msg": "Field required"}]}
        self.assertEqual(bad.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        detail = bad.json()["detail"]
        self.assertIsInstance(detail, list)
        self.assertTrue(any(loc == "name" for err in detail for loc in err.get("loc", [])))
        # An empty body exercises from_json_request's `request.body or "{}"` fallback
        # → "{}" → missing `name` (the same missing-field path, not a 500).
        empty = self.client.post("/apps/SchemaApp/e/echo", data="", content_type="application/json")
        self.assertEqual(empty.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertTrue(
            any(loc == "name" for err in empty.json()["detail"] for loc in err.get("loc", []))
        )


def _synthetic_module(*fns: Callable[..., object]) -> ModuleType:
    """Build a throwaway module carrying ``fns`` (no ``@setup`` required).

    Keys are positional (``_0``, ``_1``, …) so two functions sharing an
    ``__name__`` both survive in ``vars(module)`` — ``DynamicModule`` reads the
    endpoint name from ``obj.__name__``, not the dict key.
    """
    mod = types.ModuleType("synthetic")
    # Populate via vars() subscripts: mypy rejects `mod._0 = ...` (ModuleType
    # has no such attribute), and ruff's unsafe-fixes would convert setattr(...) back
    # to that assignment. Dict-key assignment is stable under both.
    namespace = vars(mod)
    for i, fn in enumerate(fns):
        namespace[f"_{i}"] = fn
    return mod


class EndpointRegistryTests(SimpleTestCase):
    """The ``DynamicModule`` call-boundary contract (no HTTP, no DB).

    A non-GET endpoint may not return an ``InertiaPage`` — the call boundary
    rejects it. (Name uniqueness across verbs isn't tested here: Python's module
    binding means a second ``def foo`` rebinds the name before discovery, so two
    same-named endpoints can't coexist in ``vars(module)`` to begin with.)

    - test_inertia_return_from_post_rejected, a @post_endpoint returning InertiaPage is rejected
    """

    def test_inertia_return_from_post_rejected(self) -> None:
        """A @post_endpoint returning InertiaPage is rejected at the call boundary."""

        class _Props(BaseModel):
            x: int = 0

        # Defeats the static post_endpoint check so the runtime backstop in
        # call_endpoint (the isinstance assert for non-GET returns) is tested.
        @post_endpoint  # type: ignore[type-var]
        def bad(request: HttpRequest) -> InertiaPage[_Props]:  # noqa: ARG001 # stub: registry test ignores request
            return InertiaPage(component="X", props=_Props())

        module = DynamicModule(_synthetic_module(bad))
        with self.assertRaises(AssertionError):
            module.call_endpoint(name="bad", request=a_test_request(method="POST"))


class ATestRequestTests(SimpleTestCase):
    """``a_test_request`` builds an ``HttpRequest`` for in-process endpoint calls.

    ``params`` → query string (``request.GET``, any method); ``data`` → form body
    (``request.POST``); ``json`` → JSON body (``request.body``); ``user`` defaults
    to ``AnonymousUser`` (``is_authenticated`` False). A body with GET, or both
    ``data`` and ``json``, raises ``ValueError``.

    - test_user_defaults_to_anonymous, a_test_request().user is anonymous, not authenticated
    - test_user_is_attached, a_test_request(user=...).user is the given user verbatim
    - test_params_populate_get, params appear in request.GET (GET method)
    - test_json_body_round_trips, json appears in request.body (POST method)
    - test_data_form_round_trips, data appears in request.POST (POST method)
    - test_body_with_get_raises, a body (json/data) with GET raises ValueError
    - test_both_data_and_json_raises, passing both data and json raises ValueError
    """

    def test_user_defaults_to_anonymous(self) -> None:
        """a_test_request() attaches AnonymousUser, which is not authenticated."""
        request = a_test_request()
        self.assertFalse(request.user.is_authenticated)

    def test_user_is_attached(self) -> None:
        """a_test_request(user=...) attaches that user verbatim to request.user."""
        user: Any = SimpleNamespace(is_authenticated=True, username="alice")
        request = a_test_request(user=user)
        self.assertIs(request.user, user)

    def test_params_populate_get(self) -> None:
        """Params land in request.GET (valid on any method; here GET)."""
        request = a_test_request(params={"a": "1", "b": "two"})
        self.assertEqual(request.GET["a"], "1")
        self.assertEqual(request.GET["b"], "two")

    def test_json_body_round_trips(self) -> None:
        """Json lands in request.body as JSON (POST method)."""
        request = a_test_request(method="POST", json={"x": 1, "y": [2, 3]})
        self.assertEqual(json_loads(request.body), {"x": 1, "y": [2, 3]})

    def test_data_form_round_trips(self) -> None:
        """Data lands in request.POST as form fields (POST method)."""
        request = a_test_request(method="POST", data={"k": "v"})
        self.assertEqual(request.POST["k"], "v")

    def test_body_with_get_raises(self) -> None:
        """A request body (json or data) is incompatible with GET and raises."""
        with self.assertRaises(ValueError):
            a_test_request(method="GET", json={"x": 1})
        with self.assertRaises(ValueError):
            a_test_request(method="GET", data={"k": "v"})

    def test_both_data_and_json_raises(self) -> None:
        """Passing both data and json raises ValueError (mutually exclusive)."""
        with self.assertRaises(ValueError):
            a_test_request(method="POST", data={"k": "v"}, json={"x": 1})


class ExpectErrorTests(SimpleTestCase):
    """``expect_error`` captures a raised exception — ``pytest.raises`` without pytest.

    - test_captures_exception, the block's exception is exposed as ``e.exception``
    - test_asserts_when_nothing_raised, a non-raising block fails loudly (no silent pass)
    - test_base_exception_propagates, ``KeyboardInterrupt``/``SystemExit`` are not swallowed
    """

    def test_captures_exception(self) -> None:
        """The raised exception is exposed on ``e.exception`` (instance + type)."""
        msg = "boom"
        with expect_error() as e:
            raise ValueError(msg)
        self.assertIsInstance(e.exception, ValueError)
        self.assertEqual(str(e.exception), msg)

    def test_asserts_when_nothing_raised(self) -> None:
        """A non-raising block fails the test with the "did not raise" message."""
        with self.assertRaises(AssertionError) as cm, expect_error():
            pass  # no exception
        self.assertIn("did not raise", str(cm.exception))

    def test_base_exception_propagates(self) -> None:
        """KeyboardInterrupt (a BaseException, not Exception) is NOT captured."""
        with self.assertRaises(KeyboardInterrupt), expect_error():
            raise KeyboardInterrupt

    def test_reading_before_capture_raises(self) -> None:
        """Reading ``.exception`` before the block raised fails with the documented message."""
        wrapper = ExceptionWrapper()
        with self.assertRaises(AssertionError) as cm:
            _ = wrapper.exception  # the property raises before the assignment binds
        self.assertEqual(str(cm.exception), "expect_error captured no exception")


class _ThingSchema(BaseSchema):
    """A tiny schema for BaseSchemaTests: name (str) + qty (int)."""

    name: str
    qty: int


class BaseSchemaTests(SimpleTestCase):
    """``BaseSchema.from_json_request`` parses + validates a JSON body (422 on error).

    - test_valid_body_returns_instance, a valid JSON body parses to a typed instance
    - test_invalid_body_raises_422, a schema violation raises ninja ValidationError
      (→ 422) naming the field
    - test_wrong_type_raises_422, a present-but-wrong-type field raises 422
    - test_non_dict_json_raises_422, a valid-JSON non-dict body raises 422 (not 500)
    - test_non_json_body_raises_422, a non-JSON body raises ninja ValidationError (→ 422)
    """

    def test_valid_body_returns_instance(self) -> None:
        """A valid JSON body parses to a typed, validated instance."""
        thing = _ThingSchema.from_json_request(
            a_test_request(method="POST", json={"name": "widget", "qty": 3}),
        )
        self.assertEqual(thing.name, "widget")
        self.assertEqual(thing.qty, 3)

    def test_invalid_body_raises_422(self) -> None:
        """A schema violation raises ninja ValidationError (→ 422) naming the field.

        The ``detail`` is a machine-parseable list of field errors, not a string.
        """
        # Expected 422 body (a missing required field):
        #   {"detail": [
        #     {"type": "missing", "loc": ["qty"], "msg": "Field required"}
        #   ]}
        with expect_error() as e:  # missing 'qty'
            _ThingSchema.from_json_request(a_test_request(method="POST", json={"name": "x"}))
        assert isinstance(e.exception, NinjaValidationError)
        # The error body names the missing field.
        locs = [loc for err in e.exception.errors for loc in err.get("loc", [])]
        self.assertIn("qty", locs)

    def test_wrong_type_raises_422(self) -> None:
        """A present-but-wrong-type field raises 422 (the common real-world bad input)."""
        # Expected 422 body (present but the wrong type):
        #   {"detail": [
        #     {"type": "int_parsing", "loc": ["qty"],
        #      "msg": "Input should be a valid integer, unable to parse string as an integer"}
        #   ]}
        with expect_error() as e:  # qty is a string, not an int
            _ThingSchema.from_json_request(
                a_test_request(method="POST", json={"name": "x", "qty": "not-an-int"}),
            )
        assert isinstance(e.exception, NinjaValidationError)
        locs = [loc for err in e.exception.errors for loc in err.get("loc", [])]
        self.assertIn("qty", locs)

    def test_non_dict_json_raises_422(self) -> None:
        """A valid-JSON non-dict body routes through model_validate → 422 (not a 500)."""
        # Expected 422 body (valid JSON, but not an object):
        #   {"detail": [
        #     {"type": "model_type", "loc": [],
        #      "msg": "Input should be a valid dictionary or instance of _ThingSchema",
        #      "ctx": {"class_name": "_ThingSchema"}}
        #   ]}
        with expect_error() as e:  # a JSON array, not an object
            _ThingSchema.from_json_request(a_test_request(method="POST", json=[1, 2, 3]))
        assert isinstance(e.exception, NinjaValidationError)

    def test_non_json_body_raises_422(self) -> None:
        """A non-JSON body raises ninja ValidationError (→ 422) with a clear message."""
        # Expected 422 body (body isn't JSON — from_json_request's JSON guard;
        # no `type` key, since this isn't a pydantic field error):
        #   {"detail": [
        #     {"loc": ["body"], "msg": "Request body must be valid JSON."}
        #   ]}
        with expect_error() as e:
            _ThingSchema.from_json_request(a_test_request(method="POST", data={"not": "json"}))
        assert isinstance(e.exception, NinjaValidationError)
        self.assertIn("valid JSON", e.exception.errors[0].get("msg", ""))
