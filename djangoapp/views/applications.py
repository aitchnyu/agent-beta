"""Public app-framework HTTP surface.

``apps_api`` (namespace ``apps-http``) mounts the app endpoint router under
``/apps`` — the public app endpoints (``/apps/{app}`` default and
``/apps/{app}/e/{function}`` named). The superuser-only back-office views
moved to :mod:`djangoapp.views.manage` (mounted at ``/manage``), so they can
never collide with an app name.
"""

from __future__ import annotations

from ninja import NinjaAPI

from djangoapp.views.app_endpoints import apps_endpoint_router

apps_api = NinjaAPI(urls_namespace="apps-http")
# App-framework endpoints live under the apps/ prefix.
apps_api.add_router("apps", apps_endpoint_router)


__all__ = [
    "apps_api",
]
