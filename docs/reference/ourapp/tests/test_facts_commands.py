"""Tests for the seedfacts command."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from djangoapp.models import User
from ourapp.management.commands.seedfacts import FACTS
from ourapp.models import Fact, Topic


class SeedFactsCommandTests(TestCase):
    """seedfacts seeds 10 topics × 20 facts, idempotently and audit-logged.

    - test_seed_creates_topics_and_facts, seedfacts creates 10 topics and 200 facts
    - test_seed_is_idempotent, re-running yields the same totals (clears first)
    - test_seed_keep_preserves_existing, --keep reuses topics but appends fresh facts
    - test_seed_records_created_by, every seeded row's created_by is the seeder
    """

    def _seed(self, *args: str) -> str:
        out = StringIO()
        call_command("seedfacts", *args, stdout=out)
        return out.getvalue()

    def test_seed_creates_topics_and_facts(self) -> None:
        "seedfacts creates 10 topics and 200 facts."
        self._seed()
        self.assertEqual(Topic.objects.count(), len(FACTS))
        self.assertEqual(Fact.objects.count(), sum(len(v) for v in FACTS.values()))

    def test_seed_is_idempotent(self) -> None:
        "Re-running yields the same totals (the default clears first)."
        self._seed()
        self._seed()
        self.assertEqual(Topic.objects.count(), len(FACTS))
        self.assertEqual(Fact.objects.count(), sum(len(v) for v in FACTS.values()))

    def test_seed_keep_preserves_existing(self) -> None:
        "--keep reuses existing topics (unique slug) but appends fresh facts."
        self._seed()
        self._seed("--keep")
        # Topics are reused by slug, so --keep does not duplicate them.
        self.assertEqual(Topic.objects.count(), len(FACTS))
        # Facts have no unique constraint, so --keep appends another full set.
        self.assertEqual(Fact.objects.count(), sum(len(v) for v in FACTS.values()) * 2)

    def test_seed_records_created_by(self) -> None:
        "Every seeded row's created_by is the seeder (topics use the CREATE branch)."
        admin = User.objects.create_user(username="admin", is_superuser=True)
        self._seed()
        for topic in Topic.objects.all():
            self.assertEqual(topic.created_by_id, admin.id)
        for fact in Fact.objects.all():
            self.assertEqual(fact.created_by_id, admin.id)
