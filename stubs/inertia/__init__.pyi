from typing import Any

from django.http import HttpRequest, HttpResponse

class InertiaResponse(HttpResponse):
    def __init__(
        self,
        request: HttpRequest,
        component: str,
        props: dict[str, Any] | None = None,
        template_data: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        *args: list[Any],
        **kwargs: dict[str, Any],
    ) -> None: ...

def render(
    request: HttpRequest,
    component: str,
    props: dict[str, Any] | None = None,
    template_data: dict[str, Any] | None = None,
) -> InertiaResponse: ...
def share(request: HttpRequest, **kwargs: Any) -> None: ...
