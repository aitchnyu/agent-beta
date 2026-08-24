# Replace opencode with Crush as the agent

Planned 2026-08-24. Research done; this file is the migration plan. The
cutover COMPLETED the same day (see the as-built cutover section), then
two same-day reworks (env knobs → built-in providers) and three review
rounds followed — all recorded below. Extracted from the
agent-tooling discussions following Follow-up 16 of
prompts/20260818-vm-provisioning-multipass.md — different concern,
different work.

## Why

- **Memory**: opencode (bun) measured ~493 MB RSS on the 1 GB VM — 52% of
  total RAM, 1 GiB swap in active use; upstream has a maintainer-run
  memory megathread (anomalyco/opencode#20695) with 1–2 GB growth reports.
  Crush is a compiled Go binary; expected far lower RSS — **must be
  measured on the VM before cutover** (gate, not assumption).
- **Permissions**: Crush's `PreToolUse` hooks get the raw command
  (`CRUSH_TOOL_INPUT_COMMAND`) and file path
  (`CRUSH_TOOL_INPUT_FILE_PATH`) and can allow / deny / fall through to
  prompt. That expresses our whole bash allowlist + edit path-scoping as
  **testable Python in our repo** instead of opencode's undocumented matcher.
- **Subagents**: built-in `agent` tool (opencode's was denied) — the
  "review what I did so far" requirement.
- **Env-native config**: crushrc IS Bash — `--api-key "$ZAI_API_KEY"`,
  `model large "$AGENT_MODEL"` directly; no `{env:…}` substitution
  indirection (the thing Follow-ups 14–16 fought).

## Every opencode permission → Crush equivalent

| opencode.json (current) | Crush equivalent | Mechanism |
|---|---|---|
| `"model": "{env:OPENCODE_MODEL}"` | `model large "${AGENT_MODEL:?…}"` | crushrc is Bash — env read directly |
| `"instructions": ["agentconfig/steer.md"]` | `option context-path agentconfig/steer.md` | crush also auto-reads AGENTS.md/CRUSH.md — do NOT create either (steer.md stays the only steering file) |
| `"read": "allow"` | `permissions allow view` | native |
| `"glob": "allow"` | `permissions allow glob` | native |
| `"grep": "allow"` | `permissions allow grep` | native |
| `"list": "allow"` | `permissions allow ls` | native |
| `"edit": {"*": "ask", "scratch/**": "allow", "/srv/app/scratch/**": "allow"}` | hook `^(edit\|write\|multiedit)$` → `deploy/crush_edit_guard.py` (as-built): normpath() first (closes `scratch/../main` traversals), then scratch globs (relative `scratch/*`, `*/scratch/*`, absolute `/srv/app/scratch/*`) → `{"decision":"allow"}`; else silent (exit 0, no output) → prompt | hook |
| `"external_directory": {…scratch…}` | **n/a — no equivalent concept**. Crush has no FS sandbox; tools run as the OS user (dev: you; VM: `console`, group-write-scoped to `/srv/app`). The edit-guard hook covers the prompt-suppression half; nothing enforces a hard boundary | — |
| `"bash": {"*": "ask", …30 exact/prefix allows…, "rg *": "deny", "perl *": "deny"}` | hook `^bash$` → `deploy/crush_bash_guard.py` (as-built): exact + prefix allows → allow; `rg`/`perl` bare or with args → exit 2 with reason; everything else silent → prompt | hook |
| `"bash"` compound handling (opencode decomposes `&&`/`\|\|`/`;`/`\|` and checks each segment) | **guard's own policy**: any compound metachar (`&& \|\| ; \| > < $( ) backtick newline`) → silent → prompt (fail-closed), PLUS exact-string allows for the sanctioned compounds steer.md mandates (`cd ../scratch && ./run checkscratch` etc.) | hook |
| `"doom_loop": "allow"` | nothing — Crush has built-in loop detection (internal/agent/loop_detection.go), no documented toggle | native |
| `"task": "deny"` | **DECISION: allow** (that's the point — review subagents). Crush's subagent tool is `agent`. Subagent-internal bash calls bypass hooks but hit the normal permission flow (prompt) — safe default. If parity-strict is preferred: `permissions deny agent` | native |
| `"todowrite": "deny"` | `permissions deny todos` | native |
| `"question": "deny"` | `permissions deny question` | native |
| `"webfetch": "ask"` | leave un-allowed → default ask. Verify exact tool name (`fetch` vs `web_fetch`) in the TUI tool list at implementation time | default |
| `"websearch": "allow"` | `permissions allow websearch` (verify exact name — source suggests `websearch`) | native |
| `"lsp": "deny"` | `option auto-lsp false` + `permissions deny lsp_definition lsp_symbols lsp_call_hierarchy lsp_rename lsp_replace_symbol lsp_restart` (six LSP tool files in crush source; deny is deterministic even if a server appears) | native |
| `"skill": "deny"` | no global skill tool in crush; skills auto-load from default dirs (`.agents/skills`, `.crush/skills`, …) — we ship none; disable builtins per-name with `option disable-skill <name>` if any surface | native |

Tool-name spellings (`view ls grep glob bash edit write multiedit fetch
websearch question todos agent`) must be confirmed against the installed
version's tool list before finalizing the two hooks + deny lines.

## The two guard hooks (IMPLEMENTED 2026-08-24)

Python executables (`#!/usr/bin/env python3`, +x) — unit-testable, ruff +
`./run typecheck` clean. Both speak Crush's hook protocol: stdout
`{"decision": "allow"}` = pre-approve (no prompt); exit 2 + stderr =
deny (model sees the reason); silent exit 0 = no opinion → permission
prompt.

- `deploy/crush_bash_guard.py` — matcher `^bash$`, env
  `CRUSH_TOOL_INPUT_COMMAND`. **Compound-aware (reworked 2026-08-24 on
  request):** shlex (posix + punctuation_chars) tokenizes the command;
  `&&`/`||`/`;`/`|`/`&`/subshell parens/newlines split it into SECTIONS;
  verdict = strictest section: any DENY → exit 2 (reason names the denied
  section), any PROMPT → silent (permission prompt), all ALLOW →
  `{"decision":"allow"}`. Section classification: redirects (`>` `<`
  `>>` `>&`) and `$(…)`/backticks force prompt; `export NAME=VALUE …`
  (assignments/bare names) allows; otherwise the exact/prefix allowlist
  ported verbatim from opencode.json; `rg`/`perl` first word denies.
  `ENV=VAL command` prefixes do NOT match the allowlist — the passing
  form is `export ENV=VAL && command` (steer.md documents both in a
  ```bash block, and the allowlisted commands as one too). Quoted spans
  stay whole (an operator inside quotes is an argument); newlines are
  normalized to `;` so no command can hide inside an allowed section;
  dangling separators and unbalanced quotes → prompt. The old
  SANCTIONED_COMPOUNDS set is gone — `( cd ../scratch && ./run
  checkscratch )` now passes generically (both sections allowed).
- `deploy/crush_edit_guard.py` — matcher `^(edit|write|multiedit)$`, env
  `CRUSH_TOOL_INPUT_FILE_PATH`. normpath() first (so
  `scratch/../main/x.py` cannot ride the patterns), allow iff the
  normalized path matches `scratch/*`, `*/scratch/*`, or
  `/srv/app/scratch/*`; else silent → prompt.

Unit tests: `deploy/tests/test_crush_guards.py` — 32 tests (25 before
the 2026-08-24 shlex rework) that execute
both hooks as subprocesses exactly as Crush does (stdout/exit codes ARE
the contract). Covered: every allowlist family (exact, prefix, bare
bases, sanctioned compounds); fail-closed on every metachar shape
(`&&`, `|`, `;`, `>`, `$()`, backtick, newline); a sanctioned compound
extended by a third segment still prompts; near-miss lookalikes
(`git statusx`, `rm -rf scratchx`, `npm run buildx`) prompt; rg/perl
deny with lookalikes (`rgit`, `perlix`) NOT denied; scratch-path allows
incl. VM-absolute and nested; traversal, lookalike (`scratchfoo/`), and
empty paths prompt; executable-bit wiring. Run:

```
uv run python -m unittest discover -s deploy/tests -v
```

Supporting config (also landed): pyproject.toml per-file-ignores —
`deploy/**/*.py` INP001 (scripts dir, not a package);
`deploy/crush_*.py` T201 (print IS the protocol channel);
`deploy/tests/**/*.py` PLR2004 + S603 (exit codes are the protocol;
subprocess is the point). Note: bare `uv run mypy deploy/…` file-targets
crash the django-stubs plugin — type-check via `./run typecheck`
(`mypy .` with env sourced), which is the repo's real gate.

## Env design (api keys + model/provider from env)

New env vars (replace the OPENCODE_* pair everywhere):

```
AGENT_MODEL          # provider-qualified BUILT-IN id, e.g. "zai/glm-5.3"
<PROVIDER>_API_KEY   # the provider's NATIVE env var (ZAI_API_KEY for
                     # z.ai, OPENROUTER_API_KEY for OpenRouter, …) —
                     # crush's built-in catalog defines the name
```

**Final design (same-day, second rework): BUILT-IN providers only.** z.ai
turned out to be a crush built-in (`id: "zai"` — same coding-plan
endpoint `api.z.ai/api/coding/paas/v4`, key via `ZAI_API_KEY`, glm-5.3 in
catalog), so `.crushrc` shrank to ONE line of policy input: `model large
"${AGENT_MODEL:?…}"`. No `provider add`/`model add`, no base URLs, nothing
persists into ~/.local/share/crush/ (this also explains the earlier
"cached provider" quirk: the custom `provider add` had been persisting
there — moot now). Switching provider = set its native key var +
`AGENT_MODEL=<builtin-id>/<model>` in the env file. Verified live on
BOTH machines via virgin data dirs / synced VM (provider "zai",
glm-5.3). `run` preflight checks AGENT_MODEL only; missing provider keys
fail loudly inside crush itself.

- `.env` / `.env.vm`: real values; `.env.example` / `.env.vm.example`:
  ACTIVE `DANGEROUSLYUNSET` sentinels (minors round; the provision scan
  refuses on them; dev fills them in like SECRET_KEY).
- The API key must NOT appear in this or any committed file.
- ~~Provider wiring (base URL fixed…): …/api/coding/paas/v4, type
  `openai-compat`, id `zaicoding`.~~ **SUPERSEDED by the built-in-providers
  design above** — no provider wiring exists anywhere; the shipped id is
  the BUILT-IN `zai`.

## `.crushrc` (repo root, versioned — replaces agentconfig/opencode.json)

> **SUPERSEDED (2026-08-24, two reworks later)** — the block below was the
> FIRST design (custom provider, env-auth). The SHIPPED .crushrc uses ONLY
> built-in providers: one policy line, `model large
> "${AGENT_MODEL:?…}"`, plus context-path/options/permissions/hooks. See
> the "Final design" paragraph above. The block stays as history.

```bash
# Agent config for Crush. Runs at startup with our env sourced (.env via
# ./run agent / .env.vm via the console on the VM). Project-level config
# has top priority; ~/.config/crush/crushrc still MERGES — run agent
# preflight refuses if one exists.
provider add zaicoding --type openai-compat \
  --base-url "https://api.z.ai/api/coding/paas/v4" \
  --api-key "${ZAI_API_KEY:?Refusing: ZAI_API_KEY unset — see .env.example}"
model add zaicoding/glm-5.2 --name "GLM 5.2" --context-window 200000
model add zaicoding/glm-5.3 --name "GLM 5.3" --context-window 200000
model large "${AGENT_MODEL:?Refusing: AGENT_MODEL unset — provider-qualified, e.g. zaicoding/glm-5.2}"

option context-path agentconfig/steer.md
option auto-lsp false
option metrics false

permissions allow view ls grep glob websearch
permissions deny todos question
permissions deny lsp_definition lsp_symbols lsp_call_hierarchy lsp_rename lsp_replace_symbol lsp_restart

hook add PreToolUse --matcher "^bash$" \
  --command "./deploy/crush_bash_guard.py" --name bash-guard
hook add PreToolUse --matcher "^(edit|write|multiedit)$" \
  --command "./deploy/crush_edit_guard.py" --name edit-guard
```

Crush state: data dir defaults to `.crush/` under the CWD (repo root) —
add `.crush/` to `.gitignore` AND to `_SCRATCH_EXCLUDES` in `run`
(createscratch/mergescratch must not copy it).

## Codebase touchpoints

1. **`run` `agent()`** — rewrite preflight: `crush` on PATH; `.crushrc`
   present; `ZAI_API_KEY` + `AGENT_MODEL` nonempty (setenv already sources
   the right env file); refuse if `~/.config/crush/crushrc` exists (global
   config merges into project config — same competing-config rule as
   opencode's); then `exec command crush "$@"` from repo root. Drop the
   OPENCODE_CONFIG_DIR/OPENCODE_CONFIG plumbing and `debug config`
   validation (verify instead via `crush` starting and `model large`
   printing — crushrc's `:?` lines are the validation).
2. **`.env`, `.env.vm`, `.env.example`, `.env.vm.example`** — swap
   OPENCODE_AUTH_CONTENT/OPENCODE_MODEL for ZAI_API_KEY/AGENT_MODEL
   (comments rewritten: crushrc reads env natively; unset key/model =
   refuse at startup).
3. **`agentconfig/`** — delete `opencode.json` at cutover (after Crush is
   verified on both machines). `steer.md` stays (referenced by
   context-path).
4. **`agentconfig/steer.md`** — sweep: "opencode TUI agent" → Crush;
    `agentconfig/opencode.json` refs → `.crushrc` + `deploy/crush_bash_guard.py`;
    the allowlisted-command list stays (it documents the same guard);
   "opencode runs them concurrently" phrasing; "question tool is disabled
   (`question: deny`)" → still denied, wording; pipes/redirects note —
   Crush guard also prompts on `|`/`>` (keep the rule); add: sanctioned
   compound forms (`cd ../scratch && ./run checkscratch`) are exact-match
   allowed — use them verbatim, not variations.
5. **`deploy/inside-vm.sh`** — `_OPENCODE_NPM_VERSION` block →
   `npm install -g @charmland/crush@<pinned>` (keep the lockstep-with-dev
   comment; dev installs via brew).
6. **`deploy/ttyd.service.in`** — Environment= lines: drop
   OPENCODE_CONFIG_DIR/OPENCODE_CONFIG; ZAI_API_KEY/AGENT_MODEL arrive via
   the shared EnvironmentFile (.env.vm) — update the comment block that
   names the OPENCODE_* vars.
7. **`.env.vm` staging in `testvm`** — no change in mechanism; content
   swap per (2). The `.crushrc` + the WHOLE deploy/ dir (guard hooks
   included, exec bits preserved by tar) ship in the seed tarball —
   AS-BUILT: no tree-staging installs; the tree carries /etc + /tmp
   content only (see testvm's tree comment).
8. **`deploy/console-bashrc`** — `./run agent` help line: "(opencode
   TUI)" → "(Crush TUI)".
9. **`.gitignore` + `run` `_SCRATCH_EXCLUDES`** — add `.crush/`.
10. **README / INSTRUCTIONS.md** — any opencode mentions swept (grep
    `OPENCODE\|opencode` after the code changes; TODO.md is user notes —
    leave).
11. **`pyproject.toml`** — [DONE 2026-08-24] per-file-ignores for
    deploy/ hooks + tests (see the guards section).

## Cutover order (ALL DONE 2026-08-24)

- [x] 1. Local: `npm install -g @charmland/crush` (v0.91.0 — no brew
      formula; npm on both machines keeps lockstep simple). Tool names
      + hook env vars confirmed against the installed BINARY, not docs:
      search tool is `web_search` (docs' `websearch` is wrong for
      0.91.0); also added `references` to the LSP-adjacent denies.
- [x] 2. `.crushrc` written (glm-5.2 default, glm-5.3 registered for
      later switching); guard hooks landed earlier + wired into it;
      `.gitignore` + rsync excludes carry `.crush/`; env vars swapped in
      all four env files (BOTH machines pin zaicoding/glm-5.2) [at the
      time; final state after the reworks: `zai/glm-5.3`, see above].
- [x] 3. `run agent()` rewritten: crush on PATH → .crushrc exists +
      `bash -n` parses → no competing config (repo `crushrc`,
      `.crush.json`/`crush.json`, global `~/.config/crush/*`, and — since
      the minors round — `/etc/crush/crush.json`) → AGENT_MODEL nonempty
      (auth rides the provider's NATIVE env var, not checked here) →
      `exec crush`. Steer.md, console-bashrc swept.
- [x] 4. Local verification: full `./run checkall` green (168 backend +
      25 hook + 25 Playwright); live `crush run` through zaicoding →
      glm-5.2 (verified in `.crush/logs/crush.log`); peak RSS during a
      1500-word generation: **86 MB** (opencode: ~493 MB).
- [x] 5. VM re-provisioned twice: first build hit a transient npm
      registry ETIMEDOUT (@vue/server-renderer fetch — network, not
      config; clean rebuild succeeded). Guard tests on VM: 25/25. Live
      `crush run` as console from /srv/app/main: glm-5.2, 7s roundtrip;
      peak RSS during a long generation: **81 MB**.
- [x] 6. `agentconfig/opencode.json` deleted; provisioning installs
      @charmland/crush@0.91.0; `grep -rn OPENCODE\|opencode` clean
      outside provenance comments (guards' "ported from" notes) and
      prompt history files.
- [x] 7. Follow-up 17 recorded in prompts/20260818-vm-provisioning-
      multipass.md; this section is the as-built record.

## Verification checklist (both machines)

- [x] `./run agent` preflight refusals (unset env, competing config,
      missing binary/config) + syntax gates — verified locally.
- [x] Live model resolution: `crush run` used the env-pinned model on
      BOTH machines (request log / crush.log; curl roundtrips from the
      VM). Currently `zai/glm-5.3` everywhere (was `zaicoding/glm-5.2`
      until the same-day rework; `zaicoding/` spellings in the SUPERSEDED
      blocks below are historical).
- [x] Guard unit tests: 32/32 on BOTH machines (25 pre-rework); wired into
      `./run checkall`; full checkall green locally (VM: tests only —
      the Django/Playwright suites are main/'s, unchanged).
- [x] `.crush/` state dir: created per-project after sessions; ignored
      by git; excluded from scratch rsync AND (after one stale-state
      import, hand-cleaned on the VM) from the seed tarball in testvm.
- [x] Memory: crush peak RSS — local 86 MB, VM 81 MB (opencode ~493 MB;
      ~6× lower; swap pressure gone).
- [ ] In-session interactive spot-checks (need the real TUI, first use):
      `git status` unprompted; `rg` denied with reason; a compound with
      a metachar PROMPTS; scratch edit unprompted; `question`/`todos`
      absent; the `agent` (subagent) tool works and its bash calls
      prompt.
- Gotchas recorded: `crush run` non-interactively READS STDIN until EOF
  (piped-input mode) — scripted harnesses must redirect `< /dev/null`
  or it hangs with no output (cost an hour of false "crush hangs on the
  VM" debugging). The npm wrapper spawns the Go binary with
  `cwd: process.cwd()` — run it FROM the repo dir, not a dir the user
  can't traverse (EACCES red herring).

## Risks / open decisions

- **Memory is unproven** — the primary motivator; measure before
  committing (step 4 gate).
- **Hooks fire only on the TOP-LEVEL agent** — subagent-internal tool
  calls skip the guards (they still hit normal permission prompts).
  Acceptable: subagents default-ask on bash; do not auto-allow bash for
  subagent use.
- **Compound policy is section-decomposed** (rework of the original
  prompt-by-default design): compounds of ALL-allowed sections run
  unprompted (`cd ../scratch && git diff HEAD~1` now allows); one unknown
  section still prompts the whole line; redirects/substitution always
  prompt. Zero glob-trick surface remains: operators are real shlex
  tokens, quotes are respected, newlines normalized.
- **`agent` tool allowed vs opencode's `task: deny`** — deliberate change
  (review-subagent requirement). Reversible via `permissions deny agent`.
- **crushrc is trusted shell code** — it runs with user privileges at
  startup; same class of trust as the repo's `run` script. Fine here;
  noted for the record.
- **Crush velocity** — hooks/config are young (PreToolUse is the only
  event today); pin the version in provisioning and re-verify guards on
  upgrades.
- steer.md's `/git/…` + `/files/…` viewer links are our app's, not the
  agent's — unaffected.

> ## Review round 1 (2026-08-24, 3 parallel subagent reviewers) — BLOCKERS fixed
>
> Findings numbered 1-22 (3 BLOCKER, 5 MAJOR, 9 MINOR, 5 NIT); full list
> in the session transcript. Blockers fixed same day:
>
> 1. **Comment-smuggling bypass** (`crush_bash_guard.py`): shlex's default
>    `commenters='#'` stripped `#…` to EOL even MID-WORD —
>    `git status#; rm -rf /` tokenized as bare `git status` → ALLOW while
>    bash ran the rm (verified by reviewer + reproduced pre-fix). Fix:
>    `lexer.commenters = ""`. With punctuation_chars, `#` then splits out
>    as its own literal token: smuggled operators surface as real
>    sections (prompt); word-initial bash comments degrade safely
>    (`ls -la #x` allows — bash runs bare `ls -la`, same outcome;
>    `rg# foo` denies conservatively).
> 2. **rm operand containment** (`crush_bash_guard.py`): the trailing-`/`
>    prefix rule had no word boundary — `rm -rf scratch/ /etc` and
>    `rm -rf scratch/../main` ALLOWED (verified + reproduced). Fix: the
>    trailing-/ rule is DELETED (no ALLOW_PREFIX base may end in "/");
>    rm gets a dedicated `_rm_contained()` check — exactly `rm -rf` with
>    every operand posixpath-normalizing into `scratch`/`../scratch` or
>    below; `..` traversals and extra escape operands prompt.
> 3. **NoNewPrivileges killed console sudo** (`ttyd.service.in`): NNP=yes
>    is inherited by every child and sudo is setuid — every sudo from the
>    ttyd terminal failed, dead-on-arrival for the NOPASSWD workflow the
>    console exists for. Fix: NNP=no on console_ttyd only (granian/huey
>    correctly keep =yes; they never sudo). PROVEN on the VM via
>    systemd-run A/B under the unit's properties: NNP=yes → "the 'no new
>    privileges' flag is set" + status 1; NNP=no → `sudo -n true` SUCCESS.
>    Live unit sed'ed + daemon-reload + restart; all services active.
>
> Tests: 36/36 both machines (was 32; +comment smuggling, +comment
> degrade-safe, +rm containment both directions, +rm multi-operand
> allow). ruff + `./run typecheck` clean. Majors 4-8 and minors/nits
> 9-22 still OPEN — next round.

> ### Follow-up (2026-08-24, later): `_rm_contained_within_scratch` REMOVED
>
> User decision: the dedicated rm containment check (blocker-2 fix) is
> gone — simpler, stricter policy: only the BARE `rm -rf scratch` /
> `rm -rf ../scratch` forms are allowlisted (ALLOW_EXACT, as in the
> original opencode.json); EVERY `rm -rf` with operands prompts. Operand
> cleanup routes through `./run cleanscratch` (steer.md updated). Tests:
> the containment allows became `test_rm_with_args_prompts` (all operand
> forms prompt); 36/36 both machines; ruff + typecheck clean.

> ## Review round 2 (2026-08-24): majors 4-8 + adversarial NEW-1/NEW-2 + minor 14 fixed
>
> 4. **git write flags**: `git diff|log|show --output=<file>` (+ `--no-index`
>    with scratch-controlled content, `--ext-diff`, `--open-files-in-pager`)
>    wrote anywhere on the `git diff` prefix allow. Now prompt-class:
>    GIT_WRITE_FLAGS startswith check in _classify before the allowlist.
> 5. **export exec-hooks**: unbounded `export NAME=…` allowed
>    PYTHONPATH/BASH_ENV/NODE_OPTIONS/PERL5OPT/PAGER child-hooking. Now
>    name-allowlisted: {COPYFILE_DISABLE, RUN_PROJECT_TESTS}; bare names
>    (`export FOO`) stay allowed (mark-only, harmless).
> 6. **testvm umask**: `umask 022` pinned at provision() top — tree+seed
>    modes ride through extraction, so 027/077 hosts landed /etc/redis 700
>    (redis dead) and /tmp one-shots 600 (bootstrap denied).
> 7. **ancestor configs**: crush walks cwd ancestors merging
>    .crushrc/crushrc/.crush.json/crush.json; a stray ~/crush.json slipped
>    past the preflight. run agent() now walks repo parents to / and
>    refuses (verified with a planted ../crush.json).
> 8. **stale spec block**: the first-design .crushrc block in THIS file is
>    stamped SUPERSEDED (pointer to the final built-in-providers design).
> NEW-1. **operator-run ride**: maximal-munch tokens the splitter doesn't
>    recognize (`;&`, `;;&`, `((`, `))`) rode prefix allows as words —
>    `git diff ;& rm -rf /` ALLOWED. Now any all-operator-char token
>    (OPERATOR_RUN_RE) prompts its section.
> NEW-2. **expansion args**: `git diff $FLAGS` allowed while expansion
>    content (e.g. --output=…) is invisible; also punctuation-mode splits
>    `$(` so the old SUBST_RE never fired. Now ANY token containing `$` or
>    backtick prompts (SUBST_RE removed — the $ rule subsumes it).
> 14. **trailing terminators**: `git status;` / `git status &` / trailing
>    newline prompted spuriously (dangling-separator check). main() strips
>    the command; one trailing `;`/`&` token is dropped before the check
>    (`&&`/`||` still prompt).
>
> Tests 41/41 both machines (+5 regression methods; export_form updated to
> the allowlisted names). ruff + `./run typecheck` clean. NOTE: user
> removed `_rm_contained_within_scratch` earlier — only BARE
> `rm -rf scratch` / `../scratch` allow; all operand forms prompt
> (cleanscratch is the documented path). Remaining open: minors 9-13, 15-17,
> nits 18-22.

> ### Follow-up (2026-08-24, evening): round-2 guard/run changes REVERTED
>
> User decision: the review-round-2 changes to `run` and
> `crush_bash_guard.py` are reverted (crush guard + its tests + run
> synced to both machines; 36/36). Reverted: git write-flag prompts (4),
> export name allowlist (5, export is unbounded again), operator-run
> token prompts (NEW-1), `$`-expansion prompts with SUBST_RE restored
> (NEW-2 — note SUBST_RE only catches literal `$(…)`/backticks; the
> punctuation-mode split of `$(` means those surface as `$` words and
> ride unless a section break intervenes), ancestor-config preflight
> walk (7), trailing-terminator tolerance + main() strip (14). STILL IN
> PLACE from that round: testvm `umask 022` (6) and this file's
> SUPERSEDED stamp (8). The blocker-1/2/3 fixes and the bare-only rm
> policy are untouched. KNOWN consequence (accepted): the adversarial
> holes 4/5/NEW-1/NEW-2 and ancestor-config merges are open again —
> human prompt-gating remains the only barrier on those paths.

> ## Review round 3 (2026-08-24): MINORS 9-17 fixed
>
> 9. Seed excludes +`.coverage` +`djangoapp/static` +`uploads` (gitignored
>    artifacts no longer ship or ride the first VM commit).
> 10. Both example envs: ZAI_API_KEY/AGENT_MODEL ship as ACTIVE
>     "DANGEROUSLYUNSET" sentinels (matches SECRET_KEY/DB_PASSWORD; the
>     provision scan refuses, dev fills in).
> 11. run preflight competitor list +/etc/crush/crush.json (root-owned
>     slot; absent today, refused if created).
> 12. steer.md `websearch` → `web_search`.
> 13. steer.md git list: ls-files is BARE-form-only (doc fixed to match
>     ALLOW_EXACT; no policy change).
> 15. Guard SPLIT_OPS comment documents the quoted-BARE-operator nuance
>     (posix quote-stripping makes `';'` split like a real op — fail-closed).
> 16. Tests pin previously-untested shapes: heredoc/herestring, comment-only
>     input, `;;` splitter, backslash-continuation (all prompt); lone-`&`
>     chain of allowed sections (allows); unbalanced parens (benign allow —
>     bash rejects, nothing executes); edit-guard `./`/trailing-slash
>     normalization + lexical-breadth pins (/opt/scratch/, /home/u/scratch/
>     — symlink non-resolution documented as accepted). 40/40 both machines.
> 17. This file: header "still planned" fixed, cutover item 3 preflight
>     list corrected (AGENT_MODEL only), touchpoint 7 rewritten to the
>     seed-ships-deploy/ as-built, provider-wiring paragraph + glm pins
>     struck/corrected to the zai/ final state.
>
> Nits 18-22 remain (pyproject PLR2004, exec/AGENT_MODEL format in run,
> hook cwd anchoring, edit-guard breadth tightening, ONE-mode comment).

> ## Review round 4 (2026-08-24): NITS 18-22 fixed — review list CLOSED
>
> 18. pyproject: unused PLR2004 ignore dropped from deploy/tests (S603
>     remains; the assertEqual style never trips PLR2004).
> 19. run agent(): `exec crush "$@"` (no wrapper process) + provider-
>     qualified AGENT_MODEL format check (`*/*`), refusing bare model
>     names up front instead of dying inside the TUI.
> 20. Hook-path cwd question settled EMPIRICALLY with probe hooks:
>     - project .crushrc hooks fire ONLY when cwd == project root (from a
>       subdirectory crush 0.91 does not even LOAD the file — bash runs,
>       zero hook executions);
>     - hook process cwd == the project root (pwd inside the hook);
>     - hooks registered via CRUSH_GLOBAL_CONFIG do NOT execute at all
>       (probe: zero invocations) — another reason the preflight's global
>     config refusal is right.
>     Since ./run agent() cds to the repo root before exec, `./deploy/…`
>     relative hook paths always resolve; .crushrc now documents the
>     whole constraint (subdir launches silently skip the config).
> 21. Edit guard tightened: EXACT roots scratch/, ../scratch/,
>     /srv/app/scratch/ (was the lexical-breadth `*/scratch/*` —
>     /opt/scratch, deep/dir/scratch, /tmp/scratch matched). Docstring
>     documents lexical matching (no symlink resolution); tests updated
>     (foreign-scratch-names now PROMPT; nested = deep-below-root).
> 22. testvm tmp/ comment reworded: 1777 rides in the archive because tar
>     stamps the extracted dir AND tmpfs /tmp can't be chmod'ed after via
>     landed files; umask 022 is the determinism lever for everything else.
>
> 37/37 both machines; ruff + `./run typecheck` clean. Review findings
> 1-22 + NEW-1/NEW-2 now all: fixed, or reverted-by-decision (4/5/7,
> NEW-1/NEW-2, and the round-3 bash-guard extras 15/16 — accepted risks,
> human prompt is the barrier).

> ### Follow-up (2026-08-24, later still): nits 19 + 21 REVERTED
>
> User decision: `run agent()` is back to `command crush` + the single
> non-empty AGENT_MODEL check (no provider-qualified format gate), and
> crush_edit_guard.py is back to the broad lexical patterns
> (`scratch/*`, `*/scratch/*`, `/srv/app/scratch/*` — any dir named
> scratch matches; no symlink resolution) with its round-3 tests. 36/36
> both machines; VM synced. Still standing from round 4: nit 18
> (PLR2004 drop), nit 20 (.crushrc cwd-constraint documentation), nit 22
> (testvm comment reword).

> ## Review round 5 (2026-08-24 evening, commit 64cbc76 "Crush agent
> ## with guard scripts"): 3 fresh reviewers — MAJOR 2 + minors fixed
>
> New findings: 2 MAJOR (process substitution `<(cmd)` executes
> unprompted on prefix allows — the EXECUTING edge of the reverted
> operator-run class, NOT fixed per user scope choice, human prompt
> remains the barrier on the paths it rides; steer.md's multi-line
> `&&`-chain "RIGHT" example actually prompts), 8 minors, 6 nits.
>
> Fixed this round (user scope: "fix 2 and minor ones"):
> 2. steer.md flagship example → single-line `./run lintfix &&
>    ./run typecheck` (verified allow), with an explicit warning that a
>    trailing `&&` before a newline munges into an unrecognized operator
>    run and prompts — newlines remain fine for prompt-class commands.
> 3. Both guards carry `from __future__ import annotations` — the
>    `list[...] | None` annotation crashed the hook (rc=1 TypeError)
>    under python <3.10 (stock macOS /usr/bin/python3 is 3.9); silent
>    prompt-with-traceback degradation gone.
> 4. testvm removes provisioning leftovers from VM /tmp after service
>    start: tree.tgz (EMBEDS the credentials env) sat world-readable on
>    the sticky /tmp forever, + app-seed.tgz + the three one-shots.
> 5. .gitignore +staticfiles/ (collectstatic writes into the repo on the
>    VM; agent `git add -A` would have committed collected static into
>    every later commit — baseline was clean only because seed-commit
>    runs before bootstrap).
> 6. Seed excludes +.idea +.vscode +.pytest_cache +*.tsbuildinfo
>    (editor/cache state walked the FS tar).
> 7. steer.md: git status is BARE-form only (args prompt) — doc now says
>    so; diff/log/show keep "any args".
> 8. Follow-up 17 (multipass file): "Tree staging now also ships" →
>    "The seed tarball now also ships" (as-built correction).
> 9. djangoapp/tests/playwright/_base.py:153 "opencode session id" →
>    "crush session id".
>
> NOT fixed (out of user scope this round): MAJOR-1 `<(cmd)` process
> substitution (accepted-risk category — one-line OPERATOR_RUN_RE fix
> available if ever wanted); nits 10-16 (unused ruff ignores, dead
> ALLOW_EXACT dupes, comment wording, migration-file PLR2004 mention,
> ninja_api.py "e.g. opencode" word, prevproject/empty-dirs in seed,
> granian/huey inheriting ZAI_API_KEY via shared EnvironmentFile).
>
> 36/36 both machines; ruff + `./run typecheck` clean; VM synced.

> ### Follow-up (2026-08-24, night): seed tarball driven by git; /tmp
> ### cleanup moved INSIDE
>
> Fragility of the exclude-list tar: it duplicated .gitignore BY HAND and
> drifted by construction — the tar walks the filesystem, the ignore rules
> live in the index, and every review round caught another leak
> (.coverage, staticfiles/, uploads/, .idea/, *.tsbuildinfo all shipped
> at some point). Reworked: `git ls-files -z | tar czf … --null -T -` —
> the seed IS the tracked working tree; the git index is the single
> exclude authority (gitignored + untracked can never ship; AppleDouble
> junk and empty untracked dirs stop riding along; tracked-but-deleted
> files fail tar loudly — desired). Verified dry-run: 501 tracked files
> = 501 shipped, guards/testvm at 755, zero ignored leaks. The whole
> --exclude list is gone from testvm.
>
> /tmp leftovers cleanup (round-5 fix 4) moved from the driver into the
> VM flow per user call: last step of vm-bootstrap.sh now rms
> tree.tgz (embeds the credentials env) + app-seed.tgz + the three
> one-shots — deleting the running script itself is safe (open fd
> survives unlink). testvm keeps only a pointer comment. The live VM's
> build-time leftovers (incl. my session's debug outputs) were rm'd by
> hand; future builds self-clean.
