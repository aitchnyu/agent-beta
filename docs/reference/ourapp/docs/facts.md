# Facts

Random trivia by topic, plus a daily **Fact of the Day** — a singleton row the
Huey cron rotates each local midnight, shown on the **home page**.

## Models

- `Topic` — `name`, `slug` (unique). Methods: `random_fact()`, `get_absolute_url()`
  (→ `/facts/<slug>`).
- `Fact` — `text`, `topic` (FK → `Topic`, RESTRICT). Manager: `Fact.objects.random(topic=…)`.
- `FactOfTheDay` — a **singleton**: exactly one row, DB-enforced (a unique constant
  sentinel), `fact` (FK → `Fact`, SET_NULL). Its `last_updated_at` is "the date
  this pick was set". Methods:
  - `current()` — read-only accessor (what views use); returns the row or `None`.
    Never creates a row, so a `GET` never writes.
  - `choose_for_today()` — pick one random fact and upsert the singleton (re-stamps
    `last_updated_at`); the only mutator, called by the daily cron.

## Cron task (Huey)

`ourapp/tasks/facts.py` registers `choose_fact_of_the_day`, a `@db_periodic_task`
on `crontab(hour=0, minute=0)` (local midnight). It calls
`FactOfTheDay.choose_for_today()`. Run the consumer with `./run hueydev` (or
`./run dev`, which starts it alongside the other dev processes). The home page only
*reads* the pick via `current()`, so a dead consumer shows a stale-but-present fact
(or an empty state before the first run) rather than writing on a `GET`.

## Seed command

```
./run djangomanage seedfacts
```

Creates 10 topics (cars, science, animals, geography, history, space, food,
sports, music, technology) x 20 facts = 200 rows, audit-logged. `--keep` skips
the clear-first step.

## Routes

- `GET /` (home) → Inertia page `ours/Home`, props include
  `fact_of_day: FactOut | null` (the current pick, plus login state).
- `GET /facts` → Inertia page `ours/FactsPage`, props `{ fact: FactOut | null, topics: TopicOut[] }`.
  Re-draws (random) on every request.
- `GET /facts/<slug>` → Inertia page `ours/FactTopicPage`, props
  `{ topic: TopicOut, fact: FactOut | null, topics: TopicOut[] }`. Missing topic → 404.
- `GET /fact/<public_id>` → Inertia page `ours/FactPage`, props
  `{ fact: FactOut, topics: TopicOut[] }`. A stable permalink to one fact
  (deterministic, unlike the random draws); missing fact → 404.

## Files

- Model: `models/facts.py`. Command: `management/commands/seedfacts.py` (the seed
  `FACTS` data is inlined at the top). Task: `tasks/facts.py` (under the
  `tasks/` package; re-exported from `tasks/__init__.py` for djhuey autodiscovery).
- View: `views/facts.py` (`/facts`, `/facts/<slug>`, `/fact/<public_id>`); the
  daily fact is added to the home page in `views/home.py`.
- Frontend: `frontend/src/ours/pages/{Home,FactsPage,FactTopicPage,FactPage}.vue`,
  schema in `ours/schemas.ts` (`fact_of_day` on the Home props).
- Tests: `tests/test_home_views.py` (daily fact on home), `tests/test_facts_models.py`,
  `tests/test_facts_views.py`, `tests/test_facts_commands.py`,
  `tests/test_facts_tasks.py`, `tests/test_facts_playwright.py`.
