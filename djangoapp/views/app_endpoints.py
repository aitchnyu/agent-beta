"""HTTP serving of app endpoints.

Two endpoint kinds, both under ``/apps/a/<collection>/<app>/endpoint/``:

- ``@get_endpoint`` at ``.../endpoint/get/<func>`` — returns a Pydantic model or
  dict as JSON.
- ``@inertia_endpoint`` at ``.../endpoint/inertia/<func>`` — returns an
  :class:`~djangoapp.apps.dynamic_module.InertiaPage` rendered as an Inertia
  page using the app's own bundle (derived from the collection/app names).

Both resolve the app via ``Application.app_or_404`` and call through the
``DynamicModule`` call API. Unknown collection/app/function → 404.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from inertia import InertiaResponse
from ninja import Router
from pydantic import BaseModel

from djangoapp.models.applications import Application

if TYPE_CHECKING:
    from djangoapp.models import User

apps_endpoint_router = Router()


def _viewer_user(request: HttpRequest) -> User | None:
    """Return the authenticated user (or None) to pass to endpoints via RequestContext."""
    user = request.user
    return user if user.is_authenticated else None


@apps_endpoint_router.get(
    "/a/{collection_name}/{app_name}/endpoint/get/{function_name}",
    response=None,
)
def app_endpoint(
    request: HttpRequest,
    collection_name: str,
    app_name: str,
    function_name: str,
) -> HttpResponse:
    """Serve one ``@get_endpoint`` function as JSON (Pydantic model or dict)."""
    app = Application.app_or_404(collection_name, app_name)
    module = app.module()
    if not module.has_json_endpoint(function_name):
        raise Http404
    result = module.call_json_endpoint(
        name=function_name, request=request, user=_viewer_user(request)
    )
    payload = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
    return JsonResponse(payload)


@apps_endpoint_router.get(
    "/a/{collection_name}/{app_name}/endpoint/inertia/{function_name}",
    response=None,
)
def app_inertia_endpoint(
    request: HttpRequest,
    collection_name: str,
    app_name: str,
    function_name: str,
) -> HttpResponse:
    """Serve one ``@inertia_endpoint`` function as an Inertia page.

    Uses the app's own bundle (``application.app_bundle()``) for both the
    script/css base and the ``?cache_buster=`` value (the apps generation),
    passed via ``template_data`` so ``base.html`` overrides the host default.
    """
    app = Application.app_or_404(collection_name, app_name)
    module = app.module()
    if not module.has_inertia_endpoint(function_name):
        raise Http404
    stuff = module.call_inertia_endpoint(
        name=function_name, request=request, user=_viewer_user(request)
    )
    static_url, asset_version = app.app_bundle()
    return InertiaResponse(
        request,
        stuff.component,
        {"props": stuff.props.model_dump(mode="json")},
        template_data={
            "app_static_base": static_url,
            "app_asset_version": asset_version,
        },
    )


__all__ = ["app_endpoint", "app_inertia_endpoint", "apps_endpoint_router"]
