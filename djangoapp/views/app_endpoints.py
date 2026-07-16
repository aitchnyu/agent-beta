"""HTTP serving of app endpoints.

One path serves every endpoint, dispatched by HTTP method:

- ``/a/<collection>/<app>/e/<function>`` — dispatched by the request method to the
  matching decorator (``@get_endpoint`` / ``@post_endpoint`` / ``@put_endpoint`` /
  ``@delete_endpoint``). A name under the wrong method (or absent entirely) → 404.
- ``/a/<collection>/<app>/e`` — resolves the function named ``default``. Only GET
  serves it; a non-GET ``/e`` is a 404 (the same 404-everywhere invariant as a
  method/name mismatch on the named route). PATCH and other verbs the router
  doesn't list never reach the handler — ninja answers those with its own 405.

A ``@get_endpoint`` may return a Pydantic model or dict (served as JSON) or an
:class:`~djangoapp.apps.dynamic_module.InertiaPage` (rendered as an Inertia page
with the app's own bundle); the other verbs return Pydantic/dict (JSON).

Both resolve the app via ``Application.app_or_404`` and call through the
``DynamicModule`` call API. Unknown collection/app/function → 404.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from inertia import InertiaResponse
from ninja import Router
from pydantic import BaseModel

from djangoapp.apps.dynamic_module import InertiaPage
from djangoapp.models.applications import Application

apps_endpoint_router = Router()

_VERBS = ["GET", "POST", "PUT", "DELETE"]


def _serve(request: HttpRequest, app: Application, name: str) -> HttpResponse:
    """Resolve ``name`` on ``app``, enforce the method match, and render the result.

    A registered name under a different method is a 404 (the (method, name) key
    doesn't match), matching the unknown-name case. A GET may return an
    :class:`InertiaPage` (Inertia) or a Pydantic model/dict (JSON); the other
    verbs return Pydantic/dict (JSON).
    """
    module = app.module()
    endpoint = module.endpoint_for(name)
    if endpoint is None or endpoint.method != request.method:
        raise Http404
    result = module.call_endpoint(name=name, request=request)
    if isinstance(result, InertiaPage):
        static_url, asset_version = app.app_bundle()
        return InertiaResponse(
            request,
            result.component,
            {"props": result.props.model_dump(mode="json")},
            template_data={
                "app_static_base": static_url,
                "app_asset_version": asset_version,
            },
        )
    # call_endpoint's return type is BaseModel | dict | InertiaPage; the
    # InertiaPage case returned above, so this is JSON-serialisable.
    payload = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
    return JsonResponse(payload)


# Each route is registered for all four verbs with api_operation; the handler
# raises Http404 on a method/name mismatch (via _serve, or the explicit check in
# app_default_endpoint), so a name under the wrong method — or a non-GET /e — is
# a 404, not ninja's 405. There is no annotated Pydantic body param in either
# signature, so ninja leaves request.body / request.POST for the handler to read.
_ENDPOINT_PATH = "/a/{collection_name}/{app_name}/e/{function_name}"
_DEFAULT_PATH = "/a/{collection_name}/{app_name}/e"


@apps_endpoint_router.api_operation(methods=_VERBS, path=_ENDPOINT_PATH, response=None)
def app_endpoint(
    request: HttpRequest,
    collection_name: str,
    app_name: str,
    function_name: str,
) -> HttpResponse:
    """Serve ``.../e/<function>`` for the request's method (404 on a mismatch)."""
    return _serve(request, Application.app_or_404(collection_name, app_name), function_name)


@apps_endpoint_router.api_operation(methods=_VERBS, path=_DEFAULT_PATH, response=None)
def app_default_endpoint(
    request: HttpRequest,
    collection_name: str,
    app_name: str,
) -> HttpResponse:
    """Serve ``.../e`` as the function named ``default`` (GET only).

    Only GET serves ``default``; a non-GET ``/e`` is a 404 to honour the
    404-everywhere invariant. (Only the four listed verbs reach this handler, so
    a PATCH etc. is still ninja's 405 before it gets here.)
    """
    if request.method != "GET":
        raise Http404
    return _serve(request, Application.app_or_404(collection_name, app_name), "default")


__all__ = [
    "app_default_endpoint",
    "app_endpoint",
    "apps_endpoint_router",
]
