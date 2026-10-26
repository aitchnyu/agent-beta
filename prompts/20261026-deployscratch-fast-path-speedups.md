# deployscratch fast path: cut ~30s to ~12-15s

## Why

The fast path (frontend/docs-only diffs) costs ~30s per deploy on the
2-core VM: eslint 2-3s, build 8-10s, smoke 10-15s, rsync+own 3-5s,
collectstatic+baseurls 5-8s. The mockup stage pays this on every T2
iteration, and the smoke never visits `/mockup/*` — it guards framework
surfaces only.

## Levers (1, 3, 5 taken; 2, 4, 6 not)

1. **Skip the smoke for app-surface-only frontend diffs** — LANDED.
   `_framework_files` in run (one definition, reused by `_scratch_checks`
   and the fast path) filters a changed-file listing to framework files
   (`ourapp/` + `frontend/src/app/` is the app surface); an
   app-surface-only diff deploys on lint+build alone, printing the same
   skip message as `_scratch_checks`.
3. **Prune `.venv/` + `frontend/node_modules/` from the own sweeps** —
   LANDED. Both `find`s prune them like dbbackups; they never ride the
   deploy rsync, so re-owning ~50k files per deploy was pure waste.
5. **Native type-check** — LANDED, but not as the planned
   typescript@7 swap. Ecosystem reality (probed 2026-10-26):
   typescript-eslint peers `<6.1.0` (lint crashes on TS 7), vue-tsc
   requires the JS `typescript/lib/tsc` (TS 7 ships no such export).
   Dual setup instead: root `typescript ~6.0.3` (eslint + vue-tsc
   unchanged) + `typescript7` npm-alias (typescript@7.0.2 native) +
   `vue-tsgo --tsdk typescript7` as the `type-check` script.
   Measured on the dev Mac: full `npm run build` 4.0s (was ~8-10s for
   the type-check alone); vue-tsgo probes catch .ts and .vue errors,
   exit 1, clean tree exits 0. Also repaired: `vue-eslint-parser` range
   `^10.8.0` (never published) → `^10.4.1` (what the lock already had);
   vue-tsc `^3.2.4` → `^3.3.13`.
   Risk noted at review: `vue-tsgo@0.3.0` carries an npm deprecation
   notice — it is the type gate, so `type-check:tsc` (vue-tsc --noEmit,
   TS6) stays as the fallback script; exit plan is vue-tsc's own native
   tsgo support, else revert `type-check` to the fallback.
   Caveat found while wiring: the `*.vue` ambient shim in env.d.ts
   hides unresolved .vue imports from BOTH type-checkers — vite catches
   them; the build step stays the real gate for those.
6. **baseurls → echo** — REVERTED after measuring: the command costs
   0.84s warm / 3.4s cold on the VM, and inside a deploy it usually
   runs warm (collectstatic boots the same interpreter right before
   it). The ~1-3s honest saving wasn't worth duplicating the command's
   output parsing in bash; the real invocation stays.

Layout change this rode in on: `frontend/src` split into `app/`
(feature tree) + `system/` (framework) — commit `ed98c87` — which made
the app surface one prefix instead of an enumerated dir list.

## Verification status

- Host: vue-tsgo .ts/.vue error probes, clean-tree parity, lint green,
  `npm run build` green 4.0s, ruff format/check green, `run` syntax.
- VM (pending next deploy): before/after wall-clock of
  `./run deployscratch` for an app-surface-only diff (expect ~12-15s)
  and a framework frontend diff (still smokes); full battery once.

## Non-goals

- **`--keepdb` (lever 2) + `--no-sync` (lever 4)** — not taken; they
  only cheapen the smoke, which lever 1 removes from the common case.
- **Root `typescript@7`** — until typescript-eslint and vue-tsc speak
  the native package; the alias keeps them fed with 6.
- **Restructuring the smoke**, **collectstatic `--clear`** — unchanged.
