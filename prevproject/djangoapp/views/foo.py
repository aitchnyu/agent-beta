from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from ninja import Router
from ninja.constants import NOT_SET

if TYPE_CHECKING:
    from django.http import HttpRequest

# ---------------- Experimental class-based views ----------------
# A tiny decorator-driven class-based-view layer on top of Ninja. Methods are
# tagged with @mrouter.get/@mrouter.post/... to become endpoints; the owning
# class is instantiated fresh for every request (mirrors ninja-extra's
# RouteFunction).
#
#   mrouter.get("/x") / .post("/y") : Ninja-shaped markers; tag the method with
#                                     RouteMeta (path, methods, response, ...)
#   SomeBase.get_router()            : builds a Ninja Router for the class by
#                                     registering tagged methods via Ninja's own
#                                     router.api_operation(
#                                     _method_to_ninjaable_function(...));
#                                     override to customise, then mount the
#                                     returned Router on a NinjaAPI in urls.py.


@dataclass
class RouteMeta:
    """Routing metadata for a wrapped endpoint method.

    path is the route segment and must be set explicitly (the @mrouter.<verb>
    decorator requires it); the class's mount prefix is supplied at add_router()
    time, not here.
    """

    path: str = ""
    methods: list[str] = field(default_factory=lambda: ["GET"])
    response: object = NOT_SET
    kwargs: dict[str, object] = field(default_factory=dict)


# Preserve the wrapped function's own type (so decorated methods keep their
# signatures for mypy) instead of widening to Callable[..., Any].
_F = TypeVar("_F", bound=Callable[..., object])


class MRouter:
    """Ninja-shaped endpoint marker.

    ``mrouter.get("/x")`` / ``mrouter.post("/y")`` / ... mirror Ninja's
    ``router.get`` / ``router.post`` but only tag the method with RouteMeta;
    the real Ninja Router is built in ``SomeBase.get_router()``. Each verb
    stamps its RouteMeta on the method as ``func._method_route``, which
    ``SomeBase.get_router()`` reads when registering the endpoint.
    """

    @staticmethod
    def _tag(rm: RouteMeta) -> Callable[[_F], _F]:
        """Return a decorator that stamps rm onto a method as its tag."""

        def decorator(func: _F) -> _F:
            func._method_route = rm  # type: ignore[attr-defined] # noqa: SLF001 # tag read by SomeBase.get_router
            return func

        return decorator

    def get(self, path: str, *, response: object = NOT_SET, **kwargs: object) -> Callable[[_F], _F]:
        return self._tag(
            RouteMeta(path=path, methods=["GET"], response=response, kwargs=dict(kwargs))
        )

    def post(
        self, path: str, *, response: object = NOT_SET, **kwargs: object
    ) -> Callable[[_F], _F]:
        return self._tag(
            RouteMeta(path=path, methods=["POST"], response=response, kwargs=dict(kwargs))
        )

    def put(self, path: str, *, response: object = NOT_SET, **kwargs: object) -> Callable[[_F], _F]:
        return self._tag(
            RouteMeta(path=path, methods=["PUT"], response=response, kwargs=dict(kwargs))
        )

    def patch(
        self, path: str, *, response: object = NOT_SET, **kwargs: object
    ) -> Callable[[_F], _F]:
        return self._tag(
            RouteMeta(path=path, methods=["PATCH"], response=response, kwargs=dict(kwargs))
        )

    def delete(
        self, path: str, *, response: object = NOT_SET, **kwargs: object
    ) -> Callable[[_F], _F]:
        return self._tag(
            RouteMeta(path=path, methods=["DELETE"], response=response, kwargs=dict(kwargs))
        )


mrouter = MRouter()


class SomeBase:
    """Core machinery for experimental class-based Ninja views.

    Subclasses tag methods with ``@mrouter.get/...``; ``get_router()`` builds
    the Router and ``urls.py`` mounts it under a chosen prefix via
    ``api.add_router(prefix, cls.get_router())``. Each request constructs a
    fresh instance.
    """

    @classmethod
    def _method_to_ninjaable_function(cls, func: Callable[..., Any]) -> Callable[..., Any]:
        """Adapt an instance method into a Ninja-compatible request handler.

        Ninja introspects a view's signature at registration and treats every
        parameter except ``request`` as path/query/body input. An instance
        method's leading ``self`` would be misread, so it is stripped from the
        exposed signature; the returned dispatcher instead builds a fresh
        ``cls()`` per request and forwards the call.
        """
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        # Tagged methods must be instance methods: a missing/renamed first
        # param means Ninja would have no instance to dispatch on.
        if not params or params[0].name != "self":
            msg = f"{func.__qualname__} must be an instance method (first parameter 'self')"
            raise TypeError(msg)
        new_sig = sig.replace(parameters=params[1:])

        def dispatcher(request: HttpRequest, **kwargs: object) -> object:
            return func(cls(), request, **kwargs)

        # update_wrapper (not @wraps) keeps the dispatcher's concrete type for
        # mypy while copying __name__/__wrapped__ for Ninja's operation metadata.
        functools.update_wrapper(dispatcher, func)
        dispatcher.__signature__ = new_sig  # type: ignore[attr-defined] # Ninja introspects this, not the def
        return dispatcher

    @classmethod
    def get_router(cls) -> Router:
        """Build and return this class's Ninja Router. Override to customise.

        Finds every @mrouter-tagged method (via the MRO, so inherited tagged
        methods are picked up) and registers it through Ninja's own
        ``router.api_operation`` applied to ``_method_to_ninjaable_function``.
        """
        router = Router()
        for func in (
            f for _, f in inspect.getmembers(cls, inspect.isfunction) if hasattr(f, "_method_route")
        ):
            route_meta = func._method_route  # noqa: SLF001 # _method_route set by mrouter
            router.api_operation(
                route_meta.methods,
                route_meta.path,
                response=route_meta.response,
                **route_meta.kwargs,
            )(cls._method_to_ninjaable_function(func))
        return router


class ListView(SomeBase):
    """SomeBase mixin that exposes a GET ``<prefix>/list`` endpoint.

    ``_list`` is the endpoint; it delegates to ``list()``, the override point
    for subclasses to supply the payload.
    """

    @mrouter.get("/list")
    def _list(self, request: HttpRequest) -> object:  # noqa: ARG002 # request required by Ninja's call convention
        """Endpoint at <prefix>/list; delegates to the overridable list()."""
        return self.list()

    def list(self) -> object:
        """Override in subclasses to provide the /list payload."""
        return [1, 2, 3]
