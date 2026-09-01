# deployscratch, scratch git design B, absolute links, scratch-test-subset

Date: 2026-08-31 (evening). Implements the plan agreed after reviewing the
"Chore Tracker with Schedules" crush session (the one where the agent
hand-rolled a baseline commit, shared unclickable relative links, and could
not restart granian for its design demo).

## Session findings that drove this

- `createscratch`'s VM identity fallback set `user.email=""` → git refuses
  empty ident → the baseline commit failed silently (no set -e) → the agent
  hand-committed with `-c user.email=agent@localhost`.
- steer.md's "Linking to files" section still prescribed relative HTML
  `<a href>` anchors (opencode era) → three rounds of unclickable links
  until the agent discovered the TUI only hyperlinks absolute URLs.
- On the VM, the design demo's new route needed a granian restart ("no
  restart rule" + guard denies sudo) and main's static/node_modules are
  app-owned 644 (created after the provision-time group-write pass) → the
  agent worked around with a user-approved `sudo rsync`.

## Changes

- **Scratch git = design B** (`run`): `_new_scratch` now copies main's
  `.git` into scratch (real shared history) and freezes the seeded main
  HEAD as the `scratch-baseline` ref; the framework-file watch diffs
  against the REF (agent commits in scratch can never blind it). The
  synthetic `git init` + baseline commit + identity fallback are deleted.
  `_SCRATCH_EXCLUDES` lost `.git` (directional: deployscratch re-excludes
  `.git` + `.env` so main's repo/env are never overwritten).
- **Fast scratch bootstrap**: `.venv` and `frontend/node_modules` are
  hardlink-copied (`cp -al`) from main — instant, ~free disk; uv sync /
  npm install become incremental; hardlink semantics keep scratch
  disposable.
- **`mergescratch` → `deployscratch`**, checkscratch absorbed: the ONE
  command runs the full battery in scratch (ruff/mypy/ourapp tests/
  frontend lint+typecheck+build/framework-watch → scratch-test-subset),
  then rsync-deploys, `migrate`, and on the VM collectstatic + restart
  granian/huey — **deployed routes go live immediately** (supersedes the
  "no restart rule"; console already had passwordless sudo — the guard is
  the policy layer). Nothing deploys red; every green batch goes live
  (continuous deploy). Build loop = `cd ../scratch && ./run deployscratch`
  once per edit batch; the old Verify/Deploy phases dissolved into Build.
- **Guard**: `./run deployscratch` allowlisted (checkscratch entry removed
  with the command). NO systemctl form is allowlisted — deployscratch's
  internal restarts run beneath the guard (the agent never types them);
  a hand-typed restart is out-of-band and prompts (tested, including the
  exact deploy forms).
- **`framework-subset` → `scratch-test-subset`** across the 6 test files +
  run + steer.md; `test_framework_smoke.py` gained `test_homepage_smoke`
  (goto / → status 200; content is app-owned so status is the signal).
- **Links**: steer.md's linking sections rewritten — markdown only,
  ABSOLUTE URLs (`https://app.local/…`; dev `http://localhost:8000`), and
  design-artifact links (mockup pages + design doc) shared at the END of
  the deploying message; Final message de-HTML'd.
- README/TODO/guard docs updated to the new command names.

## Validation

- [x] `uv run python -m unittest discover -s deploy/tests` — guard tests
      green (deployscratch allow incl. compounds; other-systemctl prompts).
- [x] `./run lintfix` + `./run typecheck` green; run parses (executed).
- [x] `./run playwrighttest djangoapp.tests.playwright.test_framework_smoke`
      — renamed tag + homepage smoke green in dev.
- [ ] First VM feature run exercises design B + auto-restart end to end.
