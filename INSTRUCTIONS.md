Use README.md as basic reference.

## Environment files
All env config lives in root `.env` (dev) and `.env.vm` (test VM), copied
from the matched `.env.example` / `.env.vm.example` templates. If you find a
LEGACY `deploy/env.vm` or `.env_vm` file, RENAME it to root `.env.vm` before
provisioning. `SECRET_KEY` / `DB_PASSWORD` must never stay `DANGEROUSLYUNSET`
— generate values with `openssl rand -hex 32`.

Do not run commands like:
```bash
python3 << 'EOF'
...
```
Create the file, run it. I will delete them later. Or the agent will interpret it as a series of bash commands and wait for my approval.  
Create the file inside the project dir or my agent will pause and wait for my approval.  

Run uv command instead of running python/python3 directly.

Try not to generate multiline bash commands. My agent thinks each line is a command and wait for me to .

Do not run `rm` or `ls` in bash. Use the tool calls.
Do not use curl to read urls. Use browser tool call.

## Bash helper functions over inline `bash -c` scripts
For multi-command remote scripts (`multipass exec ... -- sudo bash -c`), do not
inline the script as a quoted string. Define a real function and embed it with
`declare -f` — the body stays ordinary shell (highlighted, lintable, reusable
across calls). See `vm_app` / `deploy_ourapp` inside `checkframework2` in `run`.

Right:
```bash
deploy_ourapp() {
  tar xzf /tmp/testapp-ourapp.tgz -C /srv/app/main
  chown -R app:app /srv/app/main/ourapp
  find /srv/app/main/ourapp -exec chmod g+w {} +
  rm -f /tmp/testapp-ourapp.tgz
}

multipass exec app -- sudo bash -c "$(declare -f deploy_ourapp); deploy_ourapp"
```

Wrong — one illegible line, no editor support, and nested `python -c` calls
grow a `\"` escape per level:
```bash
multipass exec app -- sudo bash -c \
  "tar xzf /tmp/testapp-ourapp.tgz -C /srv/app/main && chown -R app:app /srv/app/main/ourapp && find /srv/app/main/ourapp -exec chmod g+w {} + && rm -f /tmp/testapp-ourapp.tgz"
```

`$` and other symbols:
- `$(declare -f fn)` output is never re-expanded, so `$VAR`, `"$1"`, quotes and
  backticks inside the function body are safe — they evaluate on the remote
  side only.
- Keep the double-quoted string to exactly `$(declare -f fn); fn`. A `$NAME`
  or backtick TYPED there expands/runs HOST-side (wrong machine, wrong values).
  A `$var` whose VALUE carries `$`/backticks inserts verbatim and is then
  evaluated as remote shell — quoting and injection bugs. If you must append a
  variable like `vm_app` does (`"; $1"`), pass single-quoted literals only.
- Fixed literal arguments go in single quotes inside the double quotes:
  `"$(declare -f fn); fn 'literal'"`. The literal must contain no `$`,
  backticks, or quotes; if it does, restructure the function to need no
  argument instead of escaping.

## aihere
If I mention `aihere`, grep for `aihere` in whole codebase except `.idea`, copy all of them into some todo list. They may not be comments — a marker can sit on any line of any file (code, strings, docs); treat the line it's on (plus its surroundings) as the instruction. The comments are instructions to modify the codebase. If you have lines with aihere in context and I mention aihere again, look at the new instances. Never remove the comments before addressing them. If you are not implementing them, write them down in existing md file.

## Prompts
They are present in `prompts/` directory and have a filename format of `yyyymmdd-slug-slug.md`.

I will write brief requirements by hand. I will then want you to prepare a detailed plan and then checklists. Append to my handwritten contents.

Add tests in checklist as soon as possible after implementing them.

Before you mark something as complete in your todo, ensure the checklist items are crossed out. Only then proceed.

When I ask you act, add checklist items into your todo before implementing.

Do dont add `aihere` to headings or citations. 
You have created examples like `#### Phase 22: Code Refactoring (aihere items)` and `- [x] Add `_modelname()` method to  [aihere-modelname-method] [djangoapp/models.py:197-213]`
In both places `aihere` is just adding noise.

Nest stuff
Instead of:
```markdown
- [ ] Added .clean() to class A
- [ ] Added .clean() to class B
- [ ] Added .clean() to class C
```

Have
```markdown
- [ ] added .clean() to
    - [ ] class A
    - [ ] class B
    - [ ] class C
```

## Backend
Ensure that functions are imported correctly. When introducing new symbols to a file, always ensure its imported.  
Imports must be at top of the file, except to solve circular import problems. If you import somewhere but the top, explain why with a comment. Dont just do `# noqa: PLC0415` and leave it.

Dont write inane docstrings. Explain why, not what.

Annotate inputs and outputs of all python functions you write.  

When I ask you to remove a python function, delete all usages and import too.  

Keep my TODOs and commented code. Do not reformat.
Keep my comments. Do not delete till I explicitly ask you.

If a user cannot access a resource due to `model.method()` then they should get a 404 error.

If we have to suppress both mypy and ruff in a single like do `# type: ignore[no-untyped-def] # noqa: ANN002, ARG002, ANN003` instead of `# noqa: ANN002, ARG002, ANN003 # type: ignore[no-untyped-def] `

When adding suppressing comments like ` # noqa: C901` add `# noqa: C901 # function too complex: 11`. Instead of `noqa: E501` write `noqa: E501 let comments exceed line width`. Explain why this particular line needs linting suppression.

Do not edit pyproject.toml tool.ruff.lint.ignore to suppress errors.

Use `./run python` to run python commands. Or it will interrupt my workflow.  

You must not allow `.pk` and `.id` to be sent to client. It is an unacceptable leak. Send only the designated public ids (which may be the pk) to client. All url paths and api responses use public ids.

#### Test database
We are not using Sqlite for main db, so dont try to delete db.sqlite3 nor delete Postgres db. Try `./run test --keepdb...`   
Dont change keepdb settings anywhere.   
Dont run `psql -U postgres -c "DROP DATABASE IF EXISTS test_tables;" 2>&1` either. You dont need to.

Default on_delete policy should be models.RESTRICT

If django manage complaints there is already a database called `test_something`, and it asks you if it should delete it, one workaround could be `--noinput` to test command. Do not try `drop database` except as last resort.  

### Tests
We need docstrings like:
```
class SomeTests(TestCase):
    """A title-like line

    Brief explanation. More why than what

    Common characteristics. One line per method in correct order.
    - method1, whats being asserted, one line
    - method2, whats being asserted, one line
    - ....


    Tests verify correct pydantic model type, field name, value, and choice title when applicable.
    """
    def method1():
        "method1, whats being asserted, maybe in more detail"
        ...
    
    def method2():
        "method2, whats being asserted, maybe in more detail"
        ...

# example class:
class RowUpdateValueSerializerTests(TestCase):
    """Tests for ROW_VALUE_SERIALIZERS dictionary functions.

    Tests use dictionary lookups: ROW_VALUE_SERIALIZERS[type(field)](field, value)

    Returns RowUpdate*Value pydantic models for row column display:
    - CharField: RowUpdateCharValue or RowUpdateCharChoiceValue (with value_title)
    - TextField: RowUpdateTextValue
    - IntegerField: RowUpdateIntegerValue or RowUpdateIntegerChoiceValue (with value_title)
    - BooleanField: RowUpdateBooleanValue
    - DecimalField: RowUpdateDecimalValue (value as string or None)
    - DateTimeField: RowUpdateDatetimeValue (value as ISO string or None)
    - FileField: RowUpdateFileValue (value as dict or None)
    - ForeignKey: RowUpdateForeignKeyValue (value as dict with id/title or None)

    Tests verify correct pydantic model type, field name, value, and choice title when applicable.
    """
```

In the bullet list, if two adjacent lines seem similar, in one line, mention whats different than previous line.

When adding/editing tests, keep method and class docstrings up to date, even for test classes which don't have docstrings.

## Frontend
Do not introduce inline css or Vue scoped styles. Ensure rules are in main.css.  
Do not create `<a href='#'>...` with click handlers till I explicitly ask you.  
Do not run `npm run build-only` except when I explicitly mention.  

After changes to TS/JS files, run these lint commands and iterate till it reports zero errors.

When you run npm commands, do not `cd ..` or it will cause my harness to interrupt me. If you must, know the pwd and `cd <absolute_path>` instead of `cd ..`

`npm run dev` shouldn't be run from an agent since it does not terminate.

Every client-side HTTP call must go through the framework's `utils/http.ts` (`postJSON`/`getJSON`/`streamPost`), be wrapped in `try/catch`, call `showErrorToast(e, fallback)` in the catch, and parse the response with a zod schema when the page has one. No silent `console.error`, no bare `catch {}` that swallows the error, and never `throw` after toasting (it double-toasts via the global handler).

## Linting
I have added linting commands in backend and frontend. When I ask you backend changes, run first backend lint command, make fixes and then run same command till it passes. Do not report something is fixed till the command succeeds. Then run second lint command the same way. Ensure all lint commands are done.  
Commands in this section should be considered safe.   
Never give up on a lint by claiming its a preexisting issue. You are always given a successfully linting codebase. You must fix it.  

### Backend
After changing Python/Backend code, run these in order:

1. Lint fix: `./run lintfix`  
2. Mypy wrapper: `./run typecheck`  
3. Test suite: `./run test` (note that these will not run playwright tests at all)

Playwright tests are at: `./run playwrighttest`  
Since Playwright tests could take a long time, you can refer playwrighttest and run each failing test individually.  
If there are fixable linting errors, please fix them before proceeding  
If there are more than 5 test failures, run typecheck and ensure its error free.

### Frontend
After changing TS/frontend code, run these in order:

1. Lint fix `cd frontend && npm run lint:fix`  
2. Type check: `cd frontend && npm run type-check`  
3. Lint: `cd frontend && npm run lint`  
4. Final check: `./run checkframework1` (this checks backend and then frontend)

Playwright tests are at: `./run playwrighttest`  
Note that `playwrighttest` takes no arguments — extra flags/module labels are ignored and the full tagged suite runs. To run one module (test_users, test_files, test_git, test_client_errors under `djangoapp/tests/playwright/`), invoke the underlying command directly with the label:

    uv run manage.py test --tag playwright --noinput djangoapp.tests.playwright.test_users

### Playwright
When you encounter Playwright tests failing, consider that a showstopper. Isolate one failing module with the direct command above (it will be time consuming to run the full suite) and diagnose it.

Dont change any timeout settings for Playwright tests. Everything is expected to run before timeout. I dont want any statement like `timeout=5000` in my tests. 
Use only `page.wait_for_url` or `page.wait_for_selector` for Playwright tests except to debug stuff. Add classes to the html elements to facilitate this. page.wait_for_event, page.wait_for_timeout, page.wait_for_function, page.wait_for_load_state will lead to fragile, hard to understand tests. Do not use them except temporarily.

Something like:
```python
def handle_console(msg: ConsoleMessage) -> None:
    print(
        {
            "type": msg.type,
            "text": msg.text,
            "location": msg.location,
        }
    )

page.on("console", handle_console)

```

### Finally

`./run checkframework1`

The checkframework1 runs all the individual commands. For example, if playwright tests fail, run playwright test command only, preferably run only the failing tests till they pass, then run checkframework1.

To save time, iterate and run the failing commands. Running failing command will take a fraction of the time.

For example, when this happens, keep fixing and running `npm run lint` many times before running checkframework1.

```bash
Running frontend linting

> frontend@0.0.0 lint
> eslint .


/Users/jesvin/dev/tables/frontend/src/components/RichTextEditor.vue
  80:22  error    '_items' is defined but never used. Allowed unused args must ...used                                           @typescript-eslint/no-unused-vars
  94:7   warning  Unused eslint-disable directive (no problems were reported from 'no-unused-vars')

✖ 5 problems (4 errors, 1 warning)
```


Only after `./run checkframework1` succeeds till the finish, you can say the task is complete. If there are errors, you must fix them and keep iterating till checkframework1 passes.

## Review
I may ask you to review code. If its a commit or a set of commits, check the changed prompts file. Verify each checklist item is correctly reflected in code, especially when conflicting checklist items exist. Check the code itself. Find any security issues and put them as high priority.