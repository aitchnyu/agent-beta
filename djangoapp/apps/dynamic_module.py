"""App framework: marker decorators + a DynamicModule built from an app module.

An app's ``app.py`` tags its functions with standalone decorators that just mark
the function's kind (no instance to create):

.. code-block:: python

    from djangoapp.apps import (
        RequestContext, backend_test, get_endpoint, inertia_endpoint, setup,
    )

    @setup
    def setup_app() -> None:
        ...  # create_application(...)

    @get_endpoint
    def facts(request_context: RequestContext) -> FactsOut:
        ...

    @inertia_endpoint
    def facts_page(request_context: RequestContext) -> InertiaPage[FactsPageProps]:
        ...

The loader imports the module and constructs a :class:`DynamicModule` from it,
which scans the module's namespace for the marked functions and exposes them as
``setup_function`` / ``endpoints`` / ``inertia_endpoints`` / ``backend_tests`` /
``playwright_tests``. ``DynamicModule`` is constructed only by the loader — app
authors never instantiate it.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from django.conf import settings
from django.http import HttpRequest
from pydantic import BaseModel

if TYPE_CHECKING:
    from types import ModuleType

    from djangoapp.models import User

F = TypeVar("F", bound=Callable[..., object])

# Props type for an InertiaPage return.
TProps = TypeVar("TProps", bound=BaseModel)

# Attribute set by each marker decorator on the function it tags; the value is
# the function's kind. A function carries exactly one marker.
_MARKER_ATTR = "_app_marker"

SETUP = "setup"
GET_ENDPOINT = "get_endpoint"
INERTIA_ENDPOINT = "inertia_endpoint"
BACKEND_TEST = "backend_test"
PLAYWRIGHT_TEST = "playwright_test"


@dataclass(frozen=True)
class RequestContext:
    """The request + viewer user handed to a ``@get_endpoint`` function."""

    request: HttpRequest
    user: User | None


def fake_context() -> RequestContext:
    """Build a no-user context for backend tests calling endpoints in-process.

    Uses a bare ``HttpRequest`` so endpoints that read the user via the context
    (not the request) work without a real WSGI environ.
    """
    return RequestContext(request=HttpRequest(), user=None)


@dataclass(frozen=True)
class InertiaPage[TProps: BaseModel]:
    """What an ``@inertia_endpoint`` returns: a component name + typed props.

    The view turns this into an ``InertiaResponse``; ``props`` is serialised
    via ``model_dump(mode="json")``. Generic over the props type so an endpoint
    can declare ``-> InertiaPage[MyPageProps]`` for type-checking.
    """

    component: str
    props: TProps


def _mark(kind: str) -> Callable[[F], F]:
    """Build a marker decorator that tags ``fn._app_marker = kind`` and returns it."""

    def decorator(fn: F) -> F:
        setattr(fn, _MARKER_ATTR, kind)
        return fn

    return decorator


# Standalone decorators — import these in app.py and apply directly. They only
# tag the function; discovery happens later in DynamicModule(module).
setup = _mark(SETUP)
get_endpoint = _mark(GET_ENDPOINT)
inertia_endpoint = _mark(INERTIA_ENDPOINT)
backend_test = _mark(BACKEND_TEST)
playwright_test = _mark(PLAYWRIGHT_TEST)


class DynamicModule:
    """An app module's tagged functions, discovered by scanning its namespace.

    Constructed by :class:`AppModuleLoader` from an imported module — never in
    app.py. Iterates ``vars(module)`` in definition order (CPython preserves it)
    and groups callables by their ``_app_marker``:

    - setup_function, the single ``@setup`` callable (None if absent)
    - json_endpoints, dict ``name -> @get_endpoint``
    - inertia_endpoints, dict ``name -> @inertia_endpoint``
    - backend_tests, list of ``@backend_test`` (definition order)
    - playwright_tests, list of ``@playwright_test`` (definition order)

    Raises :class:`DynamicModuleError` if the module has no tagged functions.
    """

    setup_function: Callable[..., object] | None
    json_endpoints: dict[str, Callable[..., object]]
    inertia_endpoints: dict[str, Callable[..., object]]
    backend_tests: list[Callable[..., object]]
    playwright_tests: list[Callable[..., object]]

    def __init__(self, module: ModuleType) -> None:
        self.setup_function = None
        self.json_endpoints = {}
        self.inertia_endpoints = {}
        self.backend_tests = []
        self.playwright_tests = []
        for obj in vars(module).values():
            if not callable(obj):
                continue
            kind = getattr(obj, _MARKER_ATTR, None)
            if kind == SETUP:
                self.setup_function = obj
            elif kind == GET_ENDPOINT:
                self.json_endpoints[obj.__name__] = obj
            elif kind == INERTIA_ENDPOINT:
                self.inertia_endpoints[obj.__name__] = obj
            elif kind == BACKEND_TEST:
                self.backend_tests.append(obj)
            elif kind == PLAYWRIGHT_TEST:
                self.playwright_tests.append(obj)
        if (
            self.setup_function is None
            and not self.json_endpoints
            and not self.inertia_endpoints
            and not self.backend_tests
            and not self.playwright_tests
        ):
            msg = (
                f"{module.__name__} has no @setup/@get_endpoint/@inertia_endpoint/"
                "@backend_test/@playwright_test functions."
            )
            raise DynamicModuleError(msg)

    def has_json_endpoint(self, name: str) -> bool:
        """Whether a ``@get_endpoint`` (JSON) with ``name`` is registered."""
        return name in self.json_endpoints

    def has_inertia_endpoint(self, name: str) -> bool:
        """Whether an ``@inertia_endpoint`` with ``name`` is registered."""
        return name in self.inertia_endpoints

    def call_json_endpoint(
        self, *, name: str, request: HttpRequest, user: User | None
    ) -> BaseModel | dict[str, Any]:
        """Call a ``@get_endpoint`` by name, building the ``RequestContext``.

        A ``@get_endpoint`` must return a Pydantic model or dict; asserted at the
        call boundary so the contract check lives with the call, not the view.
        """
        result = self.json_endpoints[name](RequestContext(request=request, user=user))
        assert isinstance(result, (BaseModel, dict)), (
            f"@get_endpoint '{name}' must return a Pydantic model or dict."
        )
        return result

    def call_inertia_endpoint(
        self, *, name: str, request: HttpRequest, user: User | None
    ) -> InertiaPage[Any]:
        """Call a ``@inertia_endpoint`` by name, building the ``RequestContext``."""
        result = self.inertia_endpoints[name](RequestContext(request=request, user=user))
        assert isinstance(result, InertiaPage), (
            f"@inertia_endpoint '{name}' did not return InertiaPage."
        )
        return result


# aihere no need of this type
class DynamicModuleError(Exception):
    """Raised when an app module has no tagged functions at all."""


# Apps root: the directory the import + frontend machinery resolves apps from.
# An app lives at ``<apps_root()>/<collection>/<app>/app.py`` (+ a ``frontend/``
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
    exposing ``setup_function`` / ``endpoints`` / ``inertia_endpoints`` /
    ``backend_tests`` / ``playwright_tests``. Each load first syncs the in-memory
    caches to the live apps generation (see :func:`sync_app_caches`), so a
    ``setup`` install in another process is picked up without a server restart.
    """

    def __init__(self) -> None:
        self._modules: dict[str, ModuleType] = {}

    def load(self, path: Path, *, force_reload: bool = False) -> DynamicModule:
        """Import (cached) the app module at ``path`` and return its handler.

        ``force_reload`` re-imports fresh (used by ``setup`` so a re-run after
        edits picks up changes).
        """
        sync_app_caches()
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


# aihere rename to be more descriptive that temp caches are actually cleared
def sync_app_caches() -> None:
    """Reset both in-memory caches when the apps generation changes."""
    global _seen_generation  # noqa: PLW0603 # module-local cache; reset on generation change
    # Section 1 — compare: read the live generation and bail early if unchanged.
    from djangoapp.models.applications import (  # noqa: PLC0415 # deferred: dynamic_module is imported during model loading
        AppsGeneration,
    )

    live = AppsGeneration.current()
    if live == _seen_generation:
        return

    # Section 2 — reset: generation bumped (by setup/buildapp in any process),
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
    "DynamicModuleError",
    "InertiaPage",
    "RequestContext",
    "app_modules",
    "apps_root",
    "backend_test",
    "fake_context",
    "get_endpoint",
    "inertia_endpoint",
    "playwright_test",
    "setup",
    "sync_app_caches",
]
