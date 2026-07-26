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

    # An app may declare several @setup functions; they run in source order,
    # and the runner resumes from the last completed one (see
    # Application.executed_setups).

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
``setups`` / ``endpoints`` / ``backend_tests`` / ``playwright_tests``.
``DynamicModule`` is constructed only by the loader — app authors never
instantiate it.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from json import dumps as json_dumps
from json import loads as json_loads
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from django.conf import settings
from pydantic import BaseModel, ValidationError

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


_EXPECT_ERROR_NO_RAISE = "expect_error(): the with-block did not raise an exception"
_EXPECT_NOT_CAPTURED = "expect_error captured no exception"


class ExceptionWrapper:
    """Holds the exception captured by :func:`expect_error` (read via ``.exception``).

    A holder rather than the bare exception because the ``as e`` binding happens at
    ``yield``, before the with-body runs and raises — so the instance isn't
    available to bind directly. The backing ``_exception`` is ``Exception | None``
    (``None`` until the block raises), but the ``exception`` property returns only
    ``Exception``: it raises :class:`AssertionError` if read before capture, which
    in practice never happens — :func:`expect_error` itself asserts on a non-raising
    block, so by the time ``.exception`` is read it is always set.
    """

    __slots__ = ("_exception",)

    def __init__(self) -> None:
        self._exception: Exception | None = None

    @property
    def exception(self) -> Exception:
        """The captured exception (raises if read before the block raised)."""
        if self._exception is None:
            raise AssertionError(_EXPECT_NOT_CAPTURED)
        return self._exception

    @exception.setter
    def exception(self, value: Exception) -> None:
        self._exception = value


@contextmanager
def expect_error() -> Iterator[ExceptionWrapper]:
    """Capture an exception raised in the block — ``pytest.raises`` without pytest.

    Apps run their ``@backend_test``s as plain function calls (buildbackend drives
    them directly), so ``pytest`` isn't available. Use this to assert a call raises::

        with expect_error() as e:
            risky_call()
        assert isinstance(e.exception, ValueError)

    The block must raise; if it doesn't, ``AssertionError`` is raised on exit so a
    missing failure can't pass silently.
    """
    captured = ExceptionWrapper()
    try:
        yield captured
    except Exception as exc:  # noqa: BLE001 -- capturing any app exception is the point
        captured.exception = exc  # the property's setter stashes it
        return
    raise AssertionError(_EXPECT_ERROR_NO_RAISE)


_REQUEST_BODY_NOT_JSON = "Request body must be valid JSON."


class BaseSchema(BaseModel):
    """Pydantic model that parses + validates a JSON request body, 422-ing on error.

    Subclass it to declare a request shape, then parse an inbound request in a
    ``@post_endpoint`` / ``@put_endpoint``:

        class CreateItem(BaseSchema):
            code: str = Field(max_length=10)

        @post_endpoint
        def add_item(request: HttpRequest) -> ItemOut:
            item = CreateItem.from_json_request(request)  # 422 if the body is invalid
            ...

    :meth:`from_json_request` reads ``request.body`` as JSON and validates it
    against the schema. A non-JSON body or a pydantic :class:`ValidationError`
    raises :class:`ninja.errors.ValidationError` → an HTTP **422** whose ``detail``
    is a machine-parseable JSON list of field errors, instead of a 500 from a
    ``KeyError``/``TypeError`` indexing the body blindly. The rejected ``input``
    and pydantic ``url`` are stripped so sensitive values aren't echoed. Example
    bodies:

    ::

        # a missing required field
        {"detail": [
          {"type": "missing", "loc": ["code"], "msg": "Field required"}
        ]}
        # body isn't JSON (from_json_request's JSON guard; no `type` key)
        {"detail": [
          {"loc": ["body"], "msg": "Request body must be valid JSON."}
        ]}
    """

    @classmethod
    def from_json_request(cls, request: HttpRequest) -> Self:
        from ninja.errors import ValidationError as NinjaValidationError  # noqa: PLC0415

        try:
            # A missing/empty body (b"") is treated as "{}" → a missing-field 422,
            # not a JSON-parse error.
            data = json_loads(request.body or "{}")
        except ValueError:
            raise NinjaValidationError(
                [{"loc": ["body"], "msg": _REQUEST_BODY_NOT_JSON}],
            ) from None
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            # exc.errors() is the structured list → ninja returns {"detail": [...]} (422).
            # Strip `input` (the rejected value) + `url` so sensitive fields aren't echoed.
            raise NinjaValidationError(
                cast("list[dict[str, Any]]", exc.errors(include_url=False, include_input=False)),
            ) from None


class DynamicModule:
    """An app module's tagged functions, discovered by scanning its namespace.

    Constructed by :class:`AppModuleLoader` from an imported module — never in
    app.py. Iterates ``vars(module)`` in definition order (CPython preserves it)
    and groups callables by their ``_app_marker``:

    - setups, the list of ``@setup`` callables (definition order; may be empty).
      The runner executes them in this order and resumes from the last
      completed one — see ``Application.executed_setups``. A module-level name
      binds once, so a second ``def setup_app`` (under any marker) rebinds it
      and the earlier definition is simply gone before discovery; duplicate
      ``__name__``s therefore cannot reach this list.
    - endpoints, dict ``name -> Endpoint`` (one method per name). Uniqueness is
      structural, not a runtime check: a module-level name binds once, so a
      second ``def foo`` (even under a different ``@verb_endpoint``) rebinds it
      and the earlier definition is simply gone — by the time ``vars(module)``
      is scanned only the last survives.
    - backend_tests, list of ``@backend_test`` (definition order)
    - playwright_tests, list of ``@playwright_test`` (definition order)

    An app may declare zero ``@setup`` functions: ``setups`` is then an empty
    list, and ``buildbackend`` runs its ``@backend_test``s + bumps the
    generation but creates no ``Application`` row (no setup to make one).
    """

    setups: list[Callable[..., object]]
    endpoints: dict[str, Endpoint]
    backend_tests: list[Callable[..., object]]
    playwright_tests: list[Callable[..., object]]

    def __init__(self, module: ModuleType) -> None:
        self.setups = []
        self.endpoints = {}
        self.backend_tests = []
        self.playwright_tests = []
        for obj in vars(module).values():
            if not callable(obj):
                continue
            kind = getattr(obj, _MARKER_ATTR, None)
            if kind == SETUP:
                self.setups.append(obj)
            elif kind in MARKER_METHOD:
                self.endpoints[obj.__name__] = Endpoint(method=MARKER_METHOD[kind], func=obj)
            elif kind == BACKEND_TEST:
                self.backend_tests.append(obj)
            elif kind == PLAYWRIGHT_TEST:
                self.playwright_tests.append(obj)

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
    exposing ``setups`` / ``endpoints`` / ``backend_tests`` /
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
    "BaseSchema",
    "DynamicModule",
    "Endpoint",
    "ExceptionWrapper",
    "InertiaPage",
    "a_test_request",
    "app_modules",
    "apps_root",
    "backend_test",
    "clear_app_caches",
    "delete_endpoint",
    "expect_error",
    "get_endpoint",
    "playwright_test",
    "post_endpoint",
    "put_endpoint",
    "setup",
]
