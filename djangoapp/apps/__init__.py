"""The app framework: marker decorators and module loading.

Apps are Python modules installed via ``./run djangomanage setup <path>``. An
app's ``app.py`` tags its functions with the standalone decorators (``@setup``,
``@get_endpoint``, ``@post_endpoint``, ``@put_endpoint``, ``@delete_endpoint``,
``@backend_test``, ``@playwright_test``); the loader builds a
:class:`DynamicModule` from the imported module and the setup runner / endpoint
views read it.
"""

from __future__ import annotations

from djangoapp.apps.dynamic_module import (
    DynamicModule,
    Endpoint,
    InertiaPage,
    a_test_request,
    app_modules,
    backend_test,
    delete_endpoint,
    get_endpoint,
    playwright_test,
    post_endpoint,
    put_endpoint,
    setup,
)

__all__ = [
    "DynamicModule",
    "Endpoint",
    "InertiaPage",
    "a_test_request",
    "app_modules",
    "backend_test",
    "delete_endpoint",
    "get_endpoint",
    "playwright_test",
    "post_endpoint",
    "put_endpoint",
    "setup",
]
