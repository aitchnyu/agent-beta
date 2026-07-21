# Multi-step setup: resumable, forward-only app installs

An app's `app.py` may declare **multiple `@setup` functions**, executed in
source order. The runner records which setup names have completed on the
`Application` row (a JSON list) and, on re-install, **resumes from where it
left off** — printing the remaining setups, then running only those. The model
is forward-only (like DB migrations): a completed setup never re-runs; to redo
work you append a *new* setup.

**Status:** Parts A–G implemented and green (224 tests; ruff clean;
`makemigrations --check` clean; mypy clean on changed files). Remaining is
only the dev-DB apply (`./run djangomanage migrate`) + the TriviaFacts smoke.

## Mental model

- `@setup` is a marker decorator (unchanged); an app may apply it to several
  functions. Discovery collects them in source order (CPython preserves module
  definition order, so `vars(module)` yields them top-to-bottom).
- `Application.executed_setups` is a JSON list of the `__name__`s of setups
  that have completed, in completion order. It is the app's "install phase."
- On each `buildbackend <app>` run, the runner compares the loaded module's
  setup names against the DB's recorded list and runs only the suffix the file
  adds beyond the recorded prefix.

## Invariant (the resume safety contract)

For a loaded module with `setup_names = [s.__name__ for s in module.setups]`
and a row with `db = application.executed_setups`:

1. `len(setup_names) >= len(db)` — the file has same-or-more setups (rejects
   downgrade).
2. `setup_names[:len(db)] == db` — the executed names are an exact **prefix** of
   the file, by name **and** position (rejects rename, reorder, mid-list
   deletion).

If both hold → run `module.setups[len(db):]`, appending each name to
`executed_setups` as it completes. If either fails → `CommandError` naming
both lists (with a `downgrade?` or `prefix` hint). The prefix check is what
makes resume machine-checkable: it surfaces every drift mode (rename, reorder,
delete-in-middle, downgrade) as one precise error.

## Decisions (locked)

- **Identity = function `__name__`, stored as a JSON list.** Not a positional
  int, not a single last-name. The list gives a full history and a clean
  prefix invariant.
- **Forward-only.** A name in `executed_setups` never re-runs, even if you fix
  a bug in that setup. Redo work by appending a new setup (e.g.
  `setup_fix_bad_seed`). Same discipline as DB migrations.
- **Column `default=list` + `blank=True`.** The empty default is correct for a
  new row (born empty inside step 1; the runner appends each completed name; a
  committed row is never empty). `blank=True` is required because the row is
  born empty and `create_application` runs `full_clean()` *before* the runner
  can append — without `blank=True`, the empty list fails validation
  (`'This field cannot be blank.'`).
- **Legacy rows migrated to `["setup_app"]` via a data step.** Every app in
  the repo (all 7 fixtures, the docs reference, and `TriviaFacts`) names its
  single setup `setup_app`, so `["setup_app"]` is honest for every
  pre-migration row. Next `buildbackend` sees `setup_names=["setup_app"]`,
  `db=["setup_app"]`, prefix matches → nothing to run. Upgrade path is free:
  legacy row `["setup_app"]` + new file `["setup_app", "setup_migrate"]` → runs
  `setup_migrate`. (NOT `default=["setup_app"]` on the column — that would make
  a new multi-step row's prefix check fail on first install.)
- **Zero-setup apps allowed (Part G, pending).** Supersedes the earlier "step 1
  must create the row" stance. An app with no `@setup` is valid; its
  `buildbackend` run is a no-op for the row (runs `@backend_test`s + bumps, but
  no `Application` row is created). To have a row (for endpoints/listing), add a
  setup that creates it. The `≥1` guard in `DynamicModule.__init__` is removed.
- **No idempotent `get_or_create_application` needed.** A failed fresh install
  rolls back the row (the install is one `transaction.atomic`), so
  `create_application`'s non-idempotency never bites on retry. A successful
  re-install skips already-run setups by name, so step 1 is never re-called.
  Contract: setups must be atomic-rollback-safe (no irreversible external side
  effects) — already true for every setup in the repo.
- **No duplicate-`__name__` check.** A second `def setup_app` rebinds the name
  at module-eval time; `vars(module)` only ever sees the survivor. Same
  shadowing property the endpoint discovery already relies on
  (`dynamic_module.py:210-213`).
- **Always run `@backend_test`s and always bump `AppsGeneration`** on every
  successful `buildbackend` (fresh, resume, or no-op). Endpoints may have
  changed alongside the new setups, so tests re-run and workers resync.
- **`out_write` param mirrors `err_write`.** Both typed
  `Callable[[str], object] | None` (return ignored; `StringIO.write` returns
  `int`, so `None` would reject it). `build_backend(identity, *, out_write=None,
  err_write=None)`; defaults are `_stdout_line`/`_stderr_line`; the `Command`
  wrapper passes `out_write=self.stdout.write` (inlined) and a styled
  `err_write` lambda. The runner prints the remaining setups through
  `out_write` before running. `build_backend` keeps returning `int` (test
  count) — the test asserts on captured `out_write` output, not the return
  value.
- **Persist `executed_setups` via `.save()`, not raw `.update()`.** After each
  step: `app_row = Application.objects.get(name=app_name); app_row.executed_setups
  = executed; app_row.save(update_fields=["executed_setups"])`. Runs the model
  `save()` hook consistently with `create_application`'s write path (a raw
  `.filter().update()` bypasses it).
- **Helpers extracted to stay under ruff complexity limits.** `_resume_start
  (identity, executed, setup_names) -> int` (pure prefix-check, raises
  `CommandError`; pulling the raises out of `build_backend`'s `try` also clears
  TRY301) and `_run_backend_tests(identity, tests, err_write)` (the savepoint
  test loop). `build_backend` stays a single atomic with setup loop + these
  two calls + bump.

## Detailed plan

### Part A — Model + migration  ✅ done

`djangoapp/models/applications.py`:

- [x] `Application.executed_setups = models.JSONField(default=list, blank=True)`
      with a docstring stating the prefix invariant + forward-only contract.
- [x] No other model changes (`ApplicationTable`, `ApplicationTableColumn`
      untouched).

`djangoapp/migrations/0016_executed_setups.py`:

- [x] `AddField("application", "executed_setups", JSONField(blank=True,
      default=list))`.
- [x] **Data step** (same migration, after AddField): `Application.objects.update
      (executed_setups=["setup_app"])` — marks every legacy row as "its one
      `setup_app` ran." Honest for all current apps.
- [x] `makemigrations --check` clean. (Dev DB apply pending — the test DB
      applies it each run; run `./run djangomanage migrate` on the dev DB.)

### Part B — `DynamicModule`: `setups` list  ✅ done

`djangoapp/apps/dynamic_module.py`:

- [x] Replace `setup_function: Callable[..., object]` (single) with
      `setups: list[Callable[..., object]]`, collected in source order from
      `vars(module)`. (Note: the `≥1` guard is still present — Part G removes
      it; for now empty `setups` raises `ValueError`.)
- [x] No duplicate-`__name__` check (module-namespace shadowing prevents it).
- [x] Update the class docstring (`setup_function` → `setups`; note source
      order; note the marker shadowing rule).
- [x] Fix the latent last-wins bug: today multiple `@setup`s silently keep only
      the last (`setup_function = obj` overwrites). The list change makes all of
      them run in order.

`djangoapp/management/commands/buildbackend.py`:

- [x] `dynamic_module.setup_function()` → iterate `dynamic_module.setups`
      (resume logic in Part C). The only caller; grep confirmed no others.

### Part C — `build_backend`: resume logic  ✅ done

`djangoapp/management/commands/buildbackend.py`:

- [x] Signature: `build_backend(identity, *, out_write=None, err_write=None)`,
      both `Callable[[str], object] | None`; defaults `_stdout_line`/`_stderr_line`.
- [x] `setup_names = [fn.__name__ for fn in dynamic_module.setups]` after load.
- [x] Resume decision in `_resume_start(identity, executed, setup_names) -> int`
      (pure; raises `CommandError` on downgrade `len` < or prefix mismatch):
      `existing = Application.objects.filter(name=app_name).first()`;
      `executed = list(existing.executed_setups) if existing else []`;
      `start = _resume_start(...)`.
- [x] Print remaining via `out_write`:
      `f"Remaining setups for {identity}: {', '.join(remaining) or '(none — already complete)'}"`,
      plus a per-step `f"  running {fn.__name__}"` line.
- [x] Run loop (inside the one `transaction.atomic`): for each
      `fn in dynamic_module.setups[start:]`, call it; on success fetch the row
      and `.save(update_fields=["executed_setups"])` (through the model layer);
      on failure report `@setup {fn.__name__} failed` via `err_write` +
      traceback, raise `CommandError`. (Per-step save is inside the atomic, so
      a later step's failure rolls the list back; a fresh-install failure rolls
      back the row entirely.)
- [x] `@backend_test`s run in `_run_backend_tests(...)` (extracted savepoint
      loop, unchanged behavior).
- [x] Always `AppsGeneration.bump()` on success (even if nothing ran).
- [x] `Command.handle` passes `out_write=self.stdout.write` + styled
      `err_write`; keeps the styled SUCCESS summary.
- [x] Module docstring "Resume safety" paragraph carries a concrete v1→v2
      resume example + the v3-rename refusal.

### Part D — Test fixtures  ✅ done

Three fixture trees, **same app name** (`MultiStepApp`, 12 chars ≥10 ✅), each
at `<tree>/MultiStepApp/app.py`. The runner finds the same `Application` row
across installs; only the `_APPS_ROOT` swap changes which file loads. Named by
their setup state (not "v1/v2/v3").

`djangoapp/tests/appfixtures/multistep_step1/MultiStepApp/app.py`:

- [x] `APP = "MultiStepApp"`. One `@setup def setup1` that calls
      `create_application(name=APP, tables={"alpha": [CharColumn("code", ...)]})`
      + one seed row.

`djangoapp/tests/appfixtures/multistep_step2/MultiStepApp/app.py`:

- [x] `setup1` **identical to step1's** (append-only contract). A second
      `@setup def setup2` that adds a `beta` table via
      `create_application_table(application=APP, table="beta", ...)`.
- [x] `setup1` / `setup2` are the `__name__`s stored in `executed_setups` —
      distinct and stable.

`djangoapp/tests/appfixtures/multistep_renamed/MultiStepApp/app.py`:

- [x] `setup1` identical to step1/step2's; `setup2` renamed to `setup_two` —
      same length, position-1 differs, so the prefix check fails.

### Part E — Test  ✅ done

`djangoapp/tests/appfixtures/test_buildbackend.py` — new
`BuildBackendResumeTests` (kept all install-runner tests together; no new
`test_setup_runner.py`):

- [x] `_install(tree)` / `_install_captured(tree)` helpers patch `_APPS_ROOT`
      per-call (the patch is swapped mid-method between installs).
- [x] `test_resume_runs_only_new_step` — install step1, reset registry,
      install step2 captured. Asserts: `executed_setups == ["setup1","setup2"]`;
      `beta` exists; `alpha`'s `physical_name` unchanged; captured output has
      `"setup2"` and NOT `"setup1"`. Three proofs of the skip (incl. step2's
      non-idempotent `setup1` would `IntegrityError` if re-run).
- [x] `test_downgrade_refuses_resume` — step2 then step1 → `CommandError`;
      `with assertRaises(...) as cm` then assert the message has `"downgrade"`,
      both lists, the app name, and NOT `"prefix"`.
- [x] `test_prefix_mismatch_refuses_resume` — step2 then renamed →
      `CommandError`; assert message has `"prefix"`, both lists, app name, and
      NOT `"downgrade"`.

### Part F — Docs + lint  ✅ done

- [x] `buildbackend.py` module docstring: resume + the "Resume safety" example.
- [x] `dynamic_module.py` module docstring + `@setup` example: two setups
      executing in order.
- [x] `docs/apps/README.md`: replaced the "re-running setup errors" open-issue
      note with the multi-step resume contract.
- [x] `./run test` — 223 passed (220 + 3).
- [x] `ruff check` — clean (helpers `_resume_start`/`_run_backend_tests` keep
      `build_backend` under complexity/branch/statement limits).
- [x] mypy clean on changed files (pre-existing errors in untouched files are
      out of scope). No frontend change.

### Part G — Zero-setup apps  ✅ done

An app may declare **no** `@setup` functions. Its install is a no-op for the
row (`buildbackend` runs `@backend_test`s + bumps, but no `Application` row is
created — to have a row for endpoints/listing, add a setup that creates it).

`djangoapp/apps/dynamic_module.py`:

- [x] Removed the `if not self.setups: raise ValueError(...)` guard in
      `DynamicModule.__init__`.
- [x] Class docstring: "≥1 required" → "may be empty" + a note that a
      zero-setup app's install creates no row.
- [x] `build_backend` handles empty `setups` (`setup_names=[]`, `start=0`,
      loop runs nothing, tests run, bump) — no change needed.
- [x] `test_endpoints.py`: dropped the now-dead `_placeholder_setup` + the
      `setup` import; synthetic modules load with empty `setups` fine.

`djangoapp/tests/appfixtures/`:

- [x] `ZeroSetupApp/app.py` (11 chars ≥10) — no `@setup`, one trivial
      `@backend_test`.
- [x] `test_zero_setup_app_installs_no_row` in `BuildBackendTests`:
      `build_backend("ZeroSetupApp")` returns 1, bumps the generation, and
      leaves no `Application` row.

---

## Lint and verify

- [x] `./run test` — 224 passed.
- [x] `ruff check` — clean.
- [x] `mypy` on changed files — clean.
- [x] `makemigrations --check` — clean.
- [ ] Smoke: apply 0016 to the dev DB (`./run djangomanage migrate`) and
      `buildbackend TriviaFacts` (single-setup path: `db=["setup_app"]`,
      `setup_names=["setup_app"]`, prefix matches, nothing to run — or fresh
      if DB was cleaned).

---

## `aihere` markers (resolved)

The `# aihere` markers flagged during review have been addressed and removed
from the code (per the convention).

- **"instead of _resume_start, we should have a function that returns remaining"**
  (`buildbackend.py`) — done: `_resume_start` → `_remaining_setups`, which
  returns the callables to run (`setups[len(executed):]`), not just the start
  index. `build_backend` consumes it directly — one slice instead of deriving
  `setup_names[start:]` and `dynamic_module.setups[start:]` separately;
  `setup_names` moved inside the helper.
- **"show an example message, otherwise these asserts are unclear"**
  (`test_buildbackend.py` — downgrade + prefix-mismatch tests) — done: each
  test now carries a literal `# Example message:` block showing the actual
  `CommandError` text, so the `assertIn`/`assertNotIn` checks read without
  inferring the format from `_remaining_setups`.
- **"update this since apps have changed. Maybe split into related sections
  like multistep"** (`appfixtures/README.md`) — done: split into "Single-app
  fixtures" (table, now incl. `ZeroSetupApp`) and a "Multi-step resume
  fixtures" section documenting the `multistep_step1/step2/renamed` trees and
  the resume-skip proof.

---

## Open decisions

1. **Identity model** — resolved: JSON list of `__name__`s (prefix invariant).
2. **Migration default** — resolved: column `default=list` + `blank=True`; data
   step sets legacy rows to `["setup_app"]`.
3. **Idempotency** — resolved: not needed (atomic rollback + name-based skip).
4. **Forward-only** — resolved: yes; redo work by appending a new setup.
5. **Always test + bump** — resolved: yes, on every successful run.
6. **`out_write` injection** — resolved: mirror `err_write`; both typed
   `Callable[[str], object] | None`; `out_write=self.stdout.write` inlined;
   test injects `StringIO`.
7. **Pass-only / zero-setup** — revised: zero-setup apps allowed (Part G,
   pending); setupful apps still need step 1 to create the row. Supersedes the
   earlier "step 1 must create the row" stance.
8. **Persist path** — resolved: `.save(update_fields=...)` through the model
   layer, not raw `.update()`.
9. **Fixture location** — `tests/appfixtures/multistep_{step1,step2,renamed}/
   MultiStepApp/`, same app name across trees, `_APPS_ROOT` swapped between
   installs. (Named by setup state, not "v1/v2".)
10. **Test file** — resolved: extend `test_buildbackend.py` (no new
    `test_setup_runner.py`; no `buildbackend`→`installorupdate` rename — those
    open tabs are stale).
