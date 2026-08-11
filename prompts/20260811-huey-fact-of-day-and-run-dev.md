# Huey cron + Fact-of-the-Day example + `./run dev` multiplexer

> ## As-built note (2026-08-11)
> Built, then **diverged from the plan below** during review. Trust this note
> where it and the plan differ.
> - The facts feature (`Topic`/`Fact`/**`FactOfTheDay`** + daily cron +
>   `seedfacts`) lives in **`docs/reference/` only** — the copyable example. The
>   live `ourapp/` is the **placeholder** (home only), per the repo's "example in
>   reference, real app in `ourapp/`" split.
> - The daily Fact of the Day is shown on the **Home page** (`/`), not a dedicated
>   route. `/facts` + `/facts/<slug>` are the secondary browsing pages; there is
>   no `FactOfDayPage.vue` and no param-less `/fact` FOTD route. (Later addition:
>   `GET /fact/<public_id>` is a per-fact **permalink** detail page — `FactPage.vue`
>   — distinct from the dropped dedicated FOTD route.)
> - The `./run hueydev` helper is **`./run hueydev`** — dev-only (foreground). Prod
>   must run the Huey consumer as a managed service, not via this helper.
> - `HUEY["immediate"]` is **`False`** (not `DEBUG`): the consumer refuses to
>   start when immediate is enabled, and tests use `task.call_local()` anyway.
> - `concurrently` 9.x is installed in `frontend/`; `./run dev` was verified (four
>   color-coded processes; an opencode refusal doesn't kill the rest).

## Goal
Bring in **Huey** (Redis-backed) as the framework for background tasks + cron, ship
a real **example feature in `ourapp/`** — a daily "Fact of the Day" chosen by a
Huey cron task and shown at a fixed URL (`/fact`) — and add one `./run dev`
command that runs the four dev processes (runserver, vite watch, opencode, huey)
in one terminal with color-coded interleaved output via **`concurrently`**.

- Huey integrated through `huey.contrib.djhuey`, reusing the existing Redis.
- `Topic` + `Fact` (lifted from the reference example) become the pick pool; a new
  `FactOfTheDay` model persists one pick per local date.
- A daily `@db_periodic_task(crontab(hour=0, minute=0))` chooses today's fact;
  `GET /fact` reads the stored pick (fixed for the whole day).
- `./run dev` = `concurrently -n runserver,vite,opencode,huey -c …`; Ctrl-C stops all.

## Current state (analysis done 2026-08-11)

### No task runner exists yet
- `huey` / `celery` / `rq` appear **nowhere** in code or deps. `huey` is mentioned
  only in `TODO.md:6` (+ scratch worktree copies). `pyproject.toml:6-21`
  dependencies have no task-runner.
- `run:362-369` dispatches `./run <func>` via `declare -F`; there is **no `dev`
  and no `huey` subcommand** today. Existing wrappers: `runserver` (`run:42-45`),
  `opencode` (`run:47-176`, with its own preflight), `python`/`djangomanage`
  passthroughs (`run:11-18`).

### Redis is already a hard dependency — reuse it for Huey
- `redis>=5.0` is in `pyproject.toml:19`.
- `djangoapp/views/client_errors.py:21,35-36` builds a client from `REDIS_URL`
  (default `redis://127.0.0.1:6379/0`); `.env.example` documents `REDIS_URL` and
  states redis is a hard dependency (fails closed).
- → Huey's `RedisHuey` backend can point at the same `REDIS_URL`. **No new infra.**

### `ourapp/` is the placeholder
- `ourapp/models/__init__.py` ships **no models** (docstring: "placeholder … add
  the first one in its own module").
- `ourapp/views/__init__.py:17` registers only `home.router`; `ourapp/views/home.py`
  is the only view. `ourapp/tests/` has only `test_home_views.py` +
  `test_home_playwright.py`. **No `ourapp/management/` dir yet.**
- `ourapp/README.md:8`: "ships only the landing page".

### The reference facts feature is the copyable base
- `docs/reference/ourapp/models/facts.py` — `Topic` + `FactManager.random()`
  (`order_by("?").first()`, Postgres `RANDOM()`) + `Fact`.
- `docs/reference/ourapp/views/facts.py:63-98` — `GET /facts` and
  `GET /facts/{slug}`, both **random per visit** (`Fact.objects.random()` on every
  request → changes on reload).
- `docs/reference/ourapp/management/commands/seedfacts.py` — 10 topics × 20 facts
  = 200 rows, audit-logged via `save_with_logs`, idempotent (`--keep`).
- `docs/reference/frontend/src/ours/pages/{FactsPage,FactTopicPage}.vue` +
  `docs/reference/frontend/src/ours/schemas.ts` (Topic/Fact/FactsPage schemas).
- These are excluded from ruff/mypy (`pyproject.toml:48` and `:111`), so lifting
  them into `ourapp/` is what makes them "real".
- **Random-per-visit ≠ the goal.** A fixed daily pick needs a **new** persistence
  model (`FactOfTheDay`) + a cron — not a reuse of the random view.

### Wiring points
- `djangoproject/settings.py`: `INSTALLED_APPS` (`:45-63`), `DEBUG` (`:29`),
  `TIME_ZONE` (`:144`), `USE_TZ=True` (`:148`). No `HUEY` setting.
- `djangoapp/models/base.py:355` — `BaseModel` (`public_id`, audit fields,
  `save_with_logs`/`delete_with_logs`, `get_absolute_url()`).
- `ourapp/tests/test_home_views.py` — the `InertiaTestCase` pattern (props nested
  under `props`, pk-free asserts).
- `frontend/package.json` scripts: `dev` = `vite build --mode development --watch`
  (a long-running watcher; Django serves the built bundle from
  `djangoapp/static/`). `npm-run-all` is already a devDep → adding `concurrently`
  fits the existing npm-tooling pattern.
- Multiplexer availability: `tmux` **not** installed; `screen` at `/usr/bin/screen`.
  Locked decision is `concurrently` anyway (npm-native, interleaved color output).
- `agentconfig/steer.md`: "Checklist — adding or changing a feature" (`:201`),
  "Checklist — every view" (`:250`), Logging/Frontend sections — but **no
  background-tasks section**. `TODO.md:11-17` is the stub ("Teach steer … Cron and
  huey").

## Decisions (locked)
- **Multiplexer = `concurrently` (npm)**, not `screen`/`tmux`. Interleaved,
  color-prefixed output; Ctrl-C stops all four. No windows/panes, no `--kill-others-on-fail`
  (an `opencode` preflight refusal must not tear down runserver/vite/huey).
- **Huey backend = `RedisHuey`**, reusing `REDIS_URL`. Redis stays a documented
  prerequisite; **not** auto-started in `./run dev`.
- **Integration = `huey.contrib.djhuey`** (auto-discovers each installed app's
  `tasks.py`); consumer runs via djhuey's `manage.py runhuey`.
- **`/fact` is fixed for the whole local day**, not random per visit. The view
  get-or-creates today's pick if missing (resilient first visit / consumer down);
  the cron is the scheduled chooser and the Huey demonstrator.
- **Cron = local midnight** (`crontab(hour=0, minute=0)`, `HUEY["utc"]=False`);
  "today" via `django.utils.timezone.localdate()` (respects `TIME_ZONE`,
  `USE_TZ=True`).
- **`FactOfTheDay.fact` = `on_delete=SET_NULL`** (not RESTRICT/CASCADE) so
  re-seeding (`seedfacts` deletes all facts first) never blocks and never wipes
  date rows.
- **All task logic on the model** (`FactOfTheDay` classmethods). The huey task is
  a one-line wrapper. Tests call the classmethod / `task.call_local()` — no
  consumer needed.
- **`FactOfTheDay` writes are direct ORM** (`update_or_create`), intentional
  system/cron writes (no human actor; daily picks aren't worth audit-log noise).
- **`/fact` is the headline; `/facts` + `/facts/<slug>` (random per visit) ship
  too** — they share the models and are lifted from the reference.

## Phased checklist

### Phase 1 — Huey framework integration
- [ ] `pyproject.toml` — add `"huey>=2.5",  # Redis-backed background tasks + cron`
      to `[project] dependencies`.
- [ ] `djangoproject/settings.py` — add `"huey.contrib.djhuey"` to `INSTALLED_APPS`
      (`:45-63`).
- [ ] `djangoproject/settings.py` — add a `HUEY` block (after the logging section):
      ```python
      # Huey — Redis-backed background tasks + cron. Reuses REDIS_URL (shared with
      # the client-error rate limiter). `immediate: DEBUG` runs enqueued tasks
      # inline in dev/test (no consumer needed for .enqueue()); periodic tasks
      # still need the consumer (./run hueydev) — the view's get-or-create covers a
      # cold first visit. `utc: False` so crontab times are local TIME_ZONE.
      HUEY = {
          "huey_class": "huey.RedisHuey",
          "name": "instant",
          "results": False,
          "store_none": False,
          "immediate": DEBUG,
          "utc": False,
          "connection": {"url": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")},
      }
      ```
- [ ] `pyproject.toml` mypy — add a per-module override mirroring allauth
      (`disallow_any_unimported` under strict; huey ships no py.typed):
      ```toml
      [[tool.mypy.overrides]]
      module = ["huey.*"]
      ignore_missing_imports = true
      ```
- [ ] `.env.example` — extend the `REDIS_URL` comment to note it is also used by
      Huey. No new var.

### Phase 2 — Facts models (`ourapp/models/facts.py`)
- [ ] Copy `docs/reference/ourapp/models/facts.py` verbatim (`Topic`,
      `FactManager.random()`, `Fact`).
- [ ] Add `from django.utils import timezone`.
- [ ] Add `FactOfTheDay(BaseModel)`:
      - [ ] `date = models.DateField(unique=True)`
      - [ ] `fact = models.ForeignKey(Fact, on_delete=models.SET_NULL, null=True, blank=True, related_name="daily_picks")`
      - [ ] `Meta.ordering = ["-date"]`, `__str__` → `"<date>: <fact text[:60] or —>"`
      - [ ] `@classmethod for_today() -> FactOfTheDay | None` —
            `today = timezone.localdate()`; return today's row if it exists
            (`.filter(date=today).select_related("fact").first()`), else call
            `choose_for_today()`; None only when the pool is empty.
      - [ ] `@classmethod choose_for_today() -> FactOfTheDay | None` —
            `fact = Fact.objects.random()`; None if empty; `update_or_create(date=today, defaults={"fact": fact})`
            (direct ORM — system write; inline-justify in a comment).
- [ ] `ourapp/models/__init__.py` — replace the placeholder docstring body with:
      ```python
      from ourapp.models.facts import Fact, FactOfTheDay, Topic
      __all__ = ["Fact", "FactOfTheDay", "Topic"]
      ```

### Phase 3 — Huey task (`ourapp/tasks.py`, new)
- [ ] Create `ourapp/tasks.py`:
      ```python
      """Huey background + periodic tasks for this app.

      Huey is enabled framework-wide via ``huey.contrib.djhuey`` (settings.HUEY);
      this module is auto-discovered. Keep task bodies thin — put logic on the
      model and call it here, so tests exercise the model directly (or
      ``task.call_local()``) without a running consumer.
      """
      from __future__ import annotations
      from huey.contrib.djhuey import crontab, db_periodic_task
      from ourapp.models import FactOfTheDay


      @db_periodic_task(crontab(hour=0, minute=0))
      def choose_fact_of_the_day() -> None:
          """Daily cron (local midnight): pick one random fact as today's pick."""
          FactOfTheDay.choose_for_today()
      ```
- [ ] If `disallow_any_decorated` errors on `@db_periodic_task`, add a targeted
      `# type: ignore[...]` on that decorator line only — do not loosen global config.

### Phase 4 — Views (`ourapp/views/facts.py`)
- [ ] Copy `docs/reference/ourapp/views/facts.py` (schemas `TopicOutSchema`/
      `FactOutSchema`, helpers `_topic_out`/`_fact_out`/`_all_topics`/
      `_topic_or_404`, `GET /facts`, `GET /facts/{slug}`).
- [ ] Add `FactOfTheDay` to the `from ourapp.models import …` line.
- [ ] Add `from djangoapp.logging import get_logger` + a `logger.info(...)`.
- [ ] Add the `GET /fact` endpoint:
      ```python
      @router.get("/fact", response=None)
      def fact_of_the_day_page(request: HttpRequest) -> InertiaResponse:
          """Today's fixed Fact of the Day (component ``ours/FactOfDayPage``).

          ``FactOfTheDay.for_today()`` get-or-creates today's pick, so the same
          fact shows to every visitor for the whole local day (and the page is
          never empty even before the consumer has run). Empty pool → ``fact=None``.
          """
          daily = FactOfTheDay.for_today()
          return InertiaResponse(
              request,
              "ours/FactOfDayPage",
              {
                  "props": {
                      "fact": _fact_out(daily.fact).model_dump() if daily and daily.fact else None,
                      "topics": [t.model_dump() for t in _all_topics()],
                  },
              },
          )
      ```
- [ ] `ourapp/views/__init__.py:17` — register the router:
      ```python
      from ourapp.views import facts, home
      api.add_router("/", home.router)
      api.add_router("/", facts.router)
      ```

### Phase 5 — Seed command + migration
- [ ] Create `ourapp/management/__init__.py` + `ourapp/management/commands/__init__.py`
      (empty — first command in the app).
- [ ] Copy `docs/reference/ourapp/management/commands/seedfacts.py` verbatim into
      `ourapp/management/commands/seedfacts.py`.
- [ ] `./run djangomanage makemigrations ourapp` → `ourapp/migrations/0001_initial.py`
      (Topic, Fact, FactOfTheDay).
- [ ] Inspect it: `FactOfTheDay.date` is `unique=True`; `fact` FK is
      `SET_NULL, null=True`.

### Phase 6 — Frontend (`frontend/src/ours/`)
- [ ] `schemas.ts` — merge the reference's `TopicSchema`, `FactSchema`,
      `FactsPagePropsSchema`, `FactTopicPagePropsSchema` (keep `HomePropsSchema`);
      add `FactOfDayPagePropsSchema = z.object({ fact: FactSchema.nullable(), topics: TopicSchema.array() })`.
- [ ] `pages/FactsPage.vue` + `pages/FactTopicPage.vue` — copy from reference; add
      `<PageTitle :value="..."/>` (import `../../components/PageTitle.vue`) — steer
      requires it on every Inertia page.
- [ ] `pages/FactOfDayPage.vue` (new) — component `ours/FactOfDayPage`, schema
      `FactOfDayPagePropsSchema`; heading "Fact of the Day"; render `fact.text` +
      topic link to `/facts/<slug>`; empty-pool hint ("run seedfacts"); link to
      `/facts`; render the topics list; `<PageTitle value="Fact of the Day" />`;
      `import "../style.scss"`.
- [ ] `style.scss` — append the reference's facts styles (`.ours-facts-page`,
      `.ours-fact-text`, `.ours-topics-list`).
- [ ] `pages/Home.vue` — add nav links to `/fact` (Fact of the Day) and `/facts`
      (Random Fact); facts is public → show to everyone (authed or not).

### Phase 7 — Tests (`ourapp/tests/`, flat; docstring per steer)
- [ ] `test_facts_models.py` — `Fact.objects.random()` None on empty / returns a
      `Fact` when seeded; `Topic.random_fact()` scopes to topic; `for_today()`
      creates+returns today's row and is idempotent (2nd call → same row+fact);
      `for_today()`/`choose_for_today()` return None on empty pool;
      `choose_for_today()` upserts (re-call same date updates `fact`, no dup row).
- [ ] `test_facts_views.py` (`InertiaTestCase`, like `test_home_views.py`):
      - [ ] `GET /fact` → component `ours/FactOfDayPage`; **two GETs return the
            same `fact.public_id`** (fixed for the day); props pk-free (no `id`/`pk`);
            empty pool → `fact=None` and still 200.
      - [ ] `GET /facts` → `ours/FactsPage`, 200, pk-free.
      - [ ] `GET /facts/<slug>` → `ours/FactTopicPage`, 200; missing slug → 404.
      - [ ] Seed minimal data in `setUp` (1 topic + a few facts) — not the 200-row seed.
- [ ] `test_facts_commands.py` — `seedfacts` creates 10 topics + 200 facts,
      audit-logged (`created` `BaseModelUpdateLog` rows exist); idempotent (still
      200/10); `--keep` appends facts without duplicating topics.
- [ ] `test_facts_tasks.py` — `ourapp.tasks.choose_fact_of_the_day.call_local()`
      (huey: runs the wrapped fn immediately, bypassing the queue) creates today's
      `FactOfTheDay` row pointing at a real `Fact`; idempotent (no dup date row);
      assert the task is importable/registered — no consumer needed.
- [ ] `test_facts_playwright.py` — subclass `BasePlaywrightTestCase` (tagged
      `playwright`); `GET /fact` end-to-end shows the seeded fact's text in a real
      browser (mirror `test_home_playwright.py`).

### Phase 8 — `run` script (`huey` + `dev`) + package.json
- [ ] `frontend/package.json` — add `"concurrently": "^9.0.0"` to `devDependencies`.
- [ ] `run` — add a `hueydev()` wrapper:
      ```bash
      hueydev() {
        # Huey consumer (djhuey's runhuey). Auto-discovers each installed app's
        # tasks.py (ourapp.tasks). Redis must be running (REDIS_URL).
        setenv
        djangomanage runhuey "$@"
      }
      ```
- [ ] `run` — add a `dev()` wrapper:
      ```bash
      dev() {
        # Run the whole dev stack in one terminal via `concurrently` (color-coded,
        # interleaved output). Ctrl-C stops all four. Idempotent: kills any stale
        # session first.
        setenv
        local repo_root
        repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local bin="$repo_root/frontend/node_modules/.bin/concurrently"
        if [ ! -x "$bin" ]; then
          echo "concurrently not found at $bin." >&2
          echo "Run ./run init first (or: cd frontend && npm install)." >&2
          return 1
        fi
        pkill -f "concurrently.*-n runserver,vite,opencode,huey" 2>/dev/null || true
        cd "$repo_root"
        "$bin" -n runserver,vite,opencode,huey -c blue,green,magenta,cyan \
          "./run runserver" \
          "cd frontend && npm run dev" \
          "./run opencode" \
          "./run hueydev"
      }
      ```
- [ ] No change to the bottom dispatcher (`run:362-369`) — it already routes
      `./run dev` and `./run hueydev`.

### Phase 9 — Documentation
- [ ] `README.md` — add **"Quick start"** near the top (after the intro, before
      "Google OAuth"): prerequisites (Python 3.14+ + `uv`, Node.js + npm,
      PostgreSQL, Redis; `opencode` only for the in-app agent chat; `screen` not
      required); one-time `./run init`; optional `./run djangomanage seedfacts`;
      `./run dev` runs all four with color-prefixed output, Ctrl-C stops all;
      http://127.0.0.1:8000/ ; visit `/fact` for the Fact of the Day.
- [ ] `ourapp/README.md` — add the **facts** feature (what it does, URLs `/fact`,
      `/facts`, `/facts/<slug>`, the daily cron, `seedfacts`); link `docs/facts.md`.
- [ ] `ourapp/docs/facts.md` (new) — catalog: models (Topic, Fact, FactOfTheDay),
      endpoints, pages, `seedfacts`, the Huey daily cron, data shapes, files.
- [ ] `agentconfig/steer.md` — add a **"Background tasks (Huey)"** subsection:
      framework-enabled (djhuey, RedisHuey via `REDIS_URL`); add tasks in
      `ourapp/tasks.py` with `@db_task` / `@db_periodic_task(crontab(...))`; keep
      logic on the model; run the consumer via `./run hueydev` or `./run dev`; Redis
      required; tests call the model method or `task.call_local()`. Reference the
      fact-of-the-day cron as the example. (Resolves `TODO.md:11-17`.)
- [ ] `TODO.md` — remove the now-done block (`TODO.md:6-9`) and the
      "Teach steer … Cron and huey" stub (`TODO.md:11-17`).

### Phase 10 — Validate (must be green before `mergescratch`)
In `scratch/`:
- [ ] `./run lintfix` (ruff format + check --fix --unsafe-fixes; eslint --fix)
- [ ] `./run typecheck` (`mypy .` strict — add the huey override / targeted
      `type: ignore` as noted)
- [ ] `./run checkscratch` (ruff + mypy + ourapp tests + frontend lint/type-check/build)
- [ ] `./run djangomanage makemigrations --check --dry-run` (migrations clean/complete)
In `main/` (full gate):
- [ ] `./run checkall` (incl. whole backend suite + Playwright)
Spot-checks:
- [ ] `GET /fact` shows the same fact across two requests (fixed for the day).
- [ ] `./run hueydev` starts the consumer (Redis running); `choose_fact_of_the_day`
      appears in its task list.
- [ ] `./run dev` runs all four with colored prefixes; Ctrl-C exits cleanly.
- [ ] New `test_facts_*` pass; existing `test_home_*` still pass.

## Out of scope
- Redis auto-start / a 5th mux window (Redis stays a prerequisite).
- `--kill-others-on-fail`, restart-on-crash, or log files.
- Inertia v3, Django 6.1 fetch modes, GitPython stubs (other `TODO.md` items).
- Production deployment / opencode-as-service.
