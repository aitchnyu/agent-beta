# Coverage wrap-up: firstsetup tests + checkframework2 asserts

Nov 20, 2026. The trimmed remainder of the coverage plan. Phases 1-2 are
DONE and recorded below; only two phases remain. **Do not write code
beyond what an item lists; stop each module at ~95; nothing commits.**

## Done (2026-11-20, for the record)

- Phase 1: dbstate/adapters/redis_client at 100% (makeloginlink +
  LoginKey single-use were already covered by 592fe19). Two pre-existing
  gate breakages unblocked: Home.vue Prettier drift + the stale
  playwright locator (both from 1563266). Full `./run checkframework1`
  GREEN at the recalibrated 98.70 floor — first green gate since Nov 18.
  The 99.78 ratchet was unreachable (generatesdk 80.82% + scattered
  misses; ceiling ~99.59).
- Phase 2 (reduced by operator ruling): only `ops/tests/
  test_scratch_commands.py` survives of the ops-infra test files;
  test_shell/test_testsuite deleted, the test_cli addition reverted.
  Ops suite: 125 tests via `python3 -m unittest discover -s ops/tests`.
- Redis test signal redesign: DESMO_TEST_REDIS, `_with_test_redis`,
  `_TEST_REDIS_URL`, and `TEST_REDIS_URL` are GONE. The URL itself is
  the signal — `clear_redis` flushes any nonzero-DB URL
  (`^rediss?://\S+/[1-9][0-9]*$`); DB 0 / suffix-less refuse naming the
  URL. `test_redis_env()` (ops/scratch.py) is the single DB-2 owner.
- aihere sweep: every live marker addressed and removed. New test rules
  written into INSTRUCTIONS.md §Tests (assertRaisesRegex with pinned
  message; method docstrings as multi-line point lists).

Dropped by operator decision: generatesdk testing (80.82% stays — the
floor prices it in) and wiring ops/ into the measured coverage stages.

## Standing rules

1. Per-module ceiling ~95% — no padding past it, no chasing 100.
2. `COVERAGE_RATCHET` stays 98.70; neither remaining phase moves the
   measured floor. Raise only if coverage measurably improves; never
   lower.
3. Test style: INSTRUCTIONS.md §Tests — point-list method docstrings,
   `assertRaisesRegex` with the message pinned, tmp trees + fakes only,
   never the real VM, nothing destructive outside tmp.
4. An item is ticked only after its verifier passed. Never edit files
   while a gate run is in flight.
5. Everything stays uncommitted for operator review.

## Phase 3 — firstsetup: extract the engine, test the system (not Textual)

Reworked by operator decision (2026-11-20): no Textual pilots — no App,
no widget tree, no 80x24 `run_test`. The underlying system logic moves
out of the screens into a plain module and is tested directly with fake
`run`/`exec`/store functions.

A first pilot-based pass (now discarded) had reached screens 98.95% /
app 100% / forms 100% / providers 100% via 80x24 pilots — the numbers
proved reachability, the method was wrong. This phase redoes it right.

### 3a — extract (mechanical, zero behavior change)

- [x] New `ops/firstsetup/flow.py` holding the engine currently trapped
      in screens.py:
      `apply_decision(spec, values)` → skip / refusal / dispatch;
      `run_actions(spec, values, run)` → ordered actions, failure stops
      with describe_failure, capture keeps the last matching line,
      crash returns an error instead of raising;
      `verify_credential(provider_id, run)` + `first_model_id` → the
      one-turn model call, incl. the 4xx-rc-0 trap;
      `oauth_login(provider_id, exec)` → device-code dance: rc≠0 →
      describe_failure detail, exception propagates to the shell's
      guard;
      `save_and_verify(provider_id, key, store, run, on_stored=)` →
      store write → verify → verdict
- [x] screens.py shrinks to widget wiring: buttons call flow functions,
      map verdicts to pop/flash/status (146 stmts, from 191)

### 3b — tests

- [x] Deleted EVERY pilot/widget test class from test_firstsetup.py —
      the six added by the discarded pass AND the pre-existing
      SetupMenuPilotTests; PanelBodyTests too (a Screen is a widget)
- [x] New `ops/tests/test_firstsetup_flow.py`: the engine as plain unit
      tests — fake run/exec/store; skip, refusal, dispatch, capture
      keeps last line, action failure, crash guard, verify paths
      (ok / 401 / 400-rc0 / no-models / empty-reply-rc / own row),
      oauth login (done / cancelled detail from stderr / argv shape),
      save_and_verify (green / on_stored / unverified verdict / store
      failure propagates)
- [x] Kept the widget-free classes in test_firstsetup.py (forms
      validation, providers parsing, authstore round-trip, app-state
      setters, setup command) — split from CredentialVerificationTests
      which moved to the flow module

### 3c — accounting (measured 2026-11-20)

- [x] flow.py 100% · forms.py 100% · providers.py 100% · authstore.py
      96.67% — all ≥95
- [x] ACCEPTED UI-shell exceptions (no pilots, by operator decision):
      screens.py 32.88% · app.py 62.18% — widget wiring and reactive
      rows only; the decisions they carry live in flow.py (100%)
- [x] Verify: ops suite green (148 tests, 0.05s — the pilot harness
      cost 16s); ruff + mypy green; full `./run test` green

## Phase 6 — checkframework2: helper unit tests + new gate asserts

Helper unit tests (VM-only file by design — never mock the live stack;
these are the only unit-worthy parts):

- [ ] `refuse_if_prod` BASE_URLS parsing: loopback origin passes,
      non-loopback refuses, unparseable/missing BASE_URLS refuses
- [ ] `_agent_scratch_edit`'s regex patch of the home view: marker
      inserted before the FIRST return, idempotent on re-run, count≠1
      refuses
- [ ] The multipart body builder bytes in `_media_upload_roundtrip`
- [ ] `_assert_eq` alternatives parsing (space-separated alts)

New gate asserts (in-VM; ride the existing battery — volatile-test-
machine only). STOP for operator approval before running the gate:

- [ ] **1b** re-GET the redeemed login path with a fresh cookie jar →
      refusal (single-use, live; pairs with test_login_keys' model-level
      single-use test)
- [ ] **2b** anonymous `GET /` shows the signed-out warning copy
      ("You are not logged in" — feature from 1563266)
- [ ] **5b** in-container resource caps: `memory.max` ≈ 2G, `cpu.max`
      = 2 (pins 1563266's raw.lxc bake; provisioning drift fails gate)
- [ ] **5c** fresh VM: credential store absent + `pi auth login
      <bogus>` prints the `Providers: …` line (pins the exact mechanism
      ops/firstsetup/providers.py parses; breaks loudly on pi upgrades —
      that is the point)
- [ ] Bump the docstring's "eleven asserts" count + README gate section
- [ ] Verify: helper tests green in the ops suite; ONE
      `./run checkframework2` green end to end (operator-approved,
      destructive to volatile-test-machine only)

## Open question (operator hasn't answered)

One-line option from the dropped wiring phase: have checkframework1 RUN
the ops suite pass/fail (unmeasured — one `shell.run` line, no
fragments, no floor change) so the 125 ops tests can't silently rot.
Awaiting yes/no; not part of any phase until answered.
