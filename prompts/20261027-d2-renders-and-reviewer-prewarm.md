# D2 renders + reviewer prewarm at stage 2

Built 2026-10-27, after the Oct 26 chores session's diagram tail: the
reviewer pass was skipped until the operator called it out, captures
meant a per-session playwright contraption chasing the superuser-only
viewer, and the reviewer ran foreground with an ask per /tmp read.

## What was built

- **`deploy/checkmarkdownd2.mjs`** — file args render each validated
  fence (the options-compile IS the validation) to
  `/tmp/desmo/render-XXXX/<doc>/fence<N>.svg`, viewer-identical. Fresh
  random dir per run: no collisions, no stale fences — the reviewer
  prompt pins the printed dir. TTY scan stays validation-only.
- **`ops/scratch.py`** — `AGENT_TMP_DIR = /tmp/desmo`, wiped by
  createscratch, removed by cleanscratch.
- **Permissions** — `external_directory` allows `/tmp/desmo` reads;
  `tool-output-cap` now parks oversized bash output under
  `/tmp/desmo/tool-output/` (same root, same wipe).
- **Reviewers** — `diagram-reviewer.md` deleted; its contract lives in
  `reviewer.md` ("Diagram duty"), rules in steer.md's `### Diagrams`.
- **steer.md** — reviewer prewarm launches at stage-2 entry (docs-less
  changes: stage-3 start); stage-4 resume pastes the render dir.
  Supersedes 20261009's "stage [4]" prewarm timing.

## Verified

Host run renders viewBox-carrying SVGs, fresh dir per run, per-doc
nesting. Full battery rides the next deployscratch.

Same day: groundwork extension argv guard — `pi -c`/`--session` boots
fire `session_start {reason:"startup"}` with no previousSessionFile
(pi 1.0.0–1.4.0), so argv is the only discriminator. TODO.md tracks
dropping it when upstream fixes the event.
