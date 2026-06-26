from django.urls import include, path

from .views.app import cbv_api, foo_api, login_for_test, tables_urls
from .views.articles import articles_api
from .views.base import ninja_api
from .views.users import users_api

urlpatterns = [
    path("tables/api/", ninja_api.urls),
    path("tables/", include((tables_urls, "tables-http"))),
    path("", articles_api.urls),
    path("", users_api.urls),
    path("", cbv_api.urls),
    path("", foo_api.urls),
    path("login-for-test/<int:userid>", login_for_test, name="login-for-test"),
]
