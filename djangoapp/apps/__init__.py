"""The app framework: marker decorators, request context, and module loading.

Apps are Python modules installed via ``./run djangomanage setup <path>``. An
app's ``app.py`` tags its functions with the standalone decorators (``@setup``,
``@get_endpoint``, ``@inertia_endpoint``, ``@backend_test``, ``@playwright_test``);
the loader builds a :class:`DynamicModule` from the imported module and the
setup runner / endpoint views read it.
"""

from __future__ import annotations

from djangoapp.apps.dynamic_module import (
    DynamicModule,
    InertiaPage,
    RequestContext,
    app_modules,
    backend_test,
    fake_context,
    get_endpoint,
    inertia_endpoint,
    playwright_test,
    setup,
)

__all__ = [
    "DynamicModule",
    "InertiaPage",
    "RequestContext",
    "app_modules",
    "backend_test",
    "fake_context",
    "get_endpoint",
    "inertia_endpoint",
    "playwright_test",
    "setup",
]
