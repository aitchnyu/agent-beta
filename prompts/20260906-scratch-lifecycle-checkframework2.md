# Test the scratch lifecycle (createscratch/deployscratch/cleanscratch) in checkframework2

Planned 2026-09-06, from TODO.md:55 ("Test `createscratch`, `deployscratch`,
`cleanscratch`"). Investigation done; design + checklist below.

## Why

The scratch cycle is the agent's ONLY edit path on the VM (steer.md § The
scratch workflow), yet nothing exercises it end to end. checkframework2
already rebuilds the VM and proves agent-user readiness (asserts 5-6: pi on
PATH, credentials env, playwright launch) — but the three commands the agent
actually lives in are untested. Real-session failures have all lived exactly
there: protected-hardlink `cp -al` dying halfway on the VM (run:450-462's
hollow-.venv archaeology), app-owned 644 files breaking the agent's deploy
rsync, identity/env resolution during the scratch bootstrap. A fresh-VM gate
is the only place these reproduce faithfully (dev on the Mac owns both trees
and never hits them).

## Findings (what the investigation established)

- **The real path is the agent user**, not app: on the VM the operator runs
  `sudo -iu agent` in `/srv/app/main` and drives `./run
  createscratch|deployscratch|cleanscratch` from there (steer.md:208-252,
  agent-login.txt lands the login shell in main/). Everything the cycle needs
  as agent is already provisioned and asserted:
  - `/srv/app` is 775 app:app, agent is in the app group (inside-vm.sh:39-43)
    → agent can create `/srv/app/scratch`.
  - agent holds full NOPASSWD sudo (testvm sudoers tree file) → deployscratch's
    `sudo rsync`/`chown`/`chmod`/`systemctl restart` tail (run:525-539) is
    non-interactive.
  - credentials env is root:app 640 → `setenv` resolves in every scratch
    command as agent (this is literally assert 5).
- **The VM-only code paths get exercised only as agent**: `_link_or_copy_tree`
  falls back to full `cp -a` (Linux protected_hardlinks block `cp -al` of
  app-owned .venv/node_modules); deployscratch's sudo-rsync + re-own + g+w
  branch (run:518-530). Testing as app or root would silently skip both.
- **Bootstraps are viable on a fresh VM**: DB_USER has CREATEDB (the battery's
  `test ourapp` creates its test DB over TCP), STATIC_ROOT="staticfiles" is
  relative → resolves under main/, which deployscratch has just `chmod -R g+w`'d
  BEFORE collectstatic runs (run:525-534) — ordering already correct for agent
  writes. uv/npm on secure_path; scratch's git is agent-owned so no
  dubious-ownership (inside-vm.sh:237-238 additionally safe.directory's
  /srv/app/scratch for the app user's git viewer).
- **A no-op deployscratch is cheap to make live-provable**: the Books test
  app's home view (`djangoapp/tests/testapp/ourapp/views/home.py`) ships props
  that land in the Inertia page JSON embedded in the HTML body — the same
  channel assert 4 greps "Framework Smoke" through. The testapp ships NO
  `ourapp` tests of its own (`tests/` is empty) and `home.py` is inside
  `ourapp/`, so a one-line marker prop:
  - keeps the framework-file watch quiet (no scratch-test-subset detour),
  - passes the battery (ruff format/mypy clean: plain dict assignment),
  - and, being Python view code, is served only after deployscratch's granian
    restart — grep-after-deploy proves deploy AND restart, not just rsync.
- **Cost**: the added wall time is dominated by the agent-side scratch build
  (full `cp -a` of .venv + node_modules, cold uv/npm caches in /home/agent)
  plus the battery (cold mypy/eslint/tsc/vite on the 2G VM) — order ~10 min on
  top of the existing gate. Accepted: this is the deployment gate and the
  TODO asks for exactly this. (Cache-sharing tweaks are out of scope.)
- **Conventions to honor**: guest bodies >2 lines live as named functions in
  `deploy/vm.sh` § agent user (INSTRUCTIONS.md § Multipass helpers); assert
  banners stay one-per-failure-abort under `set -e`.

## Design

Three new asserts appended after the current 6 (cheap read-only HTTP checks
stay first; the mutating, expensive cycle goes last). Banners renumber /6 →
/9; the `vm.sh` § agent user section gains four thin wrappers (env + repo cwd
via `_vm_env`, then main's `./run …`) so every call site stays a one-liner
gated on exit code:

- **Assert 7/9 — createscratch as agent**: `agent-scratch-create` = `_vm_env;
  ./run createscratch`, then verify `/srv/app/scratch` exists and
  `git -C /srv/app/scratch rev-parse --verify scratch-baseline` resolves (the
  framework-file watch precondition, run:389-390), echo `agent createscratch
  OK`. Call site greps the OK line like assert 6's probe.
- **Assert 8/9 — deployscratch as agent, deploy provably live**:
  1. `agent-scratch-edit`: idempotent `sed -i` inserting
     `props["scratch_marker"] = "scratch-deploy-live"` before the
     `return InertiaResponse` line in `/srv/app/scratch/ourapp/views/home.py`
     (grep-guarded so a rerun no-ops), echo the confirmation.
  2. `agent-scratch-deploy`: `_vm_env; ./run deployscratch` — exit code is
     the assert (the full battery runs inside; nothing deploys red).
  3. Host-side liveness: `systemctl is-active app_granian.service`, then curl
     `/` with the existing cookie jar (`--retry 10 --retry-delay 2
     --retry-connrefused` to absorb the restart race) and grep
     `scratch-deploy-live`. The DB-backed session survives the restart, so
     the jar from Setup 4 is still a superuser session.
- **Assert 9/9 — cleanscratch as agent**: `agent-scratch-clean` = `_vm_env;
  ./run cleanscratch`, then `[ ! -e /srv/app/scratch ]`, echo OK; call site
  greps it.
- **Optional guard sub-assert** (cheap, no battery): before assert 7's create,
  run `cd /srv/app/scratch && ./run deployscratch` style refusal once scratch
  exists — expect `_require_main_run`'s nonzero refusal (run:493-498) — and/or
  deployscratch-before-createscratch's "Run createscratch first" refusal
  (run:514). Take both only if they stay one-liners; otherwise skip.

## Checklist

- [ ] deploy/vm.sh — § agent user, after `agent-playwright-probe`:
    - [ ] `agent-scratch-create` — `_vm_env`, `./run createscratch`, dir +
          `scratch-baseline` ref checks, OK line
    - [ ] `agent-scratch-edit` — grep-guarded marker insert into
          scratch's `ourapp/views/home.py`, confirmation line
    - [ ] `agent-scratch-deploy` — `_vm_env`, `./run deployscratch`
    - [ ] `agent-scratch-clean` — `_vm_env`, `./run cleanscratch`, dir-gone
          check, OK line
- [ ] run — checkframework2:
    - [ ] header comment "Assert 1-6" → 1-9 (run:235-236)
    - [ ] renumber existing `=== Assert N/6 ===` banners → `/9`
    - [ ] Assert 7/9 (create), 8/9 (edit+deploy+is-active+curl grep marker,
          reusing `cookie_jar`), 9/9 (clean) per Design
    - [ ] optional refusal sub-asserts (only if one-liners)
- [ ] README.md — checkframework2 bullet (~line 346): mention the scratch
      lifecycle cycle among what the gate smokes.
- [ ] steer.md — nothing (checkframework2 stays operator-only, run:870 note
      untouched; the scratch commands were already allowlisted for the agent
      in .pi/extensions/pi-permission-system/config.json:47-49).

## Out of scope

- Shared uv/npm caches for the agent user (would cut the ~10 min; a knob like
  UV_CACHE_DIR under /srv/app is a separate, measurable change).
- Dev-side (non-VM) scratch-cycle testing — `checkproject` already runs two
  `_new_scratch` cycles locally (run:564-592); only the VM-only paths lack
  coverage, and that is what these asserts add.
- Any behavioral change to createscratch/deployscratch/cleanscratch
  themselves — this is test-only.

## Verification

- [ ] `bash -n run deploy/vm.sh` parses; `./run lintfix` + `./run typecheck`
      green (repo untouched by the marker edit — it happens only inside the
      VM's scratch copy).
- [ ] Operator (destructive, operator-only per steer:870): `./testvm delete
      && ./run checkframework2` → all 9 asserts green, including
      `scratch-deploy-live` visible on `/` after the cycle, and no
      `/srv/app/scratch` remaining afterwards.
- [ ] Watch the added wall time on one run; if it exceeds ~15 min, file the
      cache-sharing follow-up rather than trimming asserts.
