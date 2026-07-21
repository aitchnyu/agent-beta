"""App framework: marker decorators + a DynamicModule built from an app module.

An app's ``app.py`` tags its functions with standalone decorators that just mark
the function's kind (no instance to create):

.. code-block:: python

    from djangoapp.apps import (
        HttpRequest, backend_test, get_endpoint, post_endpoint, setup,
    )

    @setup
    def setup_app() -> None:
        ...  # create_application(...)

    @get_endpoint
    def facts(request: HttpRequest) -> FactsOut:
        ...

    @post_endpoint
    def save(request: HttpRequest) -> SavedOut:
        ...

All four verbs (get/post/put/delete) are served at one path
``/apps/<app>/e/<function>`` and dispatched by HTTP method; a function
name is registered under exactly one method — globally unique across verbs, so a
duplicate name under two methods is rejected at load. A ``@get_endpoint`` may
additionally return an :class:`InertiaPage` (rendered as an Inertia page); the
other verbs return a Pydantic model or dict (JSON).

The loader imports the module and constructs a :class:`DynamicModule` from it,
which scans the module's namespace for the marked functions and exposes them as
``setup_function`` / ``endpoints`` / ``backend_tests`` / ``playwright_tests``.
``DynamicModule`` is constructed only by the loader — app authors never
instantiate it.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from json import dumps as json_dumps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from django.conf import settings
from pydantic import BaseModel

if TYPE_CHECKING:
    from types import ModuleType

    from django.http import HttpRequest

    from djangoapp.models import User

F = TypeVar("F", bound=Callable[..., object])

# Props type for an InertiaPage return.
TProps = TypeVar("TProps", bound=BaseModel)

# Attribute set by each marker decorator on the function it tags; the value is
# the function's kind. A function carries exactly one marker.
_MARKER_ATTR = "_app_marker"

SETUP = "setup"
GET_ENDPOINT = "get_endpoint"
POST_ENDPOINT = "post_endpoint"
PUT_ENDPOINT = "put_endpoint"
DELETE_ENDPOINT = "delete_endpoint"
BACKEND_TEST = "backend_test"
PLAYWRIGHT_TEST = "playwright_test"

MARKER_METHOD: dict[str, str] = {
    GET_ENDPOINT: "GET",
    POST_ENDPOINT: "POST",
    PUT_ENDPOINT: "PUT",
    DELETE_ENDPOINT: "DELETE",
}


@dataclass(frozen=True)
class InertiaPage[TProps: BaseModel]:
    """What a ``@get_endpoint`` may return to render an Inertia page.

    The view turns this into an ``InertiaResponse``; ``props`` is serialised
    via ``model_dump(mode="json")``. Generic over the props type so an endpoint
    can declare ``-> InertiaPage[MyPageProps]`` for type-checking. Only a GET
    endpoint may return this; the other verbs return a Pydantic model or dict.
    """

    component: str
    props: TProps


@dataclass(frozen=True)
class Endpoint:
    """One registered endpoint: its HTTP method and the handler callable."""

    method: str
    func: Callable[..., object]


def _mark(kind: str) -> Callable[[F], F]:
    """Build a marker decorator that tags ``fn._app_marker = kind`` and returns it."""

    def decorator(fn: F) -> F:
        setattr(fn, _MARKER_ATTR, kind)
        return fn

    return decorator


# Approved endpoint returns. A GET handler may return Pydantic, dict, or an
# InertiaPage; post/put/delete return Pydantic or dict. Enforced statically by
# the typed decorators below (the runtime assert in call_endpoint re-checks it).
GetEndpointReturn = BaseModel | dict[str, Any] | InertiaPage[Any]
WriteEndpointReturn = BaseModel | dict[str, Any]


# Standalone decorators — import these in app.py and apply directly. They only
# tag the function; discovery happens later in DynamicModule(module).
def get_endpoint[RTGet: GetEndpointReturn](
    func: Callable[[HttpRequest], RTGet],
) -> Callable[[HttpRequest], RTGet]:
    """Tag a GET endpoint handler (returns Pydantic, dict, or InertiaPage)."""
    return _mark(GET_ENDPOINT)(func)


def post_endpoint[RTWrite: WriteEndpointReturn](
    func: Callable[[HttpRequest], RTWrite],
) -> Callable[[HttpRequest], RTWrite]:
    """Tag a POST endpoint handler (returns Pydantic or dict)."""
    return _mark(POST_ENDPOINT)(func)


def put_endpoint[RTWrite: WriteEndpointReturn](
    func: Callable[[HttpRequest], RTWrite],
) -> Callable[[HttpRequest], RTWrite]:
    """Tag a PUT endpoint handler (returns Pydantic or dict)."""
    return _mark(PUT_ENDPOINT)(func)


def delete_endpoint[RTWrite: WriteEndpointReturn](
    func: Callable[[HttpRequest], RTWrite],
) -> Callable[[HttpRequest], RTWrite]:
    """Tag a DELETE endpoint handler (returns Pydantic or dict)."""
    return _mark(DELETE_ENDPOINT)(func)


setup = _mark(SETUP)
backend_test = _mark(BACKEND_TEST)
playwright_test = _mark(PLAYWRIGHT_TEST)


def a_test_request(
    *,
    user: User | None = None,
    method: str = "GET",
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
    json: object | None = None,
) -> HttpRequest:
    """Build a Django ``HttpRequest`` for in-process calls to endpoints/tests.

    Replaces ``fake_context``. ``params`` is the query string (``request.GET``,
    valid on any method). ``data`` (form-encoded → ``request.POST``) and ``json``
    (→ ``request.body``) are request bodies: mutually exclusive, and incompatible
    with GET — supplying a body with GET, or both ``data`` and ``json``, raises
    ``ValueError``. ``user`` defaults to ``AnonymousUser`` when ``None`` so
    handlers check ``request.user.is_authenticated`` rather than a None sentinel.
    """
    # Deferred to runtime: django.test / auth.models pull in model machinery that
    # isn't ready during app-registry population, and djangoapp.apps imports this
    # module at setup — a top-level import would raise AppRegistryNotReady.
    from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415
    from django.test import RequestFactory  # noqa: PLC0415

    method = method.upper()
    if data is not None and json is not None:
        msg = "a_test_request: pass either data or json, not both."
        raise ValueError(msg)
    if (data is not None or json is not None) and method == "GET":
        msg = "a_test_request: a request body (data/json) is incompatible with GET."
        raise ValueError(msg)
    factory = getattr(RequestFactory(), method.lower())
    if method == "GET":
        request = factory("/", data=params or {})
    elif json is not None:
        request = factory("/", data=json_dumps(json), content_type="application/json")
    elif data is not None:
        request = factory("/", data=data)
    else:
        request = factory("/", data={})
    # RequestFactory's methods are typed ``Any``; the built object is an HttpRequest.
    request.user = user if user is not None else AnonymousUser()
    return cast("HttpRequest", request)


class DynamicModule:
    """An app module's tagged functions, discovered by scanning its namespace.

    Constructed by :class:`AppModuleLoader` from an imported module — never in
    app.py. Iterates ``vars(module)`` in definition order (CPython preserves it)
    and groups callables by their ``_app_marker``:

    - setup_function, the single ``@setup`` callable (required)
    - endpoints, dict ``name -> Endpoint`` (one method per name). Uniqueness is
      structural, not a runtime check: a module-level name binds once, so a
      second ``def foo`` (even under a different ``@verb_endpoint``) rebinds it
      and the earlier definition is simply gone — by the time ``vars(module)``
      is scanned only the last survives.
    - backend_tests, list of ``@backend_test`` (definition order)
    - playwright_tests, list of ``@playwright_test`` (definition order)

    Raises ``ValueError`` if the module has no @setup function.
    """

    setup_function: Callable[..., object]
    endpoints: dict[str, Endpoint]
    backend_tests: list[Callable[..., object]]
    playwright_tests: list[Callable[..., object]]

    def __init__(self, module: ModuleType) -> None:
        setup_function: Callable[..., object] | None = None
        self.endpoints = {}
        self.backend_tests = []
        self.playwright_tests = []
        for obj in vars(module).values():
            if not callable(obj):
                continue
            kind = getattr(obj, _MARKER_ATTR, None)
            if kind == SETUP:
                setup_function = obj
            elif kind in MARKER_METHOD:
                self.endpoints[obj.__name__] = Endpoint(method=MARKER_METHOD[kind], func=obj)
            elif kind == BACKEND_TEST:
                self.backend_tests.append(obj)
            elif kind == PLAYWRIGHT_TEST:
                self.playwright_tests.append(obj)
        if setup_function is None:
            msg = f"{module.__name__} has no @setup function."
            raise ValueError(msg)
        self.setup_function = setup_function

    def has_endpoint(self, name: str) -> bool:
        """Whether an endpoint with ``name`` is registered (under any method)."""
        return name in self.endpoints

    def endpoint_for(self, name: str) -> Endpoint | None:
        """Return the registered :class:`Endpoint` for ``name``, or ``None`` if absent."""
        return self.endpoints.get(name)

    def call_endpoint(
        self, *, name: str, request: HttpRequest
    ) -> BaseModel | dict[str, Any] | InertiaPage[Any]:
        """Call an endpoint by name, asserting its return matches the method contract.

        The caller (the view) decides the 404 (name absent or method mismatch);
        this assumes ``name`` exists. A GET endpoint may return a Pydantic model,
        dict, or :class:`InertiaPage`; the other verbs must return a Pydantic
        model or dict. The contract check lives with the call, not the view; the
        declared union return type lets callers narrow with ``isinstance`` alone.
        """
        ep = self.endpoints[name]
        result = ep.func(request)
        if ep.method == "GET":
            assert isinstance(result, (BaseModel, dict, InertiaPage)), (
                f"@get_endpoint '{name}' must return a Pydantic model, dict, or InertiaPage."
            )
        else:
            assert isinstance(result, (BaseModel, dict)), (
                f"@{ep.method.lower()}_endpoint '{name}' must return a Pydantic model or dict."
            )
        return result


# Apps root: the directory the import + frontend machinery resolves apps from.
# An app lives at ``<apps_root()>/<app>/app.py`` (+ a ``frontend/``
# sibling). Default ``<BASE_DIR>/apps``; tests patch this (via the module global
# or ``apps_root``) to point at the fixture tree, so no per-app path is stored.
_APPS_ROOT: Path = Path(str(settings.BASE_DIR)) / "apps"


def apps_root() -> Path:
    """Apps root the import/frontend machinery resolves apps from.

    It is a function (not a module constant) so tests can patch the
    ``_APPS_ROOT`` global it returns — pointing it at the fixture tree — without
    touching settings or callers that read ``apps_root()``.
    """
    return _APPS_ROOT


class AppModuleLoader:
    """Load app modules by ``app.py`` path, cache them, and return their handler.

    ``load`` returns a :class:`DynamicModule` built from the module — the handler
    exposing ``setup_function`` / ``endpoints`` / ``backend_tests`` /
    ``playwright_tests``. Each load first syncs the in-memory caches to the live
    apps generation (see :func:`clear_app_caches`), so a ``setup`` install in
    another process is picked up without a server restart.
    """

    def __init__(self) -> None:
        self._modules: dict[str, ModuleType] = {}

    def load(self, path: Path, *, force_reload: bool = False) -> DynamicModule:
        """Import (cached) the app module at ``path`` and return its handler.

        ``force_reload`` re-imports fresh (used by ``setup`` so a re-run after
        edits picks up changes).
        """
        clear_app_caches()
        key = str(path)
        module = self._modules.get(key)
        if module is None or force_reload:
            module = self._import(path, force_reload=force_reload)
            self._modules[key] = module
        return DynamicModule(module)

    def clear(self) -> None:
        """Drop every cached app module (used between tests so imports are fresh)."""
        for mod_name in [k for k in sys.modules if k.startswith("_djapp_")]:
            del sys.modules[mod_name]
        self._modules.clear()

    def _import(self, path: Path, *, force_reload: bool) -> ModuleType:
        # force_reload re-imports even when cached: ``setup`` is re-run after an
        # app.py edit (often in-process via call_command in tests), and must pick
        # up the changed module rather than the cached one.
        if not path.exists():
            msg = f"App script not found: {path}"
            raise FileNotFoundError(msg)
        mod_name = f"_djapp_{abs(hash(str(path)))}"
        if force_reload:
            sys.modules.pop(mod_name, None)
        # spec is the importlib ModuleSpec (loader + origin) for the file path,
        # used to build and exec the module from disk rather than via a normal
        # package import.
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:  # pragma: no cover - path exists check above
            msg = f"Could not build import spec for {path}"
            raise ImportError(msg)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        return module


# Process-local last-seen apps generation; ``None`` forces a sync on first use.
_seen_generation: int | None = None


def clear_app_caches() -> None:
    """Clear the app-module + dynamic-model caches when the apps generation changes.

    This *drops* the caches (they rebuild on next use) rather than updating them
    in place, so a ``setup``/``buildfrontend`` in any process is visible without a
    server restart.
    """
    global _seen_generation  # noqa: PLW0603 # module-local cache; reset on generation change
    # Section 1 — compare: read the live generation and bail early if unchanged.
    from djangoapp.models.applications import (  # noqa: PLC0415 # deferred: dynamic_module is imported during model loading
        AppsGeneration,
    )

    live = AppsGeneration.current()
    if live == _seen_generation:
        return

    # Section 2 — reset: generation bumped (by setup/buildfrontend in any process),
    # so drop this loader's modules and the dynamic-model registry's model
    # cache; both rebuild from the latest installed app on next use.
    from djangoapp.models.dynamic import (  # noqa: PLC0415 # deferred to avoid dynamic_module <-> dynamic cycle
        dynamic_models,
    )

    app_modules.clear()
    dynamic_models.reset()
    _seen_generation = live


app_modules = AppModuleLoader()


__all__ = [
    "AppModuleLoader",
    "DynamicModule",
    "Endpoint",
    "InertiaPage",
    "a_test_request",
    "app_modules",
    "apps_root",
    "backend_test",
    "clear_app_caches",
    "delete_endpoint",
    "get_endpoint",
    "playwright_test",
    "post_endpoint",
    "put_endpoint",
    "setup",
]
