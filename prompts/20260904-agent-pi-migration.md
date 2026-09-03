# Replace goose with pi as the agent

Planned 2026-09-04, after the goose migration (prompts/20260904-agent-goose-migration.md)
— fourth agent-tooling cutover (opencode → crush → goose → pi). EXECUTED
the same day; the "As built" section below is the record. History note:
the operator squashed the whole migration (goose and pi phases alike) into
the single commit `1fee90f` ("Replaced Crush with Pi") — every hash cited
below (`ae7aa6d` — an earlier squash of the same title — plus
54ee81b, b45bc36, d2c6e7b, a983fae, 533790c, 55f0dd7, 7cf1c73, 3cfaaed,
c54fa77, ac48d68, b9a41c6, and the goose range 08fa3d1..308a25e) is a
dangling reflog object, kept here for narrative only. Decisions
recorded up front:

- **The launcher subcommand renames**: `./run goose` becomes **`./run pi`**
  (same dispatcher trick — `declare -F "$1"`).
- **Existing packages over custom code (operator directive, 2026-09-04
  14:37)**: the permission layer is `@gotgenes/pi-permission-system`
  (allow/ask/deny with TUI dialogs, tree-sitter bash decomposition,
  symlink-aware path gates, subagent ask-forwarding) and subagents are
  `@gotgenes/pi-subagents` (in-process children auto-registered with the
  permission system). The first implementation (custom guards shim exec'ing
  the Python policy + an adapted subagent example) was replaced by this on
  the operator's instruction; commit 54ee81b holds the intermediate state.
- **The Python guards are retired** with it: the whole policy lives in
  `.pi/extensions/pi-permission-system/config.json` (versioned,
  project-trust-gated); the 43-test suite and `.agents/` are gone. The
  port is behavior-complete modulo three accepted divergences (as-built).
- **A subagent plugin is a hard requirement** (operator directive
  2026-09-04): steer.md's review-your-work flow depends on spawning
  subagents; @gotgenes/pi-subagents + our project agents cover it, with
  asks forwarded to the operator's TUI (goose's hole closed).
- **steer.md stays the only steering file** (no AGENTS.md — pi auto-loads
  AGENTS.md/CLAUDE.md, so their absence must be preserved deliberately);
  injection rides the one remaining custom extension,
  `.pi/extensions/context/` (~25 lines — no catalog package does this).

## Why

- **The prompt tier comes back.** pi's `tool_call` extension hook can
  `{ block: true, reason }` AND call `ctx.ui.confirm(...)` mid-hook — a
  REAL operator approval prompt inside the guard, the exact three-state
  verdict (allow / ask / deny) crush had and goose's auto-mode design
  forced us to collapse into fail-closed blocks. steer.md's "propose it
  to the operator in chat" workaround could go back to "the TUI asks".
- **TypeScript extensions, project-local**: `.pi/extensions/*.ts`, loaded
  via jiti (no build step), hot-reloadable with `/reload`. Extensions can
  register tools, commands, intercept every event, and build TUI widgets.
- **Subagents are a first-class extension pattern**: the official examples
  ship `subagent/` ("Spawn sub-agents") — the agent spawns
  isolated sub-sessions as callable tools.
- **Native z.ai**: `/login zai` or plain `ZAI_API_KEY` env (no
  ZHIPU_API_KEY mapping — the env contract gets SIMPLER), `/model` picks
  glm-5.3.
- **Self-described minimalism**: small core, everything else extensions —
  philosophically close to this repo's launcher-centric design.
- Caveats kept in view: pi is TypeScript/Bun (not Rust/Go — correcting the
  earlier agent-CLI list), single-maintainer-origin project now under
  earendil-works (~102k stars, very active), and it ships **no built-in
  permission system** by design — our guards extension IS the policy
  layer, exactly like crush/goose before it.

## Probe gates (run BEFORE any code lands — verify against the INSTALLED
## binary, not docs; same discipline as the last two cutovers)

- [x] **P1 — tool_call verdict semantics + the trust trap.** In the TUI:
      allow (no return) runs; `{ block, reason }` denies with the reason
      reaching the model; `ctx.ui.confirm` prompts the OPERATOR in-TUI
      (the restored third tier). Then the trap: pi's **project trust**
      gate — headless `-p` runs with `defaultProjectTrust: "ask"` SKIP
      `.pi/extensions` entirely (guards silently absent!) unless
      `--approve`/`-a` or a saved `~/.pi/agent/trust.json` decision.
      Probe: (a) TUI first-run in the repo asks to trust (we want the
      opposite of crush's suppressed dialog — decide: pre-seed trust.json
      from `./run pi`? note trust.json is keyed by canonical dir, per
      user), (b) headless `-p` with `-a` loads the guards, (c) does
      `tool_call` fire for `!`-prefixed USER bash (docs say that's the
      separate `user_bash` event — confirm the guard covers it too),
      (d) input MUTATION works (event.input.command rewrite reaches
      execution — needed if we ever sanitize instead of block).
- [x] **P2 — subagent plugin coverage (the requirement).** Build/extend
      the `subagent/` example: spawn a sub-session as a tool, run a
      review-style task. Probe: do the PARENT's `tool_call` hooks fire
      for tool calls made INSIDE the subagent (goose's hole — if pi has
      the same hole, the guards extension must wrap the subagent's tool
      execution itself, which the extension API allows since subagents
      are just extensions); does the subagent inherit the system prompt /
      steer.md context or need it injected; concurrency limits.
- [x] **P3 — zai/glm-5.3 provider.** `ZAI_API_KEY` env + `/model` (or
      `--model zai/glm-5.3` / settings `defaultModel`) live roundtrip on
      dev; confirm the coding-plan endpoint is used automatically (z.ai's
      pi guide says /login zai OR env — verify env-auth hits the plan
      quota, and that `/login` isn't required when the env var is set).
      Verify model id format and that reasoning/thinking levels map.
- [x] **P4 — first-run, sessions, RSS, VM.** Cold start with ZAI_API_KEY
      set: no login wizard, no telemetry ask (find the opt-out), no
      update check surprise. Peak RSS on the 1GB VM during a long
      generation (Node/Bun runtime — expect heavier than goose's 131 MB;
      gate, not assumption). Session storage location (~/.pi/agent/) and
      whether an isolation knob exists (goose had GOOSE_PATH_ROOT; pi may
      need HOME override or XDG — probe; affects the nothing-touches-
      $HOME property).

## Every goose integration point → pi equivalent

| goose (at plan time; superseded) | pi equivalent | Mechanism |
|---|---|---|
| `GOOSE_PROVIDER`/`GOOSE_MODEL` split from AGENT_MODEL | `--model zai/glm-5.3` or settings `defaultModel`; AGENT_MODEL feeds it | CLI/settings |
| `ZHIPU_API_KEY` mapped from ZAI_API_KEY | **ZAI_API_KEY directly** (pi's native name) | env (mapping DELETED) |
| `GOOSE_MODE=auto` (no prompt tier existed) | nothing — the guards extension provides allow/ask/deny itself via tool_call + ctx.ui.confirm | extension |
| `.agents/plugins/guards/` plugin + hooks.json | `.pi/extensions/guards.ts` shim (+ keeps calling the same Python scripts) — trust-gated, /reload-able | extension |
| guards never fire in subagents (documented hole) | P2: cover via the subagent extension or accept+document | probe |
| `CONTEXT_FILE_NAMES='["steer.md"]'` | settings: context-files list — probe exact key (AGENTS.md/CLAUDE.md auto-load must stay absent) | settings.json |
| `GOOSE_PATH_ROOT=.goose` isolation | unknown — probe (HOME/XDG or accept ~/.pi/agent) | probe |
| `GOOSE_TELEMETRY_ENABLED=false` etc. | find pi's telemetry opt-out + update check disable | settings/env |
| `goose session` TUI (inline, scrollback-native) | `pi` TUI (pi-tui, differential rendering — full-screen? probe; either is fine) | TUI |
| `goose session -r` resume | `/resume` + tree navigation (sessions are JSONL files) | TUI |
| headless `goose run -t` | `pi -p "prompt"` (print mode; also --mode json/rpc) | CLI |
| VM: release tarball, arch-detected | `npm install -g --ignore-scripts @earendil-works/pi-coding-agent` (node 22 already on the VM) or standalone release binaries (Bun-compiled, version-pinned) — pick + pin | provisioning |
| `.goose/` state dir (gitignored, scratch-excluded) | `~/.pi/agent/` (+ trust.json, auth.json) unless P4 finds isolation | probe |

Tool names for the guards: pi's built-ins are `bash`, `read`, `write`,
`edit` (event.toolName strings; typed via isToolCallEventType) — probe
against the installed version like last time.

## Guard port design (superseded — see as-built; kept for the record)

The first cut kept `.agents/guards/*.py` as the single policy source with a
~60-line TS shim (stdin-JSON protocol, ctx.ui.confirm prompt tier,
headless-degrade-to-deny). The operator then directed existing packages;
the shim, the Python policy, and the 43 tests were retired in favor of
`.pi/extensions/pi-permission-system/config.json` — behavior-complete
except: in-cwd redirect targets run allowed (were ask), `VAR=val cmd`
prefixes are stripped-and-gated (were denied with a pointer), and
`rm scratch/*` greedily covers directories (single-file-only isn't
expressible). `.pi/extensions/context/` remains the only custom code.

## Subagent plugin (the requirement)

@gotgenes/pi-subagents (pinned 21.4.0 in .pi/settings.json packages):
in-process child sessions, auto-registered with the permission system —
per-agent policy enforcement and ask-forwarding to the parent's TUI
(headless parents can't answer → deny after forwardingTimeoutMs 10 min).
Builtins: general-purpose / Explore / Plan; our project agents ship in
`.pi/agents/` (scout, reviewer — read-only, permission-frontmatter'd).
The `subagent` TOOL itself is allowed outright (`"subagent": "allow"` in
the config) so spawns don't ask; everything the child DOES still goes
through policy.

## Codebase touchpoints (delta from the goose state)

1. **`run`** — `goose()` → `pi()`: preflight (pi on PATH, AGENT_MODEL
   still `zai/glm-5.3` — no split needed, ZAI_API_KEY passthrough — the
   ZHIPU mapping DELETED), guards shim + Python scripts present, exec
   `pi`. Decide trust pre-seeding (P1) vs `--approve` flag in the
   launcher. checkvm assert, _SCRATCH_EXCLUDES (`.goose/` → pi state
   dir), scratch restore line.
2. **`agentconfig/steer.md`** — identity line (`./run goose` → `./run pi`),
   guard paths (`.agents/...` stay! only the wiring text changes), the
   fail-closed block wording → back to prompt wording IF P1 confirms the
   confirm-tier, tool names (shell → bash tool), subagent section
   rewrite (the hole note goes away or stays per P2).
3. **`deploy/inside-vm.sh`** — goose tarball block → pi install (npm
   global or release binary; keep version pin + the arch lesson);
   `.env.vm.example` + `.env.example` agent sections (simpler: ZAI_API_KEY
   is native, no ZHIPU mapping).
4. **`.gitignore`** — `.goose/` → pi state dir (or nothing if state is
   global-only); keep `.agents/plugins/guards/` (still the policy source).
5. **README.md, deploy/agent-login.txt, deploy/access-steps.txt,
   testvm** — one-line sweeps.
6. **New in-repo artifacts**: `.pi/extensions/guards/index.ts`,
   `.pi/extensions/subagent/`, `.pi/settings.json`,
   `deploy/tests/test_pi_guards.py` (shim-level tests: verdict
   translation incl. the confirm tier via headless `-p` where confirm
   degrades to block/deny — assert THAT explicitly, it's the headless
   contract).
7. **Deletes at cutover**: none (goose artifacts stay until the
   side-by-side period ends — the Python guards are shared; only
   hooks.json/plugin.json become goose-only).
8. Final sweep both ways: `grep -rn "goose"` (live files) and
   `grep -rn "run goose"` — prompt-history files and the goose
   migration's as-built excepted (they're records).

## As built (2026-09-04)

Pinned: **pi 0.85.0** (npm `@earendil-works/pi-coding-agent`, npm global
on dev + VM) · `@gotgenes/pi-permission-system@31.0.1` ·
`@gotgenes/pi-subagents@21.4.0` (both declared in `.pi/settings.json`
`packages`, project-trust auto-install into `.pi/npm/` — verified on a
clean root). Two phases: custom-implementation (commit 54ee81b, E2E-verified)
then the operator-directed pivot to existing packages (this state).

**Probe results (all measured, none assumed):**
- **P1 — trust trap is real**: headless `pi -p` with default project
  trust silently skips `.pi/extensions` AND packages (the permission
  system included) — `touch marker` ran with zero policy. `--approve`
  fixes it; the launcher passes it unconditionally. In-TUI: the
  permission system's ask renders a real y/s/b/n/r dialog.
- **P2 — subagents**: children run in-process, registered with the
  permission system; asks FORWARD to the parent's UI (headless parents
  can't answer → deny, 10-min forwardingTimeoutMs). Verified: scout
  spawn, steer-aware answer, clean return. The `subagent` tool itself
  needed `"subagent": "allow"` — the delegation surface hit the universal
  `ask` and died headless before that.
- **P3 — zai**: `ZAI_API_KEY` env + `--model zai/glm-5.3` verbatim
  (AGENT_MODEL passes through — no splitting, no key renaming; the env
  contract got SIMPLER than goose's). Live roundtrips on dev.
- **P4**: first-run has no wizard with env auth; peak RSS 150 MB (Node)
  vs goose 131 MB vs crush 81-86 MB — fine on 2G+swap. Sessions land in
  `/sessions` (repo root, gitignored — `sessionDir` resolves against the
  cwd, not `.pi/`); `~/.pi/agent/` keeps only trust.json + auth.json.

**Key facts for the policy port** (all from the permission-system docs,
spot-verified live): bash chains are decomposed per-command with real
parsing (tree-sitter), substitutions/subshells/heredoc-interpolations
evaluated, wrappers (`bash -c`/`eval`/`sudo`/`xargs`/`find -exec`)
floored to ask, unparseable → ask (fail-closed), `VAR=val` prefixes
stripped before matching, deny-with-teaching-reason supported, `x *`
patterns also match the bare `x`, last-match-wins with the `*` catch-all
first. Path gates match referenced + cwd-normalized + symlink-resolved
forms (traversal/symlink evasion dead). Project config loads only under
project trust — same story as the extensions, handled by `--approve`.

**Retired with the pivot**: `.agents/guards/*.py` (the crush-lineage
policy), `deploy/tests/` (43 guard tests), the checkframework1 unittest
block, the pyproject `.agents` globs. steer.md's permission sections now
point at the config.json `bash` map; the env-prefix guidance softened to
"prefer export" (the gate strips prefixes instead of denying).

**Left deliberately:**
- The three accepted divergences (in-cwd redirects, env prefixes,
  greedy rm globs) — documented above.
- `forwardingTimeoutMs` stays at the 10-min default: lowering it would
  time out a slow operator answering a forwarded subagent ask in the TUI;
  headless E2E just needs allowlist-clean subagent tasks.
- The notification bell TODO — a natural `agent_settled` extension later.

**Postscript (same day, evening — folded into the `1fee90f` squash):**
- First live VM session surfaced friction, fixed as found: read-only
  TOOL allows (`read`/`ls`/`find`/`grep`/`sed -n *` — subagent read tools
  were riding the extension surface into the `"*": "ask"` catch-all and
  forwarding to the operator, 5 dialog rounds); the bare `../scratch`
  external_directory entries; `fd` pre-install; `playwrighttest` now
  forwards test labels (steer.md's own subset example was a silently
  ignored no-op before); Playwright harness timing (`_DEFAULT_TIMEOUT_MS`
  2s + 15s cold-start budget — the suite's 1s default was calibrated on
  dev hardware and flaked deterministically on the VM).
- Two z.ai stream stalls (SSE truncation without a terminal event)
  wedged turns mid-thinking; Ctrl-C deadlocks on the stuck stream —
  SIGKILL + `reset` recovers, sessions survive. Upstream: pi issues
  #8996/#8997 (fixed for the proxy transport only), #8705, #6789; the
  zai thinking-handler bug #8706/PR #8707. Watch for the direct-path fix
  and upgrade the pin.
- Workflow rules added to steer.md: stage gates are now "choice menu as
  the message's last line" (the question tool never existed in pi),
  progress tracking is a checklist in messages (no todos tool either),
  and **a green `deployscratch` IS the whole verification** — no
  post-deploy e2e runs; the operator verifies live pages.
- A second agent review (2026-09-05) verified the squashed tree end to
  end (policy config, wiring, steer rules, sweeps) — clean except the
  doc fixes folded into this postscript's commit.

## Cutover order (checklist)

- [x] 0. P1–P4 probes pass (pi 0.85.0; results in the as-built above).
- [x] 1. Policy ported + local gates green (ruff, mypy, Django suite,
      frontend, Playwright via `./run checkframework1`; guard unit tests
      retired with the Python policy).
- [x] 2. Subagents: package builtins + project agents; scout spawn,
      steer-aware, ask-forwarding verified.
- [x] 3. `run pi()` + steer.md + env examples + trust story; E1–E5 headless
      E2E green (allow / deny-with-reason / ask-degrade / steer injection /
      subagent).
- [x] 4. VM: re-provision, verify as the agent user (packages auto-install,
      live verdicts, RSS), `./run checkframework2` green.
      → gate green; on-VM: pi 0.85.0 on agent PATH, .pi/npm auto-populated
      on first trusted run, allow/deny/ask-degrade verified as agent,
      peak RSS 158 MB.
- [x] 5. Sweeps, commit, goose removal decision.
      → commits 54ee81b (custom phase), b45bc36 (package pivot), d2c6e7b
      (model pin dropped — AGENT_MODEL is the single knob, provider-
      agnostic; subagents inherit the parent model). goose UNINSTALLED
      from dev (brew, 327.5 MB freed); no state dirs remained (the
      GOOSE_PATH_ROOT isolation meant it never touched $HOME); the
      rebuilt VM never had it. Its artifacts live only in git history.

## Verification checklist (both machines)

- [x] `./run pi` preflight refusals: pi missing, AGENT_MODEL unset,
      policy config/context extension missing — each refuses clearly.
      (ZAI_API_KEY is NOT launcher-checked: auth rides pi's native env
      handling and pi itself fails loudly — deliberate.)
- [x] Policy ACTIVE headless (trust story: launcher `--approve`) and in
      subagents (ask-forwarding; deny when headless).
- [x] The ask tier: headless degrades to deny with a clear reason
      (E3); TUI dialog verified interactively.
- [x] Model is zai/glm-5.3 from env; live roundtrips.
- [x] steer.md is the only context file (no AGENTS.md pickup; injection
      via `.pi/extensions/context/`).
- [x] grep sweeps clean (records excepted) + VM half after provisioning.

## Risks / open decisions (post-cutover resolutions inlined)

- **Trust gate vs headless silence** — the goose approve-mode lesson
  generalizes: a config layer that CONDITIONALLY loads is a policy hole.
  RESOLVED: the launcher passes `--approve` unconditionally (deterministic
  trust; the shim-era checkvm-assert idea went away with the shim — the
  package auto-installs on trust, which the E2E asserts directly).
- **Node runtime RSS on the 1GB VM** — RESOLVED by measurement: 158 MB
  peak (goose 131 MB, crush 81-86 MB) on 2G RAM + 2G swap.
- **Bus factor / velocity**: pi moves fast under one primary author +
  company (earendil); pin versions, re-probe P1/P2 on bumps (same rule
  as crush 0.91 and goose 1.49.0). STILL LIVE.
- **The shim's exec boundary** — MOOT: the TS-spawning-Python shim was
  retired with the package pivot; no per-tool-call process anymore.
- **Session state in $HOME** (~/.pi/agent: auth.json, trust.json) —
  RESOLVED as accepted: sessions themselves land in the repo-root
  `/sessions/` (gitignored, rsync-excluded); $HOME keeps only the two
  tiny state files, env auth means auth.json stays empty.
- **Keep goose installed side-by-side during a comparison week?** —
  RESOLVED: uninstalled at cutover (brew; no state remained anywhere).
