# Replace Crush with goose as the agent

Planned 2026-09-04. Research done (docs study at goose-docs.ai — goose moved
to the Agentic AI Foundation 2026-04-07, GitHub `aaif-goose/goose`; this file
is the migration plan. Extracted from the crush→goose research session
following prompts/20260824-agent-crush-migration.md — third agent-tooling
cutover (opencode → crush → goose). Decisions recorded up front:

- **The launcher subcommand renames**: `./run agent` becomes **`./run goose`**
  (run's dispatcher is `declare -F "$1"`, so renaming `agent()` → `goose()`
  IS the rename — no dispatch table to touch).
- **steer.md stays the only steering file** (no AGENTS.md, no `.goosehints`)
  via `CONTEXT_FILE_NAMES='["steer.md"]'` exported by `./run goose`.
- **The guard classifiers port verbatim** — only the I/O shim changes; goose's
  `PreToolUse` protocol is nearly crush's (exit 2 + stderr = deny,
  `{"decision":"allow"}` stdout = allow).
- **The env contract stays**: `ZAI_API_KEY` + `AGENT_MODEL="zai/glm-5.3"`,
  both `.env*` files unchanged in KEYS (comments rewritten).

## Why

- TODO.md pain points goose answers natively: "resume old session?" →
  `goose session --resume/--fork/-r` + `session list/export`; "notifications
  bell?" → `Stop` / `AfterShellExecution` hooks are built for exactly that
  (crush had no equivalent); "not showing command output" → `GOOSE_DEBUG`,
  `GOOSE_SHOW_FULL_OUTPUT`, `/r`.
- Hooks are plugin-based and PROJECT-scoped (`.agents/plugins/<name>/` —
  versioned in our repo), not a cwd-fragile `.crushrc` line.
- Env-first config: `GOOSE_PROVIDER`/`GOOSE_MODEL`/`GOOSE_MODE` env vars have
  top priority over `~/.config/goose/config.yaml` — the setenv flow maps
  directly.
- No in-repo state dir: sessions/data live globally
  (`~/.local/share/goose/`), so the whole `.crush/` gitignore/rsync/exclude
  apparatus disappears.

## Probe gates (run BEFORE any code lands — same discipline as the crush
## cutover: verify against the INSTALLED binary, not docs)

- [ ] **P1 — hook verdict semantics (the dangerous one).** In crush, silent
      exit 0 = no opinion → permission prompt. In goose, exit 0 + EMPTY
      stdout counts as an ALLOW. There is no documented abstain verdict; the
      docs only guarantee "no decision" for malformed/unrecognized output
      (candidates: `{"decision":"ask"}` stdout; exit 1 with no stdout —
      noisy). Probe with a scratch plugin on a live session: (a) does
      allow-JSON bypass the `GOOSE_MODE=approve` prompt? (b) does a
      no-decision hook leave the approve-mode prompt intact? (c) which
      abstain idiom is clean and does `on_failure: block` treat it as a
      failure (it must NOT — the prompt tier would become a deny tier)?
      THE MIGRATION DOES NOT PROCEED until P1 has a verified answer.
- [ ] **P2 — project plugin discovery.** `.agents/plugins/<name>/` loading is
      young (announced 2026-05). Probe on the pinned version: plugin loads
      when goose starts from the repo root; do hooks also fire from
      subdirectories (crush 0.91 silently skipped its whole config there)?
      What is the hook process cwd (drives whether guard paths may be
      relative — cf. crush nit 20)? Timeout default 30 s good enough?
- [ ] **P3 — z.ai provider.** goose has NO built-in Z.AI provider (GLM only
      via aggregators: Novita `zai-org/glm-5.1`, Avian, EmpirioLabs, SayGM).
      Chosen design: custom provider JSON (`engine: openai`,
      `api_key_env: ZAI_API_KEY`, base_url = z.ai OpenAI-compatible endpoint,
      glm-5.3 in `models`) shipped in-repo, installed by the `./run goose`
      preflight — keeps `AGENT_MODEL="zai/glm-5.3"` meaningful. Probe: live
      roundtrip with glm-5.3 tool-calling through goose's openai engine.
      Fallbacks: env-only `GOOSE_PROVIDER__HOST`/`GOOSE_PROVIDER__API_KEY`
      against the same endpoint; or switch provider entirely (anthropic /
      openrouter — then .env.example key docs change).
- [ ] **P4 — first-run prompts + memory.** Cold start with
      `GOOSE_PROVIDER`/`GOOSE_MODEL`/`GOOSE_TELEMETRY_ENABLED=false` exported
      must NOT open the provider wizard or the telemetry consent ask (the
      goose analog of crush's "initialize this project" dialog +
      `.crush/init` hack). Also measure peak RSS on the 1 GB VM during a long
      generation (crush: 81–86 MB; goose is Rust, expect fine — gate, not
      assumption).

## Every crush integration point → goose equivalent

| Crush (current) | goose equivalent | Mechanism |
|---|---|---|
| `.crushrc` `model large "${AGENT_MODEL:?…}"` | `GOOSE_PROVIDER=zai` + `GOOSE_MODEL=glm-5.3` (parsed from AGENT_MODEL by `./run goose`, or via the custom provider id) | env beats config.yaml |
| `option context-path agentconfig/steer.md` | `CONTEXT_FILE_NAMES='["steer.md"]'` (looks up filenames in the cwd hierarchy — root steer.md matches) | env |
| `permissions allow view ls grep glob web_search` | per-tool Always-Allow via hooks (or `permission.yaml` — global, interactive: REJECTED as primary, not versionable) | hook |
| `permissions deny lsp_* references` + `option auto-lsp false` | moot — goose's developer extension has no LSP tools | — |
| `option metrics false` | `GOOSE_TELEMETRY_ENABLED=false` | env |
| hook `^bash$` → `deploy/crush_bash_guard.py` (env `CRUSH_TOOL_INPUT_COMMAND`) | plugin `PreToolUse` matcher `^developer__shell$` → guard reads stdin JSON `.tool_input.command`; allow → stdout `{"decision":"allow"}`; deny → exit 2 + stderr (SAME as crush); prompt-tier → the P1 abstain idiom | hook |
| hook `^(edit\|write\|multiedit)$` → `deploy/crush_edit_guard.py` (env `CRUSH_TOOL_INPUT_FILE_PATH`) | matcher `^developer__(edit\|write)$`, stdin `.tool_input.path`; scratch-glob logic unchanged | hook |
| permission prompt tier (silent exit 0) | `GOOSE_MODE=approve` + tool-level ask on `developer__shell` / `developer__text_editor` | mode |
| `.crush/init` first-run suppression | none needed if P4 passes (env pre-answers) | env |
| `command crush "$@"` | `exec goose session "$@"` (TUI) | cli |
| `.crush/` state dir (gitignore, rsync excludes, scratch checkout restore) | gone — global state; `.agents/` is tracked content | — |

Tool names (`developer__shell`, `developer__text_editor`, `developer__edit`,
`developer__write`, `developer__read`?, search/websearch tool names) must be
confirmed against the installed version (`goose info -v`) before finalizing
matchers + steer.md wording — same rule as last time.

## Guard port design

- New layout: `.agents/plugins/guards/{plugin.json, hooks/hooks.json,
  scripts/}` — the two Python guards move here from deploy/ (self-contained
  plugin, no cwd dependence); hooks.json wires both PreToolUse rules with
  `on_failure: block` (fail CLOSED — matches the refuse-loudly preflight
  philosophy; only safe once P1 confirms the abstain idiom isn't a
  "failure").
- Shim changes per guard (~30 lines each): input env var → stdin JSON;
  output: allow-JSON only on allowlisted verdicts; exit 2 + stderr on denies
  (unchanged); ABSTAIN for the prompt tier per P1. The classifier core
  (shlex sections, allowlists, find/rm rules, 80-char gate) ports VERBATIM.
- Unit tests `deploy/tests/test_crush_guards.py` → `test_goose_guards.py`:
  same subprocess contract, feed stdin instead of env; exit-code/stderr/
  allow-JSON assertions survive as-is; + new cases for the abstain idiom and
  malformed-stdin fail-closed.
- pyproject per-file-ignores: `deploy/crush_*.py` glob → the new guard
  paths (T201 stays — stdout IS the protocol).

## Codebase touchpoints

1. **`run`** — `agent()` → `goose()`: preflight rewrite. `goose` on PATH →
   AGENT_MODEL nonempty (split `provider/model` → GOOSE_PROVIDER/GOOSE_MODEL
   exports) → plugin dir + both guard scripts present and executable
   (replaces the `.crushrc` `bash -n` gate) → custom provider JSON installed
   (if P3 route) → first-run-suppression exports → `exec goose session
   "$@"`. Competing-config refusal (`~/.config/goose/config.yaml` etc.) is
   REPLACED by env-priority (env beats config) — but still consider
   `GOOSE_PATH_ROOT` pointing at a gitignored in-repo dir to isolate
   config+data+state entirely (open decision D2). Sweep the `agent` word in
   run:95-96 comment, checkvm assert 5/6 (`command -v crush` → `goose`,
   run:339-346), `_SCRATCH_EXCLUDES` drops `--exclude='.crush/'` (run:429),
   scratch checkout restore drops `.crush` (run:472).
2. **`agentconfig/steer.md`** — line 3 "You are the Crush TUI agent
   (`./run agent`)" → goose TUI (`./run goose`); ~10 spots: guard paths
   (35, 769-771, 777, 788, 807), tool names — `bash` → the shell tool,
   `write`/`edit` → goose's editor tools, `web_search` → verify name, the
   "crush runs them concurrently" claim (875-876) → re-verify for goose.
   The allowlisted-command list itself is unchanged (same guard core).
3. **`deploy/inside-vm.sh`** — `_CRUSH_NPM_VERSION` + `npm install -g
   @charmland/crush@…` (24-26, 64-68) → pinned goose CLI install (deb asset
   from GitHub releases via `dpkg -i`, or `download_cli.sh` with
   `GOOSE_VERSION`; keep the lockstep-with-dev comment; dev installs via
   `brew install block-goose-cli`). Revisit the ripgrep-for-crush comment
   (56-58) — check whether goose's search tool wants rg too (apt line
   stays either way).
4. **`deploy/agent-login.txt:18`** — "start the Crush TUI" + `./run agent` →
   `./run goose`, "start the goose TUI".
5. **`deploy/access-steps.txt:12`** — same sweep.
6. **`.env.example:33-44` + `.env.vm.example:34-45`** — section header
   "Crush agent" → goose agent; comments rewritten (built-in-providers
   sentence → custom-provider/env story; `crush models` reference → provider
   list pointer). KEYS UNCHANGED (ZAI_API_KEY, AGENT_MODEL sentinels ride).
7. **`pyproject.toml:96-107`** — guard-path glob rename + the "Crush
   PreToolUse hooks" comments → goose.
8. **`.gitignore:31-36`** — drop the `.crush/*` block; add the goose state
   dir only if D2 (GOOSE_PATH_ROOT) lands in-repo.
9. **README.md:7,37-38`** — Crush link/mentions → goose
   (github.com/aaif-goose/goose); install line `npm install -g
   @charmland/crush` → brew/CLI install.
10. **testvm:155,237`** — comment sweeps only (phase list, seed-exclude
    comment mentions `.crush/`).
11. **Delete at cutover**: `.crushrc`, `.crush/README.md`, `.crush/init`,
    `deploy/crush_bash_guard.py`, `deploy/crush_edit_guard.py` (after the
    plugin copies land), `deploy/tests/__pycache__` stale bytecode.
12. **New in-repo artifacts**: `.agents/plugins/guards/*`,
    `deploy/tests/test_goose_guards.py`, custom-provider JSON (P3 route).
13. Final sweep both ways after code changes: `grep -rn "crush\|Crush"` and
    `grep -rn "run agent"` (TODO.md is user notes — leave).

## Cutover order (checklist)

- [x] 0. P1–P4 probes pass on a throwaway local goose install (pinned
      version recorded here when chosen); abort/report if P1 has no clean
      abstain idiom or P3 roundtrip fails.
      → DONE, 2026-09-04, goose 1.49.0 (brew). See "As built".
- [x] 1. Guards ported to `.agents/plugins/guards/` + tests green locally
      (`uv run python -m unittest discover -s deploy/tests -v`), ruff +
      `./run typecheck` clean.
- [x] 2. `run goose()` rewritten (preflight per design D1/D2); steer.md,
      agent-login.txt, access-steps.txt, env example comments swept.
- [x] 3. Local verification: full `./run checkall` green; live `./run goose`
      session — allowlisted `git status` unprompted, `rg` denied with
      reason, unknown compound PROMPTS (P1 behavior confirmed in-situ),
      scratch edit unprompted, model is glm-5.3 via z.ai.
      → checkframework1 green; live headless E2E on the repo verified
      allow/deny/block tiers (the "prompt" tier is a block — see As built).
- [x] 4. VM: inside-vm.sh install swap; re-provision; guard tests on VM;
      live `./run goose` as the agent user from /srv/app/main; RSS measured
      (P4); `./run checkframework2` green.
      → checkframework2 green (all 6 asserts); 43 guard tests green as
      agent; headless roundtrip + allow/deny verified on the VM; peak RSS
      131 MB (crush: 81–86 MB; 2G RAM + 2G swap absorbs it).
- [x] 5. Deletes + sweeps (touchpoints 11, 13); both example envs still
      DANGEROUSLYUNSET-correct; commit.
      → commits 08fa3d1, a90ab58, 00d9be9, c75e9fe.
- [x] 6. As-built section appended here (deviations, probe results, pinned
      version) — this file becomes the record, like 20260824's.

## Verification checklist (both machines)

- [x] `./run goose` preflight refusals: goose missing, AGENT_MODEL
      unset/empty, guard scripts missing/non-executable — each refuses with
      a clear message, no TUI start.
- [x] Model resolution: session uses env-pinned provider/model on BOTH
      machines (goose info -v / session log).
- [x] Guard unit tests wired into `./run checkall`, green on both machines.
- [x] First-run prompts: fresh HOME/config on the VM agent user → `./run
      goose` opens straight into the session (no wizard, no telemetry ask).
- [x] In-session spot-checks: prompt tier prompts; allows allow; denies
      deny with reason reaching the model; session resume
      (`goose session -r`) works — the TODO.md ask.
      → the prompt tier is a BLOCK by design (As built); resume ships with
      goose (`goose session -r`/`--fork`); allow/deny/block confirmed live
      on dev + VM.
- [x] grep sweeps clean (provenance comments in the guards' "ported from"
      notes and prompt history files excepted).

## As built (2026-09-04)

Pinned: **goose 1.49.0** (brew on dev; release tarball on the VM).
Docs: goose-docs.ai (goose moved to the AAIF 2026-04-07; repo
github.com/aaif-goose/goose).

**Probe results (all measured, none assumed):**
- **P1 — the big one.** PreToolUse hooks execute with full authority in
  `goose run` AND in `goose session` under **auto** mode. In **approve**
  mode the TUI prompts on EVERY tool call (even `todo_write`) and never
  executes PreToolUse hooks — a hook allow cannot suppress the prompt.
  Therefore: `GOOSE_MODE=auto` is mandatory, and goose has NO three-state
  verdict. The crush prompt tier became an explicit
  `{"decision":"block","reason": "propose to the operator in chat"}` —
  fail-closed, per operator decision 2026-09-04. Deny channel is
  IDENTICAL to crush: exit 2 + stderr reason.
- **Tool names:** the docs' `developer__shell` naming is stale in 1.49.0 —
  the platform tools are bare `shell`, `write`, `edit` (verified from hook
  payloads). hooks.json matchers: `^shell$`, `^(write|edit)$`.
- **P2:** project plugins load from `<project>/.agents/plugins/<name>/`
  in run AND TUI mode; hooks fire from subdirectories too; hook cwd = the
  session working dir.
- **P3:** z.ai is a BUILT-IN provider in 1.49.0 ("Z.ai GLM-5.3" shipped
  in this exact release) — no custom provider JSON needed. Its key var is
  `ZHIPU_API_KEY`; `./run goose` maps `ZAI_API_KEY` → `ZHIPU_API_KEY`
  when the provider is zai (env contract unchanged). Live roundtrip
  verified on dev + VM.
- **P4:** fresh `GOOSE_PATH_ROOT` + env-pinned provider → no first-run
  wizard, no telemetry ask. Peak RSS on the VM: **131 MB** vs crush's
  81–86 MB.

**Deviations / discoveries beyond the plan:**
1. **PEP 758 trap (cost one debugging round):** the repo targets Python
   3.14, where `except A, B:` is legal — so `ruff format` strips the
   parentheses from `except (A, B):`. Unit tests run under uv's 3.14
   (green), but goose ran the hooks via `#!/usr/bin/env python3` → an
   older stock python → SyntaxError → exit 1 → `on_failure: block` denied
   everything. Fixes (both): hooks.json invokes
   `${PLUGIN_ROOT}/../../../.venv/bin python` (project venv, 3.14, same
   on both machines), and the guards use the paren-stable
   `except (...) as _exc:` form (parens are mandatory with `as`, so ruff
   can never strip them). Same failure class as crush round 5's py3.9
   crash — the interpreter is now pinned, not ambient.
2. **VM install: CLI tarball, not the deb.** The goose deb hard-depends
   the desktop GUI stack (gtk-3/nss/gbm/xdg-utils) — unsatisfiable and
   unwanted on a headless server. And the tarball arch must be detected:
   the multipass VM is **arm64** on Apple Silicon (npm's arch-agnostic
   install hid this in the crush era; the first attempt shipped an
   x86_64 binary that `command -v` happily found). GNU tar also needs the
   member name `./goose`, not `goose`.
3. **GOOSE_PATH_ROOT adopted** (D2 resolved yes): all goose state
   (config/, data/sessions, state/logs) lives in the gitignored repo-local
   `.goose/` — strictly stronger than the old competing-config refusal;
   nothing touches `$HOME`. Sessions are inspectable
   (`.goose/data/sessions/sessions.db`, sqlite) — the TODO "resume old
   session" also has `goose session -r`.
4. **Session-behavior env:** GOOSE_DISABLE_SESSION_NAMING=true (no
   background naming model call) rides along with the plan's
   telemetry/keyring/mode exports.
5. **Subagent hole, documented in steer.md:** subagent tool events don't
   emit PreToolUse hooks (and auto mode runs what isn't blocked) — the
   compensating note tells the agent to keep subagent commands to the
   allowlisted forms (same acceptance as the crush era's equivalent hole).
6. **ttyd-era text swept** while in here (operator request): steer.md's
   Security section no longer claims a "superuser-only Django proxy";
   stale `test_agent_auth` bytecode removed; vm.sh/access-steps/login
   banner updated. `.env.vm` (the live filled copy) header comment
   refreshed to match the new example.
7. **Committed at cutover** (required: the VM seed tarball is
   `git ls-files`-driven — untracked `.agents/` would not ship, and
   tracked-but-deleted `.crushrc` fails tar loudly): 08fa3d1, a90ab58,
   00d9be9, c75e9fe. (History note: the operator later squashed the goose
   and pi migrations into the single commit `1fee90f`; the hashes above
   are dangling reflog objects, kept for narrative.)

**Left deliberately:**
- The TODO.md bell/notification ask → a `Stop` / `AfterShellExecution`
  hook in the guards plugin is the natural home; not in scope here.
- `permission.yaml` untouched (global, interactive, not versionable) —
  all policy lives in the plugin + env, exactly as planned (D1).

## Risks / open decisions

- **D1 — where policy lives**: hooks carry allow/deny; the prompt tier rides
  `GOOSE_MODE=approve` + tool-level ask. Decided AGAINST `permission.yaml`
  as primary (global file, interactive `goose configure`, not versionable).
  Open: which read-tools get hook-allows vs rely on approve-mode's read
  classification.
- **D2 — full isolation via `GOOSE_PATH_ROOT`**: pointing it at a
  gitignored in-repo dir replaces the old competing-config refusal entirely
  (all config/data/state under it) but is documented under "Development &
  Testing" — probe before relying on it; else keep a light
  `~/.config/goose/config.yaml` absence check.
- **Hook authority**: only `PreToolUse` (and `Stop`) can block;
  `BeforeShellExecution`/`BeforeReadFile` are observation-only — guards stay
  on PreToolUse. Subagent-internal calls: re-verify whether goose hooks fire
  there (crush's didn't; same acceptance: default-ask is the barrier).
- **Goose velocity**: project plugins + hooks are recent (2026-05); the
  AAIF move is fresh. Pin versions in provisioning AND dev; re-probe P1/P2
  on every bump.
- **Model-fit caveat**: goose docs say it works best with Claude models;
  glm-5.3 via openai-engine custom provider is unproven (P3 gates).
- **Notifications**: the TODO bell ask is post-cutover work (a `Stop` hook
  calling the terminal bell) — noted here so it isn't lost, NOT in scope.
