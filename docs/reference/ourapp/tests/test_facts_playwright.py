"""E2e for the facts pages (``/facts``, ``/facts/<slug>``)."""

from __future__ import annotations

from http import HTTPStatus

from djangoapp.tests.playwright._base import BasePlaywrightTestCase
from ourapp.models import Fact, Topic


class FactsE2e(BasePlaywrightTestCase):
    """``/facts`` + per-topic page end-to-end (headless firefox).

    - test_seeded_fact_renders, an ORM-seeded fact renders on the live /facts page
    - test_topic_page_renders_fact, /facts/<slug> renders a fact from that topic
    - test_missing_topic_404, /facts/<bad-slug> is 404
    """

    def setUp(self) -> None:
        super().setUp()
        # The base harness's 1s default is too tight for Inertia reloads; 5s
        # matches the framework e2e suites.
        self.page.set_default_timeout(5000)
        self.topic = Topic.objects.create(name="cars", slug="cars")
        self.fact = Fact.objects.create(text="E2E fact about cars", topic=self.topic)

    def test_seeded_fact_renders(self) -> None:
        "An ORM-seeded fact renders on the live /facts page."
        page = self.page
        page.goto(f"{self.live_server_url}/facts", wait_until="networkidle")
        self.assertIn("E2E fact about cars", page.inner_text("body"))

    def test_topic_page_renders_fact(self) -> None:
        "/facts/<slug> renders a fact from that topic."
        page = self.page
        page.goto(f"{self.live_server_url}/facts/cars", wait_until="networkidle")
        self.assertIn("E2E fact about cars", page.inner_text("body"))

    def test_missing_topic_404(self) -> None:
        "/facts/<bad-slug> is 404."
        with self.anon_page() as page:
            response = page.request.get(f"{self.live_server_url}/facts/does-not-exist")
            self.assertEqual(response.status, HTTPStatus.NOT_FOUND)
