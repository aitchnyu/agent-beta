# Facts

Random trivia by topic, plus a daily **Fact of the Day** — a singleton row
the Huey cron rotates each local midnight, shown on the home page.

## Who can do what

```d2
direction: down
visitor: Anyone — no sign-in {shape: person}
facts: Facts pages {
  browse: Browse the list — a fresh draw {shape: oval}
  pick_topic: Open a topic {shape: oval}
  read_one: Read one fact — permalink {shape: oval}
}
visitor -> facts.browse
facts.pick_topic -> facts.browse: extend {style.stroke-dash: 3}
facts.read_one -> facts.pick_topic: extend {style.stroke-dash: 3}
note: Open to everyone — facts have no sign-in gate. {shape: text}
```

## The data

A **topic** groups facts ("cars", "science"); a **fact** is one piece of
trivia in that topic. The **Fact of the Day** is a singleton — exactly one
row, DB-enforced — whose `fact` is today's pick.

```d2
topic: Topic {
  shape: sql_table
  name: varchar
  slug: varchar {constraint: unique}
}
fact: Fact {
  shape: sql_table
  text: text
  topic_id: int
}
pick: FactOfTheDay {
  shape: sql_table
  fact_id: int
  singleton: smallint
}
fact.topic_id -> topic.id: groups · 1..N · RESTRICT
pick.fact_id -> fact.id: today's pick · 1..1 · SET_NULL
```

Reading the diagram: deleting a topic that has facts is refused
(`RESTRICT`); re-seeding facts never wipes the pick (`SET_NULL`). A `GET`
never writes — `FactOfTheDay.current()` is the read-only accessor views
use, and `choose_for_today()` is the only mutator.

## How the data changes

- **The daily rotation.** At local midnight the Huey task
  `choose_fact_of_the_day` calls `choose_for_today()`: pick one random
  fact, upsert the singleton, re-stamp `last_updated_at`. A dead consumer
  shows a stale-but-present fact rather than writing on a `GET`.
- **The seed.** `./run djangomanage seedfacts` creates 10 topics × 20
  facts (audit-logged); `--keep` skips the clear-first step.

## What you see

- The **home page** shows today's pick (or an empty state before the first
  cron run).
- **`/facts`** lists the facts (a fresh random draw per request) with the
  topics to browse.
- **`/facts/<slug>`** shows one topic's fact; **`/fact/<public_id>`** is a
  stable permalink to one fact (deterministic, unlike the random draws).

![The facts page — a fresh draw with the topics to browse](screenshots/facts.png)

## For developers

- Model: `models/facts.py`. Methods: `Topic.random_fact()`,
  `Fact.objects.random(topic=…)`, `FactOfTheDay.current()` /
  `choose_for_today()`.
- Cron: `tasks/facts.py` — `@db_periodic_task(crontab(hour=0, minute=0))`.
- Seed: `management/commands/seedfacts.py` (the `FACTS` data is inlined at
  the top).
- Views: `views/facts.py` (`/facts`, `/facts/<slug>`, `/fact/<public_id>`).
- Frontend: `ours/pages/{Home,FactsPage,FactTopicPage,FactPage}.vue` (each
  page declares its own props schema inline), shared `TopicSchema`/
  `FactSchema` in `ours/factsSchemas.ts`.
- Tests: `tests/test_facts_{models,views,commands,tasks,playwright}.py`,
  plus `tests/test_home_views.py` (the daily fact on home).
