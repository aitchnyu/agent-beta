# Oct 28 pi session — deep review: slowdowns, confusion, and the next structure

Built 2026-10-29 from the final transcript of session
`2026-10-28T15-56-15…` (15:56–18:09 UTC, 2h13m, $1.08, 486 events;
chores feature: mockups → docs → code → review ×2 → fixes → DB repair).
Every item below is timestamped session evidence. Questions for the
operator are asked one at a time; answers get recorded in the log at
the bottom.

## A. The slowdown ledger (ranked by minutes lost)

1. **Gate-poisoned DB → the migration-collision repair (~16 min,
   17:53–18:09).** `GET /chores` 500ed at the end: `django_migrations`
   carried a books-era `ourapp/0001_initial` row (a leftover of the
   gate's Books-overlay deploy + its backup/restore round-trip), so
   the session's own `0001_initial` was "already applied" — tables
   never created, every page 500. Diagnosis + repair needed FIVE
   `./run python -c` probes (django.setup() boilerplate each time,
   each one a permission prompt): introspect tables, inspect
   `django_migrations`, create tables, verify counts. The session
   fixed it correctly — but the landmine was OUR gate's leftovers.
   Fix in the plan: the gate must hand back a CLEAN desmo_db
   (drop/recreate/migrate at gate end), so no session inherits
   books-era migration rows.
2. **dbbackrest outage — self-inflicted by host-side me (~15 min,
   16:05–16:21).** First deploy failed in the backup tail (my earlier
   recursive chown had broken pgbackrest's repo ownership). The
   session diagnosed well but its tools weren't allowlisted:
   `sudo journalctl` asked once and blocked ~7 min; `./run backupdb`
   prompted at 16:13, 16:15, 16:17 (retries around my repair).
3. **Unmandated stage-2 reviewer round (~14 min, 16:43–16:54).**
   The session ran the FULL trio over the design doc ("you are
   reviewing a DESIGN DOC — no backend code exists yet") before any
   code existed. The workflow says prewarms SPAWN at stage 2 and are
   CONSUMED at stage 4 (after code). Design-doc review is DocsGate's
   (the operator's) job plus the ONE diagram check.
4. **Extension crashes — my `.filter` bug (~10 min, 16:42/17:04/
   17:09).** Three TUI kills from the wrong tool-result shape; each
   cost a restart. Fixed 2026-10-28 (86f41b9).
5. **Reviewer waits, round 2 (~10 min, 17:40–17:50).** All three
   reviewers ran COLD (keepalive tool was returning empty results —
   same `.filter` bug), so round 2 re-studied everything:
   correctness 518s, conventions 622s, trace 469s.
6. **Permission tax: 19 prompts across the session.** Breakdown:
   `./run backupdb` ×4, my own tools `reviewers` ×3 + `compact` ×3
   (unknown tools ask by default — should be allowed), `sudo
   journalctl` ×1, raw `python`/`python3` ×2, `./run python -c` ×5
   (all DB-state work with no management command exposing it).

## B. Confusion items

- **Terse operator-facing messages.** "Approved — compacting the
  stage-2 transcript, then starting the code stage with the wiring
  files I need:" — the operator couldn't tell what "stage-2
  transcript" or "compacting" meant. Rule to add: operator-facing
  text explains in plain words what is about to happen and why
  ("Cleaning up the conversation history so the coding stage starts
  fresh — your decisions are kept; this takes a moment.").
- **Compact criteria (operator question).** Today compact is
  agent-proposed per steer: at stage boundaries — after DocsGate
  approval and after CommitOffer — and "whenever the transcript
  holds a finished stage's probes/deploys." The session called it
  exactly once (17:08, post-approval; a second call at 18:02 hit
  the crash window). Evidence it works: post-compact re-orientation
  cost five quick reads, then 30 min of dense coding.
- **Why python scripts were needed (operator question).** All five
  probes were DB-state inspection Django has no command for: does
  table X exist, what migrations are recorded, row counts. The
  session even had to export DJANGO_SETTINGS_MODULE itself (twice)
  because no preloaded probe entry exists. Remedies in the plan: a
  read-only `dbstate` management command + allowlist.
- **Prewarm aging (operator question: "think if prewarmed reviewers
  save time").** Session numbers: prewarm map-build ≈ 2–3 min per
  reviewer (overlapped with writing — invisible); cold review round
  = 4.6–10.4 min per reviewer (conventions slowest every round);
  keepalive pings ≈ free. If keepalive works, round 2 warm should
  collapse from ~10 min toward tens of seconds. Brand-new reviewers
  cost the full cold study every round. Data favors prewarm IF
  (and only if) the keepalive actually runs.

## C. What the conventions reviewer is (operator question)

`.pi/agents/reviewer-conventions.md` — a read-only reviewer carrying
FIVE duties: doc-claims-vs-code drift (every touched sentence in
README/steer/docs must match committed behavior), mirror checks
(permission config vs steer's quoted allowlist; run help vs scripts),
comment style, TODO hygiene, AND the d2-diagram duty. That's why it's
the slowest every round (578.6s and 622.2s vs 277–518s for the
others; 43–54 tool uses). It's not stuck — it's doing five reviews.

## D. Accesses & thoughts — what the agent discovered vs knew

The scout's map (3.2 min, flash) covered the session's entire working
set: 15 of 17 file clusters it later touched map 1:1 onto the scout's
pattern-pack enumeration; only `djangoapp/ninja_api.py` (×2) and one
docs/reference component fell outside. Zero router/API introspection
probes (the morning session burned 10 min on those). Conclusion: the
MAP is the value, not the scout's liveness — grounds for a committed
repo-map file and no scout agent (plan item 1).

## E. The plan (proposed; nothing coded until the operator says go)

1. **`.pi/repo-map.md`** — committed map (pattern-pack trio
   enumeration, mockup hatch mechanics, wiring points, layer flow,
   rules-where-they-live), harvested from the session's scout output;
   path-sync unit test like the steer-inventory one. Scout background
   agent REMOVED; groundwork = read steer + repo-map.
2. **Reviewer round after code only** — steer line: trio runs once at
   stage 4 (+ round 2 after fixes); stage 2 gets the single diagram
   check, never the full trio on a design doc.
3. **Prewarm decision** (question below) with working keepalive.
4. **Image reviewer for every generated markdown** — background
   (prewarmed?) reviewer that renders d2 fences + screenshots pages
   and judges them visually, for design docs AND feature READMEs
   (reviving the abandoned visual-review idea; pi ≥1.0.4 can pass
   image blocks to agents).
5. **`dbstate` management command** (tables, recorded migrations,
   row counts — read-only) + allowlist; kills the python-probe class.
6. **Allowlist trims**: `./run backupdb`, my `compact`/`reviewers`
   tools, `sudo journalctl -u desmo_*` (read-only); keep python ask.
7. **Gate hands back a clean DB** (drop/recreate/migrate at gate end)
   — no session inherits books-era migration rows.
8. **Plain-language operator messages** rule in steer.
9. **pi → 1.4.0** in the VM AND the repo's install pin
   (vm-bootstrap/inside-vm), verifying the two extensions load.
10. Compact criteria stays "stage boundaries, agent-proposed" unless
    the operator wants extension-driven auto-compaction.
11. **Steer gains a canonical Django-query script example** — the
    exact verified incantation from tonight's working probes
    (`export DJANGO_SETTINGS_MODULE=djangoproject.settings &&
    ./run python -c 'import django; django.setup(); from ourapp.models
    import …'`), with the script rules applied (top comment, readable
    names). The session fumbled this twice (missing settings module,
    raw `python`/`python3` calls); the example removes the fumbling.
    Pairs with `dbstate` for the common cases.
12. **Split the conventions reviewer's duties** — it carries five and
    is slowest every round (578.6s / 622.2s vs 277–518s). The d2
    diagram duty moves to the image reviewer (already decided);
    conventions keeps doc-claims, mirrors, style, TODO — a
    materially lighter pass. If it still lags, mirrors split out as
    a fourth lightweight agent (they run in parallel anyway).
13. **Gate must never clobber a real desmo_db.** Two layers:
    (a) REFUSE-to-start interlock — gate users take a reserved
    pattern (`*@gate.test`, single source of truth in gate.sh); the
    pre-flight lists users and refuses if any NON-gate-pattern user
    exists (prints them via listusers-style output), overridable only
    with `GATE_OVERWRITE_REAL_DB=1`; (b) belt-and-suspenders — the
    gate dumps desmo_db before its first write and restores that
    snapshot as its FINAL step, because the real danger isn't only
    users: tonight's landmine was migration rows, and the restore
    clobbers feature data even with zero real users.

## Questions log

1. **Prewarm vs brand-new reviewers** — ANSWERED: prewarm +
   keepalive. Spawn at docs-stage entry (invisible map-build
   overlap), reviewer-manager holds them through coding, round 2
   resumes warm.
2. **Image reviewer** — ANSWERED: one PREWARMED image reviewer,
   all markdown. Spawned with the other prewarms at docs entry,
   kept alive; every markdown reaching deployed state (design docs
   AND feature READMEs) gets d2 fences rendered + pages screenshotted
   and judged visually; findings fold into the stage-4 round.
3. **Allowlists** — ANSWERED: full set, but ABSOLUTELY NO sudo.
   `./run backupdb` + `compact`/`reviewers` tools allowlisted;
   journalctl becomes non-sudo by provisioning: add the app user to
   the `systemd-journal` group (Debian/Ubuntu grants full journal
   read to that group) — `usermod -aG systemd-journal` in the
   provisioner + live VM, then allowlist `journalctl -u desmo_*`
   with no sudo anywhere.
4. **pi version** — ANSWERED: 1.4.0 now, VM and repo install pin;
   watch the next release for #9265 (render-spin).
5. **Compact trigger** — ANSWERED: agent-proposed at stage
   boundaries (unchanged); the operator-facing message must explain
   in plain words what is cleaned and why (confusion item B).
