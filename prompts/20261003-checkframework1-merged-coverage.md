# checkframework1: merged two-stage coverage (unit + Playwright)

## Goal

- Run **both checkframework1 test stages under coverage** — the unit pass
  (``--exclude-tag playwright``) and the Playwright pass (``--tag
  playwright``) — and **merge them into one report in ``main/``**:
  ``coverage combine`` → ``report -m`` (printed) → ``htmlcov/``.
- Source scope: ``--source=djangoapp,ourapp`` (the standalone ``run
  coverage`` measures ``djangoapp`` only). Playwright attribution measures
  e2e-only server paths for the first time.
- Follow-up (separate session): read the merged ``report -m``, add tests
  for the biggest gaps. TODO.md's "merge coverage from both stages" line;
  the two stages are the gate's own passes — **checkproject is untouched**.

## Decisions (settled with operator, 2026-10-03)

- Target is ``checkframework1``, not ``checkproject``; overlays are not
  measured (different code at the same ``scratch/ourapp/…`` paths would
  corrupt a merge — main's ``ourapp`` is fine: one tree).
- ``--parallel-mode`` both stages; ``combine`` after stage 2.
- Drop ``run coverage``'s ``--omit djangoapp/tests/test_playwright.py`` —
  stage 2 now executes that module.
- Playwright needs no subprocess plumbing: the suite runs on
  ``StaticLiveServerTestCase`` (``_base.py:153``) — in-process server,
  plain ``coverage run`` captures it.
- Report in ``main/``, no ``open`` (agent-run gate). Standalone
  ``./run coverage`` stays unit-only; it overwrites ``.coverage`` if run
  after a gate — accepted.
- ``RUN_PROJECT_TESTS`` stays unset (project tests remain checkproject's).
- Known trade: Playwright ~10–20% slower under instrumentation.

## Design

- ``run`` — ``checkframework1()``, order otherwise unchanged:
  - Stage 1 (replaces ``test --noinput``): ``uv run coverage run
    --parallel-mode --source=djangoapp,ourapp manage.py test
    $_DJANGO_NO_COLOR --exclude-tag playwright --noinput``
  - Stage 2 (replaces the ``playwrighttest`` call, inlined — that command
    stays bare for interactive use): frontend build (as ``playwrighttest``
    does) → same coverage run with ``--tag playwright --noinput``
  - Merge: ``uv run coverage combine`` → ``coverage report -m`` →
    ``coverage html``. Help line updated.
- ``.gitignore``: add ``.coverage.*`` and ``htmlcov/``.
- ``README.md``: checkframework1 bullet (~line 606) mentions the merged
  report.
- New framework tests go in ``djangoapp/tests/`` so the gate covers them.

## Follow-up plan — improve coverage (from the 2026-10-03 merged report)

**Principle: no per-file 100% targets.** Fix the high-value gaps; leave
one-line error branches untested when a test would only parrot the
branch. No number to hit — stop when the remaining misses are cheap
noise or by-design.

**P1 — huey task bodies — DONE 2026-10-03**
- ``djangoapp/tests/test_tasks.py`` + ``ourapp/tests/test_tasks.py``: run
  the tasks inline via huey 3.x's ``TaskWrapper.call_local()`` (NOT
  ``.call()`` — that's huey 2.x). ``deliver_push``: patched
  ``djangoapp.models.notify_sessions`` (the function-local import
  resolves it at call time) + missing-pk-raises; ``clear_expired_sessions``:
  expired session → CASCADE drops UserSessionIndex + PushSubscription,
  live chain survives. Both task modules now 100%; 288 unit tests (+4).

**Not reachable in the unit tier — ``djangoapp/models/base.py`` 65% (``save_plus``/``delete_plus`` audit machinery)**
- No concrete ``BaseModel`` exists in main: ``User`` is ``AbstractUser``;
  ``Notification``/``PushSubscription`` are plain models BY DESIGN (their
  module docstring says so); ``BaseModel`` is "abstract base for the
  concrete models in ourapp/" — which exist only under the testapp
  overlay. Covering it here would need a test-defined model with
  schema-editor table creation, against the repo's overlay architecture.
  Stays ``checkproject``-tier (``test_basemodel_*_project.py``). Corrected
  2026-10-03 — the earlier draft wrongly assumed User/Notification were
  BaseModels.

**P2 — selected error branches — DONE 2026-10-04 (batch 2)**
- 14 tests, all green: ``/mockup-todos`` superuser render + anon 404
  (``ourapp/views/home.py`` → 100%); git commit-id guards (non-hex view
  404 + direct ``diff_commit`` None paths, ``git_data.py`` → 96%, only
  defensive backstops left); ``/files/download`` missing-file 404 + image
  preview kind=image (``files.py`` → 99%); ninja ``PermissionDenied`` →
  fixed 403 JSON on a scratch API (``ninja_api.py`` → 98%); notification
  ``__str__`` ×2, zero-subscription → 0, fan-out crash containment
  (``models/notifications.py`` → 100%); client-errors ``_RATE_LIMIT=0``
  off-switch works with redis down; ``promotetosuperuser`` duplicate-email
  + ``makeloginlink`` DEBUG-derived origin (both commands → 100%).
  Gotchas found: huey needs ``call_local()``; Django forbids
  ``patch.object`` on reverse related descriptors (patch the manager
  class's ``get_queryset`` instead — ``Manager.all()`` returns
  ``get_queryset()`` itself).

**Remaining by design (do not chase — see Non-goals)**: ``base.py`` 65%
  and ``views/manage.py`` 62% (overlay-tier), ``files.py`` 209/221 and
  ``git_data.py`` 95-96/127-128 (defensive backstops the 404 tests reach
  via earlier raises), ``client_errors.py`` 40-41 (import-time),
  ``ninja_api.py`` 139 (debug repr), ``views/notifications.py`` 246
  (session backstop), ``*_project.py`` / screenshots self-skips,
  migrations, playwright harness internals.

**Non-goals (by design — do not chase in the unit tier)**
- ``views/manage.py`` deep flows (248-269, 346-371, 386-414) and
  ``base.py`` FileField cleanup: exercised only against the testapp
  overlay — that's ``checkproject``'s ``test_manage_project.py`` /
  ``test_basemodel_*_project.py`` territory.
- ``*_project.py`` test bodies (22–31%) and ``test_screenshots.py`` (32%):
  they self-skip without ``RUN_PROJECT_TESTS`` / ``GENERATE_SCREENSHOTS``.
- Migrations' untested branches.
- Optional (operator decision): make the headline % product-only by
  omitting ``djangoapp/tests/**``, ``ourapp/tests/**``, and migrations
  in a shared coverage config — changes ``run coverage`` too, so it
  needs its own approval.

**Verification per batch:** ``./run checkframework1`` green; spot-check
the targeted files' rows in the report; keep new tests in the repo's
test conventions (``djangoapp/tests/test_test_conventions.py`` enforces
them).

## Batch 3 — checkproject merged into checkframework1 (2026-10-04, operator-approved)

**checkproject is DELETED.** Its two scratch cycles are now the gate's
stages 3-4, under coverage:

- Stage 3 (project tier): ``create_new_scratch`` + testapp overlay →
  ``./run typecheck`` (read-only; lint stays in main — no ``lintfix`` in
  scratch, which would rewrite files and corrupt merged line data) →
  ``RUN_PROJECT_TESTS=1 coverage run --parallel-mode
  --source=djangoapp`` + ``--exclude-tag playwright``.
- Stage 4 (reference tier): ``create_new_scratch`` + docs/reference overlay
  (+ its Vue pages) → npm build → ``./run test --noinput ourapp``
  (playwright tag excluded by ``./run test``). NOT under coverage —
  operator correction: the reference app is validated FOR ITS OWN SAKE;
  only the testapp (stage 3) contributes scratch coverage.
- Fragments staged to ``.coverage-stage/`` (gitignored) between
  ``create_new_scratch`` wipes; final ``coverage combine . .coverage-stage``
  folds the testapp scratch's djangoapp onto main's via new
  ``[tool.coverage.paths]`` in pyproject ("Combined 3, skipped 2").
- Result: **TOTAL 91% → 97%** (530 → 154 missed — identical with or
  without stage-4 measurement, confirming it was immaterial).
  ``base.py`` 65→97, ``manage.py`` 62→94, all ``*_project.py`` test
  files 22-31→100.
- All checkproject references updated: help, README, steer.md, pi
  allowlist (→ ``./run checkframework1``), test docstrings, testapp/
  reference READMEs. Historical prompts/ left as-is.

**Gotchas found:**
- The old ``./run test`` implicitly passes ``--exclude-tag playwright``;
  the inlined coverage invocations must too — without it, stage 4 ran
  the reference app's Playwright suite and exposed a LATENT FAILURE:
  ``ourapp.tests.test_downloads_playwright.DownloadsE2e`` (docs/
  reference) — its upload-row assertion never matched. That suite never
  ran under checkproject (tag-excluded) and is not exercised anywhere
  else; REPORTED, not fixed (out of scope — needs its own decision).
- Remaining misses after the merge (44 statements): playwright/_base
  harness internals, defensive backstops (``base.py`` 11,
  ``manage.py`` 9, ``git_data.py`` 4, ``files.py`` 2), migration 0007
  rollback, import-time branches — all accepted.
- ``test_screenshots.py`` is OMITTED from coverage entirely
  (``[tool.coverage.run]``/``[tool.coverage.report]`` omit in
  pyproject) — it self-skips in every measured run (GENERATE_SCREENSHOTS
  is only set by ``./run screenshots``), so its row was permanent noise.
  TOTAL: **99%**.

## aihere sweep (2026-10-04, addressed same day)

- [x] ``run`` — "split up the part of comment below, its a huge
      unreadable mass": the 8-line block above ``checkframework1`` was
      split into per-spot comments (stage-3 fixture/source note, the
      no-lintfix-in-scratch note at ``./run typecheck``, fragment-staging
      note at the ``mv``, scratch-kept-on-failure at ``rm -rf``, and the
      paths-fold/``run coverage`` note at ``combine``).
- [x] ``pyproject.toml`` — "halve this comment": the
      ``[tool.coverage.paths]`` comment went 8 lines → 3.

## Review fixes + aihere sweep #2 (2026-10-04)

Three-agent review of the squashed commit found the follow-ups below;
all fixed together with the second aihere sweep.

**Gate/run fixes**
- ``checkframework1`` now refuses scratch's own ./run
  (``_require_main_run``) AND the VM (``/etc/credentials/desmo/.env.vm``
  marker — the VM runs checkframework2 instead).
- Stale-fragment hygiene: the gate clears main's ``.coverage.*`` strays at
  start (an aborted run's fragments previously folded into the next
  combine with stale line data), and ``_SCRATCH_EXCLUDES`` gained
  ``.coverage*`` / ``.coverage-stage/`` / ``htmlcov/`` so artifacts never
  round-trip through scratch.
- ``./run coverage`` dropped its bogus CLI ``--omit`` (nonexistent path,
  and CLI omit OVERRIDES the pyproject omit — silently re-including
  test_screenshots); the pyproject omits now govern both commands.
- help() lists checkframework1.

**aihere (second sweep)**
- [x] ``test_notifications.py`` — "no need to test __str__ method": both
      ``__str__`` tests deleted; class renamed DispatchEdgeTests; the
      zero-subscription test now pins the configured branch explicitly
      (``vapid_subject() == "root@example.com"``) instead of the vacuous
      either-branch-returns-0 axis.
- [x] ``test_client_errors.py`` — "dont allow 0 rate limit in first
      place": client_errors.py no longer honors ``CLIENT_ERROR_RATE_LIMIT
      <= 0`` as unlimited — invalid values (unparseable or <= 0) fall
      back to the 30/min default; the disabled-limit branch in
      ``_rate_limited`` and its test are gone.
- [x] README — "split into points": the deployscratch bullet split into
      sub-points; "Four tiers:" → "Three tiers:" (checkproject bullet was
      already gone); "a fifth Playwright pass" → fourth.

**Other review findings fixed**
- The standalone ``./run coverage`` command was REMOVED (operator
  decision, 2026-10-04): the gate owns the only report now — the quick
  unit loop was stage-1-only, understated the merged number, and
  overwrote the merged ``.coverage``. Help/README references dropped.
- TODO.md stale "run all tests in checkproject" line removed (this work
  completed it).
- docs/social-login.md: the lintfix-mangled tuple element
  ``("allauth...google",)`` restored to the plain string.
- Test nits: ``-> None`` + docstring on the PermissionDenied test; its
  assert compares the literal friendly text (not the private
  ``_FORBIDDEN`` — a message regression now fails the test); both
  test_tasks docstrings de-duplicated (the stale ``.call()`` sentence
  removed — huey's ``call_local()`` is the inline one); /mockup-todos
  gained the logged-in-non-superuser 404 test its docstring claimed;
  steer.md's gate parenthetical mentions all four tiers.

## Checklist

- [x] ``run``: two-stage coverage + merge in ``checkframework1``; help line
- [x] ``.gitignore``: ``.coverage.*`` + ``htmlcov/``
- [x] ``README.md``: checkframework1 bullet
- [x] ``bash -n run``; ``git diff`` review
- [x] ``./run checkframework1`` green end-to-end (unit 284 OK + Playwright
      70 OK; ``combine`` merged 2 files; ``report -m`` 90% total over
      ``djangoapp`` + ``ourapp``; ``htmlcov/`` written). NB: the first run
      aborted at ruff format over drift the other in-flight session
      committed (``INSTRUCTIONS.md`` / ``agentconfig/steer.md`` /
      ``docs/social-login.md``) — fixed with ``./run lintfix``
      (operator-approved; format-only, nothing else touched).
- [x] Follow-up: huey tasks (batch 1) + selected error branches (batch 2)
      done — 90% → 91% total; both task modules, ``home.py``, both
      management commands, ``models/notifications.py``, ``views/git.py``
      at 100%. Remaining misses are by-design (see the P2 notes above).
