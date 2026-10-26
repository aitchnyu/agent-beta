# deployscratch → Python (ops/): the scratch-lifecycle trio port

## Why

`run`'s deployscratch had ~15 lines of pure bash workarounds
(`_step_failed`'s BASH_LINENO/`@P` source introspection, bare `local`
declarations, `_SHARE_BASE` expansions) and bash-only constant costs:
a double `git` changed-set on the slow path, `./run test` re-entering
the whole script, one traversal per `find` sweep. The 2026-10-26
session planned the port (phases 0-5); this is the implementation of
phases 0-4 for the minimal closed boundary: the scratch trio
(deployscratch + createscratch + cleanscratch) and its exclusive
helpers. Everything else in `run` stays bash.

## What

- `ops/shell.py` — the only subprocess touchpoint: `run` (set -e
  parity, inherited stdio), `capture` (command substitution),
  `step`/`step_failed` (the failed-step hint block verbatim — the retry
  command is data, not BASH_LINENO introspection), `die` (Refusing:
  guard idiom).
- `ops/scratch.py` — the trio: paths, env loading,
  `changed_files_vs_baseline`/backup-probe/`rsync_excludes_file`
  plumbing, the battery, fast-path classification
  (`classify_changed_files` → frozen `FastPath`), the deploy pipeline,
  and the command entry points. Message parity is the contract (gate
  asserts refusal strings).
- `ops/cli.py` — `python -m ops.cli <cmd>` dispatch.
- `ops/tests/test_scratch.py` — 19 unit tests for the pure logic
  (classify/framework_files/share_base/filter_excludes), discovered by
  `manage.py test` (checkframework1 stage 1).
- `run` — delegation block before the function dispatch:
  `deployscratch|createscratch|cleanscratch` exec
  `uv run python -m ops.cli` (PYTHONUNBUFFERED for output ordering)
  unless `DEPLOYSCRATCH_BASH=1` — the bash implementations stay as
  the rollback path until retirement.
- `pyproject.toml` — ruff per-file-ignores: `ops/*.py` (T201 print is
  the CLI's output channel; S603/S607 literal-argv subprocess),
  `ops/tests/**` (PLR2004 literal listings, FBT003 FastPath positional
  booleans).

Deliberate deviations (planned): changed-set computed once; battery
steps call uv/manage.py directly with the test-redis env applied
in Python; retry hints carry the clean re-run command.

## Verification (2026-10-26, host + desmo VM; nothing committed)

Host: ruff format/check clean, full-repo mypy clean (136 files),
19/19 unit tests, refusal messages byte-identical between the Python
and `DEPLOYSCRATCH_BASH=1` paths, unknown commands still hit run's
help.

VM (main at its own 2e44fdb history + ~100 uncommitted files, in sync
with scratch — danger set verified empty before every deploy):

- Control: the pre-port bash deployscratch shipped the port into
  main — full battery + framework-watch smoke green, 47.6s.
- Python path, full battery (empty diff and the 100-file dirty set —
  the VM's uncommitted state drags every deploy to the full path,
  same as bash): green end-to-end — battery, rsync, own sweeps,
  backup, migrate, collectstatic, restarts, baseurls — 27.6s vs the
  47.6s bash control (no `./run` re-entry, single changed-set).
- Two bugs caught by the VM run and fixed: `--color-never` typo
  (ruff wants `--color=never`) and stdout block-buffering under
  pipes (PYTHONUNBUFFERED in the delegation). The typo fix shipped
  via the `DEPLOYSCRATCH_BASH=1` rollback — the switch's first real
  use, worked as designed.
- Refusals byte-identical on both paths: scratch's own ./run, no
  scratch after cleanscratch.
- createscratch (Python) end-to-end: 42s (hardlink-fallback copy,
  uv sync, npm install, baseline tag); cleanscratch; rollback
  switch dispatch confirmed.
- Fast path NOT exercised end-to-end: it needs a committed-clean
  baseline, and the VM's uncommitted state classifies every deploy
  as full — for bash identically. Covered by the 19 unit tests plus
  the shared `shell.step` calls the battery just proved.
- End state: probe edit reverted, main/scratch dirty sets IN_SYNC
  (101 = prior 100 + untracked ops/), granian/huey active.

## Pending

- `checkframework2` (the gate) — destructive VM rebuild; deferred
  because the VM holds ~100 uncommitted files of prior work. Run it
  when that work lands or the operator OKs the rebuild.
- Fast-path wall-clock on a committed baseline (~12-15s target from
  the fast-path doc) — same precondition.

## Update (later on 2026-10-26): retraction

The rollback scaffold is gone — the bash implementations were
overwritten, not shadowed:

- `run`'s trio functions are now one-line wrappers over a shared
  `_ops_cli` helper (`uv run python -m ops.cli`); the `case "$1"`
  delegation block and the `DEPLOYSCRATCH_BASH` switch were removed.
- Dead bash helpers deleted: `_scratch_changed_files`,
  `_framework_files`, `_step_failed`, `_scratch_checks`,
  `scratch_excluded_files`, `_link_or_copy_tree`, `create_new_scratch`,
  `_banner` (~230 lines). `_require_main_run` (checkmarkdownd2,
  checkframework1) and `overlay_app` + `_backup_running` (checkframework1
  / restoredb) stay.
- checkframework1's stage-3/4 `create_new_scratch` calls became
  `_ops_cli createscratch` — one implementation, no duplicate.
- ops/ docstrings rewritten to stand on their own (no references to a
  previous implementation); tests follow the repo conventions (class
  docstring + `- test_<name>, <assertion>` bullets, behavioral names).

Re-verified: host ruff/mypy/19 tests, wrapper refusals byte-identical,
host `./run createscratch` via the wrapper (15.7s, hardlinked) +
cleanscratch; VM: ship deploy, empty-diff full battery through the
wrapper version, scratch's-own-run refusal, main/scratch IN_SYNC,
granian/huey active.

## Update 2 (2026-10-26 evening): agent review round + VM-first verification

Three review agents over the uncommitted diff (Python quality /
integration surface / behavior parity). Applied:

- fail-fast: a failed `scratch-baseline` tag now aborts createscratch
  (was check=False → misleading "ready"); rmtree of the old scratch
  dies loudly on failure instead of ignore_errors.
- the changed-set is genuinely computed once (the framework watch
  re-classified a second listing); `changed_files_vs_baseline` inlined
  into deployscratch (single-caller rule).
- env loading: main/.env (not cwd), trailing `# comment` stripping
  (bash-parity for `KEY="v" # note`), git plumbing stderr now visible
  on diff/ls-files failures.
- colors configured at CLI startup (configure_output) — importing
  ops.scratch (the test runner) no longer mutates NO_COLOR/FORCE_COLOR.
- share_url_base drops ALL trailing slashes; cli docstring honest about
  ignored extras; gate.sh comments updated to ops/ names; dead PLR2004
  ignore removed; names de-cryptified (exit_code, path, tree_dir,
  directional_carries, url_base, fast_path, probe_output…); +3 tests
  (double-slash base, test_redis_env ×2) → 22 total.

Declined: --quiet passthrough for checkframework1's createscratch noise
(accepted), try/finally for the excludes temp file (bash parity),
TypedDict for the pgbackrest lock shape (future-proofing).

All verification ran on the VM this round (host = edits only): VM
scratch ruff format/check, ./run typecheck (143 files), 22/22 tests,
ship deploy, scratch's-own-run refusal, IN_SYNC, granian/huey active.
Host files byte-identical to the VM-verified tree (pulled back and
diffed).

## Non-goals

- Porting backupdb/restoredb (systemd timer contract), test/typecheck
  wrappers, checkframework1/2, pi/init/dev.
- Packaging (`[project.scripts]`) — `python -m ops.cli` needs no
  build-system change; the repo stays a non-package venv project.
- Rewrite-only optimizations beyond the planned deviations (one-pass
  own sweep, lint ∥ build) — deferred until the gate proves the port.
