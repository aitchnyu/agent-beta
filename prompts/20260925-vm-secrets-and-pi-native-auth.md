# VM secrets generated at provision + pi native auth; sentinel logic deleted

Status: IMPLEMENTED + VERIFIED (2026-09-25). This file is the implementation
prompt; the As-built deltas section records where the landed work differs.
Context: the TODO items `VAPID_PRIVATE_KEY="DANGEROUSLYUNSET" Generate in
provision along with db pass?` and `Pi's native login`, plus the design
discussion from the 2026-09-25 sessions (row_version work is separate/landed).

## Why

- Hand-filling machine secrets invites weak values, parks them in the host's
  `.env.vm`, and blocks provisioning until a human conjures entropy the machine
  could just make. None of `SECRET_KEY` / `DB_PASSWORD` / `VAPID_PRIVATE_KEY`
  needs human input.
- Production VMs are KEPT, not deleted: in-place re-provision (new code tree,
  same database, same secrets) is the deployment model. `testvm`'s
  build-only/delete-rebuild flow is a test-VM constraint, not the model.
- pi owns its auth and model choice natively: `/login` stores provider
  credentials in `~/.pi/agent/auth.json`; `/model` + Ctrl+S persists
  `defaultProvider`/`defaultModel` in `~/.pi/agent/settings.json`
  (pi 0.85.0 docs; `--model` flag overrides the saved default per run).
  With those, no env value is human-mandatory before provisioning — so the
  DANGEROUSLYUNSET sentinel system has nothing left to guard and dies.

## Design decisions (agreed with user, 2026-09-25)

1. **Auto-generated on the VM, write-once, never on the host**:
   - `SECRET_KEY` + `DB_PASSWORD`: `openssl rand -hex 32`, generated in
     `inside-vm.sh provision_app` right after tree extraction and BEFORE the
     postgres role is created.
   - `VAPID_PRIVATE_KEY`: `./run python manage.py generatevapid` in
     `deploy/vm-bootstrap.sh` (the venv/code only exist once the seed lands;
     services start only after bootstrap), written into the installed creds
     env before the `systemctl restart` step.
   - Generated only if absent in the installed `/etc/credentials/desmo/.env.vm`.
     Re-provision NEVER overwrites an existing generated value (write-once);
     it prints "keeping VM-generated SECRET_KEY/DB_PASSWORD/VAPID_PRIVATE_KEY".
     This keeps the DB role password, push subscriptions, and sessions valid
     across in-place upgrades.
   - Generated values are written into the INSTALLED env copy only
     (`root:desmo 640` as today); the host `.env.vm` and the tree tarball
     never carry them.
2. **`provision_app` becomes idempotent/re-runnable**: extraction must not
   clobber generated keys (preserve + print). `testvm` keeps its
   build-only refusal (disposable test instances) — that is the only
   delete-to-rebuild path that remains.
3. **Sentinel logic deleted entirely**:
   - Remove the generic DANGEROUSLYUNSET scans: host-side `./testvm`
     (provision lines ~103-113) and in-VM `inside-vm.sh` (~163-173).
   - Remove sentinel values + DANGEROUSLYUNSET mentions from all four env
     templates and docs (README secrets bullet, INSTRUCTIONS.md lines ~7-8).
   - Replacement safety net (not sentinel logic): after generation/merge,
     assert the three generated keys are non-empty in the installed env.
   - Templates ship real values/defaults for everything else; the three
     generated keys ship empty (`KEY=""`) marked "auto-generated on the VM".
   - `djangoproject/settings.py` VAPID handling: treat EMPTY as "push off"
     (currently maps the sentinel string to None). No sentinel strings in
     code after this.
4. **pi native auth (same change)**:
   - `ZAI_API_KEY` leaves both env templates (and the env contract). The
     one-time post-provision step is `/login zai` in the TUI as the desmo
     user → key lands in `~/.pi/agent/auth.json`. (pi still reads its native
     env vars if a user ever sets them — that stays pi's business, not our
     contract.)
   - `AGENT_MODEL` becomes an OPTIONAL override: keep the key in the
     templates with an empty default + comment. `./run pi` passes
     `--model "$AGENT_MODEL"` only when set; otherwise pi falls back to its
     saved `/model`+Ctrl+S default. The current hard refusal (run ~155-159)
     becomes a warning when `AGENT_MODEL` is unset (pointing at `/model`
     Ctrl+S). Do NOT refuse.
5. **Dev side behavior unchanged**: `./run init` still fills `SECRET_KEY`;
   dev `DB_PASSWORD` is the local postgres password; dev `VAPID_PRIVATE_KEY`
   optional-empty = push off. Comment updates only.

## Post-provision one-time setup (the human steps that replace env filling)

On the VM as desmo (documented in `deploy/access-steps.txt`):

1. `/login zai` — provider credentials → `~/.pi/agent/auth.json`.
2. `/model` + Ctrl+S — startup model → `~/.pi/agent/settings.json`.

## Touchpoints

- `testvm` — delete host-side sentinel scan; keep build-only refusal; keep
  knob/ALLOWED_HOSTS validation; tree build unchanged (templates now carry
  empty generated-keys).
- `deploy/inside-vm.sh` — delete in-VM sentinel scan; add generation
  (SECRET_KEY, DB_PASSWORD) + write-once preservation + idempotent
  re-runnability; postgres role creation consumes the generated DB_PASSWORD;
  post-merge non-empty assertion for the three keys.
- `deploy/vm-bootstrap.sh` — generate VAPID_PRIVATE_KEY (generatevapid) after
  uv sync, write into installed creds env (preserve-if-present), before
  services start.
- `run` — `pi()`: AGENT_MODEL optional (pass `--model` only when set; warn,
  don't refuse, when unset).
- `.env.example` + `.env.vm.example` — remove ZAI_API_KEY; AGENT_MODEL
  optional-empty; the three generated keys empty + "generated on the VM"
  notes; strip DANGEROUSLYUNSET prose everywhere.
- `djangoproject/settings.py` — VAPID empty-string → None (push off);
  comment no longer says "sentinel".
- Python VAPID check surface (logic already treats empty as off — these are
  dead code, machine-output, and wording):
  - `djangoapp/management/commands/generatevapid.py`:
    - DELETE the unreachable `--check` branch "set but sentinel — treat as
      unset" (settings maps sentinel/empty → None before `is_push_enabled()`
      sees it; the branch can never fire).
    - ADD a quiet, machine-readable output mode (e.g. `--quiet`: print ONLY
      the base64url private key token) — `vm-bootstrap.sh` captures stdout
      to write the env line; keep the human prose + paste instructions as
      the default output, reworded for dev-only pasting (the VM writes it
      itself now).
    - `--check` wording: "unset — browser push off" stays; no sentinel talk.
  - `djangoapp/models/notifications.py` — `is_push_enabled()` logic is
    already plain truthiness; drop "no sentinel" from its docstring and the
    "dev sentinel" phrasing in `notify_sessions` comments/log context.
  - `djangoapp/tests/test_notifications.py` + `test_notifications.py`
    docstrings that say "the dev sentinel default" — reword to "unset".
- `deploy/access-steps.txt` — add the two `/login` + `/model` steps.
- `README.md`, `INSTRUCTIONS.md`, TODO.md — doc updates; drop the two TODO
  lines.
- Tests: update anything asserting sentinel refusal behavior
  (checkframework2 asserts, guard tests referencing DANGEROUSLYUNSET).

## Phased checklist

### Phase 1 — templates + settings + VAPID check surface
- [x] Both env templates: remove ZAI_API_KEY; AGENT_MODEL optional-empty; the
      three generated keys empty + notes; zero DANGEROUSLYUNSET strings.
- [x] settings.py: VAPID empty → None (push off).
- [x] generatevapid.py: delete the dead "set but sentinel" `--check` branch;
      add `--quiet` key-only output for vm-bootstrap; reword paste prose
      (dev-only; VM writes it itself). Tests for the new mode.
- [x] notifications.py + test docstrings: drop "sentinel" wording.
- [x] INSTRUCTIONS.md / README.md wording.

### Phase 2 — generation + idempotent provision
- [x] inside-vm.sh: generate-if-absent (SECRET_KEY, DB_PASSWORD), write-once
      preserve, non-empty assertion; provision_app re-runnable; postgres uses
      the generated password.
- [x] vm-bootstrap.sh: generate-if-absent VAPID via
      `manage.py generatevapid --quiet`.
- [x] testvm: drop the sentinel scan only.

### Phase 3 — run + pi flow
- [x] run pi(): optional --model, warning-not-refusal.
- [x] access-steps.txt: /login + /model steps.

### Phase 4 — sweeps + verification
- [x] grep sweep: zero DANGEROUSLYUNSET outside prompts/ (historical records
      stay).
- [x] bash -n / zsh -n on all touched scripts; ruff/mypy; checkframework1 +
      checkproject green.
- [x] Live VM: fresh provision (secrets generated, services up, push works);
      second provision_app run over the existing VM (secrets preserved —
      compare before/after md5 of values, DB + subscriptions survive);
      `/login` + `/model` flow as desmo; `./run pi` starts on the saved
      model; AGENT_MODEL override still works when set.

## As-built deltas (2026-09-25)

- **AGENT_MODEL is gone from the env contract entirely** (user call, not
  optional-empty): no key in either template, no warning/refusal in
  `run pi()`. The override path is argument pass-through:
  `./run pi --model <provider/model>`. Assert-5's readability probe switched
  from `AGENT_MODEL` to the generated `SECRET_KEY`.
- **`--terse`, not `--quiet`** (user call): `manage.py generatevapid --terse`
  prints only the base64url token; tests in
  `djangoapp/tests/test_generatevapid.py` cover default output, terse output,
  the 32-byte scalar shape, and `--check`.
- **VAPID seeding lives in `deploy/vm.sh vapid-seed`** (root), invoked by
  `testvm` as step 6a after bootstrap — not in `vm-bootstrap.sh`, because the
  credentials env is root-writable only and bootstrap runs as desmo. It mints
  via the sanctioned `runasdesmo` wrapper and preserves existing values.
- **provision_app preserves VAPID across extracts too**: the extract lands
  the host's empty value, so an existing generated key is sed-restored
  (found by the idempotency dry run — without it, a re-provision would have
  silently killed every push subscription).
- **Idempotency hardening found by the kept-VM re-provision test**: postgres
  CREATE ROLE/DATABASE got `WHERE NOT EXISTS` guards; `git config --system
  safe.directory` switched to grep-guarded `--add` (a plain re-set errors on
  the multi-valued key).
- Live verification: framework suite 272 OK; fresh `./testvm provision`
  (secrets generated, `root:desmo 640`, units active, `generatevapid --check`
  derives); `vapid-seed` re-run keeps; full `provision_app` re-run over the
  kept VM — identical secret hashes before/after, services active;
  `./run checkframework2` green (fresh rebuild + all 9 in-VM asserts).

## As-built deltas round 2 (2026-09-25, later)

- **VAPID generation left Python entirely** (user call, "route A"):
  `deploy/inside-vm.sh gen-vapid-b64()` mints the base64url P-256 scalar
  with OpenSSL only (`genpkey` → `pkey -text` → extract `priv:` hex →
  left-pad → `\xNN` escapes → printf → base64url; no xxd, no Python, no
  venv — runs in provision_app BEFORE the seed lands). All three machine
  secrets now generate in one write-once block in `provision_app`;
  `vm.sh vapid-seed` and testvm's step 6a are deleted (playwright step
  renumbered 6b→6a).
- **`generatevapid` is gone; `checkvapid` replaces it** — verification only
  (unset / configured + derived public key + RFC 8292 subject). Dev docs
  (.env.example) point at the `gen-vapid-b64` recipe for optional local
  minting; `djangoapp/tests/test_checkvapid.py` covers the three report
  paths (tests for generation/`--terse` deleted with the functionality).
- Local sanity: three `gen-vapid-b64` runs (macOS LibreSSL) produce valid
  43-char tokens whose scalars derive through the app's own
  `vapid_public_key` math; VM sanity: `checkvapid` on the rebuilt VM
  derives a public key + subject from the openssl-minted value (note: the
  VM seed is `git ls-files`-driven, so checkvapid.py reached the VM via a
  manual transfer until committed).
- Re-verified after the change: framework suite 270 OK;
  `./run checkframework2` green (fresh rebuild, 9/9 asserts); kept-VM
  `provision_app` re-run — identical secret hashes (incl. VAPID), services
  active.

## As-built deltas round 3 (2026-09-25, later still)

- **VAPID is required, like DB_PASSWORD** (user call — "why is it even
  unset?"): settings reads `os.environ["VAPID_PRIVATE_KEY"]` with no
  empty→None mapping (missing key fails the boot; empty/malformed is
  runtime containment only — `is_push_enabled`/`vapid_public_key` degrade,
  in-app stays up). `./run init` now mints the dev key with the same
  openssl recipe as `gen-vapid-b64` (lockstep comment in both).
  Docs/tests reworded away from "optional in dev"; the notifications
  screenshot's committed PNG predates mandatory VAPID (noted in the test).
- Local dev .env re-minted compliant; `checkvapid` derives
  (public key + real mailto subject); suite 270 OK, ruff/mypy/eslint clean.

## As-built deltas round 4 (2026-09-25, final)

- **`checkvapid` deleted too** (user call): the app-side verifier went with
  generation; runtime warnings + the notifications page cover the rest.
- **All empty-key hedging removed** (user call: "as necessary as
  DB_PASSWORD"; containment removal superseded by round 5):
  `is_push_enabled` is GONE (model, exports, page props,
  subscribe gate, tests); `vapid_public_key()` no longer checks
  empty/None; `notify_sessions` lost its unset-skip branch; the page's
  `push_enabled` prop and the frontend "Unavailable on this server" card
  state are gone (zod schema + Notifications.vue updated;
  `docs/screenshots/notifications.png` regenerated). A missing env key
  fails the boot; provisioning/init refuse to proceed when the mint fails.
- **One canonical mint, no duplication** (sourcing superseded by round 5's
  executed script): `deploy/gen-vapid-b64.sh` holds
  the recipe; `run init` runs it from the repo, inside-vm.sh runs the
  tree-installed copy at `/usr/local/lib/desmo/` after extraction.
  `run init` hard-fails (rm .env + exit) when the mint fails.
- Verified: suite 264 OK, ruff/mypy/eslint/vue-tsc clean; full
  `./run checkframework2` green on a fresh rebuild (VAPID generated
  write-once, 9/9 asserts).

## As-built deltas round 5 (2026-09-26, agent-review fixes)

- Three review agents (security / bash+Python correctness / tests+docs)
  audited commit 9a207f6; verdict ship-worthy, findings fixed same day:
- `gen-vapid-b64.sh`: empty scalar extraction (openssl format drift) now
  REFUSES instead of left-padding to the invalid scalar 0; the mktemp PEM
  is trap-cleaned on every exit path (the explicit rm was the redundant
  one and is gone); "scrape" renamed to "extract", `hex` to `scalar_hex`.
- `run init`: openssl is REQUIRED — a missing binary refuses and deletes
  the half-configured .env instead of silently skipping the mints.
- `inside-vm.sh`: the three secret lines are rewritten by one awk pass
  with values in ENVIRON — no `/proc/*/cmdline` exposure and no sed
  metacharacter corruption of hand-rotated values; postgres adds a
  converging `ALTER ROLE … PASSWORD` (kept VM + regenerated creds
  realign instead of crash-looping).
- Doc rot swept: vapid-seed/generatevapid/AGENT_MODEL-era mentions, the
  "sourced" vs "executed" contradictions, `_deliver`'s stale VAPID-gate
  docstring, pi()'s env claim, testvm's tree/validation comments.

## As-built deltas round 6 (2026-09-26, build-only)

- **In-place re-provisioning ABANDONED** (user call: "overwriting seems
  dangerous and we aren't testing it"): provision_app now REFUSES before
  mutating anything when `/etc/credentials/desmo/.env.vm` already holds a
  non-empty generated secret (a file with all three empty = a half-failed
  pre-generation run; retry allowed). The write-once snapshot/merge block,
  the keep-vs-generate branches, and the converging `ALTER ROLE` are
  deleted — the round-2/round-3 kept-VM idempotency verifications are
  historical. Provisioning is build-only end to end (testvm refuses
  existing instances; inside-vm.sh is the belt-and-braces guard for any
  future driver); a production upgrade path gets designed deliberately
  when needed.

## Invariants

- A generated secret exists ONLY in the installed
  `/etc/credentials/desmo/.env.vm` — never host-side, never in the tree
  tarball, never in logs.
- No supported path rotates an existing generated secret. Rotation = edit the
  installed env by hand (documented for operators).
- The generic tripwire concept dies completely; no new sentinel strings.
