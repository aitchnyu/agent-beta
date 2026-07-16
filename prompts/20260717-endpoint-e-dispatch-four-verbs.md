# Endpoint simplification: unified `/e` dispatch, four verbs, raw `request`

Collapse the two endpoint URL shapes (`.../endpoint/get/{fn}`, `.../endpoint/inertia/{fn}`,
both GET) into one method-dispatched path, add POST/PUT/DELETE, drop `inertia_endpoint`
(Inertia becomes a return type of a GET endpoint), and hand handlers the raw Django
`HttpRequest` instead of a bespoke `RequestContext`.

Final URL surface (mounted under the existing `/apps` router prefix):

- `/apps/a/{collection_name}/{app_name}/e/{function_name}` — dispatched by HTTP method
  to the matching decorator (`@get_endpoint` / `@post_endpoint` / `@put_endpoint` /
  `@delete_endpoint`).
- `/apps/a/{collection_name}/{app_name}/e` — GET only, resolves the function named
  `default` (must be a `@get_endpoint`).

A request whose (method, name) doesn't match a registered endpoint is a **404** (name
absent, or name present under a different method). Function names are **globally unique**
across the four verbs — enforced structurally by Python (a module-level name binds once;
a second `def foo`, even under another verb, rebinds it and the earlier definition is gone
before discovery, so two same-named endpoints can't coexist in `vars(module)`).

---

## Decisions (locked)

- **Method mismatch → 404**, not 405. `(method, name)` is the lookup key; any miss is a
  404. (PATCH etc., which the router doesn't list at all, still 405 from ninja — only the
  four supported verbs go through our 404 logic.)
- **Names globally unique (structurally).** A function name is registered under exactly
  one method — but this is enforced by Python's module binding, not a runtime check: a
  second `def foo` rebinds the name (the first is gone before discovery), so `get foo` +
  `post foo` can't coexist. No `ValueError` is raised; the last definition silently wins.
- **`/e` aliases `default`.** `GET /e` serves `@get_endpoint default`; `/e/default` also
  resolves it. Non-GET on `/e`, and `GET /e` when no `default` (or `default` is a non-GET
  endpoint), → 404.
- **Inertia is GET-only.** `@get_endpoint` may return `dict | Pydantic | InertiaPage`;
  `@post/put/delete_endpoint` may return only `dict | Pydantic` (asserted at the call
  boundary).
- **User via `request.user` + `is_authenticated`.** Anonymous = `AnonymousUser()`. The old
  `ctx.user is None` (truthy check) is replaced everywhere by `request.user.is_authenticated`.
- **`build_request` replaces `fake_context`** — one helper:
  `build_request(*, user=None, method="GET", params=None, data=None, json=None)
  -> HttpRequest`. `params` is the query string (`request.GET`, valid on any method).
  `data` (form-encoded → `request.POST`) and `json` (→ `request.body`) are bodies: mutually
  exclusive with each other, and incompatible with GET — supplying a body with GET (or both
  `data`+`json`) raises `ValueError`, so incompatible method/body combos are precluded.
- **Browser writes migrate:** `create_row` → `@post_endpoint`, `modify_seed` →
  `@put_endpoint`.

---

## Migration map (old → new)

| Old | New |
|---|---|
| `.../endpoint/get/{fn}` (GET) | `.../e/{fn}` (method from decorator) |
| `.../endpoint/inertia/{fn}` (GET) | `.../e/{fn}` with `@get_endpoint` returning `InertiaPage` |
| `@inertia_endpoint` | removed (merge into `@get_endpoint`) |
| `RequestContext(request, user)` arg | `request: HttpRequest` arg |
| `fake_context()` | `build_request()` |
| `json_endpoints` / `inertia_endpoints` | single `endpoints: dict[str, Endpoint]` |
| `ctx.user` (None when anon) | `request.user.is_authenticated` |

---

## Detailed plan

### 1. Core framework — `djangoapp/apps/dynamic_module.py`
- [ ] Marker constants: keep `GET_ENDPOINT="get_endpoint"`; add `POST_ENDPOINT`,
      `PUT_ENDPOINT`, `DELETE_ENDPOINT`; drop `INERTIA_ENDPOINT`.
- [ ] `MARKER_METHOD: dict[str, str]` mapping each marker → HTTP method
      (`get_endpoint→GET`, `post_endpoint→POST`, …).
- [ ] Decorators `get_endpoint` / `post_endpoint` / `put_endpoint` / `delete_endpoint`
      via `_mark(...)`; remove `inertia_endpoint`.
- [ ] `@dataclass(frozen=True) Endpoint: method: str; func: Callable[..., object]`.
- [ ] `DynamicModule`: replace `json_endpoints` / `inertia_endpoints` with
      `endpoints: dict[str, Endpoint]`. No runtime duplicate-name check — it's
      unreachable (Python rebinds a redefined name) and a false-positive on
      aliasing; uniqueness is structural (see intro).
- [ ] Replace `has_json_endpoint` / `has_inertia_endpoint` with:
    - [ ] `has_endpoint(name) -> bool`
    - [ ] `endpoint_for(name) -> Endpoint | None`
- [ ] Replace `call_json_endpoint` / `call_inertia_endpoint` with
      `call_endpoint(name, request) -> object`: calls `ep.func(request)`, asserts the
      return type by method (`GET` allows `InertiaPage`; others forbid it); returns the
      raw result for the view to branch on.
- [ ] Remove `RequestContext` + `fake_context`; add
      `build_request(*, user=None, method="GET", params=None, data=None, json=None)
      -> HttpRequest` — `RequestFactory`-backed; sets `.method`, `.user`
      (anon → `AnonymousUser()`); `params` → `request.GET`; `data` → form body
      (`request.POST`), `json` → JSON body (`request.body`). `data`/`json` mutually
      exclusive; a body with GET (or both together) raises `ValueError`.
- [ ] Keep `InertiaPage` unchanged.
- [ ] Update module + `DynamicModule` docstrings (single `endpoints` dict, four verbs,
      raw request, `default` at bare `/e`).
- [ ] `__all__`: drop `RequestContext`, `fake_context`, `inertia_endpoint`; add
      `post_endpoint`, `put_endpoint`, `delete_endpoint`, `build_request`; keep
      `get_endpoint`, `InertiaPage`, `setup`, `backend_test`, `playwright_test`.

### 2. View layer — `djangoapp/views/app_endpoints.py`
- [ ] Named route:
      `@apps_endpoint_router.api("/a/{collection_name}/{app_name}/e/{function_name}",
      methods=["GET","POST","PUT","DELETE"], response=None)` → `app_endpoint`.
- [ ] Default route:
      `@apps_endpoint_router.api("/a/{collection_name}/{app_name}/e",
      methods=["GET","POST","PUT","DELETE"], response=None)` → `app_default_endpoint`;
      `raise Http404` if `request.method != "GET"`, else serve `default` (see `/e`
      non-GET note in Inconsistencies).
- [ ] Shared `_serve(request, app, name)`:
    - [ ] `ep = module.endpoint_for(name)`; if `ep is None or ep.method != request.method`
          → `Http404`.
    - [ ] `result = module.call_endpoint(name, request)`.
    - [ ] `isinstance(result, InertiaPage)` → `InertiaResponse` with `app.app_bundle()`
          `template_data` (unchanged bundle logic).
    - [ ] else `JsonResponse(result.model_dump(mode="json") if isinstance(result, BaseModel)
          else result)`.
- [ ] Remove `_viewer_user` (user now comes from `request.user`).
- [ ] Update module docstring (one `/e` path, method-dispatched, `default` at bare `/e`).

### 3. Exports — `djangoapp/apps/shortcuts.py`, `djangoapp/apps/__init__.py`
- [ ] Re-export `HttpRequest` (from `django.http`) so handlers annotate
      `def fn(request: HttpRequest)`.
- [ ] Add `post_endpoint`, `put_endpoint`, `delete_endpoint`, `build_request`; remove
      `inertia_endpoint`, `RequestContext`, `fake_context`; keep `get_endpoint`,
      `InertiaPage`.
- [ ] Update the import-example comment block at the top of `shortcuts.py`.

### 4. Fixtures & docs (handlers take `request: HttpRequest`; inertia → `@get_endpoint`+`InertiaPage`)
- [ ] `Tests/AllTypes/app.py` — `row` get endpoint: `request` arg; `row(build_request())`.
- [ ] `Tests/Endpoints/app.py` — `random_code` (get, `request` arg); `endpoint_page`
      `@inertia_endpoint` → `@get_endpoint` returning `InertiaPage`; tests →
      `build_request()`. Add small `@post_endpoint` / `@put_endpoint` / `@delete_endpoint`
      here so `test_endpoints.py` covers writes without a browser.
- [ ] `Tests/Browser/app.py`:
    - [ ] `browser_page`: `@inertia_endpoint` → `@get_endpoint` + `InertiaPage`.
    - [ ] `current_value`: get, `request` arg.
    - [ ] `create_row`: `@get_endpoint` → `@post_endpoint`.
    - [ ] `modify_seed`: `@get_endpoint` → `@put_endpoint`.
    - [ ] Playwright calls: `current_value` → `context.request.get(".../e/current_value")`;
          `create_row` → `.post(".../e/create_row")`; `modify_seed` →
          `.put(".../e/modify_seed")`; `browser_page` → `.../e/browser_page`.
- [ ] `Tests/Mock/app.py` — `random_fact` get, `request` arg, `build_request()`.
- [ ] `Tests/FailsTest/app.py` — `things` get, `request` arg; drop `RequestContext` import.
- [ ] `docs/apps/reference/app.py` — `current_count` get (`request` arg); `reference_page`
      inertia → get + `InertiaPage`; `build_request()`; playwright URL.
- [ ] Migrate every `request_context.user` truthiness check → `request.user.is_authenticated`.

### 5. Per-app frontend (URL strings only; keep existing try/catch + zod)
- [ ] `Tests/Browser/frontend/src/pages/BrowserPage.vue` —
      `.../endpoint/get/current_value` → `.../e/current_value`.
- [ ] `docs/apps/reference/frontend/src/pages/ReferencePage.vue` —
      `.../endpoint/get/current_count` → `.../e/current_count`.

### 6. Tests
- [ ] `test_endpoints.py`:
    - [ ] Rewrite all URLs to `/e/...` (get + the inertia-as-get case).
    - [ ] Rename `test_inertia_endpoint_*` → reflect "get endpoint returning InertiaPage";
          refresh the class + method docstrings.
    - [ ] `test_default_route_serves_default` — `GET /e` returns `default`'s payload;
          `GET /e/default` identical; `GET /e` with no `default` → 404.
    - [ ] `test_post_put_delete_served` — POST/PUT/DELETE `/e/{fn}` dispatch to the right
          decorator and return JSON.
    - [ ] `test_method_mismatch_is_404` — POST to a get-only name → 404 (not 405).
    - [ ] `test_inertia_return_from_post_rejected` — a `@post_endpoint` returning
          `InertiaPage` is rejected at the call boundary.
    - [ ] `test_build_request_*` — `user`, `params` (`request.GET`), `json` body
          (`request.body`), `data` form (`request.POST`) round-trip; anon →
          `AnonymousUser` (`is_authenticated is False`); a body (`json`/`data`) with GET
          raises `ValueError`; `data`+`json` together raises.
- [ ] `test_buildfrontend.py` — update docstring (`@inertia_endpoint` → `@get_endpoint`
      returning `InertiaPage`).
- [ ] Grep-sweep: no remaining `endpoint/get`, `endpoint/inertia`, `RequestContext`,
      `fake_context`, `inertia_endpoint`, `json_endpoints`, `inertia_endpoints` outside
      this plan's intentional removals.

---

## Inconsistencies / open tensions found while planning

### Resolved

1. **Capability delta vs. the old design — RESOLVED (global uniqueness).** The old system
   kept JSON gets and inertia pages in *separate* registries, so one app could expose both
   `/get/foo` (JSON) and `/inertia/foo` (Inertia page) under the same name `foo`. The new
   globally-unique design forbids this: `foo` has exactly one method, and JSON-vs-Inertia
   is decided by the runtime return type, not a separate registration. **Decision: keep
   global uniqueness and accept the delta.** Verified no in-repo app relies on it; document
   the change in the README + module docstring.

2. **`build_request` body coverage — RESOLVED (both `data` and `json`).** `build_request`
   gains both `data` (form-encoded → `request.POST`) and `json` (→ `request.body`). They
   are mutually exclusive, and supplying a body with GET (an incompatible method) raises
   `ValueError`, so incompatible method/body combinations are precluded at build time.
   `params` (query string) stays valid on any method.

### Note / verify

3. **`/e` returns 404 (not 405) on non-GET by deliberate override.** Registering all four
   methods on `/e` and `raise Http404`-ing non-GET overrides ninja's natural 405, to keep
   the 404-everywhere invariant from decision #1. Don't later "simplify" `/e` to a
   GET-only route — that would reintroduce 405 and break the invariant. **Verified:** the
   route registers all four verbs via `api_operation` and 404s non-GET; locked by
   `test_non_get_on_bare_e_is_404`.

4. **`test_endpoints.py` docstring/name updates under-specified.** Checklist step 6 now
   explicitly renames `test_inertia_endpoint_*` and refreshes docstrings (AGENTS.md
   requires current docstrings) — don't skip these.

5. **Direct-call vs. call-API in backend_tests.** `@backend_test`s call handlers directly
   (e.g. `row(a_test_request())`), which bypasses `call_endpoint`'s return-type assertion.
   Same as before (`random_code(a_test_request())`), so acceptable — but it means the
   return-type contract only fires over HTTP / via the call API, not in direct in-process
   calls.

6. **Route registration order: `/e` vs `/e/{function_name}`.** Two `api_operation` routes
   share a prefix; confirm the resolver doesn't let bare `/e` shadow `/e/foo` (it shouldn't
   — distinct path shapes). **Verified:** `test_default_route_serves_default` hits both
   `/e` and `/e/default`, and `test_unknown_function_404` hits `/e/nope`.

7. **`default` as a non-GET endpoint.** If an app registers `@post_endpoint def default`,
   `GET /e` 404s (method mismatch). Consistent with the decisions, but the prose "default
   is a convention, not reserved" can mislead — clarify in the docstring that `/e` serves
   `default` **only** when it is a `@get_endpoint`.

---

## Risks / notes

- **One `api_operation` per route (all four verbs):** both routes register
  `GET`/`POST`/`PUT`/`DELETE` together via `Router.api_operation(methods=[...])`
  (this ninja version has no `Router.api`; `api_operation` is typed and preserves
  the view type). The handler 404s on a miss — a method/name mismatch on
  `/e/{fn}` (via `_serve`) and a non-GET on bare `/e` (an explicit check) — so any
  unmatched `(method, name)` is a 404, not ninja's 405 (PATCH etc. still 405 from
  ninja, since the router doesn't list them). With no annotated Pydantic body
  param in the signature, ninja doesn't consume the body before the handler reads
  `request.body` / `request.POST`.
- **Deferred imports in `a_test_request`:** `RequestFactory` / `AnonymousUser`
  pull in auth-model machinery that isn't ready during app-registry population
  (and `djangoapp.apps` imports `dynamic_module` at setup), so they're imported
  inside the function, not at module top — else `AppRegistryNotReady`.
- **`request.user` over HTTP** is populated by `AuthenticationMiddleware`; in-process
  tests set it via `a_test_request`. No separate `user` param threads through the
  call API.
- **Breaking API for `app.py`:** all `app.py` live in-repo (`tests/appfixtures/Tests/*` +
  `docs/apps/`), so removing `RequestContext` / `inertia_endpoint` is fully contained.
  `djangoapp/tests/apps/*` open tabs are stale (no source); `Tests/Relations/` has only a
  stale `.pyc` (no `app.py`).
- **`buildfrontend.py`** only calls `application.module()`; it does not read the endpoint
  dicts, so renaming `json_endpoints`/`inertia_endpoints` → `endpoints` does not affect it.
- Lint gate order: `./run lintfix` → `./run typecheck` → `./run test` → `./run checkall`.

---

## aihere addressed during implementation

The following `# aihere` markers were added in the code during this work and have
been resolved (then removed from the code).

- **"why allow other methods"** (`app_endpoints.py`, `/e` route) — resolved: both
  routes register all four verbs via `api_operation`; bare `/e` serves `default`
  only on GET and `raise Http404`s non-GET to keep the 404-everywhere invariant (a
  method/name mismatch on `/e/{fn}` is `_serve`'s 404). **404 is the settled
  answer for any unmatched `(method, name)`** — see Decisions #1 and Note #3.
- **"decorators must enforce static typing of functions, ie taking request and
  returning approved types"** (`dynamic_module.py`) — implemented: the four endpoint
  decorators are typed (`Callable[[HttpRequest], RT] -> ...` with a return bound of
  `Pydantic | dict | InertiaPage` for GET and `Pydantic | dict` for the others) so
  mypy rejects a bad signature while preserving the handler's return type.
- **"rename to a_test_request"** (`dynamic_module.py`) — done: `build_request` →
  `a_test_request` across the framework, exports, fixtures, and tests.
- **"assert type of result as dict, inertia, pydantic"** (`call_endpoint`) —
  implemented: `call_endpoint` asserts the return matches the method contract (GET
  allows `Pydantic | dict | InertiaPage`; the others `Pydantic | dict`) and is
  declared to return that union, so `_serve` narrows with `isinstance` alone and
  needs no redundant assert of its own — the runtime backstop lives in one place.

### aihere considered and rejected

- **"consider storing key as (method, fnname)"** (`DynamicModule.endpoints`) —
  **rejected**: it conflicts with the locked **global-uniqueness** decision. Keying by
  `(method, name)` would let one name register under multiple methods (per-method),
  which the Q&A explicitly forbade. A name has exactly one method, so `name` alone is
  the unique key and the method is stored on the `Endpoint`; `_serve`'s method check
  gives the 404-on-mismatch. Kept the name-keyed dict; comment removed.

---

## Out of scope

- Row list/detail Inertia pages (`views/applications.py`) — separate subsystem, untouched.
- Auth/permissions, OpenAPI tuning, host `frontend/` changes.
