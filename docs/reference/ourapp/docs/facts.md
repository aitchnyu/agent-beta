# Facts

Random trivia, optionally scoped to a topic.

## Models

- `Topic` — `name`, `slug` (unique). Methods: `random_fact()`, `get_absolute_url()`
  (→ `/facts/<slug>`).
- `Fact` — `text`, `topic` (FK → `Topic`, RESTRICT). Manager: `Fact.objects.random(topic=…)`.

## Seed command

```
./run djangomanage seedfacts
```

Creates 10 topics (cars, science, animals, geography, history, space, food,
sports, music, technology) × 20 facts = 200 rows, audit-logged. `--keep` skips
the clear-first step.

## Routes

- `GET /facts` → Inertia page `ours/FactsPage`, props `{ fact: FactOut | null, topics: TopicOut[] }`.
- `GET /facts/<slug>` → Inertia page `ours/FactTopicPage`, props `{ topic: TopicOut, fact: FactOut | null, topics: TopicOut[] }`.
  Missing topic → 404.

## Files

- Model: `models/facts.py`. Command: `management/commands/seedfacts.py` (the
  seed `FACTS` data is inlined at the top of the command).
- View: `views/facts.py` (`router`).
- Frontend: `frontend/src/ours/pages/FactsPage.vue`, `FactTopicPage.vue`, schema in `ours/schemas.ts`.
- Tests: `tests/test_facts_models.py`, `tests/test_facts_views.py`,
  `tests/test_facts_commands.py`, `tests/test_facts_playwright.py`.
