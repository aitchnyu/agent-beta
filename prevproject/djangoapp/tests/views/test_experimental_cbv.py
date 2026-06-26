"""Tests for the experimental decorator-driven class-based Ninja views."""

from django.test import TestCase, override_settings
from django.urls import path
from ninja import NinjaAPI

from djangoapp.views.app import C1, C2
from djangoapp.views.foo import ListView


class _InstanceCounter(ListView):
    """SomeBase subclass that counts instantiations per request.

    Proves a fresh instance is built for every call: if the same instance were
    reused, the counter would not advance between requests.
    """

    instances = 0

    def __init__(self) -> None:
        super().__init__()
        type(self).instances += 1

    def list(self) -> list[int]:
        return [type(self).instances]


# Each class's get_router() returns its Router; mount them on one NinjaAPI here
# under explicit prefixes.
cbv_api = NinjaAPI(urls_namespace="test-cbv", openapi_url=None)
cbv_api.add_router("c1", C1.get_router())
cbv_api.add_router("c2", C2.get_router())
cbv_api.add_router("counter", _InstanceCounter.get_router())

urlpatterns = [
    path("", cbv_api.urls),
]


@override_settings(ROOT_URLCONF=__name__)
class ClassBasedViewTests(TestCase):
    """SomeBase/C1/C2 endpoints mount and dispatch from a fresh instance.

    The class-based layer tags methods with @mrouter.get(...), discovers them
    across the MRO via get_router(), mounts each under its add_router prefix,
    and serves every request from a freshly constructed instance.

    - test_c1_list: /c1/list returns C1.list() payload [1,2,3]
    - test_c2_list: /c2/list returns C2.list() override ['a','b','c']
    - test_c2_custom: /c2/custom hits the C2-only endpoint 'hello'
    - test_c1_custom_404: /c1/custom is not defined on C1, so 404
    - test_fresh_instance_per_call: each request builds a new instance (counter advances)
    - test_inheritance_picks_up_base_endpoint: C1 inherits _list from SomeBase
    """

    def test_c1_list(self) -> None:
        """/c1/list serializes C1.list() as JSON [1,2,3]."""
        response = self.client.get("/c1/list")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [1, 2, 3])

    def test_c2_list(self) -> None:
        """/c2/list returns C2's override of list() (['a','b','c'])."""
        response = self.client.get("/c2/list")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["a", "b", "c"])

    def test_c2_custom(self) -> None:
        """/c2/custom hits the endpoint C2 added via @mrouter.get('/custom')."""
        response = self.client.get("/c2/custom")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), "hello")

    def test_c1_custom_404(self) -> None:
        """Custom is C2-only, so /c1/custom is not routed (404)."""
        response = self.client.get("/c1/custom")
        self.assertEqual(response.status_code, 404)

    def test_fresh_instance_per_call(self) -> None:
        """Two calls each advance the instance counter, proving no reuse."""
        _InstanceCounter.instances = 0
        first = self.client.get("/counter/list")
        second = self.client.get("/counter/list")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), [1])
        self.assertEqual(second.json(), [2])

    def test_inheritance_picks_up_base_endpoint(self) -> None:
        """C1 inherits SomeBase._list, exposing /c1/list without redeclaring it."""
        self.assertNotIn("_list", vars(C1))
        response = self.client.get("/c1/list")
        self.assertEqual(response.status_code, 200)
