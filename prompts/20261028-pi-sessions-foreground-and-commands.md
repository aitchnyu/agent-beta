# Oct 28 sessions — foreground coding, user commands, prewarm retirement

Built 2026-10-28 from the three fresh-VM sessions (15:14–18:00 IST):
groundwork, the DocsGate-freeze session, and the 1h42m chores run.
This file records the findings, the agreed changes, and the open
questions resolved with the operator one at a time.

## What the sessions showed

- **The silent hour.** Stage-3 coding ran as a background subagent
  11:30→12:30 with zero output to the operator, who asked "is chores
  agent stuck" at the exact minute it finished (3579s, 152 tool uses,
  453.7k tokens). The operator wants to watch coding progress live.
- **The reviewer round never ran.** The one-turn [3]→[5] rule was
  violated: code → deploy → e2e happened, then verification dumps — no
  reviewer consumption, no fix round, no CommitOffer. The feature
  shipped unreviewed within the session.
- **Prewarms rotted.** Three reviewers prewarmed 11:21, maps done by
  11:23 (~90KB), consumed never — ~70 minutes idle guarantees the
  pi-subagents retention window expires them. Prewarm cost was paid
  for nothing, twice over (Oct 26 had the same failure).
- **Python hand-rolls for user ops.** Sessions listed users via
  `./run python -c "from djangoapp.models import User; for u in …"`
  (groundwork session AND the coder). Each was a permission prompt
  (~13 python-probe asks today) and the operator had to approve/nag.
- **createuser friction.** Email-first positional; first-user-must-be-
  superuser surprise → CommandError → retry with --superuser; login
  link printed once and lost in later subagent output dumps.
- **Where the hour actually went** (coder transcript): ~12m reading
  docs/reference → ~15m models+tests → 3m fail-fix loop (the fast
  test path WORKED: five scoped runs in 42s) → **~10m python probe
  storm** (django.setup boilerplate, ninja-router introspection
  `api.urls`, reading `inertia/test.py` from site-packages) → ~10m
  deploys + mockup graduation → 3m migration delete/recreate churn.
  No single stall — probe friction + router/inertia unfamiliarity is
  the biggest compressible chunk.
- **Info dumping buried the important bits.** Prewarm confirmations,
  FinalReport, and verification output scrolled the operator's
  terminal; the login link and gate menus got lost mid-scroll.

## Agreed changes

1. **`createuser` signature → `createuser <first> <last> <email>
   [--superuser]`** (first user auto-hint stays). Callers updated
   (gate.sh, README, docs).
2. **New `listusers` command** — table of first, last, email, staff,
   superuser; `--page N`, 100 rows/page default. Allowlisted.
3. **Management-command inventory in steer.md, kept in sync** —
   a unit test enumerates `djangoapp/management/commands/` and
   asserts every command appears in steer's inventory section, so
   sessions can never not-know.
4. **Script-proposal rules in steer.md** — any proposed script
   carries a top comment explaining intent, section comments (double
   for write operations), and readable variable names.
5. **Stage coding runs FOREGROUND** — the stage subagent is spawned
   blocking (not run-in-background): the operator watches its output
   live for the hour; main resumes only at the FinalReport. Context
   isolation is kept; visibility is restored.
6. **Reviewer round is restructured** (per operator Q&A): see the
   resolution recorded below once settled — prewarm retires or moves.
7. **Permission-tax trims** — allowlist the read-only djangomanage
   inventory commands (listusers, makeloginlink) so user ops never
   prompt; python-probe needs shrink accordingly.

## Proposed (needs operator decision, asked one at a time)

- **Auto-compact between stages** — pi extension sketch: after each
  stage gate (MockupGate/DocsGate/CommitOffer), rewrite the main
  transcript in place — collapse the finished stage's messages into
  one compact handoff note (decisions, summaries, open items), keep
  operator turns verbatim. Main context stays bounded without
  launcher restarts or operator copy-paste.
- **Coding-structure simplification** — evidence of ninja-router +
  inertia test-helper friction (probe storm, site-packages reading).
  Options: a chores-style copy-me reference that includes router URL
  introspection and inertia test idioms; or a thinner view convention
  the agent completes faster.

## Questions log

1. **Reviewers** — ANSWERED: a reviewer-manager pi extension owns
   reviewer lifetimes. It spawns the three reviewers at docs-stage
   entry, sends keepalive resumes itself on a timer (the main agent
   cannot be trusted to ping while blocked on the coder — operator's
   own catch), and exposes a reviewers() status tool. Prewarm survives
   the coding hour; round 2 resumes warm context. (pi core has no
   retention setting to raise — verified in the installed package.)
2. **Operator preferences stated alongside**: full live progress for
   the coding hour; a compact TOOL the agent can call between stages
   (the auto-compact sketch becomes an extension-provided tool, not a
   hook).
3. **Coding stage** — ANSWERED: **main codes directly** (Oct 26
   style). The stage-subagent rule is reverted from steer's Feature
   workflow [3]; the compact tool becomes the context control (main
   calls it between batches/stages); reviewer keepalive stays with
   the extension (main is busy coding). Full raw visibility wins over
   isolation.
4. **Router/inertia structure** — ANSWERED: all three. (a) A
   chores-style copy-me trio under docs/reference/ demonstrating the
   recurring idioms (ninja Router mounting + URL names for APIs,
   inertia props shape, inertia test helper usage); (b) a view/router
   SHAPE CHECKLIST in steer.md; (c) **drop the ninja Router for page
   routes** — page endpoints become plain Django views returning
   inertia responses, ninja Router stays for JSON APIs only. Simpler
   patterns the agent completes fast.
5. **Permission trims** — ANSWERED: allowlist `./run typecheck*`,
   `./run djangomanage listusers*`, `makeloginlink*`, and
   `./run screenshots <label>`. `python -c` stays ask-only (the
   standing no-arbitrary-python rule holds).
6. **Login link** — ANSWERED: hint only. createuser's output ends
   with "login link: ./run djangomanage makeloginlink <email>";
   makeloginlink stays separate (no unprompted secret printing).

## Implementation checklist

1. `createuser <first> <last> <email> [--superuser]` — signature
   change, first-user-superuser hint kept, login-link hint line; all
   callers updated (gate.sh, README, docs).
2. `listusers` — first/last/email/staff/superuser table, `--page N`,
   100 rows default; allowlisted.
3. steer.md: management-command inventory section (+ unit test that
   syncs it against `djangoapp/management/commands/`); script-
   proposal rules (top comment, sectioned comments, readable names);
   view/router shape checklist; revert stage-subagent [3] → main
   codes directly; reviewer round spawns at FinalReport via the
   reviewer-manager extension.
4. Allowlist trims (item 5 above) in .pi permission config.
5. docs/reference/ chores-style copy-me trio (router-for-APIs +
   plain-view-pages + inertia test idioms) — rides the router
   refactor.
6. Router refactor: page endpoints → plain Django views returning
   inertia responses; ninja Router only for JSON APIs (ourapp home
   first, then any other page routes).
7. pi extensions: `compact` tool (agent-callable between stages;
   rewrite transcript to a handoff note) and reviewer-manager
   (spawn at docs entry, timed keepalive, reviewers() status tool).
8. d2 prompt-file prewarm convention updated to match item 3.
