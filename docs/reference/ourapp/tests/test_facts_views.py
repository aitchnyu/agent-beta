"""Tests for the facts views (``GET /facts``, ``GET /facts/<slug>``, ``GET /fact/<public_id>``)."""

from typing import Any

from django.test import TestCase

from ourapp.models import Fact, Topic


class FactsViewTests(TestCase):
    """The /facts pages: random fact + topic list, plus per-topic random fact.

    - test_facts_page_renders_with_fact, GET /facts renders FactsPage with one fact + topics
    - test_facts_page_empty_fact_none, GET /facts with no facts has fact null
    - test_facts_page_lists_topics, GET /facts props carry every topic (pk-free)
    - test_fact_topic_page_renders, GET /facts/<slug> renders FactTopicPage (pk-free)
    - test_fact_topic_page_missing_is_404, GET /facts/<bad-slug> is 404
    - test_fact_permalink_renders, GET /fact/<public_id> renders FactPage with that one fact (pk-free)
    - test_fact_permalink_missing_is_404, GET /fact/<bad-id> is 404
    """

    def setUp(self) -> None:
        self.cars = Topic.objects.create(name="cars", slug="cars")
        self.science = Topic.objects.create(name="science", slug="science")
        self.fact = Fact.objects.create(text="VW Beetle ran 65 years.", topic=self.cars)

    def _facts_props(self) -> dict[str, Any]:
        # X-Inertia makes InertiaResponse return the page JSON directly.
        resp = self.client.get("/facts", HTTP_X_INERTIA="true")
        return resp.json()["props"]["props"]  # type: ignore[no-any-return]

    def test_facts_page_renders_with_fact(self) -> None:
        """GET /facts renders FactsPage with one fact + topics (pk-free)."""
        page = self.client.get("/facts", HTTP_X_INERTIA="true").json()
        self.assertEqual(page["component"], "ours/FactsPage")
        props = page["props"]["props"]
        self.assertEqual(props["fact"]["public_id"], self.fact.public_id)
        self.assertEqual(props["fact"]["text"], self.fact.text)
        self.assertNotIn("id", props["fact"])  # pk-free: public_id, never the integer pk
        self.assertEqual(len(props["topics"]), 2)

    def test_facts_page_empty_fact_none(self) -> None:
        """GET /facts with no facts has fact null."""
        Fact.objects.all().delete()
        props = self._facts_props()
        self.assertIsNone(props["fact"])

    def test_facts_page_lists_topics(self) -> None:
        """GET /facts props carry every topic (pk-free)."""
        props = self._facts_props()
        names = {t["name"] for t in props["topics"]}
        self.assertEqual(names, {"cars", "science"})
        for t in props["topics"]:
            self.assertIn("public_id", t)
            self.assertNotIn("id", t)

    def test_fact_topic_page_renders(self) -> None:
        """GET /facts/<slug> renders FactTopicPage scoped to the topic (pk-free)."""
        page = self.client.get("/facts/cars", HTTP_X_INERTIA="true").json()
        self.assertEqual(page["component"], "ours/FactTopicPage")
        props = page["props"]["props"]
        self.assertEqual(props["topic"]["slug"], "cars")
        self.assertEqual(props["fact"]["public_id"], self.fact.public_id)
        # pk-free: topic + fact expose public_id, never the integer id/pk.
        self.assertNotIn("id", props["topic"])
        self.assertNotIn("id", props["fact"])

    def test_fact_topic_page_missing_is_404(self) -> None:
        """GET /facts/<bad-slug> is 404."""
        resp = self.client.get("/facts/does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_fact_permalink_renders(self) -> None:
        """GET /fact/<public_id> renders FactPage with that one fact (pk-free)."""
        page = self.client.get(
            f"/fact/{self.fact.public_id}", HTTP_X_INERTIA="true"
        ).json()
        self.assertEqual(page["component"], "ours/FactPage")
        props = page["props"]["props"]
        self.assertEqual(props["fact"]["public_id"], self.fact.public_id)
        self.assertEqual(props["fact"]["text"], self.fact.text)
        self.assertNotIn("id", props["fact"])  # pk-free

    def test_fact_permalink_missing_is_404(self) -> None:
        """GET /fact/<bad-id> is 404."""
        resp = self.client.get("/fact/does-not-exist")
        self.assertEqual(resp.status_code, 404)
