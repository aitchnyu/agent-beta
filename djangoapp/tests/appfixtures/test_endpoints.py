from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from djangoapp.apps import dynamic_module
from djangoapp.management.commands.installorupdate import install_or_update
from djangoapp.models.dynamic import dynamic_models

_APPS_ROOT_PATCH = patch.object(
    dynamic_module,
    "_APPS_ROOT",
    Path(str(settings.BASE_DIR)) / "djangoapp" / "tests" / "appfixtures",
)


class EndpointViewTests(TestCase):
    """HTTP serving of ``@get_endpoint`` and ``@inertia_endpoint`` functions.

    Each test installs the relevant fixture app (inside the test's transaction),
    then hits the endpoint over HTTP and asserts the JSON shape / values / 404s /
    Inertia page object. ``apps_root`` is patched to the fixture tree so
    ``<collection>/<app>`` resolves.

    - test_demo_random_code, GET returns 200 JSON with a seeded code
    - test_demo_random_code_varies, repeated calls return more than one code
    - test_alltypes_row, GET returns the seed row with every type serialised
    - test_unknown_collection_404, an unknown collection resolves to 404
    - test_unknown_app_404, an unknown app resolves to 404
    - test_unknown_function_404, an unknown function resolves to 404
    - test_inertia_endpoint_page_object, X-Inertia GET returns the app's component + props
    - test_inertia_endpoint_loads_app_bundle, first-load HTML loads the app's bundle, not the host's
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
        install_or_update(identity)

    def test_demo_random_code(self) -> None:
        """GET returns 200 JSON with a code drawn from the seeded set."""
        self._install("Tests/Page")
        resp = self.client.get("/apps/a/Tests/Page/endpoint/get/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.json()
        self.assertIn("code", body)
        self.assertIn(body["code"], {"A1", "A2", "A3"})

    def test_demo_random_code_varies(self) -> None:
        """Repeated calls return more than one distinct code (randomness works)."""
        self._install("Tests/Page")
        seen = {
            self.client.get("/apps/a/Tests/Page/endpoint/get/random_code").json()["code"]
            for _ in range(20)
        }
        self.assertGreater(len(seen), 1)

    def test_alltypes_row(self) -> None:
        """GET returns the seed row with every column type serialised."""
        self._install("Tests/AllTypes")
        resp = self.client.get("/apps/a/Tests/AllTypes/endpoint/get/row")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.json()
        self.assertEqual(body["code"], "A1")
        self.assertEqual(body["qty"], 7)
        self.assertTrue(body["active"])
        self.assertEqual(body["price"], "9.99")
        self.assertIsNone(body["due"])

    def test_unknown_collection_404(self) -> None:
        """An unknown collection resolves to 404."""
        resp = self.client.get("/apps/a/Nope/Page/endpoint/get/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_unknown_app_404(self) -> None:
        """An unknown app resolves to 404."""
        resp = self.client.get("/apps/a/Tests/Nope/endpoint/get/random_code")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_unknown_function_404(self) -> None:
        """An unknown function on an installed app resolves to 404."""
        self._install("Tests/Page")
        resp = self.client.get("/apps/a/Tests/Page/endpoint/get/nope")
        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_inertia_endpoint_page_object(self) -> None:
        """An X-Inertia GET returns the page object with the app's component + props."""
        self._install("Tests/Page")
        resp = self.client.get(
            "/apps/a/Tests/Page/endpoint/inertia/demo_page",
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        page = resp.json()
        self.assertEqual(page["component"], "DemoPage")
        # Props are nested under "props" (host InertiaResponse convention).
        self.assertEqual(page["props"]["props"]["label"], "A1")

    def test_inertia_endpoint_loads_app_bundle(self) -> None:
        """A first-load GET renders base.html with the app's bundle URL."""
        self._install("Tests/Page")
        resp = self.client.get("/apps/a/Tests/Page/endpoint/inertia/demo_page")
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.content.decode("utf-8")
        # base.html must load the app's own bundle, not the host's.
        self.assertIn("/static/djangoapp/apps/Tests/Page/main.js", body)
        self.assertNotIn('src="/static/djangoapp/main.js', body)
