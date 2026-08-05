# Rename the scratch workspace `copy` → `scratch` everywhere

## Goal
The repo's `main`/`copy` git-worktree "scratch" workflow names the throwaway
sibling `copy/` in some places and `scratch` in others. The naming is already
half-migrated (`createscratch`, `mergescratch` use "scratch"; `cleancopy`,
`checkcopy`, `_COPY_DIR`, the `copy/` directory, and the `/git/uncommitted/copy/`
URL worktree name still say "copy"). Make it consistently **`scratch`** everywhere
it refers to the workspace — in code and docs. The `copy/` directory is created on
demand by `createscratch` (a sibling at `../scratch`); there is **no on-disk dir to
migrate**.

## Decisions (locked across Q&A)
- **Rename everything in scope**: the physical dir `copy/`→`scratch/`, the `run`
  command names (`checkcopy`→`checkscratch`, `cleancopy`→`cleanscratch`), the
  internal vars (`_COPY_DIR`/`_COPY_EXCLUDES`/`_new_copy`), the
  `/git/uncommitted/copy/` URL worktree name, and the `agentconfig/opencode.json`
  permissions.
- **Leave `prompts/*.md` as-is** — dated historical records (immutable). New docs
  use "scratch"; existing prompts keep "copy" as a frozen record.
- **Rename test-fixture internals** → `scratch`: `TodoApp/copy_only.py`→
  `scratch_only.py`, `copy_notes.md`→`scratch_notes.md`, git identity
  `name=Copy`/`email=copy@example.com`→`name=Scratch`/`scratch@example.com`,
  `copy_root`→`scratch_root`.
- **`prevproject/` is OUT OF SCOPE** — vendored legacy; its "copy" usages are
  unrelated English/legacy words.

## Scope rules — what NOT to change (English word "copy")
A blind find/replace is unsafe. Preserve these legitimate English usages:
- `steer.md`: "copyable example" (×3), "never copy or CSS", "breaks if the copy
  changes" (UI copy), "copy-paste".
- `README.md` / `docs/reference/README.md`: "copyable example"; the **verb**
  "copy `main/`" (keep the verb; rename only the `copy/` dir noun).
- `INSTRUCTIONS.md`: "copy all of them into some todo list".
- `run` `init()`: "Copy from .env.example?".
- `model_copy`, `article_pk_copy`, `cp`, etc. anywhere.

Rename only the **workspace concept**: the `copy/` directory, the `copy` worktree
name, `copy_root`, and the `copy`-prefixed command/variable names.

## Per-file changes

- **`run`** — rename `checkcopy()`→`checkscratch()`, `cleancopy()`→`cleanscratch()`
  (`createscratch`/`mergescratch` already "scratch"). Rename internals
  `_COPY_EXCLUDES`→`_SCRATCH_EXCLUDES`, `_COPY_DIR`→`_SCRATCH_DIR`,
  `_new_copy()`→`_new_scratch()` (update every `$…` ref). `_COPY_DIR` value
  `…/copy`→`…/scratch`; exclude `--exclude='copy/'`→`'scratch/'`. Rewrite
  comments/echoes that name the workspace ("The copy/ fast loop", "copy/ ready at
  …", "Deploying … → …", "copy/ → main/", "Removed …", `_overlay_app` comment).
  Keep the verb "Copy from .env.example?". The bottom `declare -F "$1"` dispatcher
  finds renamed commands automatically.
- **`agentconfig/opencode.json`** — `"copy/**"`→`"scratch/**"`; `"main/run
  cleancopy"`→`"main/run cleanscratch"`; `"./run checkcopy"`→`"./run checkscratch"`;
  `"cd copy *"`→`"cd scratch *"`; `"rm -rf copy"` / `"rm -rf copy/*"`→`scratch` /
  `scratch/*`. Leave `createscratch`/`mergescratch`/`checkproject`/`migrate` and the
  `"main/agentconfig/steer.md"` instruction path.
- **`djangoapp/views/git.py`** — module docstring (main, copy)→(main, scratch);
  comment "`copy` = the scratch sibling"→"`scratch` = the scratch sibling";
  `WORKTREES = ("main", "copy")`→`("main", "scratch")`; list docstring + missing-
  worktree note; `copy_files`→`scratch_files` (`uncommitted_or_none("scratch")`);
  `GitUncommittedWorktree(name="copy", …)`→`name="scratch"`.
- **`djangoapp/views/git_data.py`** — module docstring; `worktree_root()` docstring
  + body (`if name == "copy": root.parent / "copy"`→`"scratch"`); the
  `uncommitted_or_none` docstring "no `copy/` yet".
- **`djangoapp/views/files.py`** — docstring: "both `main/` and `copy/`"→`scratch/`;
  "browse `copy/`"→`scratch/`.
- **`djangoapp/tests/_git_fixtures.py`** — docstrings (parent/main+copy→scratch;
  "Copy uncommitted…"→"Scratch uncommitted…"; "Copy: a baseline commit"→"Scratch…");
  `copy_root = Path(tmp.name) / "copy"`→`scratch_root` (return tuple + docstring);
  `GitRepoMixin.setUp` `copy_root`→`scratch_root`, `copy = _init_repo(copy_root,
  email="copy@example.com", name="Copy")`→`scratch = _init_repo(scratch_root,
  email="scratch@example.com", name="Scratch")`; fixture files
  `TodoApp/copy_only.py`→`scratch_only.py`, `copy_notes.md`→`scratch_notes.md` (in
  `_commit`/`_write`). The commit message `"scratch baseline"` already matches.
- **`djangoapp/tests/views/test_git.py`** — `["main", "copy"]`→`["main", "scratch"]`;
  `sections["copy"]`→`sections["scratch"]`; fixture file paths in the asserts;
  rename method `test_uncommitted_copy_diff`→`test_uncommitted_scratch_diff`, its
  docstring/GET URL, and title assert `"Uncommitted (copy): …"`→`"Uncommitted
  (scratch): …"`; path-traversal URL `/git/uncommitted/copy/../main/…`→`scratch/…`.
- **`djangoapp/tests/playwright/test_git.py`** — `TodoApp/copy_only.py` link
  name/text asserts→`scratch_only.py`; `copy_notes.md`→`scratch_notes.md`; href
  `/git/uncommitted/copy/TodoApp/copy_only.py`→`/git/uncommitted/scratch/TodoApp/scratch_only.py`.
- **`djangoapp/tests/testapp/ourapp/models.py`** — docstring "Overlaid onto
  `copy/ourapp/` by `checkproject`"→`scratch/ourapp/`.
- **`agentconfig/steer.md`** — workspace concept throughout: headers
  "## Layout: parent / main / copy"→"… / scratch", "## The copy workflow"→
  "## The scratch workflow"; all `copy/`→`scratch/` (`cd /abs/path/copy`,
  "Edit `copy/`", "`copy/` is disposable", "`copy/`'s own history/edits",
  "edit files under `copy/`", "Edits are scoped to `copy/`", "cd copy …");
  commands `./run checkcopy`→`checkscratch`, `main/run cleancopy`→`cleanscratch`,
  `rm -rf copy`→`rm -rf scratch`; worktree name "`copy` (the scratch sibling)",
  "main then copy"; URL `/git/uncommitted/copy/<path>`→`/git/uncommitted/scratch/<path>`.
  **KEEP** English: "copyable example", "never copy or CSS", "breaks if the copy
  changes", "copy-paste", "UI copy/style".
- **`README.md`** — "`copy/` is a throwaway sibling"→`scratch/`; "into a fresh
  `copy/`"→`scratch/`; "Edit `copy/`"→`scratch/`; "`( cd copy && ./run checkall )`"
  →`cd scratch`; "deploy `copy/` into `main/`"→`scratch/`. **KEEP** the verb "copy
  `main/` (minus …)" and "copyable example".
- **`docs/reference/README.md`** — line 84 "Edit in `copy/`, then `./run checkall`"
  →"Edit in `scratch/` …". **KEEP** "copyable example" (line 3).
- **`TODO.md`** — remove line 2 ("Rename copy to scratch", now done); line 22
  "checkall vs checkcopy"→"checkall vs checkscratch".
- **No change (verify)** — `frontend/src/pages/GitUncommitted.vue` renders worktree
  names dynamically (`wt.name`); `djangoapp/urls.py` uses a runtime URL param.

## Validation
1. `uv run ruff check` then `./run typecheck` (`uv run mypy .`).
2. `./run test` — unit suite; confirm `djangoapp.tests.views.test_git` passes.
3. (Optional) `./run playwrighttest` for the `test_git` browser suite.
4. Residual sweep — `Grep` for `checkcopy|cleancopy|_COPY_DIR|_COPY_EXCLUDES|"copy"|
   'copy'|/copy/|copy/` across `*.py`, `run`, `*.json`, `*.md` (excluding
   `prompts/`, `prevproject/`). Remaining hits must be only the English-word usages
  listed above.

## Risks / edge cases
- **`opencode.json` must stay in lockstep** with `run` + the dir name — a stale
  permission string prompts (or blocks) the web-chat agent from editing `scratch/`.
- **URL contract change** `/git/uncommitted/copy/`→`/scratch/` is documented to the
  agent in `steer.md`; change both together or the agent emits dead links.
- **Fixture ↔ test coupling** — `_git_fixtures.py` filenames must match the path
  strings asserted in `test_git.py` (views) and `playwright/test_git.py`; rename all
  three together or suites fail.
- **Two sources of the worktree name** — `git.py`'s `WORKTREES` and
  `git_data.worktree_root`'s literal; change both or scratch diffs 404.
- Avoid `replaceAll` blind edits in `steer.md`/`README.md` — skip the English-word
  "copy" instances catalogued above.

## Checklist

- [ ] `run`: `checkscratch`/`cleanscratch` + `_SCRATCH_DIR`/`_SCRATCH_EXCLUDES`/
      `_new_scratch` + `…/scratch` path + exclude + comments/echoes
- [ ] `agentconfig/opencode.json`: edit scope + bash allowlist → scratch
- [ ] `git.py` + `git_data.py`: `WORKTREES`, `worktree_root`, docstrings
- [ ] `files.py` docstring
- [ ] `_git_fixtures.py`: `scratch_root`, identity, fixture filenames + docstrings
- [ ] `test_git.py` (views) + `playwright/test_git.py`: asserts, URLs, method name
- [ ] `testapp/ourapp/models.py` docstring
- [ ] `steer.md`: workspace concept only (keep English "copy")
- [ ] `README.md` + `docs/reference/README.md`: `scratch/` (keep "copyable"/verbs)
- [ ] `TODO.md`: drop line 2, fix `checkcopy`→`checkscratch`
- [ ] ruff + mypy + tests green; residual grep confirms no stray workspace "copy"
