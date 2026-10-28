# Oct 26 pi session review + ruff TC/pydantic runtime fix

Built 2026-10-27 from a start-to-finish review of the Oct 26 chores
session (`sessions/2026-10-26T20-38-40-*.jsonl`, one session, 20:38 →
02:02 UTC). This file records where time went and what confused, the
config fix shipped out of it, and the still-open opportunities. The
diagram-reviewer tail of the same session is fixed separately in
`20261027-d2-renders-and-reviewer-prewarm.md`.

## Session facts

- Chore tracker end-to-end (scout → mockup → design+d2 → code → 2
  review rounds → weekend modes), 274 turns, 22 operator prompts,
  $2.09, commit `ff51f56`, all gates green at the end.
- Context grew 25k → 366k tokens with one trivial context edit; 60M of
  61M input tokens were cache reads — cost and latency are context
  rent, not work. 3.5–4 min prompt-to-first-action on the big turns.
- 148 bash / 115 edit / 22 write calls, 5 bash failures, 3 edit
  anchor misses. 15 lintfix runs (~7s each). 50 permission approvals:
  6.3 min total wait, median 4s — permission forwarding is not a
  bottleneck.

## Where time was lost (ranked)

1. **Diagram reviewer skipped, then wrong recovery — ~25 min, 2
   operator corrections (23:34–23:59).** Validated fences with
   `checkmarkdownd2` only; when caught, chased the superuser-only
   live viewer via user research instead of rendering the fences.
   Fixed mechanically by the d2 prompt file above; still open: make
   the reviewer pass a hard gate at stage exit.
2. **Pydantic ForwardRef debug — 22 min (00:23–00:46).** lintfix
   (ruff TC rules, py314) had moved `datetime.date` into
   TYPE_CHECKING; ninja read the schema at runtime and every POST
   crashed. Wrong-first-hypothesis (future-annotations trap), 10
   python probes, 2 crashed on missing DJANGO_SETTINGS_MODULE. Fixed
   below; residual confusion items in the next section.
3. **Postgres stall on deploy — ~5 min + 1 operator turn
   (01:30–01:36).** Deploy failed "database system is shutting
   down"; agent reported and waited. It was already back when
   checked — self-diagnose (systemctl, pg_isready) and retry once
   before reporting.
4. **Read-but-ignored instruction — 1 operator turn (22:21).**
   Home.vue's `<!-- Agent: remove ALL placeholder… -->` comment was
   read at 22:18 and still built on top of.
5. **Design micro-prompts — 5 round trips in 18 min (22:27–22:45).**
   Schedule kinds, summary card, shared list, create-on-home,
   absolute dates — one options question up front.
6. **Abandoned tail (02:02:23).** Weekend feature deployed 02:01;
   its targeted reviewer was spawned and the session transcript just
   ends — the review result was never consumed.

## What was confusing

- **lintfix mutates behind the agent's back.** Docstring reformat and
  TC import moves landed between read → edit → lint cycles: 3 broken
  edit anchors, and the TYPE_CHECKING move was invisible for 20 min.
  lintfix prints nothing about what it changed.
- **No cheap probe entry point.** `./run python -c` dies importing
  ninja without settings boilerplate; `djangomanage shell -c` is not
  allowlisted; each retry re-paid a 24–37s permission dialog.
- **Prewarm expiry.** Reviewers warmed 00:12–00:16 were expired by
  01:37 (round-2 spawned fresh) — prewarm cost paid, benefit lost.
  TODO.md already tracks "Review with same agents".
- **Test output noise.** JSON log lines interleaved with results;
  errors extracted via awk/sed over `/tmp/pi-tool-output` — 6 calls.

## What was built

- **`pyproject.toml`** — `[tool.ruff.lint.flake8-type-checking]`:
  `runtime-evaluated-base-classes = ["ninja.Schema",
  "pydantic.BaseModel"]` (schema-class annotations count as runtime,
  so their imports stay put) plus `exempt-modules = ["typing",
  "typing_extensions", "datetime"]` (typing entries are ruff's
  DEFAULTS — overriding the list drops them, which first try here
  did; datetime is exempt because Django imports it anyway).
  `runtime-evaluated-modules` does not exist in ruff (0.15 rejects
  it); handler-signature reads, if ever needed, belong in
  `runtime-evaluated-decorators`. Reason recorded as principles at
  the config site. When chores syncs back from the VM, drop the
  `noqa` and the "deliberately NO future annotations" block from
  `ourapp/views/chores.py` — the config replaces both.
- **oxlint 1.89** (repo `min-release-age=7` pins it; same engine
  Vite+ 1.4 ships) — `frontend/oxlintrc.json` mirrors the old eslint
  tweaks (no-debugger off, TS no-unused-vars `^_` args ignore,
  browser env). `package.json`: lint = `oxlint` for all JS/TS +
  `.vue` script blocks, then eslint scoped to `src/**/*.vue` ONLY
  (template rules — oxlint has no template linting yet, oxc#15761)
  with `--cache --cache-strategy content`. Measured in-VM: oxlint
  4–22ms; full `npm run lint` 6.1s cold → 1.0s warm. One warning
  surfaced and was taken: `d2.ts` regex → `startsWith`. Endgame:
  drop eslint when oxc#15761 lands; Vite+ (`vp`) is the aligned
  destination — adopting oxlint now is adopting its linter, config
  unchanged.
- **lintfix visibility** — ruff now runs with `--show-fixes`
  (run:454): every applied fix is printed (file, rule). Verified
  in-VM: it surfaced and auto-removed the stale `noqa: TC003` in
  scratch's chores.py as `1 × RUF100`. eslint has NO counterpart
  flag; the equivalent is a `--fix-dry-run --format json` pre-pass
  listing messages carrying a `fix` — deliberately NOT added: the
  new eslint scope is template rules, which are essentially never
  auto-fixable, so its mutation surface is nil (all session anchor
  breaks were ruff-side). Operator rejected the mtime-marker
  variant (tier 2).
- **steer.md infra rule** — "Debugging build / serve issues" now
  says: on infra failures (postgres shutting down, connection
  refused), diagnose (`pg_isready`, `systemctl status`) and retry
  once BEFORE reporting; only blockers that survive a retry get
  escalated. The deployscratch `pg_isready` preflight was
  deliberately NOT added — steer-only per operator.
- **steer.md stage subagent** — Feature workflow [3] now executes in
  a FRESH stage subagent (spawn prompt = handoff: mission, pointers
  incl. steer.md itself, operator decisions verbatim, compact-result
  contract); fix rounds RESUME the same subagent; the one-turn
  [3]→[5] rule respelled as five points: spawn, collect compact
  result, reviewer round, resume for fixes, CommitOffer. Stage
  messages renamed T1–T6 → MockupGate, DocsGate, BlockerAsk,
  FinalReport, CommitOffer, CloseOut (operator: T-numbers were
  untrackable).
  Keeps the main session at gates + summaries instead of the
  200k+ of probes/logs/deploys — the self-serve answer to the
  context-rent problem (no launcher automation needed).
- **`./run test` fast default** (folded over a separate testq) —
  quiet logs via new `LOG_LEVEL` settings knob, `--failfast`,
  `--keepdb` gated by a migrations fingerprint (`_migrations_hash`:
  paths+contents of both migration trees vs
  `/tmp/desmo/test-migrations.sha`; drift or missing marker ⇒ fresh
  create). `--full` = legacy full run (fresh DB, full logs, no
  failfast); checkframework1 uses it (deployscratch invokes
  manage.py test directly). Unknown flags pass through to
  manage.py test (parse_known_args) and --noinput is always
  passed. Playwright tag still excluded. Measured in-VM, 9-test module: ~0.6–0.7s scoped,
  clean output. Persistent-process/pytest alternatives rejected:
  boot is always post-edit in an agent loop (staleness), and pytest
  doesn't touch the fixed costs. Logic lives in **ops/testsuite.py**
  (Python port of test/playwrighttest/screenshots; run keeps thin
  `setenv` + `_ops_cli` wrappers, cli.py now passes through args).
  Verified in-VM: fast path 0.5–1.0s scoped, `--full` OK, ruff +
  mypy clean over ops/ and the full repo.

## Opportunities (open)

- Reviewer gate + drain-on-resume: no stage exit without a reviewer
  result; a resumed session drains pending reviewer results before
  new work (closes both the skipped diagram pass and the abandoned
  02:02 review).
- Batch design questions into one options prompt per stage.
- Scout map indexes `Agent:` comments in files likely to be touched.
- Test parallelism: none today (single process everywhere incl. the
  battery); `--parallel` is a battery lever if its wall time starts
  to matter — irrelevant for scoped testq runs, and it composes with
  --keepdb (Django keeps per-worker DBs).

REJECTED by operator: `./run py` — any allowlisted preloaded runner is
a door for arbitrary python; the probe tax stays (ask per probe).

## Verified

- ruff: in-VM `ruff check` over scratch (which carries the chores
  schemas) — config parses, tree clean, sole finding was the
  session's `noqa: TC003` flagged RUF100-unused (proof the
  exemption, not the noqa, does the work); a later `--show-fixes`
  run auto-removed it and reported `1 × RUF100`.
- oxlint: in-VM — 0 problems, 4–22ms over 69 files; full
  `npm run lint` (oxlint + scoped eslint) 6.1s cold → 1.0s warm.
  Full battery rides the next deployscratch.
