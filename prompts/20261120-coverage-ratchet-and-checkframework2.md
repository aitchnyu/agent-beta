# Coverage wrap-up: firstsetup tests + checkframework2 asserts

Nov 20, 2026 (updated 20:30). The coverage plan's working record. Phases
1-3 are DONE; ops/ is wired into the gate; only phase 6 (checkframework2)
remains. **Do not write code beyond what an item lists; stop each module
at ~95; nothing commits.**

## Done (for the record)

- Phase 1: dbstate/adapters/redis_client at 100% (makeloginlink +
  LoginKey single-use were already covered by 592fe19). Two pre-existing
  gate breakages unblocked: Home.vue Prettier drift + the stale
  playwright locator (both from 1563266).
- Phase 2 (reduced by operator ruling): only `ops/tests/
  test_scratch_commands.py` survives of the ops-infra test files;
  test_shell/test_testsuite deleted, the test_cli addition reverted.
- Phase 3: firstsetup engine extracted from the TUI — flow.py holds the
  verbs (get_model, wait_for_success_response, verify_provider,
  run_pi_oauth_login, create_superuser_with_link → UserCreated,
  store_google_oauth), screens are thin shells (UserScreen/GoogleScreen,
  no FormSpec, no pilots). flow/forms/providers 100%, authstore 96.67%,
  screens/app accepted UI-shell gaps.
- Redis test signal redesign: DESMO_TEST_REDIS, `_with_test_redis`,
  `_TEST_REDIS_URL`, and `TEST_REDIS_URL` are GONE. The URL itself is
  the signal — `clear_redis` flushes only a bare nonzero-DB URL
  (`^rediss?://[^/]+/[1-9][0-9]*$`; redis-py strips ALL path slashes, so
  the authority must stay slash-free); everything else refuses naming
  the URL. `test_redis_env()` (ops/scratch.py) is the single DB-2 owner.
- Commands emit only JSON: createuser (message/created/email/username),
  makeloginlink (message/login_url), listusers (message/page/pages/
  total/users). checkframework2 parses the JSON; no bash consumers, so
  no jq anywhere. flow's djangomanage calls capture stdout/stderr
  separately (stderr noise can't corrupt the JSON line) and parse
  login_url.
- Error messages everywhere: every bare `raise Http404` carries a
  fixed, non-revealing message (manage.py: one generic "not found";
  auth-shaped 404s never confirm existence; no request-derived echo).
  `shell.die`, cli's usage error, and postdeploychecks raise
  SystemExit(message) — the message rides the exception.
- Test rules (INSTRUCTIONS.md §Tests + steer.md checklist): method
  docstrings are point lists; errors pinned by message — assertRaises
  is GONE repo-wide; die-idiom/SystemExit sites pin the refusal text;
  dropped asserts from the sweep were restored via `as raised` (cli
  COMMANDS list, postdeploychecks exit-arg, addoauth both ids). Ruff
  ignores EM101/EM102/TRY003 — string literals may be raised inline.
- Playwright locators: text-located clicks replaced — files mode
  buttons via role+name inside the "View mode" group; the navbar Code
  dropdown via `data-testid="navbar-code"` (testId prop threaded
  CollapsibleButton → NavbarMenu → Layout). Text as ASSERTED content
  stays.
- ops/ wired into the gate: stage 1 runs `unittest discover -s ops/tests`
  measured (`--source=djangoapp,ourapp,ops` in stages 1-2);
  [tool.coverage.paths] ops = ["ops", "*/main/ops"] (no scratch entry —
  scratch tiers measure djangoapp only).
- Ratchet: measured 92.54/92.51 across two clean runs → floor set to
  92.50 (0.04 variance margin). Gate GREEN at the new floor. Accepted
  gaps priced in: checkframework1 28%, checkframework2 0%, shell 55%,
  testsuite 75%, screens 31%, app 61%.
- Python 3.15: .python-version + requires-python >=3.15 (containers
  fetch per the pin); README + inside-vm comment bumped. Toolchain and
  all suites green on 3.15.2.

## Standing rules

1. Per-module ceiling ~95% — no padding past it, no chasing 100.
2. `COVERAGE_RATCHET` is 92.50; raise only if coverage measurably
   improves; never lower it to make a regression pass.
3. Test style: INSTRUCTIONS.md §Tests — point-list method docstrings,
   `assertRaisesRegex` with the message pinned (die-idiom refusals pin
   the message riding SystemExit), tmp trees + fakes only, never the
   real VM, nothing destructive outside tmp.
4. An item is ticked only after its verifier passed. Never edit files
   while a gate run is in flight.
5. Everything stays uncommitted for operator review.

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
- [ ] Bump the docstring's assert count + README gate section
- [ ] Verify: helper tests green in the ops suite; ONE
      `./run checkframework2` green end to end (operator-approved,
      destructive to volatile-test-machine only)

## Out of scope, permanently

- Unit tests for `ops/checkframework2.py`'s VM-only body (gate(),
  _asserts_*, shims) — mocking the live stack tests a mock; its
  coverage is a real gate run.
- In-VM coverage collection of the gate itself.
- The `Select.BLANK` / declarative-TUI refactor thread in TODO.md.
