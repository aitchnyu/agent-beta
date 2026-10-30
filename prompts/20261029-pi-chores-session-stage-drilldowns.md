# Oct 29 chores session — per-stage drill-downs (2h03m wall / 112m agent-active)

Built 2026-10-29 from the transcript of session `2026-10-29T17-09-11`
(17:09→19:12 UTC = 22:39→00:42 IST): the first feature run on the
re-provisioned VM — repo-map, allowlists, foreground stages, and the
reviewer round all live for the first time. Times below are UTC.
"Human" = >15s gaps before operator messages + 5 permission waits
(27s, 27s, 38s, 7s, 16s = 115s total).

| phase | wall | human | active |
|---|---|---|---|
| P0 connect/model pick | 4m41s | — | operator setup, not agent work |
| P1 create user + login link | 1m27s | 0 | 1m27s |
| P2 stage-1 mockups | 15m23s | 2m51s | 12m31s |
| P3 stage-2 docs + diagrams | 37m14s | 1m07s | 36m06s |
| P4 compact + approval | 4m19s | 0m54s | 3m25s |
| P5 stage-3 code | 32m02s | 1m01s | 31m01s |
| P6 stage-4 doc-drift fix | 3m15s | 0 | 3m15s |
| P7 stage-4 review + fixes | 18m15s | 0 | 18m15s |
| P8 final report + commit | 5m08s | 3m43s | 1m24s |

## P1 createuser (1m27s — clean)

createuser → first-user refusal (plain user on empty DB) → retry with
`--superuser` → listusers → baseurls for the link. The one retry is the
documented first-user surprise, cost ~15s. Nothing wrong.

## P2 stage-1 mockups (12m31s active)

- Orientation 17:16 (repo-map read, createscratch, Home.vue) — the map
  worked: zero discovery detours.
- Reads + first mockup write 17:17–17:20, lintfix + deploy + verify by
  17:22:12 (one curl HTTPS→TLS-fail→HTTP detour, ~1m).
- **Design Q&A AFTER the first deploy** (17:22→17:24): the answers
  ("every N days/weeks/months, days-per-week, history view") reshaped
  the mockups — cycle-1's work was partially thrown away.
- Rewrite turn 17:27:44 (214s pure generation), reference select-pattern
  reads, second write+deploy+verify by 17:31:19.

**Wrong:** the requirement questions were asked after building v1
instead of before — one redundant deploy cycle (~3m). Everything else
was model latency (88s/214s/118s turns ≈ 7m).

## P3 stage-2 docs + diagrams (36m06s active)

Anatomy: stage-opening generation 3m20s (plan + 4 prewarm prompts) ·
doc prose + fences + validate + deploy 3m30s · image-reviewer geometry
pass **11m41s** (blocked wait; internally lumpy — 230s and 403s
generation gaps) · five fix cycles ~15m (edit + `checkmarkdownd2` ~25s +
reviewer spot-check 49s–4m + `deployscratch` ~1m each; 5 validates,
5 deploys).

**Wrong, ranked:**
1. Diagrams shipped blind — the doc deployed 17:38 with fences never
   eyeballed; the operator flagged "a mess" **41s later**. No
   render-and-self-check before deploy.
2. The loop missed what the human caught twice — "a mess" came before
   any reviewer verdict; "text escaping the ovals" (18:03) came AFTER
   the reviewer OK'd widths in round 3.
3. Rulebook knowledge gap — "d2 never wraps labels" was only
   discovered in round 4 (fix: manual `\n` in four labels); round 3
   was a dead end (dagre ignores declaration order). Two of five
   cycles (~5–6m) avoidable with one rulebook sentence.
4. Reviewer latency — six image-reviewer engagements (1 prewarm study
   + 1 full pass + 4 spot-checks) ≈ 20m of the 36m. Only round 5
   (49s, "confirm wrapped labels fit") was tightly scoped.

## P4 compact + approval (3m25s active)

"code" → 76s generation → compact (85s) → **agent went idle** →
operator nudged "continue" (54s). Also: "Reviewer bench expired" —
the 17:35 prewarm bench (3 studies) was dead by 18:13 because stage 2
ran 33m; the prewarm spend was wasted.

**Wrong:** (a) post-compact stall — the agent parks instead of
resuming; needed a manual "continue". (b) Prewarm timing: prewarming
reviewers at stage START when they're consumed at stage END exceeds
retention whenever the stage runs long.

## P5 stage-3 code (31m01s active)

- **Reading 18:13→18:20 (~7m):** 13 reference files + 4 scratch pages,
  straight to the reference trio — repo-map paying off, no probe storm.
- **Writing 18:20→18:24 (~4m):** models, migration, views, router/URLs,
  home wiring, three test layers.
- **Fix-loop churn 18:24→18:35 (~11.5m), roughly half avoidable:**
  - lintfix auto-fixed 41 + 11 hand edits (formatting on write —
    predictable, fine);
  - `chores/<str:public_id>` route shadowing the JSON endpoints
    (18:28→18:31, ~3 cycles) — a reference-checkable mistake;
  - migration rm + recreate (18:26) — same churn as Oct 28;
  - one edit call "failed atomically" (18:33) — a silently unapplied
    edit cost an extra test cycle;
  - `TestResponse` import guess wrong for this Django (18:26, then mypy
    forced the rewrite again at 18:43);
  - dead-end probes (findstatic --help, cat urls.py) ~1m.
- **Frontend + e2e 18:35→18:42 (~7m):** schemas, two real pages
  (mockups deleted), npm build, playwright — caught a REAL bug
  (Home card reading `usePage().props` at the wrong nesting) plus one
  wrong test expectation ("every 1 days").
- **Battery 18:41→18:45 (~4m):** README, mypy rewrite, deploy; one
  failure was a pre-existing home test asserting old empty props —
  legit, not agent-caused.

Permission asks here: rm-migration (38s), `./run python -c` probe (7s),
findstatic redirect (16s).

**Wrong:** the churn cluster (route shadowing, migration rm/recreate,
atomic-edit miss, TestResponse) is one class: write-then-discover
instead of check-the-reference-first. ~5–6m of the 11.5m churn was
avoidable.

## P6 doc-drift fix (3m15s — the structural tax)

Doc written in stage 2 drifted from stage-3's implementation (detail
URL ×2, `schedule_text` field, archived-detail note). Four calls,
clean fix. Not "wrong" — the doc-before-code order makes this tax
structural; the levers are smaller (fix drift during stage 4's triage
batch, which is exactly what happened) or none.

## P7 stage-4 review + fixes (18m15s, fully active)

- 3 fresh reviewers spawned in parallel 18:48:37; curls verify live
  URLs while they run (good overlap).
- Reviewer wall = slowest ≈ 11m (correctness 7m13s; spans 18m02/9m48/
  9m53 internally — multiple 45–130s generation gaps per reviewer).
- Triage 18:59→19:03: re-read final state (~2m), one 14-edit batch
  across 10 files (one major = doc overpromise, converged minors),
  test + deploy.
- Round-2 reviewer on the fix diff: 63s, no regressions.

**Wrong:** nothing in orchestration — parallel spawn, batch triage,
tight round 2. The 11m is reviewer LLM latency on big diffs; the only
lever is smaller review scopes or faster reviewer turns.

## P8 final report + commit (1m24s active, 3m43s human)

git status → compact (#2) → **idle again** → operator "continue"
(112s) → FinalReport 19:09 → commit menu → operator "1" (111s) →
commit `ee16d28` + cleanscratch → shipped 19:12:02.

**Wrong:** the post-compact stall hit a SECOND time — both manual
"continue"s in this session came immediately after a `compact`.
Systemic, not operator impatience.

## Cross-cutting findings

1. **Post-compact stall ×2** (P4, P8): after `compact`, the agent
   parks awaiting input instead of resuming the plan. Fix in steer
   ("after compacting, resume immediately") or the extension.
2. **Prewarm/retention mismatch** (P4): prewarm at stage start +
   review at stage end fails whenever the stage >~30m. Either prewarm
   at stage END (as done for stage 4 — worked, 18m round) or drop
   prewarm for stages expected to run long.
3. **Ship-blind renders** (P3): render + self-inspect (or reviewer
   pass) BEFORE the first doc deploy.
4. **Rulebook gap: d2 never wraps labels** — add to the d2 rulebook /
   reviewer-image map (kills 2 of 5 fix cycles).
5. **Write-then-discover churn** (P5): route shadowing, migration
   rm/recreate, TestResponse, atomic-edit miss — all checkable against
   the reference before first test run.
6. **Permission asks from curl variants** (P2: https/http curls asked
   twice) — consider allowlisting the loopback curl probe pattern the
   stages always run.

## Compression levers (ranked, estimated)

1. Pre-deploy render self-check in stage 2: ~−8m (P3).
2. d2 label-wrap rule in the rulebook: ~−5m (P3).
3. Requirement Q&A before first mockup: ~−3m (P2).
4. Reference-first checks in stage 3 (routes, imports, migration):
   ~−5m (P5).
5. Fix the post-compact stall: ~−3m of operator nudging (P4+P8).
6. Batch validate+deploy per accepted fix batch: ~−2m (P3).

## Operator Q&A (2026-10-29 evening)

**Q: Why did the agent run python at all (TestResponse probe, URL
resolver)? Weren't the references enough?**

Two probes, two different verdicts:

- `./run python -c 'import django.test as t; print([n for n in dir(t)
  if "Response" in n])…'` (18:28:06, 7s ask) — checked whether this
  Django exports `TestResponse`. **Reference-avoidable.** The agent
  wrote the import from memory, the test run failed, THEN it probed;
  mypy forced the same rewrite again at 18:43. The reference tests
  never annotate with `TestResponse` — copying their import style
  first would have skipped the probe and both fix cycles.
- `./run python -c 'import django … '` printing the live URL patterns
  (`admin/ accounts/`, 18:28:47) — diagnosed the route shadowing
  (`chores/<str:public_id>` swallowing `POST /chores/`). **Partially
  excusable:** the reference has a page route and a ninja router but
  no detail-page route to copy, so this collision was a new design
  element — still, the router docstring it then re-read ("each
  endpoint is served at its literal URL") was already in its context;
  comparing registrations before the first test run beats resolver
  introspection after a 404.

Pattern: both probes were **diagnose-after-failure** where
**check-reference-before-first-run** was cheaper. Steer lever: "before
debugging a failing import/route you wrote, diff it against the
reference's equivalent first."

**Q: When/why was compaction decided? Was it counterproductive?**

Steer mandates it: "Call the `compact` tool at stage boundaries"
(steer.md:166). Two calls:

- #1, 18:10:45 — at the docs→code boundary, announced ("Shedding the
  finished design stage's transcript"). Took 85s (event 18:12:11).
  Defensible: stage-2's diagram-churn context shed before the big
  reference read. Side damage: the same turn's `reviewers
  {"refresh":true}` returned **"Operation aborted"** — the bench
  keepalive failed, so the 17:35 prewarm investment died here.
- #2, 19:07:03 — before assembling the FinalReport; **you canceled
  it** (no compaction event ever landed). Net effect: 112s stall plus
  a manual "continue" for zero benefit. Counterproductive, yes.

**Q: Why didn't the session automatically continue after compaction?**

The compact tool result reads "compaction started — **the next turn
begins lean**" — compaction lands between turns, and the model treats
that tool result as a natural end-of-turn: it parks instead of issuing
the next batch. Nothing in pi or steer instructs it to proceed. Steer
fix: "after `compact`, immediately continue the plan — never end a
turn on a compact call."

**Q: Why didn't it continue after I canceled the compaction?**

Same root, worse optics: the cancel injects **no transcript event**
(the #2 call shows only the tool result, no COMPACTION entry), so the
agent never learns anything happened — it had already parked, and only
a user message ("continue") restarts the loop. Fix is the same steer
rule; a pi-side fix would be turning a canceled compaction into a
continuation prompt.

**Q: Why did curl trigger permission asks? Approved loopback pattern?**

The allowlist has exactly one narrow curl entry:
`"curl -sk -o /dev/null -w *": "allow"`. The asked commands were
plain-`-s` HTTP variants (17:20:50 `curl -s -o /dev/null -w "http:
%{http_code}" http://localhost…`, 17:30:33 `curl -s … http://localhost/chores…`)
— outside the glob, so 54s of asking across two stage-1 verify steps.
Proposal (steer documents the idiom, config allowlists the shapes):

```jsonc
"curl -sk -o /dev/null * https://localhost*": "allow"
```

(read-only status probes on loopback only — no -X POST, no external
hosts). The stage-verify curl shape in steer should match these
patterns verbatim so sessions never improvise variants.

