# App frontends (reference)

An **app** is a Python module (`app.py`) plus an optional Vue+Inertia frontend.
This directory holds the reference app apps copy/adopt, and documents the
commands and conventions for building/running one.


## Directory layout

```
apps/<app>/                      # install dir (gitignored at the repo root)
    app.py
    frontend/
        package.json
        vite.config.js
        src/
            main.ts
            pages/<Component>.vue
            components/Layout.vue
```

The committed **reference app** lives in `docs/apps/reference/` (copy it to
`apps/<app>/` to start a new app). `buildfrontend` writes to
`djangoapp/static/djangoapp/apps/<app>/` (gitignored build artifacts).

## Commands (workflow order)

```bash
# 1. Install: run @setup functions (resumes from the last completed), then
#    @backend_tests. An app may declare several @setup functions (source
#    order); buildbackend runs only the ones past the last completed, tracked
#    via Application.executed_setups. Rolls back the whole install on any
#    failure. No CLI for creating apps/tables — that is @setup's job.
./run djangomanage buildbackend <app>

# 2. Build the app's frontend into its derived static folder (vite, emptyOutDir),
#    then drive its @playwright_test funcs in a browser against the live install
#    (a green buildfrontend means the bundle mounts + interacts). Constant main.js path;
#    cache-bust via ?cache_buster=<generation>. --skip-playwright builds only
#    (fast dev-loop; the browser suite is skipped). buildfrontend also installs deps
#    (npm install) when node_modules is missing.
./run djangomanage buildfrontend <app>

# Read-only inspection of what's installed:
./run djangomanage applications list_applications
./run djangomanage applications describe_application_table --app <a> --name <t>
```

## Dev loop & invalidation

Edit `app.py`/Vue → `setup`/`buildfrontend` → refresh the browser. A running
devserver or gunicorn worker picks up a `setup` install **without a restart**:
`setup` bumps an `AppsGeneration` counter, and every registry/view call runs
`clear_app_caches`, which resets the worker's dynamic-model + app-module caches
when the counter changes (no middleware needed).

> **Multi-step, resumable setups.** An app may declare several `@setup`
> functions; they run in source order, and `buildbackend` **resumes from the
> last completed one** — `Application.executed_setups` records the `__name__`s
> that have finished, and only the suffix past that recorded prefix runs.
> Forward-only (like DB migrations): a completed setup never re-runs; to redo
> work, append a *new* setup. The loaded module's setup names must extend the
> recorded prefix (same names, same order) — a rename, reorder, mid-list
> deletion, or downgrade is refused with an error naming both lists.

## Mandatory shell checklist (definition of done for every app frontend)

Every app frontend **must** satisfy this — verify each before considering an app
done. (The reference app under `docs/apps/reference/` is the canonical example.)

- [ ] Wraps every page in the shared `Layout` (current user + home link).
- [ ] Shows the current logged-in user via the shared `viewer` prop
      (`usePage().props.user`), not a hardcoded value.
- [ ] Global error handling surfaces as a toast (`showErrorToast`); no silent
      `console.error` and no bare `catch {}` that swallows errors.
- [ ] Every client-side `axios` call is wrapped in `try/catch`, calls
      `showErrorToast(e, fallback)` in the catch, and parses the response with a
      zod schema when the page has one. Never `throw` after toasting
      (double-toasts via the global handler).
- [ ] "Go home" / back-to-host navigation works.
- [ ] Loads Bootstrap exactly once **and includes its CSS** — the app bundle
      ships Bootstrap itself (`import "bootstrap"` **and**
      `import "bootstrap/dist/css/bootstrap.min.css"` in `main.ts`). App pages
      load only the app bundle; the host CSS/JS does not load on them, so the
      bundle must carry Bootstrap (the host uses it) or the app renders unstyled.
- [ ] `buildfrontend <app>` emits CSS —
      `djangoapp/static/djangoapp/apps/<app>/main.css` exists and is non-empty
      (a build that emits only JS leaves the page unstyled).

## Reference app

`docs/apps/reference/` — a minimal but complete app: `app.py` with `@setup`,
`@get_endpoint` (one returning JSON, one returning `InertiaPage`), `@backend_test`;
a `frontend/` with `vite.config.js`,
`main.ts` (createInertiaApp + axios CSRF + global error toast + Bootstrap), a
`Layout.vue` (current user + home link), and a page component. Copy it, rename,
and adapt.

`@backend_test`s call endpoints in-process (no HTTP), passing each handler an
`HttpRequest` built by `a_test_request()` — the same object the HTTP layer hands
a handler, so `request.user.is_authenticated`, `request.GET`, `request.POST`, and
`request.body` all work. `user` defaults to `AnonymousUser` (unauthenticated);
`params=`/`data=`/`json=` populate the query string, form body, and JSON body
respectively. A body (`data`/`json`) is incompatible with GET and the two are
mutually exclusive — both raise `ValueError`.

## Request validation with `BaseSchema`

A `@post_endpoint`/`@put_endpoint` that takes a JSON body should declare its shape
as a subclass of `BaseSchema` (a pydantic `BaseModel`, exported from
`djangoapp.apps.shortcuts`) and parse the request with `from_json_request`, which
returns a **422** (`ninja.errors.ValidationError`) on any bad input instead of
500-ing on a `KeyError`/`TypeError`:

```python
from djangoapp.apps.shortcuts import BaseSchema
from pydantic import Field, field_validator

class CreateItem(BaseSchema):
    code: str = Field(max_length=10)

    @field_validator("code")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("code is required")
        return value

@post_endpoint
def add_item(request: HttpRequest) -> ItemOut:
    item = CreateItem.from_json_request(request)  # 422 if the body is invalid
    ...
```

`from_json_request` reads `request.body` as JSON and validates it against the
schema; a non-JSON body or any pydantic validation failure raises
`ninja.errors.ValidationError` → an HTTP **422** whose `detail` is a
machine-parseable JSON list of field errors (the rejected `input` and pydantic
`url` are stripped, so sensitive values aren't echoed). Example 422 bodies:

```json
{"detail": [
  {"type": "missing", "loc": ["code"], "msg": "Field required"}
]}
```

```json
{"detail": [
  {"type": "string_too_long", "loc": ["code"],
   "msg": "String should have at most 10 characters",
   "ctx": {"max_length": 10}}
]}
```

```json
{"detail": [
  {"loc": ["body"], "msg": "Request body must be valid JSON."}
]}
```

(The last has no `type` key — it's `from_json_request`'s own guard for a non-JSON
body, not a pydantic field error.) Use `expect_error` (also from `shortcuts`) to
assert the 422 in a `@backend_test`:

```python
from djangoapp.apps.shortcuts import a_test_request, backend_test, expect_error
from ninja.errors import ValidationError

@backend_test
def test_add_item_rejects_bad_input() -> None:
    with expect_error() as e:
        add_item(a_test_request(method="POST", json={}))  # missing code
    assert isinstance(e.exception, ValidationError)
    # the error body names the bad field:
    err = e.exception.errors[0]
    assert tuple(err["loc"]) == ("code",)
```
