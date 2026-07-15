# Rename the build commands + sweep the deferred code markers

Two management commands have confusing names: `installorupdate` (it doesn't
"install" an OS thing — it builds the app's backend: runs `@setup` + seeds +
`@backend_test`s) and `buildapp` (it builds the frontend bundle and runs the
browser smoke). Rename them to say what they do:

- `installorupdate` → `buildbackend`
- `buildapp` → `buildfrontend`

This file also collects every live `# aihere` marker still in the code
(excluding `prevproject`, which is a frozen reference project, and historical
`prompts/`). Each marker is an instruction to change the code; they are copied
here as a checklist and must be removed from the code only as each is addressed
(never sooner).

The rename and the marker sweep touch overlapping files, so do the rename
first (it moves files via `git mv`, which carries the markers along), then
work through the markers.

---

# Rename the build commands

## Decisions

- **Command names** come from the filename in `management/commands/`, so the
  rename is a file move + updating every textual reference. Use `git mv` to
  keep history.
- **Public function** `install_or_update()` is imported by tests; rename it to
  `build_backend()` to match the new command.
- **Test files/classes/methods** that encode the old names are renamed too, so
  the suite stays greppable.
- **Gotcha — the rollback middleware's dotted path**: `_drive_playwright_tests`
  references it by module path
  `djangoapp.management.commands.buildapp.RollbackEveryRequestMiddleware`. That
  string MUST change to `...buildfrontend...`, or the drive's `modify_settings`
  import fails at runtime (it is only exercised by the playwright-tagged test).
- Markers in a renamed file travel with it; do not delete them during the rename.

## Detailed plan

- [x] move the command modules with `git mv`:
    - [x] `djangoapp/management/commands/installorupdate.py` → `buildbackend.py`
    - [x] `djangoapp/management/commands/buildapp.py` → `buildfrontend.py`
- [x] rename the public function and its self-references (in `buildbackend.py`):
    - [x] `def install_or_update(...)` → `def build_backend(...)` [installorupdate.py:42]
    - [x] docstring + `_stderr_line` docstring refs [installorupdate.py:37,43]
    - [x] the `force_reload` comment "installorupdate is a fresh CLI process" [installorupdate.py:62]
    - [x] the three `f"installorupdate {identity} ..."` error/err strings [installorupdate.py:92,95,114]
    - [x] the `Command.help` usage string + the `build_backend(...)` call inside `handle()` [installorupdate.py:121,133]
- [x] update `buildfrontend.py`'s own references to itself:
    - [x] module docstring `Usage: ./run djangomanage buildapp ...` [buildapp.py:3]
    - [x] `Command.help` usage string [buildapp.py:46]
    - [x] the `modify_settings` middleware dotted path
          `djangoapp.management.commands.buildapp.RollbackEveryRequestMiddleware`
          → `...buildfrontend...` [buildapp.py modify_settings block]
    - [x] the lazy-import comment "importing buildapp never needs playwright" [buildapp.py:246]
- [x] rename the test files with `git mv` and update them:
    - [x] `test_installorupdate.py` → `test_buildbackend.py`
    - [x] `test_buildapp.py` → `test_buildfrontend.py`
    - [x] imports: `from ...installorupdate import install_or_update` → `from ...buildbackend import build_backend` [test_installorupdate.py:12, test_buildapp.py:17, test_endpoints.py:11]
    - [x] import: `from ...buildapp import Command` → `from ...buildfrontend import Command` [test_buildapp.py:16]
    - [x] every `install_or_update(...)` call → `build_backend(...)` [test_installorupdate.py:66, test_buildapp.py:52,160, test_endpoints.py:50]
    - [x] every `call_command("buildapp", ...)` → `call_command("buildfrontend", ...)` [test_buildapp.py:57,62,68,183]
    - [x] every `patch("djangoapp.management.commands.buildapp._drive_playwright_tests")` → `...buildfrontend...` [test_buildapp.py:100,106,116]
    - [x] class `InstallOrUpdateTests` → `BuildBackendTests` [test_installorupdate.py]
    - [x] classes `BuildappCommandTests` / `BuildappPlaywrightPhaseTests` / `BuildappDrivesPlaywrightTests` → `BuildFrontend...` [test_buildapp.py]
    - [x] test method names `test_buildapp_*` → `test_buildfrontend_*` [test_buildapp.py:54,59,64,173]
    - [x] docstrings/inline comments that name `buildapp`/`installorupdate` (≈10 spots across both test files)
- [x] update fixture-app docstrings + the one cross-reference that names these:
    - [x] `Tests/Browser/app.py` (5 spots: module docstring + the rollback comments) [Browser/app.py:2,5,10,142,153]
    - [x] `Tests/Page/app.py` "Feeds test_installorupdate.py" [Page/app.py:4]
    - [x] `Tests/Endpoints/app.py` "rendering is exercised by Tests/Browser via buildapp" [Endpoints/app.py:8]
    - [x] `Tests/FailsSetup/app.py` + `Tests/FailsTest/app.py` — `InstallOrUpdateTests.test_...` refs → `BuildBackendTests.test_...` [FailsSetup/app.py:7, FailsTest/app.py:7]
    - [x] `djangoapp/models/applications.py` comment "by setup/buildapp" [applications.py:202]
    - [x] `djangoapp/apps/dynamic_module.py` comment "by setup/buildapp in any process" [dynamic_module.py:297]
- [x] update the docs:
    - [x] `README.md` — the two `./run djangomanage ...` lines + the 2 prose mentions [README.md:176,187,198,203]
    - [x] `docs/apps/README.md` — `buildapp`/`installorupdate` usage + prose [docs/apps/README.md:23,33,37,39,41,51]
    - [x] `djangoapp/tests/appfixtures/README.md` — file-name refs + the Tests/Browser row [appfixtures/README.md:7,19,21]
    - [x] `TODO.md` — remove the now-done `rename` note (installorupdate→buildbackend, buildapp→buildfrontend)
- [x] Lint and verify: `./run lintfix`, `./run typecheck`, `./run test`, `./run checkall`

## Notes / risks

- The middleware dotted path is a runtime-only import (only the
  `@tag("playwright")` `BuildFrontendDrivesPlaywrightTests` exercises it), so a
  miss there passes unit tests but fails the playwright phase — assert it.
- `prevproject/` is a frozen reference; do not touch it. Historical `prompts/`
  mention the old names — leave them (they record past work).
- No `./run` wrapper or `.kilo/` command references these names, so nothing
  else to update there.

---

# Deferred code markers collected from the codebase

Copied from every live `# aihere` comment (current project only). Grouped by
file; do each, then delete the comment. Files listed under their **current**
names — if the rename lands first, adjust the paths.

## `djangoapp/management/commands/buildapp.py` (→ `buildfrontend.py`)

- [x] `static_folder` should be a method `.static_folder()`, not a property, for clarity (`# aihere dont keep as property`) [buildapp.py:86]
- [x] move the `npm = shutil.which("npm")` / missing-npm `CommandError` check into `_run_npm` (`# aihere why not put this in _run_npm`) [buildapp.py:88]
- [x] drop `_run_npm`'s `step` param; build the error message from `args` instead (`# aihere dont take this param`) [buildapp.py:148]

## `djangoapp/management/commands/installorupdate.py` (→ `buildbackend.py`)

- [x] give the `err` param a better name (`# aihere a better name for err`) [installorupdate.py:41]
- [x] let exceptions propagate instead of wrapping foreign exceptions in `CommandError`; only do work before the reraise (`# aihere let exceptions fail`) [installorupdate.py:66]
- [x] change the module/type so `setup_function` can't be `None`, then drop the `assert` mypy guard (`# aihere modify class so setup_function cant be None`) [installorupdate.py:74]

## `djangoapp/models/applications.py`

- [x] make `Application` have no properties — convert `script_path` to a method (`# aihere no properties for this class`) [applications.py:168]
- [x] rename `get_table(name)` → `.table_as_model(name)` (`# aihere should be .table_as_model(name)`) [applications.py:217]
- [x] remove the middleware reference above `AppsGeneration` (`# aihere remove middleware reference`) [applications.py:426]

## `djangoapp/apps/dynamic_module.py`

- [x] remove the unneeded `DynamicModuleError` type (`# aihere no need of this type`) [dynamic_module.py:202]
- [x] rename `sync_app_caches` to convey that the temp caches are actually cleared (`# aihere rename to be more descriptive`) [dynamic_module.py:284]

## Tests

- [x] move the two "fails/rolls back" tests to sit right after `test_backend_test_writes_roll_back` so the test names read as a top-to-bottom trend (`# aihere move below two tests`) [test_installorupdate.py:107]
- [x] add/expand the explanation of which `app.py` test the `test_buildapp_drives_browser_app` assertion corresponds to (`# aihere explain the corresponding test in app.py`) [test_buildapp.py:172]
- [x] merge `test_demo_random_code` into `test_demo_random_code_varies` (`# aihere merge above test to this`) [test_endpoints.py:61]

---

# Document the user-management features in the README

The README already covers the auth setup (Google OAuth via `addgoogleoauth`,
promoting via `makesuperuser`) and has a `### Superuser views` section — but
that section lists only the `/apps/...` application-management views
[README.md:216-222] and **omits the whole `/users/*` management UI**
(`djangoapp/views/users.py`). Add a user-management section so operators and
contributors know the routes, who can reach them, and the identity/visibility
rules.

## What exists (ground the docs in the code)

Routes under `USERS_PATH_PREFIX = "/users"` (`djangoapp/views/users.py`):

- `/users/list` — superuser-only paginated list (25/page, `orphans=5`); `?q=`
  trigram search across name/username; `?page=N`. `superuser_or_404` → 404 for
  anyone else.
- `/users/api/search?q=` — superuser-only, top-20 username matches for the list
  page's jump-to-profile.
- `/users/id/{public_id}` — the profile page. Public bits (first/last name)
  always; `username` + `description` only when `has_public_profile`; a
  superuser viewer additionally sees the admin panel (email, flags, history
  count). Anonymous never sees admin attrs.
- `/users/edit/{public_id}` (GET form + POST) — superuser-only edit.
  `username` is read-only; editable: first/last name, email, description
  (HTML-sanitized on save), `has_public_profile`, `is_active`, `is_staff`,
  `is_superuser`.
- `/users/history/{public_id}` — superuser-only audit trail (`UserHistory`).

Model facts worth stating (`djangoapp/models/base.py`):

- `public_id` is a URL-safe UUID7 used in **all** URLs and API responses; the
  integer `pk` is never sent to clients.
- `has_public_profile` gates visibility of username/description to anonymous.
- `User.update(...)` records the diff into `UserHistory` (so `makesuperuser`
  and the edit endpoint are audited).

## Decisions

- Non-superusers get a **404** (not 403) on every management route, to avoid
  leaking which users exist — document this explicitly.
- Call out the **admin self-lockout guard**: a superuser can't clear their own
  `is_superuser`/`is_active`, and because every route gates on an active
  superuser the active-superuser count can't fall to zero via the UI.
- Rename/relable the existing `### Superuser views` section: it is really
  *application*-management views, not user-management — split it so the new
  user-management section isn't confused with it.

## Checklist

- [x] add a `## User management` section to `README.md` covering:
    - [x] the `/users/*` routes (list, search, profile, edit, history) with a
          one-line purpose + who can reach each
    - [x] the 404-for-non-superusers rule on the management routes
    - [x] profile visibility: public name always; username/description only
          when `has_public_profile`; admin panel (email/flags/history) for
          superuser viewers only
    - [x] editable fields + read-only `username` + the self-lockout guard
    - [x] identity rule: URLs/API use `public_id` (UUID7), never the `pk`
    - [x] the `UserHistory` audit trail (recorded via `User.update`)
- [x] relabel the current `### Superuser views` section [README.md:216] so it
      reads as application-management (not user-management), or fold it into
      the app-framework section
- [x] cross-link from `## Promote a user to superuser` [README.md:33] to the
      new user-management section (the promoted user is what unlocks it)
- [x] keep it consistent with the `addgoogleoauth`/`makesuperuser` examples
      (same `./run djangomanage` / `./run python manage.py` style)
- [x] no code change expected — docs-only; still run `./run checkall` to be safe
