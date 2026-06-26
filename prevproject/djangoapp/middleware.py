from typing import TYPE_CHECKING

from inertia import share  # type: ignore[attr-defined]

from djangoapp.models.base import RowUpdateUserNotification

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


class NotificationCountMiddleware:
    def __init__(self, get_response: Callable[..., HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            count = RowUpdateUserNotification.objects.filter(user=request.user).count()
            share(request, notification_count=count)

        return self.get_response(request)
