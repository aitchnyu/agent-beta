from django.urls import path

from djangoapp.views import home, login_for_test
from djangoapp.views.applications import apps_api
from djangoapp.views.opencode import opencode_api, opencode_page
from djangoapp.views.users import users_api

urlpatterns = [
    path("", home, name="home"),
    path("", users_api.urls),
    path("", apps_api.urls),
    path("api/opencode/", opencode_api.urls),
    path("login-for-test/<int:userid>", login_for_test, name="login-for-test"),
    path("agent/", opencode_page, name="opencode"),
]
