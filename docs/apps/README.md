# App frontends (reference)

An **app** is a Python module (`app.py`) plus an optional Vue+Inertia frontend.
This directory holds the reference app apps copy/adopt, and documents the
commands and conventions for building/running one.


## Directory layout

```
apps/<collection>/<app>/        # install dir (gitignored at the repo root)
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
`apps/<collection>/<app>/` to start a new app). `buildfrontend` writes to
`djangoapp/static/djangoapp/apps/<collection>/<app>/` (gitignored build
artifacts).

## Commands (workflow order)

```bash
# 1. Install: run @setup (creates app+tables, commits) then @backend_test s.
#    Rolls back the whole install on any failure. No CLI for creating
#    apps/tables — that is @setup's job.
./run djangomanage buildbackend <collection>/<app>

# 2. Build the app's frontend into its derived static folder (vite, emptyOutDir),
#    then drive its @playwright_test funcs in a browser against the live install
#    (a green buildfrontend means the bundle mounts + interacts). Constant main.js path;
#    cache-bust via ?cache_buster=<generation>. --skip-playwright builds only
#    (fast dev-loop; the browser suite is skipped). buildfrontend also installs deps
#    (npm install) when node_modules is missing.
./run djangomanage buildfrontend <collection>/<app>

# Read-only inspection of what's installed:
./run djangomanage applications list_application_collections
./run djangomanage applications list_application_collection --name <collection>
./run djangomanage applications describe_application_table --appcollection <c> --app <a> --name <t>
```

## Dev loop & invalidation

Edit `app.py`/Vue → `setup`/`buildfrontend` → refresh the browser. A running
devserver or gunicorn worker picks up a `setup` install **without a restart**:
`setup` bumps an `AppsGeneration` counter, and every registry/view call runs
`clear_app_caches`, which resets the worker's dynamic-model + app-module caches
when the counter changes (no middleware needed).

> Open issue: re-running `setup` on an already-installed app errors on the
> collection/app unique constraints (the "track setup runs" TODO). Until that
> lands, reinstalling means dropping the app first.

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
- [ ] Loads Bootstrap exactly once (app pages load only the app bundle; the
      host CSS must not also load on app pages).

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
