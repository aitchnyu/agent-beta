# Tool & permission rendering redesign (opencode chat)

Render the agent's tool calls and permission prompts in the chat with
tool-specific, readable layouts instead of the current generic JSON box, and
pin the active permission prompt above the input.

## Current state (ground truth)

- `frontend/src/pages/OpencodeChat.vue` renders a `tool` block as one generic
  box: a header (`tool` name + `status`) and two `<pre>`s for `input` and
  `output`. Writes, edits, and bash all look the same — JSON.
- `useOpencodeChat.ts` `upsertPart` builds the tool block from the SSE
  `message.part.updated` event and stores `input`/`output` as
  **stringified JSON** (`JSON.stringify(state.input ?? {}, null, 2)`).
- Wire shape (`frontend/src/schemas.ts`): `Part = { id, type, tool?, state?,
  text? }` with `.passthrough()`. `Part.state = { status?, input?, output?,
  metadata? }` where `input`/`output` are `z.unknown()` (the raw object). Tool
  parts also carry a human **`title`** at runtime via passthrough (not typed) —
  e.g. "Write to …", "Run command".
- Tool input shapes (confirm against the live Debug event log while building):
  - `write`  → `{ filePath, content }`
  - `edit`   → `{ filePath, oldString, newString }`
  - `bash`   → `{ command, workdir?, … }` (+ a part `title`)
  - other tools (`read`, `grep`, `glob`, `task`, …) keep the generic rendering.
- Permission block (`types.ts`): `{ id, permission, command, always, state:
  "asked"|"answered"|"cancelled", answer?, pending? }`; rendered inline by
  `components/opencode/PermissionCard.vue`.
- Reuse targets (do **not** reinvent):
  - `utils/filePreview.ts` → `highlightDiff(diffStr)` runs highlight.js's `diff`
    grammar (+/-/@@) and sanitizes; `highlightCode(code, lang)` exists too.
    (`highlightDiff` is already a generic name — keep it.)
  - `pages/GitDiff.vue` renders `<pre class="git-diff"><code
    class="hljs language-diff" v-html="rendered"></code></pre>` — **rename this
    class to `.code-diff`** (generic; the same block now serves git diffs and
    opencode edit diffs).
  - The diff styling (mono, long lines scroll, hljs github theme styles
    `.hljs-addition`/`.hljs-deletion`) currently lives as `.git-diff` in
    `_git.scss`, mirroring `.files-code`. Rename → `.code-diff` and move it to a
    shared partial (alongside `.files-code` in `_files.scss`, or a new
    `_code.scss`); update `GitDiff.vue` to the new class.
  - `_opencode.scss` `.opencode-tool-input, .opencode-tool-output` =
    `max-height: 600px; overflow: auto; white-space: pre` — the existing
    scroll-box pattern to reuse.

## Decisions (from the Q&A)

1. **Write content** → plain `<pre>` (no syntax highlighting).
2. **Edit (oldString/newString)** → single-column **unified diff** rendered
   through `highlightDiff()` (hljs `diff` grammar) — the same approach as the git
   pages, but on a **renamed, generic** `.code-diff` class (see "Rename diff
   styling" below).
3. **Bash** → header shows **command + title**; body is `output` with
   max-height + overflow + scroll-to-bottom.
4. **Max-height / overflow** → reuse the existing
   `.opencode-tool-input/output` pattern (extract a shared class; minimize
   copy-paste).
5. **Permission** → keep a compact inline record in the transcript showing only
   **complete / not** (no command, no answer detail), **and** pin the active
   pending prompt above the input, one at a time (sequential queue of pending).
6. **Components** → a thin `ToolBlock.vue` dispatcher delegating to focused
   children (chosen — see below).

## Component structure (chosen: thin dispatcher + focused children)

A thin `ToolBlock.vue` dispatcher reads `block.tool` and delegates to focused
children. The page stays a flat `<ToolBlock :block="b" />`; each tool gets its
own small component.

Proposed children:

- `ToolBlock.vue` — dispatcher. Props: the tool block. Reads `block.tool`:
  `write`/`edit` → `<WriteBlock>`; `bash` → `<BashBlock>`; else generic.
- `WriteBlock.vue` — props derived from the parsed input: `filePath`, `content?`,
  `oldString?`, `newString?`, `status`, `title?`.
  - Title row: the tool label ("Write"/"Edit") + **`filePath`** + status badge.
  - Body: `content` present → plain `<pre>` (no highlighting). Else
    `oldString`/`newString` → `<DiffBody :old :new />`.
- `BashBlock.vue` — props: `command`, `title?`, `status`, `output`.
  - Header: `command` (mono) + `title` (fall back to the `tool` name if absent)
    + status badge.
  - Body: `output` `<pre>` with scroll-to-bottom.
- `DiffBody.vue` (shared) — props `old`, `new`. Builds a unified-diff string via
  `buildUnifiedDiff(old, new)` (`utils/diff.ts`), runs `highlightDiff(...)`, and
  renders `<pre class="opencode-tool-body code-diff"><code class="hljs
  language-diff" v-html="rendered"></code></pre>`.
- `PermissionPrompt.vue` — the pinned, interactive prompt (Allow once / Allow
  always / Reject). Bound to the first pending permission block; emits `answer`.

Shared helpers (don't duplicate):

- A tiny `useScrollBottom(elRef, deps)` composable (watch deps, `nextTick` →
  set `scrollTop = scrollHeight`) for bash output (and write content if streamed).
- A shared CSS class `.opencode-tool-body` = the current
  `.opencode-tool-input/output` rule (`max-height: 600px; overflow: auto;
  white-space: pre`); all tool bodies use it. Move the rule rather than
  copy-pasting.

## Implementation outline

### 1. Parse tool input (stop stringifying)
- `types.ts`: change the tool block to keep the **parsed** `input` (object), not
  a stringified blob. Suggested shape:
  `{ kind: "tool", partID, tool, status, title?, input: unknown, output: string }`.
- `useOpencodeChat.ts` `upsertPart` (tool branch): keep `state.input` as the raw
  object; keep `output` stringified only when non-string. Capture the part
  `title` (passthrough) if present.

### 2. `utils/diff.ts` — pure unified-diff builder
- `buildUnifiedDiff(oldStr: string, newStr: string): string` — hand-rolled LCS
  **line** diff emitting `@@ … @@` headers, `- ` removed lines, `+ ` added lines.
  No new dependency. (oldString/newString are arbitrary snippets, so diff just
  those two strings.)
- `utils/diff.test.ts` — unit tests (mirror `parseSse.test.ts`'s style): added
  lines, removed lines, mixed, no-change → empty/no-hunk.

### 3. `WriteBlock` / `DiffBody`
- Content → `<pre class="opencode-tool-body">{{ content }}</pre>`.
- Edit → `DiffBody` → `highlightDiff(buildUnifiedDiff(old, new))` →
  `<pre class="opencode-tool-body code-diff"><code class="hljs language-diff"
  v-html="rendered"></code></pre>`. The hljs github theme styles the
  `.hljs-addition`/`.hljs-deletion` tokens; reuse, don't re-style.

### 3b. Rename diff styling (generic, not git-specific)
- Rename the `.git-diff` class → `.code-diff` everywhere (it now serves both git
  diffs and opencode edit diffs).
- Move the rule out of `_git.scss` to a shared partial (alongside `.files-code`
  in `_files.scss`, or a new `_code.scss`); update `pages/GitDiff.vue` to the
  new class. `highlightDiff` (the function) is already generic — keep it.

### 4. `BashBlock`
- Header = `command` + `title` (+ status badge). Body = `output` in
  `.opencode-tool-body` with `useScrollBottom` watching `output`.

### 5. `ToolBlock` dispatcher + page wiring
- `OpencodeChat.vue`: replace the inline `v-else-if="b.kind === 'tool'"` box with
  `<ToolBlock :block="b" />`.
- Add `.opencode-tool-body` to `_opencode.scss` (move the existing
  `.opencode-tool-input/output` rule onto it, or have those alias it) so the
  scroll-box rule is single-source.

### 6. Permission redesign (compact inline + pin active)
- **Inline (transcript):** a compact marker showing the **type + subject +
  complete/not** — `filepath` for write/edit (from `metadata.filepath`),
  `command` for bash (from `metadata.command`), plus the status. No buttons —
  those live only in the pinned prompt. (Originally specced as "complete/not
  only", but expanded to include the subject so it matches the tool block's
  `Edit: <path>` / bash command instead of a bare `edit`.) Reuse
  `.opencode-permission*` styling.
- **Pinned (above the input):** between the transcript and the input form, render
  `PermissionPrompt.vue` bound to the **first** block with `state === "asked"`.
  When answered (state flips off "asked"), the next pending block becomes the
  pinned prompt → **sequential**. Hide the pinned area when none are pending.
  Emit `answer` → existing `answerPermission(block, reply)`.
  - **Queue indicator (per-turn):** show `i / n` on the pinned prompt, where the
    counts are **per-turn** — `send()` snapshots the permission-block count at
    turn start (`turnPermissionBase`) and `i`/`n` subtract it, so a lone prompt
    in a multi-turn session doesn't read "3 of 3". It reads `1/2 → 2/2` as you
    answer each within the turn, and `n` grows if more arrive mid-turn. Show it
    **only when `n > 1`** (a lone prompt needs no counter).
- `useOpencodeChat.ts`: expose `activePermission` (computed: first `permission`
  block with `state === "asked"`) plus the per-turn counts for the `i / n`
  indicator — the active prompt's 1-based index and the total, both relative to
  `turnPermissionBase`.

## Files

- New: `components/opencode/{ToolBlock,WriteBlock,BashBlock,DiffBody,PermissionPrompt}.vue`,
  `utils/diff.ts`, `utils/diff.test.ts`.
- Edit: `pages/OpencodeChat.vue`, `pages/opencode/useOpencodeChat.ts`,
  `pages/opencode/types.ts`, `styles/_opencode.scss`, `pages/GitDiff.vue`,
  `styles/_git.scss` (remove the relocated rule), `styles/_files.scss` (or new
  `_code.scss`) for the renamed `.code-diff`.
- Reuse: `utils/filePreview.ts` (`highlightDiff`).

## Verify

- `npm run type-check`, `npm run lint`, `npm run test` (incl. the new
  `diff.test.ts`).
- Manual in the chat: trigger a **write** (plain content block, filePath in
  title), an **edit** (single-column +/- diff, colored), a **bash** call
  (command + title header, output scrolls to bottom), and a **permission
  prompt** (pinned above the input, answers sequentially and shows `1/n` when
  more than one is queued; inline shows only complete/not).
- Also open a git diff page to confirm the renamed `.code-diff` still renders
  identically.
