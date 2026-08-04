# Git viewer worktrees: pending files in `main/` and `copy/` on one page

The `/git` viewer reads two worktrees: `main` (the repo the dev server runs in)
and `copy` (the scratch sibling `createscratch` builds). The uncommitted **list**
(`/git/uncommitted/`) shows every worktree's pending files together — `main`
then `copy` — each file marked with a git-status letter (U/M/A/D); an
uncommitted **diff** takes a worktree segment, so a file links like
`/git/uncommitted/<worktree>/<path>` (e.g. `/git/uncommitted/main/TODO.md`).

## URL scheme

- `/git/uncommitted/` — every worktree's pending files, one page (main, copy).
- `/git/uncommitted/<worktree>/<path>` — one file's uncommitted diff.
- Commits are `main`-only: `/git/commits`, `/git/commits/<sha>`,
  `/git/commits/<sha>/<path>` (`copy/`'s history is just its throwaway baseline).

`<worktree>` is a short word (`[A-Za-z0-9_-]+`); the viewer knows `main` (=
`BASE_DIR`) and `copy` (= its sibling). Unknown worktrees → 404; a bare worktree
path with no file (`/git/uncommitted/main`) 404s rather than serving a
per-worktree list.

## Backend

- `djangoapp/views/git_data.py` — `worktree_root(name)` (`main` → `_REPO_ROOT`,
  `copy` → its sibling) and the worktree threaded through `_repo(name)` /
  `uncommitted(name)` / `diff_uncommitted(path, name)`. Both derive from
  `_REPO_ROOT` so tests patching it get both.
- `djangoapp/views/git.py` — `WORKTREES = ("main", "copy")` (URL-accepted names;
  `_worktree_or_404` 404s on unknown). `git_uncommitted_list(request)` builds a
  section per worktree (`GitUncommittedWorktree{name, files}`), **omitting** any
  whose repo is missing (no `copy/` yet) instead of 404-ing the whole page.
  `git_uncommitted_diff(request, worktree, rel)` is unchanged; `_confined_to_repo`
  takes the worktree root as a parameter.
- `djangoapp/urls.py` — `^git/uncommitted/?$` (list) and
  `^git/uncommitted/(?P<worktree>[A-Za-z0-9_-]+)/(?P<rel>.+)$` (diff; `.+` so a
  bare `/git/uncommitted/<worktree>` 404s rather than APPEND_SLASH-redirecting).

## Frontend

- `frontend/src/pages/GitUncommitted.vue` — one section per worktree (heading +
  files). Each file: a status letter (U/M/A/D) left of the path, no per-file
  outline (`list-unstyled`). Colours: untracked grey (`text-muted`), deleted
  strikethrough, added/modified black. File links keep the worktree:
  `/git/uncommitted/<worktree>/<path>`. No worktree switcher.
- `frontend/src/schemas.ts` — `GitUncommittedPropsSchema` =
  `{ worktrees: [{ name, files }] }`.
- `frontend/src/components/GitNav.vue` + `Layout.vue` — "Uncommitted"/"Git" point
  at `/git/uncommitted/`; nav links are `nav-link` (not buttons), the navbar has
  a background, and the "Hello, user" greeting sits at the right (`ms-auto`).

## Tests (real repos, no mocks)

- `djangoapp/tests/_git_fixtures.py` — `GitRepoMixin` (mixed into both suites)
  builds the shared `parent/main` + `parent/copy` repos + the `_REPO_ROOT` patch.
- `djangoapp/tests/views/test_git.py` — combined-list assertions (both worktrees
  on one page), missing-`copy` omitted from the list, missing-repo diff 404,
  unknown-worktree 404, per-worktree path confinement.
- `djangoapp/tests/playwright/test_git.py` — no function mocks; real repos.
  `test_uncommitted_renders` checks both worktrees on one page, the U/M status
  letters, and the untracked rows greyed.

## Docs

- `agentconfig/steer.md` — "Linking to git" lists `/git/uncommitted/` (combined)
  + `/git/uncommitted/<worktree>/<path>` diffs; the copy-workflow notes say both
  worktrees' pending files show live on `/git/uncommitted/`.
- `prompts/20260727-git-viewer.md` — supersede note pointing here.

## Checklist

- [x] `git_data.py`: `worktree_root()`; worktree threaded through `_repo`/
      `uncommitted`/`diff_uncommitted`; commits stay `main`-only
- [x] `git.py`: `WORKTREES` + `_worktree_or_404`; combined `git_uncommitted_list`
      (one section per worktree, missing worktree omitted); diff unchanged
- [x] `urls.py`: `/git/uncommitted/` list + `/git/uncommitted/<wt>/<path>` diff
- [x] `schemas.ts` + `GitUncommitted.vue`: combined sections, U/M/A/D letters,
      grey/strike/black, no per-file outline, no switcher
- [x] `GitNav.vue`/`Layout.vue` → `/git/uncommitted/`; navbar background +
      greeting right-aligned; nav links de-buttoned to `nav-link`
- [x] views + playwright tests updated for the combined page; ruff/mypy clean
- [x] steer.md + this prompt file updated
