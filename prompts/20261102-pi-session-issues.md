# Nov 2 chores session — first run under the squashed session fixes

From session `2026-11-02T12-39-54` (12:39:54→14:38:59 UTC, 119m wall):
chores v2 (day-of-week / fixed-interval schedules, summary card, detail +
edit pages, past instances, catch-up) — the first live run of everything the
`streamline pi sessions` commit shipped: trust.json seeded at provision,
prep digest + §9-skeletons-first, two-phase review fleet (familiarize at
first green → verify at final green), image review one-spawn-per-batch.

Subagents: prep 5:07 · coder 77:06 (216 tool uses, 244.6k tokens) ·
4× FAMILIARIZE reviewers (parked 25-27m by design) · image reviewer ×2.

## Hierarchical time (wall; GEN = model turns where measured)

```
                                                        wall
SESSION 12:39:54→14:38:59Z                            119:00

├─ 1. setup: superuser + login link                     0:51
├─ 2. stages 1-2: spec → mockups → design doc         ~25:00  4 operator turns
│  ├─ operator refinement turns (00:51…21:22)              —
│  ├─ mockup batch [12:27] → lintfix → deployscratch  ~0:40  battery fast-path
│  ├─ probes OK · ⚠ python authed check DENIED        ~1:00  [13:40→14:38] → Levers 4
│  └─ design doc [25:06]                                    —
├─ 3. d2 validation loop [26:55→36:38]                ~10:00  5 edit→render cycles
│  └─ image reviewer #1 — ONE spawn, whole doc          8:18  verdict GEN 4:47
├─ 4. DocsGate + prep → SWITCH LOSS [→38:58]           ~2:20
│  ⚠ session-switch cleared BOTH background agents (prep + spot-check);
│    operator nudged [37:44]; coder re-spawned fresh WITH the digest
│    [38:58] — the steer fallback rule absorbed it
├─ 5. coder — fresh spawn → completed [38:58→14:37]    77:06  span
│  ├─ GEN 39:55 / 178 turns ~13.5s avg (split below)       —
│  ├─ deployscratch ×5                                ~13:53  ⚠ ≥10:00 = ONE dialog [14:02]
│  ├─ notify_parent ×3                                 ~1:01  first-green ping +44s forwarding
│  ├─ parked awaiting review triage                    14:51
│  └─ review-fix round [+69:54]                         7:12  GEN 5:22 · 41 turns · 18 writes
├─ 6. fleet FAMILIARIZE at first green [67:11]             —  parallel to 5 · 3-7m each · parked 25-27m
├─ 7. verify round + triage [94:28→108:55]             14:27
│  ├─ final diff parked + doc renders                   1:06
│  ├─ 5 reviewers verify — blocked on slowest          11:22  trace 110 uses/161k tok
│  │    correctness 64/150k · conventions 60/140k · mirrors 54/114k · image#2 5:27
│  ├─ triage turn (no blockers, three majors)           1:02
│  └─ steer FAILED on completed coder → resume         ~0:30  resume landed [108:55]
└─ 8. fix round + CloseOut [108:55→119]               ~10:10  inside 5's span
```

## Coder GEN split — 39:55 measured, rows sum 39:50 (per-second truncation), no single stall

| phase | GEN | turns | writes |
|---|---|---|---|
| orientation (prep digest + §9) | 3:26 | 25 | 0 |
| implementation plan + backend start (turns of 3:13 + 2:56) | 6:21 | 3 | 0 |
| models + views + tests | 9:31 | 33 | 17 |
| frontend + e2e | 8:34 | 41 | 19 |
| deploy + fix cycles | 5:58 | 31 | 11 |
| review-fix round | 5:22 | 41 | 18 |
| final battery + report | 0:38 | 4 | 0 |

178 turns × ~13.5s at thinking-high ≈ the whole number. Composing the
feature's files is ~23.5m of it; re-work loops (fix cycles + review round)
~11m; orientation is no longer the problem.

## Permission ledger — every ask traced to our own `bash: ask` override

**CORRECTED (final root cause):** all seven `.pi/agents/*.md` files carried
`permission: {bash: ask}` in frontmatter (from the review-fleet commit
`2d87b4e`). Agent scope is the HIGHEST merge precedence (global → project →
agent → project-agent), so that block forced every bash call in every agent
session to ask — overriding the entire allowlist — and each ask forwarded to
the parent. The earlier "trust gap" and "relay-by-design" theories were both
wrong: instrumentation shows the child is `projectTrusted: true` and loads
config from every scope (`config.loaded`, `warning=null`); the user-scope
mirror did nothing; `defaultProjectTrust: "always"` did nothing. The block
is now removed from all seven agent files; a VM probe with it stripped ran
the child's `rg -n …` silently on the project rule. Expected effect: the
116-forward tax and the 676s deadlock class collapse to rare
unlisted-command asks. `promptTimeoutMs` (42.0.0) remains worth setting as
a guard for those. Upstream issue: unnecessary. (The raw numbers below
remain as observed.)

119 requests, 19:25 total wait, operator saw only **4** dialogs. But the
shape census says it was never about pipe suffixes: **all 116 child asks
recorded `matchedPattern: "*"`** — including 70× `cd ../scratch …`
compounds and ~40× plain `rg` / `sed -n` / `find` / `git status` reads
that HAVE matching entries (`"cd *"`, `"rg *"`, `"sed -n *"` …) in the
project config. Subagent sessions never receive the project allowlist
(pi's known config-store/project-trust gap); what trust.json changed is
WHERE unmatched asks go: forwarded to the main agent — 115 auto-approved
there (~0.3s when free, 20-48s while mid-generation). The main's own
unlisted verbs asked the operator directly (3× `./run python -c`, one
denied), and ONE coder forward escalated to the operator for 676s
(`./run deployscratch 2>&1 | tail -8` at 14:02) — the main was blocked
in its 23m get_subagent_result wait at that moment, so nobody was left
to decide the forward. Nov 1 for contrast: 27 operator dialogs / 21:39.

## Wins vs Nov 1 (the squashed commit's first live run)

- Human permission dialogs 27 → 4 (and the one big one is a pattern miss,
  not trust).
- Orientation 17m → 3:26; prep 13.4m → 5:07 (digest + §9-first).
- Image review: 2 spawns total (validation 8:18 + verify 5:27) vs serial
  per-fence renders before.
- Fleet hold pattern worked exactly as designed (familiarize → parked →
  resumed to verify, no re-reads).

## Levers

1. **Steerable coder (operator-endorsed):** after the final-green
   notify_parent, HOLD on an open question ("awaiting triaged fixes") —
   the same trick as prep's READY-hold and the reviewers' STORED-hold — so
   `steer_subagent` lands the triage instantly. No failed-steer detour, no
   resume spin-up, context stays warm; keep the resume fallback for aged-out
   sessions.
2. **DONE — the real fix was ours:** remove `permission: {bash: ask}`
   from the `.pi/agents/*.md` frontmatter (all seven files; see the
   ledger correction above). The exact `./run X` entries suffice on
   42.0.0 — VM-probed: `./run dbstate 2>&1 | tail -2` was allowed
   silently by an exact-only rule (the redirect/pipe is parsed away;
   the command unit is judged as written); no prefix twins needed and
   none shipped. The user-scope mirror in inside-vm.sh was REMOVED
   (proven ineffective and unnecessary). Remaining guard worth adding:
   `promptTimeoutMs` in the project config to bound any future
   forwarded-ask deadlock.
3. **checkmarkdownd2 geometry check:** flag wide fences (aspect > ~1.4) at
   validation time — the 5-cycle aspect loop ran entirely before the image
   reviewer looked; 2-3 cycles per doc are cuttable.
4. **Mockup-phase contract (operator-directed, final form):** mockups →
   lintfix → deployscratch → SEND LINKS — a green deploy IS the
   verification; not even curl probes ("No point, if it deploys, trust
   it"). This run: the anonymous probes already showed 404/404/404/200,
   then it tried a `python -c` Django test-client for the authed view,
   crashed twice, and the third attempt was denied ("you are supposed to
   just curl and then send me links" — since superseded: skip the curl
   too). Repo-map §8's Django-shell recipe made python feel sanctioned.
   Written into steer (stage [1] bullet + Mockups mechanics).
5. Watch items (no fix yet): trace reviewer is the verify-round long pole
   (110 tool uses); first-green notify_parent waited 44s in forwarding.
