# Prewarm groundwork + reviewer (background study at session start)

Built 2026-10-09. Three pieces: a groundwork extension, a reviewer
prewarm/resume rule in the feature workflow, and this record.

## Why

Measured from the Oct 7 chores session (107.7 min busy, 168 tool calls):

- **Orientation was a tax** — ~29 `read` calls plus discovery `bash` were
  "where is everything"; a briefing already in context replaces them
  (~15–30 min at the observed 1–3 min per roundtrip).
- **The stage-5 reviewer oriented for 10.8 min** (49 tool uses, 94.1k
  tokens) before judging a single line. A prewarmed reviewer starts at
  "read the touched files".
- **Input waits behind pending work** (pi's queueing semantics). Studying
  in a background subagent keeps the main agent idle at READY, so operator
  input is serviced immediately.
- **Proven headless first**: a `pi -p` study ran clean on the VM. Traps
  found: `pi -p` over `multipass exec` needs `< /dev/null` (stdin EOF), and
  killing the parent leaves the orphan child to finish.

## What was built

- **`.pi/extensions/groundwork/index.ts`** — on a fresh interactive session
  (`reason: "startup"`, no previous session file, TTY stdout, main session
  only) it sends one kickoff message: spawn the scout subagent in
  background with a map task, reply READY, go idle. Guards: resume/fork
  never re-study; subagent children fire `session_start` with the same
  shape (they load project extensions in-process) — excluded by their
  `…/tasks/` session-file path; headless `-p` exits before a background
  study could finish. The kickoff fires once a model exists (at boot on
  configured launches via model restore, after /model on fresh ones),
  with an `agent_start` fallback queued as followUp. Compatible with
  `desmo pi "task"` — study overlaps the task.
- **Reviewer prewarm → resume** (steer.md, Feature workflow) — stage [4]
  spawns the reviewer in background; stage [5] resumes it with the diff.
  Staleness is handled by contract: the prewarm builds a **map, not a
  copy** (conventions, patterns, tree — nothing that churns mid-session)
  with the open-mind rule (re-read anything you judge; trust the file over
  memory), and the resume prompt re-anchors with requirement + `git
  status` + touched files. The reviewer has no bash tool, so the prewarm
  runs allowlist-clean — no permission asks mid-loop.

## Verification

Three rounds on the VM, each catching what the previous missed:

- Headless `pi -p`: no kickoff (TTY guard), no extension load errors.
- First TUI pty run exposed two extension bugs, found by reading the
  session transcript (not just its existence): (1) a fresh session already
  has bootstrap entries at `session_start` (measured: 2), so an
  entries-empty guard never fires — fixed by gating on
  `previousSessionFile`; (2) subagent children load project extensions
  in-process and fire `session_start` with `reason=startup` just like the
  main session — the kickoff injected into a freshly spawned scout raced
  its task prompt ("Agent is already processing"; the scout errored at
  0.1 s). Fixed by skipping sessions whose file lives under `…/tasks/`.
- Final TUI pty runs: kickoff fires at launch, the scout spawns in
  background with the CORRECT task ("Build a MAP, not a copy…"), READY in
  ~11 s, no collision. On a fresh VM (no model configured) the kickoff
  defers to the first operator prompt after /login and model selection —
  `ctx.model` is undefined at `session_start` even on configured
  launches, so the deferral is the effective path there.
- The VM copy of the extension was updated in place for testing; the repo
  is its permanent home.

## Non-goals

- Permission-ask policy and VM sizing — the other two measured costs (the
  37.7-min ask wait, the 1-CPU battery) — stay separate.
- No headless prewarm: `-p` exits after the final message.
