# Experimental class-based views on Ninja

A small decorator-driven class-based-view layer built on top of django-ninja,
inspired by the [django-ninja CBV proposal (#15)](https://django-ninja.dev/proposals/cbv/)
and ninja-extra's `RouteFunction`. Lives in `djangoapp/views/app.py` and is
mounted experimentally in `djangoapp/urls.py`. Tests in
`djangoapp/tests/views/test_experimental_cbv.py`.

## Goal

Instance methods on a class become Ninja endpoints; **a fresh instance is
constructed for every request** (so per-request setup/state is possible and
nothing leaks between requests), and endpoints are declared with Ninja-shaped
decorators that mirror `router.get` / `router.post` / ...

## Final shape

```python
class ListView(SomeBase):
    @mrouter.get("/list")
    def _list(self, request: HttpRequest) -> object:
        return self.list()

    def list(self) -> object:
        return [1, 2, 3]

class C1(ListView):
    def list(self) -> list[int]:
        return [1, 2, 3]

class C2(ListView):
    def list(self) -> list[str]:
        return ["a", "b", "c"]

    @mrouter.get("/custom")
    def custom(self, request: HttpRequest) -> str:
        return "hello"

cbv_api = NinjaAPI(urls_namespace="cbv", openapi_url=None)
cbv_api.add_router("c1", C1.get_router())
cbv_api.add_router("c2", C2.get_router())
```

`urls.py` simply does `path("", cbv_api.urls)`.

### Pieces

- `RouteMeta` dataclass: `path`, `methods`, `response`, `kwargs`.
- `MRouter` + `mrouter = MRouter()`: Ninja-shaped markers (`mrouter.get/.post/.put/.patch/.delete`).
  Each tags the method with its `RouteMeta` as `func._method_route` (it does
  NOT register anything at decoration time).
- `SomeBase.get_router()`: builds the class's Ninja `Router` by discovering
  every `@mrouter`-tagged method via the MRO and registering each through
  Ninja's own `router.api_operation(...)`. Override to customise.
- `SomeBase._method_to_ninjaable_function(func)`: strips `self` from the
  signature and returns a dispatcher that builds a fresh `cls()` per request.

## How it works (the `self` problem)

Ninja introspects a view's signature at registration time
(`Operation.__init__` -> `ViewSignature`, `ninja/operation.py`) and treats every
parameter except one named `request` as path/query/body input. An instance
method's leading `self` would be misread, so `_method_to_ninjaable_function`
drops `self` from the exposed `__signature__` while its body does
`func(cls(), request, **kwargs)`.

## Decisions

- **Don't reuse `@router.get` directly on the method.** Two blockers: (1) no
  router exists at class-body time (it is built lazily in `get_router()`); (2)
  Ninja introspects `self` immediately on registration. ninja-extra ships its
  own `http_get`/`route` decorators for exactly this reason -- it does not reuse
  `router.get` either. We tag with `@mrouter.<verb>` and register later.
- **Reuse Ninja's real router at registration.** `get_router()` calls Ninja's
  own `router.api_operation(methods, path, response, ...)` (replacing an earlier
  `getattr(router, verb)` loop) applied to the self-stripped dispatcher.
- **Fresh instance per request.** The dispatcher does `func(cls(), request, ...)`.
  Verified by `_InstanceCounter` (counter advances on each request).
- **Inheritance via MRO.** `get_router()` uses `inspect.getmembers(cls,
  inspect.isfunction)`, which walks the MRO (most-derived first), so `C1`/`C2`
  inherit `ListView._list` and override `list()` correctly.
- **`ListView` mixin owns the list endpoint.** `_list` (tagged endpoint)
  delegates to `list()` (override point), keeping `SomeBase` free of endpoint
  responsibility.
- **`path_prefix` is NOT a class attribute.** The mount prefix is supplied at
  `add_router("c1", ...)` time, so classes need not know where they are mounted.
- **`route_meta.path` is required.** The `@mrouter.<verb>` decorator takes a
  mandatory `path`; no method-name derivation (`_list` -> `@mrouter.get("/list")`).
- **`_method_to_ninjaable_function` enforces instance methods** (raises
  `TypeError` if the first parameter is not `self`).
- **NinjaAPI assembly lives in `app.py`** (`cbv_api`); `urls.py` only includes it.
- **No `urls()` method.** `get_router()` returns the `Router`; mounting happens
  at the call site.
- **ARG002 kept inline.** The `# noqa: ARG002` on `_list`/`custom` (Ninja
  requires `request` in the signature) stays inline with an explanation, per
  `AGENTS.md` and `prompts/20260622-minimize-noqa.md`. ARG002 was NOT disabled
  repo-wide (would violate the `lint.ignore` rule and mask real unused-arg bugs).

## Relation to the django-ninja proposal (#15)

We match the proposal's core mechanic (**fresh instance per request**) but do
NOT implement its central feature: a constructor (or named init) that receives
the request + shared path params and runs common setup once, shared across
sibling methods. Our constructor is parameter-less, so each endpoint method
stands alone -- there is no shared per-request computation hook, and the
proposal's `async def __init__` problem is sidestepped rather than solved.

## Files

- `djangoapp/views/app.py` -- `RouteMeta`, `MRouter`/`mrouter`, `SomeBase`,
  `ListView`, `C1`, `C2`, `cbv_api`.
- `djangoapp/urls.py` -- mounts `cbv_api.urls`.
- `djangoapp/tests/views/test_experimental_cbv.py` -- 6 tests.

## Checklist

### Core mechanism
- [x] `RouteMeta` dataclass (path, methods, response, kwargs)
- [x] `MRouter`/`mrouter` Ninja-shaped markers (`get/post/put/patch/delete`)
- [x] tag methods via `func._method_route`
- [x] `_method_to_ninjaable_function`: strip `self`, per-request dispatch
- [x] `get_router()` discovers tagged methods via MRO + registers via `router.api_operation`
- [x] `ListView` mixin (`_list` -> `list()` override point)
- [x] `C1` / `C2` examples
- [x] `cbv_api` NinjaAPI assembled in `app.py`, mounted in `urls.py`

### Behavioural guarantees (tests)
- [x] /c1/list returns `[1,2,3]`
- [x] /c2/list returns `['a','b','c']` (override honoured)
- [x] /c2/custom returns `'hello'` (C2-only endpoint)
- [x] /c1/custom -> 404 (not defined on C1)
- [x] fresh instance per request (counter advances)
- [x] C1 inherits `_list` from SomeBase/ListView without redeclaring it

### Evolution (decisions revisited)
- [x] `@wrap(route(...))` -> `wrap.get/.post` (Ninja shape)
- [x] `wrap` instance renamed to `mrouter`; class `_Wrap` -> `MRouter`; `_tag` moved in
- [x] `_route` -> `_method_route` tag name
- [x] `_collect_routes` inlined into `get_router` via `inspect.getmembers`
- [x] `getattr(router, verb)` -> `router.api_operation(...)`
- [x] `__init_subclass__` + `cls.router` removed; router built fresh in `get_router`
- [x] `urls()` removed; mount via `get_router()` + `add_router`
- [x] NinjaAPI (`cbv_api`) moved from `urls.py` to `views/app.py`
- [x] `path_prefix` removed from classes; prefix supplied at `add_router` time
- [x] `route_meta.path` made required (no method-name derivation)

## Verification

- [x] `./run lintfix`
- [x] `./run typecheck`
- [x] `./run test` (561 backend tests, including the 6 CBV tests)

Run the CBV tests alone:
`./run test djangoapp.tests.views.test_experimental_cbv --keepdb --noinput`
