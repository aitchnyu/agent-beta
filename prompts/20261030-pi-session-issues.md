# Oct 30 chores session — issues (2h02m wall / 87m active)

From session `2026-10-30T12-09-49` (12:09→13:51 UTC): the first run
under the streamlined rules. Times assume instant operator responses;
human ≈ 15m (12 message gaps + 6 permission waits ≈ 103s).

## Hierarchical time (everything, column-aligned)

Phase rows are measured [exec | GEN | human]; leaves carry the same
columns and sum to their parent (leaf splits approximate, ±0:02).
Exec = tools actually running; GEN = model thinking/streaming turns;
human = operator waits. Times m:ss.

```
                                                 wall   exec    GEN   human
SESSION                                         102:06  23:00  68:00   15:06
├─ 1. start + createuser                          5:41   0:02   2:59    2:40
│  ├─ pre-first-prompt idle                       1:03     —       —     1:03
│  ├─ orientation: repo-map + dirs + Home.vue     0:50     —    0:50      —
│  ├─ requirement Q&A composition                 1:44     —    1:44      —
│  ├─ createuser ×2 + listusers + login link      0:27   0:02   0:25       —
│  └─ operator request/answer gaps                1:35     —       —      1:35
│
├─ 2. stage-1 mockups                             9:35   0:58   6:51    1:47
│  ├─ scratch + shared-props + Bootstrap checks   3:00   0:25   2:35      —
│  ├─ writes: 2 mockup pages + styles + link      1:00     —     1:00      —
│  ├─ lintfix + deploy + URL verify               1:28   0:31   0:57      —
│  ├─ tweak round: detail page + lint + deploy    1:12   0:02   1:10      —
│  └─ between-turn generation + operator gaps     2:56     —     1:09    1:47
│
├─ 3. DocsGate "2" wait                           1:58     —       —     1:58
│
├─ 4. stage-2 docs + diagrams                    11:51   3:57   7:54       —
│  ├─ d2.md read + stage-opener turn              2:44     —     2:44      —
│  ├─ design-doc write                            2:14     —     2:14      —
│  ├─ validate fences + render self-check         0:40   0:40      —       —
│  ├─ deploy doc                                  0:25   0:25      —       —
│  ├─ 4 per-fence image reviewers (parallel)      2:51   2:51      —       —
│  ├─ fence-3 drift fix + revalidate              0:25     —     0:25      —
│  └─ redeploy + stage wrap-up                    2:32   0:01    2:31      —
│
├─ 5. code-approval gap                           0:26     —       —      0:26
│
├─ 6. stage-3 code                              42:56   2:51   40:05       —
│  ├─ reference reading (8 files)                 5:15     —    5:15      —
│  ├─ backend writes (models+views+urls+home)     2:20   0:05   2:15      —
│  ├─ migration gen + import fix                  0:30   0:06   0:24      —
│  ├─ frontend pattern check + writes             4:20   0:10   4:10      —
│  ├─ test writes (3 layers)                      1:50     —    1:50      —
│  ├─ lint churn round (34 fixes + re-reads)      7:40   0:25   7:15      —
│  ├─ test loop (6 scoped runs + fixes)           8:00   0:35   7:25      —
│  ├─ deploys ×2 + home-test conflict fix         1:10   0:40   0:30      —
│  ├─ Inertia-props rabbit hole (12+ probes)      8:40   0:40   8:00      —
│  └─ settle tests + deploy + docs touch          3:11   0:10   3:01      —
│
├─ 7. review round                               19:07  14:23   4:44       —
│  ├─ spawn 3 reviewers + docs touch              1:00     —    1:00      —
│  ├─ correctness verdict wait                    6:28   6:28      —       —
│  ├─ conventions verdict wait                    0:44   0:44      —       —
│  ├─ trace verdict wait                          5:52   5:52      —       —
│  ├─ triage reads                                1:20     —    1:20      —
│  ├─ fix batch (11 edits + lint + test)          1:40   0:34   1:06      —
│  └─ deploy + wrap                               2:16   0:55   1:18      —
│
├─ 8. compact → park                              1:13     —       —      1:13
│
├─ 9. CommitOffer wait                            1:22     —       —     1:22
│
├─ 10. homepage saga                              6:11   0:57   4:19    0:54
│  ├─ diagnose: dbstate + bundle hash + link      0:45   0:20   0:25      —
│  ├─ Inertia debug probes ×3                     2:28   0:22   2:06      —
│  ├─ placeholder removal + deploy                1:54   0:15   1:39      —
│  └─ operator interjection gaps                  0:54     —       —     0:54
│
└─ 11. commit + cleanscratch                      1:06   0:02   1:03    0:01
   ├─ commit + verify                             0:45   0:02   0:43      —
   └─ cleanscratch + ship note                    0:21     —    0:20    0:01

Headline: generation-bound — ~68 of ~87 active minutes are model
turns (stage 3: 40m). Tool exec is ~23m total, 15:19 of it subagent
waits. Levers: fewer/smaller turns, faster reviewer tier.
```


## What the new rules fixed (vs Oct 29)

- Diagram loop 36m → 9m: render self-check + 4 per-fence image
  reviewers in parallel; one real drift caught and fixed.
- Requirement Q&A before building ✓ — no thrown-away mockup cycle.
- Zero unnecessary compactions (floor held); deploys are publications.
- Permission asks: 6 total / ~103s (curl allowlist held).

## Issues, ranked by cost

1. **Stage-3 churn — 16m20s.**
   a. *Lint round* (7m40s): 34 auto-fixes, then mandatory re-reads of
      every reformatted file. The write-in-style rule did NOT bite —
      the agent still authors unformatted and pays the lintfix→re-read
      loop. The tax is the re-reads, not the fixes.
   b. *Test loop* (8m): one wrong test premise (complete-twice is
      legitimate), one wrong assertion, a pre-existing home-test
      conflict. Partly inherent TDD.
   c. *Inertia-props rabbit hole* (8m40s): self-inflicted twice —
      first a stray `rg -rn "json.loads"` (the `-r n` flag REPLACES
      matches with "n"), fabricating a phantom `n()` alias the agent
      then hunted for a minute; then not knowing the repo's assertion
      idiom (`BaseInertiaTestCase` + `self.props()["props"][…]` from
      `djangoapp/tests/_base.py`), ending in site-packages. Fixed:
      §9 carries the test-harness excerpt; steer bans no-op python
      heredocs (one such wrapper cost a 42s permission ask for an
      empty script) and flags the `rg -rn` trap.
2. **Reviewer wall — 13m57s.** Diff-fed reviewers, spawned in
   parallel; wall = slowest (correctness 395s, trace 352s). Triage +
   fixes after were tight (2m10s). Only remaining lever: a faster
   model tier per reviewer agent (pi agent frontmatter supports
   `model:` — operator's choice).
3. **Compact park — 73s.** The tool was called correctly
   (`continue_with: "Present the CommitOffer gate message…"`), the
   result says "Continue NOW", and the model STILL ended its turn —
   the CommitOffer appeared only after the operator's "continue".
   pi appears to terminate the agent turn on the compact tool result
   regardless of its text. Upstream issue to file; the floor rule
   (which held everywhere else) is the only mitigation.
4. **Homepage saga — 4m45s active + 4 operator messages.** The real
   card's props/schema landed but Home.vue's template kept the
   placeholder markup; "I want to see 0 chores" finally forced the
   removal. Steer's graduation rule covers deleting `Mockup<Name>.vue`
   but not evolving Home's placeholder block. Rule gap: the empty
   feature state must render (0 chores), placeholder text goes when
   the real card lands.
5. Minor: createuser first-user retry (~15s) — the refusal hint
   exists; the agent retried correctly. Acceptable.

## Levers

- Image review: ONE reviewer spawn per markdown doc (all its
  fence<N>.svg in one prompt) — the session spawned four, one per
  fence, paying four cold starts; steer now mandates the single
  spawn.

- §9: add the Inertia-assertion helpers excerpt from
  `djangoapp/tests/_base.py` (kills the rabbit hole, ~8m).
- Steer graduation bullet: extend with "Home's placeholder block is
  replaced by the real card; the empty state renders".
- Reviewer model tier: one `model:` line per reviewer agent file.
- Lint churn: open question — the re-read-after-lintfix loop is
  structural unless writes come out format-clean (rule insufficient)
  or subsequent edits target the lintfixed text without a full re-read
  (edit-tool hygiene).
- Compact: file the upstream pi issue (turn terminates on the compact
  tool result even when the result text commands continuation).
