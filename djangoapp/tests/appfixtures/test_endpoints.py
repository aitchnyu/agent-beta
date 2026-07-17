from __future__ import annotations

import types
from http import HTTPStatus
from json import loads as json_loads
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from pydantic import BaseModel

from djangoapp.apps import dynamic_module
from djangoapp.apps.dynamic_module import (
    DynamicModule,
    InertiaPage,
    a_test_request,
    post_endpoint,
    setup,
)
from djangoapp.management.commands.buildbackend import build_backend
from djangoapp.models.dynamic import dynamic_models

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest

_APPS_ROOT_PATCH = patch.object(
    dynamic_module,
    "_APPS_ROOT",
    Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures",
)


class EndpointViewTests(TestCase):
    """HTTP serving of every endpoint verb at ``.../e/<fn>`` (method-dispatched).

    Each test installs the relevant fixture app (inside the test's transaction),
    then hits the endpoint over HTTP and asserts the JSON shape / values / 404s /
    Inertia page object. ``apps_root`` is patched to the fixture tree so
    ``<collection>/<app>`` resolves. A (method, name) mismatch is a 404, not 405.

    - test_demo_random_code_varies, GET returns 200 with a seeded code, and repeats vary
    - test_alltypes_row, GET returns the seed row with every type serialised
    - test_unknown_collection_404, an unknown collection resolves to 404
    - test_unknown_app_404, an unknown app resolves to 404
    - test_unknown_function_404, an unknown function resolves to 404
    - test_get_endpoint_renders_inertia_page, X-Inertia GET returns the app's component + props
    - test_get_endpoint_loads_app_bundle, first-load HTML loads the app's bundle, not the host's
    - test_default_route_serves_default, GET /e serves `default`; /e/default is identical
    - test_default_route_missing_is_404, GET /e with no `default` endpoint resolves to 404
    - test_post_put_delete_served, POST/PUT/DELETE dispatch to their decorators and return JSON
    - test_method_mismatch_is_404, POST to a get-only name resolves to 404 (not 405)
    - test_non_get_on_bare_e_is_404, POST/PUT/DELETE on bare /e resolve to 404 (not 405)
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
        self._install("Tests/Endpoints")
        url = "/apps/a/Tests/Endpoints/e/random_code"
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
        self._install("Tests/AllTypes")
        resp = self.client.get("/apps/a/Tests/AllTypes/e/row")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.json()
        self.assertEqual(body["code"], "A1")
        self.assertEqual(body["qty"], 7)
        self.assertTrue(body["active"])
        self.assertEqual(body["price"], "9.99")
        self.assertIsNone(body["due"])

    def test_unknown_collection_404(self) -> None:
        """An unknown collection resolves to 404."""
        resp = self.client.get("/apps/a/Nope/Page/e/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_unknown_app_404(self) -> None:
        """An unknown app resolves to 404."""
        resp = self.client.get("/apps/a/Tests/Nope/e/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_unknown_function_404(self) -> None:
        """An unknown function on an installed app resolves to 404."""
        self._install("Tests/Endpoints")
        resp = self.client.get("/apps/a/Tests/Endpoints/e/nope")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_get_endpoint_renders_inertia_page(self) -> None:
        """An X-Inertia GET returns the page object with the app's component + props."""
        self._install("Tests/Endpoints")
        resp = self.client.get(
            "/apps/a/Tests/Endpoints/e/endpoint_page",
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        page = resp.json()
        self.assertEqual(page["component"], "EndpointPage")
        # Props are nested under "props" (host InertiaResponse convention).
        self.assertEqual(page["props"]["props"]["code"], "A1")

    def test_get_endpoint_loads_app_bundle(self) -> None:
        """A first-load GET renders base.html with the app's bundle URL."""
        self._install("Tests/Endpoints")
        resp = self.client.get("/apps/a/Tests/Endpoints/e/endpoint_page")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.content.decode("utf-8")
        # base.html must load the app's own bundle, not the host's.
        self.assertIn("/static/djangoapp/apps/Tests/Endpoints/main.js", body)
        self.assertNotIn('src="/static/djangoapp/main.js', body)

    def test_default_route_serves_default(self) -> None:
        """GET /e serves `default`; /e/default serves the same endpoint."""
        self._install("Tests/Endpoints")
        base = "/apps/a/Tests/Endpoints/e"
        resp = self.client.get(base)
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(resp.json(), {"code": "A1"})
        # The bare /e and /e/default resolve the same `default` endpoint.
        self.assertEqual(self.client.get(base).json(), self.client.get(f"{base}/default").json())

    def test_default_route_missing_is_404(self) -> None:
        """GET /e on an app with no `default` endpoint resolves to 404."""
        self._install("Tests/AllTypes")
        resp = self.client.get("/apps/a/Tests/AllTypes/e")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_post_put_delete_served(self) -> None:
        """POST/PUT/DELETE dispatch to their decorators and return JSON."""
        self._install("Tests/Endpoints")
        post_resp = self.client.post("/apps/a/Tests/Endpoints/e/echo")
        self.assertEqual(post_resp.status_code, HTTPStatus.OK)
        self.assertEqual(post_resp.json(), {"created": "echoed"})
        # echo inserted a row: 3 seeds + 1 = 4. rename_first re-titles a row but
        # doesn't change the count.
        put_resp = self.client.put("/apps/a/Tests/Endpoints/e/rename_first")
        self.assertEqual(put_resp.status_code, HTTPStatus.OK)
        self.assertEqual(put_resp.json()["count"], 4)
        # drop_first deletes a row: 4 - 1 = 3.
        delete_resp = self.client.delete("/apps/a/Tests/Endpoints/e/drop_first")
        self.assertEqual(delete_resp.status_code, HTTPStatus.OK)
        self.assertEqual(delete_resp.json()["count"], 3)

    def test_method_mismatch_is_404(self) -> None:
        """A POST to a get-only name resolves to 404 (not 405)."""
        self._install("Tests/Endpoints")
        resp = self.client.post("/apps/a/Tests/Endpoints/e/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_non_get_on_bare_e_is_404(self) -> None:
        """A non-GET to bare ``/e`` resolves to 404, not 405 (404-everywhere)."""
        self._install("Tests/Endpoints")
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                resp = getattr(self.client, method)("/apps/a/Tests/Endpoints/e")
                self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)


@setup
def _placeholder_setup() -> None:
    """Stand-in ``@setup`` so synthetic modules load (DynamicModule requires one)."""


def _synthetic_module(*fns: Callable[..., object]) -> ModuleType:
    """Build a throwaway module carrying ``fns`` plus a placeholder ``@setup``.

    Keys are positional (``_0``, ``_1``, …) so two functions sharing an
    ``__name__`` both survive in ``vars(module)`` — ``DynamicModule`` reads the
    endpoint name from ``obj.__name__``, not the dict key.
    """
    mod = types.ModuleType("synthetic")
    # Populate via vars() subscripts: mypy rejects `mod._setup = ...` (ModuleType
    # has no such attribute), and ruff's unsafe-fixes would convert setattr(...) back
    # to that assignment. Dict-key assignment is stable under both.
    namespace = vars(mod)
    namespace["_setup"] = _placeholder_setup
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
