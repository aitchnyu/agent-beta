# Superuser git viewer at `/git/...`

A read-only Inertia git browser over the **apps inner repo** (`apps/` in prod;
`fakeapps/` in tests), superuser-only (non-superuser → 404, never 403 — same gate
as `/files`, `/manage/apps`). Shows uncommitted files, paginated commits, and
syntax-highlighted diffs (unified-diff rendering via highlight.js). Mirrors the
`/files` viewer's confinement + superuser-gate conventions.

- `/git` — uncommitted files (working-tree status).
- `/git/uncommitted/<path>` — the unified diff of one uncommitted file.
- `/git/commits?page=N` — paginated commit list (25/page, newest first).
- `/git/commits/<commit_id>` — the files changed by commit `<commit_id>` (full-or-short sha).
- `/git/commits/<commit_id>/<path>` — the diff of `<path>` in commit `<commit_id>`.

## Decisions (already made — implement to these)

- **Git library: GitPython** (`import git`, BSD-3-Clause). High-level read ops
  (`Repo`, `repo.untracked_files`, `commit.diff(create_patch=True)`,
  `repo.iter_commits(...)`, `commit.stats.files`) without parsing CLI output.
  Add `gitpython` to runtime deps in `pyproject.toml`. It shells out to git
  (same runtime dep `buildbackend` already assumes). **Security:** GitPython has
  had CVEs around `clone`/subprocess injection on *untrusted remotes* — not
  applicable; the viewer only reads the **local `apps/` repo it controls** (no
  clone/fetch from user input).
- **Pagination: page-number** (`?page=N`), matching the users-list pager
  (`UserListPagination{page,total_pages,total_count}`). Count via
  `git rev-list --count HEAD`; page via `git log --skip=(N-1)*25 -n 25`
  (GitPython `iter_commits` with `skip`/`max_count`). Offset cost is negligible
  for a modest app repo; leave `?after=<sha>` keyset as a future knob if history
  ever gets huge.

## Data contract — DONE (`djangoapp/views/git_data.py`)

The Pydantic shapes the views return are **already defined**:
`UncommittedFile`, `CommitSummary`, `CommitFile`, `GitPagination`. The real
The real `git_data` functions, the `git_mock` functions, and the tests all conform to these — do
not redefine them.

## Mock data — DONE (`djangoapp/tests/views/git_mock.py`)

Deterministic canned data for smoke tests (the live `apps/` repo is
non-deterministic across envs). Functions mirror the view's data-call
signatures: `mock_uncommitted()`, `mock_commits(page)`, `mock_commit(commit_id)`,
`mock_diff_uncommitted(path)`, `mock_diff_commit(commit_id, path)`.

## Backend (`djangoapp/views/git.py`, new — mirror `files.py`)

The data layer is a set of **module-level functions** in `git_data.py` (real
GitPython impls) that the view calls directly:

- `git_data.uncommitted()`, `commits(page)`, `commit(commit_id)`,
  `diff_uncommitted(path)`, `diff_commit(commit_id, path)` — each reads the apps
  repo via a module-level `_APPS_REPO_ROOT` (resolves `apps/`, patchable to
  `fakeapps/` in tests, like `_REPO_ROOT` / `apps_root`).
- **No provider class, no `GIT_DATA_BACKEND` setting.** Tests swap behaviour by
  `patch`-ing these functions (see Tests) — works for both unit (`self.client`)
  and playwright because the playwright live server is a `LiveServerThread` in
  the **same process**, so a `patch` is visible to its requests.

Views (all start with `require_superuser(request)` → 404):

| Route | View | Calls | Returns |
|---|---|---|---|
| `GET /git` | `git_uncommitted_list` | `git_data.uncommitted()` | Inertia `GitUncommitted` |
| `GET /git/uncommitted/<path:rel>` | `git_uncommitted_diff` | `git_data.diff_uncommitted(rel)` | Inertia `GitDiff` (404 if `None`) |
| `GET /git/commits` | `git_commit_list` | `git_data.commits(filters.page)` | Inertia `GitCommitList` + pagination |
| `GET /git/commits/<commit_id>` | `git_commit_file_list` | `git_data.commit(commit_id)` | Inertia `GitCommit` (404 if `None`) |
| `GET /git/commits/<commit_id>/<path:rel>` | `git_commit_file_diff` | `git_data.diff_commit(commit_id, rel)` | Inertia `GitDiff` (404 if `None`) |

- `<path:rel>` is a Django path converter (matches `/`); confine via the
  `PathWrapper` resolve + `is_relative_to` pattern **rooted at the apps repo**
  (not `_REPO_ROOT`) → `..`/absolute/symlink escapes → 404.
- `<commit_id>`: validate hex; resolve full-or-short sha; unknown → 404.
- `?page=` validated like `UserListFilters.page` (`int, ge=1`).
- Reuse `host_template_data()` for the host shell; return `InertiaResponse`.

## Frontend (Vue/Inertia — reuse `Layout` + the lazy `filePreview` chunk)

- `GitUncommittedPage.vue`, `GitCommitListPage.vue`, `GitCommitPage.vue` —
  lists + the same pager UI as `UserList`.
- A shared `DiffViewer.vue` for both diff routes — renders the unified diff via
  highlight.js's **`diff`** grammar (green additions / red deletions).
- **Action:** register the `diff` language in `frontend/src/utils/filePreview.ts`
  (not currently registered) and expose `highlightDiff(text)`; call it explicitly
  (no `detectLanguage` — diffs aren't files).

## Tests

### Unit smoke (primary) — `djangoapp/tests/views/test_git.py`, `self.client` + mock
`patch` the `git_data` functions with the `git_mock` ones (in-process,
deterministic). Covers the full route/props/confinement/auth contract without
standing up a git repo:

```python
@patch("djangoapp.views.git_data.uncommitted", git_mock.mock_uncommitted)
@patch("djangoapp.views.git_data.commits", git_mock.mock_commits)
@patch("djangoapp.views.git_data.commit", git_mock.mock_commit)
@patch("djangoapp.views.git_data.diff_uncommitted", git_mock.mock_diff_uncommitted)
@patch("djangoapp.views.git_data.diff_commit", git_mock.mock_diff_commit)
```

1. `/git` → 2 uncommitted files; each links to its diff route.
2. `/git/uncommitted/TodoApp/app.py` → 200; diff text has `diff --git` + the
   `+@post_endpoint` line; `language="diff"`.
3. `/git/uncommitted/nope.py` → 404.
4. `/git/commits` → 3 commits newest-first; pagination `{1,1,3}`.
5. `/git/commits?page=2` → empty list, pager `{2,1,3}` (clamped, no 404).
6. `/git/commits/b2c3d4e` → subject "Add create endpoint" + files
   `[TodoApp/app.py, TodoApp/endpoints.py]`.
7. `/git/commits/a1b2c3d` → resolves short sha.
8. `/git/commits/deadbeef` → 404.
9. `/git/commits/b2c3d4e/TodoApp/endpoints.py` → diff with `new file mode` + `+`.
10. `/git/commits/b2c3d4e/nope.py` → 404.
11. `/git/uncommitted/../../etc/passwd` → 404 (confinement).
12. non-superuser `/git` → 404.
13. `/git/commits?page=abc` → 400 (filter validation) or clamped to 1.

### Real-git tests — `fakeapps/` inner repo
Fixture dir `djangoapp/tests/fakeapps/` (an inner repo like `apps/`). Base test
class **setUp, before each test**: `rm -rf fakeapps/.git`; `git init`; set
`user.name`/`user.email`; build known history (commit A adds `file1.py`; commit B
modifies `file1.py` + adds `file2.md`); leave uncommitted (modify `file1.py`, add
untracked `file3.txt`); patch the view's repo-root → `fakeapps/`. Same assertions
as the smoke suite but against real git output. `tearDown` removes `fakeapps/.git`.

### Playwright (required — render + interaction)
Patch the individual `git_data` functions with the `git_mock` ones for the test
(works because the playwright live server is a `LiveServerThread` in the same
process, so the patch is visible to its requests). Every test asserts
deterministic canned data; these verify the pages mount, the hljs `diff` grammar
renders, and the link chain works end-to-end in a real browser:

- `test_uncommitted_renders` — `/git` mounts; `.git-uncommitted-list` shows the 2
  files (`TodoApp/app.py`, `TodoApp/notes.md`), each linking to its diff route.
- `test_commit_list_renders` — `/git/commits` shows the 3 commits with their
  subjects (newest first) + a pager reading "page 1 of 1".
- `test_diff_highlighted` — `/git/uncommitted/TodoApp/app.py` renders `.git-diff`
  with `.hljs-addition` (green) / `.hljs-deletion` (red) spans — proves the
  `diff` grammar colors.
- `test_commit_navigation` — `/git/commits` → click a commit → the commit's files
  page → click a file → its diff renders (the full link chain works).
- `test_non_superuser_404` — anonymous viewer of `/git` gets 404 (the gate holds
  over HTTP, not just in-process).

## steer.md — evidence links in chat

Add to the "Linking to files" section a "Linking to git" subsection + directive:
when you make a claim about code or a change, link the most specific evidence:
- file source: `/files/<repo-relative path>`
- a file's uncommitted change: `/git/uncommitted/<path>`
- what a commit changed: `/git/commits/<sha>`
- a file's diff in a commit: `/git/commits/<sha>/<path>`
- commit list: `/git/commits` (paginated)

Example: "this regressed in
`<a href='/git/commits/ab12c3'>ab12c3</a>` — see the
`<a href='/git/commits/ab12c3/app.py'>diff</a>`."

## Constraints
- Superuser-only (404, never 403) — reuse `require_superuser`.
- Path confinement rooted at the **apps repo** (not the main `_REPO_ROOT`).
- Read-only — no git write operations from the viewer.
- `commit_id` and `path` validated; escapes/unknowns → 404.
- Diff rendering reuses the lazy `filePreview` chunk (register the `diff` grammar).

## Checklist
- [ ] add `gitpython` to runtime deps (`pyproject.toml`); `uv sync`
- [ ] real `git_data` functions (GitPython) reading a patchable `_APPS_REPO_ROOT`; `mock_*` functions in `git_mock.py`
- [ ] 5 views + routes in `urls.py` (all `require_superuser`, path-confined)
- [ ] register hljs `diff` grammar in `filePreview.ts`; `highlightDiff(text)`
- [ ] 4 Vue pages + `DiffViewer.vue`; reuse the `UserList` pager
- [ ] `fakeapps/` fixture + setUp `.git` reset; patchable repo-root
- [ ] unit smoke suite (`test_git.py`, mock-backed, #1–#13)
- [ ] real-git suite (`fakeapps/`)
- [ ] playwright suite (mock-mode server): uncommitted/commit-list/diff-highlight/navigation/anon-404
- [ ] steer.md "Linking to git" subsection
- [ ] `uv run ruff check` · `uv run mypy .` · `npm run lint`/`type-check`/`build-only`
