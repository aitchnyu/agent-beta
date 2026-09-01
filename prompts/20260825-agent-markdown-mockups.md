# Agent: terminal markdown, deployed mockups, questions/todos/subagents back

Date: 2026-08-25 (final design reached 2026-08-31 after two rework rounds;
nothing committed in between, so this file describes the end state and notes
the evolution at the bottom). Implements the TODO items "We were assuming a
web ui…", "No more mermaid and mockups will happen within agent", the
mockup-demo block, and "Questions, todos and subagents were banned with
opencode. Lets bring them back."

## Why

The Crush agent (`./run agent`) runs in a **terminal** (the TUI locally,
ttyd on the VM), but its instructions dated from the opencode web-UI
assumption: replies were forced into a safe-HTML subset and Design-phase
diagrams/mockups were emitted as in-chat `rich-diagram`/`rich-mockup` HTML
blocks — none of which a terminal renders. Final decisions:

- Chat replies are **markdown**; the question/todos denials are lifted
  (crush's `agent` subagent tool was already allowed).
- Diagrams stay in the system: the `/files` doc viewer renders mermaid, so
  the agent writes ER/state diagrams as mermaid into the design doc (in
  scratch) and links it after deploy.
- **Mockups need no special machinery**: a mockup IS the feature's real
  files — route in `ourapp/views/<feature>.py`, page in
  `frontend/src/ours/pages/<Page>.vue`, zod schema in `ours/schemas.ts`, at
  the final URL — carrying three temporary markers: superuser-only gate
  (404), hardcoded static props (never DB), and a root `div.mockup`
  crosshatch wrapper. Becoming real = swap in queries, set the real access
  rules, drop the wrapper, write the tests. Nothing to delete.
- Everything lives in `../scratch/` and reaches `main/` only via
  `mergescratch` — which **prompts** (removed from the bash allowlist), so
  the user approves every landing. Design demos iterate
  edit → checkscratch → mergescratch; Build continues the same scratch.

## Changes

- `.crushrc` — `permissions deny todos question` removed (deny beats allow,
  so this single line was the whole ban).
- `agentconfig/steer.md` — Reply format → markdown; "Asking the user
  questions" → use the question tool (one per call, stop); new "Todos and
  subagents"; Design phase = createscratch → doc + mocked-up pages in
  scratch → checkscratch → ask → mergescratch (loopable demo rounds); Build
  continues the same scratch and evolves the mockups into the real
  implementation; Deploy stays single-shot; "Mockups and diagrams"
  rewritten (doc-in-browser mermaid + the three-markers mockup model).
- `deploy/crush_bash_guard.py` — `./run mergescratch` removed from the
  allowlist: crush prompts on every deploy, mechanically enforcing
  approval of each landing in `main/`.
- `deploy/crush_edit_guard.py` — unchanged scratch-only scope; docstring
  notes design artifacts ride mergescratch too.
- `frontend/src/ours/style.scss` — `.mockup, .mockup *` crosshatch overlay
  (`repeating-linear-gradient`, semi-transparent 12% black stripes layered
  via `background-image` so real colors stay visible).
- TODO.md — the implemented items removed.

## Validation

- [x] `uv run python -m unittest discover -s deploy/tests -v` — guard tests
      green (incl. `mergescratch` prompts, bare and inside a compound).
- [x] `./run lintfix` + `./run typecheck` green; ourapp tests green;
      frontend lint/type-check/build green; `bash -n run` clean.
- [ ] First feature run exercises the loop end to end (design demo →
      feedback rounds → real deploy).

## Evolution (for the record)

1. Round 1 (08-25): mockups as a dedicated transient module
   (`ourapp/views/mockups.py`, own NinjaAPI, try/except mount in urls.py,
   `pages/mockups/` dir with inline schemas) written DIRECTLY to main/ via
   an edit-guard carve-out; mergescratch explicitly rm'd them.
2. Round 2 (08-31): direct writes dropped — mockups ride scratch +
   mergescratch; wipe became emergent rsync `--delete`; mergescratch
   removed from the bash allowlist (prompt-gated deploys).
3. Round 3 (08-31, "no need of special mockup modules or components"): the
   dedicated module/directory/URL prefix/mount/wipe logic all deleted —
   mockups are the feature's normal files with the three markers above;
   crosshatch SCSS stays. `ourapp/urls.py`, `run`, and the edit guard
   reverted to their committed shapes except for the intentional diffs
   listed under Changes.
4. Round 4 (08-31, VM-session autopsy follow-up): `./run mergescratch`
   re-allowlisted (the round-2 prompt gate slowed every demo deploy; the
   compensating rule is steer.md's MUST-share-links-after-deploy). Guard
   gained `head`/`tail`/`wc` filter prefixes; `deploy/inside-vm.sh` now
   installs uv SYSTEM-WIDE (`/usr/local/bin`) — the per-user-for-app
   install left the console user (where the agent runs) without uv on
   PATH — and adds ripgrep (crush's internal grep tool shells out to rg;
   its bash-typed form stays denied). Also fixed this day, unrelatedly:
   `.crush/init` (the "initialize this project?" dialog suppressor) was
   never tracked — crush's own `.crush/.gitignore` (`*`) defeated the root
   whitelists — and `run agent()` gained the documented-but-missing
   preflight that creates the flag.
