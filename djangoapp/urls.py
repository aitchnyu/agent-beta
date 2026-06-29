from django.urls import path

from djangoapp.views import applications, home, login_for_test
from djangoapp.views.users import users_api

urlpatterns = [
    path("", home, name="home"),
    path("", users_api.urls),
    path("login-for-test/<int:userid>", login_for_test, name="login-for-test"),
    path("apps/collections", applications.collections_page, name="apps-collections"),
    path("apps/a/<str:collection_name>/list", applications.app_list_page, name="apps-app-list"),
    path(
        "apps/a/<str:collection_name>/<str:app_name>/manage",
        applications.manage_page,
        name="apps-manage",
    ),
]
