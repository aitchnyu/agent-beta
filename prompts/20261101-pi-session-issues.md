# Nov 1 chores session — first full overlap run

From session `2026-11-01T18-45-19` (18:45→20:46 UTC): the first
feature run with the complete overlap architecture — image review at
validation, coder in background with notify_parent pings, two-phase
review board, warm fix resumes. Ended on a pending CommitOffer.

## Hierarchical time (agent-active only, column-justified)

Operator waits excluded (≈15m). exec = tools running; GEN = model
turns. Times m:ss, right-aligned; leaf splits ±0:02.

```
                                                  wall    exec     GEN
SESSION                                           105:00    ~78:   ~27:
│
├─ 1. start + Q&A + createuser                     8:40    0:30    8:10
├─ 2. stage-1 mockups (+ link rework)              5:05    0:50    4:15
├─ 3. stage-2 docs + image review + incident      17:10   13:30    3:40
│  ├─ doc write + validate + render self-check            (GEN 3:40)
│  ├─ image reviewer — one spawn, 4 fences         0:14 (exec)
│  ├─ scratch-wipe recovery (external incident)    3:00 (exec+GEN)
│  └─ diagram fixes + deploy + gate                0:56 (exec)
├─ 4. coder run (background)                       1:00:49   57:00  3:49
│  ├─ orientation — RE-PAID (resume:null bug)     23:00 (GEN-heavy)
│  ├─ writes + lint/migration/tests               17:00    1:00   16:00
│  │  (incl. one 6:45 generation turn post-lintfix)
│  ├─ framework-test debugging spiral             11:30    1:30   10:00
│  ├─ .venv spelunking                             1:30    0:30    1:00
│  ├─ backend green → notify_parent FIRST ping        — at 50:08
│  └─ frontend + e2e + battery + deploy           11:00    3:00    8:00
├─ 5. review board warm (overlapped in 4)         10:41   10:41       —
│  └─ 4 reviewers familiarized + holding          (parallel)
├─ 6. verify (resumed with closing diff)            8:00    6:00    2:00
├─ 7. triage + coder fix resume (warm)             13:00   10:00    3:00
└─ 8. round-2 confirmations + docs + offer          3:00    0:30    2:30
```

## Agents

| agent | time | tokens | tools |
|---|---|---|---|
| coder (implement) | 61:02 | 273.7k | 192 |
| coder (fix resume) | ~13:00 | — | — |
| reviewer-image (docs) | 10:14 | 88.9k | 29 |
| reviewer-trace (fam) | 6:55 | 133.9k | 111 |
| reviewer-mirrors (fam) | 4:52 | 125.5k | 61 |
| reviewer-correctness (fam) | 4:27 | 80.1k | 37 |
| reviewer-conventions (fam) | 4:12 | 84.0k | 51 |
| verify spans (resumes) | ~2:00 each | — | — |

## What the architecture delivered

- Two-phase board worked end to end: four reviewers familiarized and
  HOLDING during the coder's 11-minute tail; verification cost 8m of
  wall after final green instead of a 14m cold round.
- Warm coder fix-resume: 9m gap between final green and the fix
  resume, well inside the 45m retention — no cold start.
- Image verdict landed IN the DocsGate message (one spawn, 3 real
  catches fixed pre-gate).
- Evidence pasted from the coder's outputs — no re-run battery.
- The fleet earned its keep: verify found 2 MAJORS (a date-math bug
  on edit + one more); both fixed and confirmed in round 2.
- The scratch incident (external — a host-side verification loop
  wiped scratch mid-session) was disclosed transparently at the gate
  and recovered in ~3m with zero lost work.

## Issues, ranked by cost

1. **`resume: null` — the prep context was discarded (~23m).** Steer
   says "resume it with implement," but the implement spawn created a
   FRESH coder (`resume: null` in the call) that re-read the entire
   reference set + framework + harness the 13.4m prep session already
   held. The mechanism is missing: the prep's ask_parent READY result
   carries the agent id — steer must say to resume THAT id.
2. **Framework-test debugging spiral (~11.5m).** Pre-existing suite
   failures (logging/CSRF) pulled the coder into repo archaeology:
   debug scripts, a scratch test_zz_dbg.py, git stash isolation,
   reading ops/ + settings + deployscratch internals. Its contract
   has no boundary for tests it didn't write.
3. **`.venv` spelunking (~1.5m).** The no-site-packages rule lives in
   repo-map §8; coder.md doesn't carry it.
4. **One 6:45 generation turn** after the first lintfix (composing
   the fix batch) — model-side; noted, no rule fix.
5. Scratch wipe — external (host-side process error), recorded for
   the record: verification loops must never touch a live session's
   scratch.

## Levers

- steer stage [3]: the implement spawn resumes the prep session's
  agent id from its ask_parent READY result — spell out the id source.
- coder.md: "a failing test you did not write → report it in your
  final report; never repair the framework to make it pass" and
  "never read .venv/ — the reference and repo-map answer shape
  questions."
