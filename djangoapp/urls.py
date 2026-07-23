from django.urls import path, re_path

from djangoapp.views import home, login_for_test
from djangoapp.views.applications import apps_api
from djangoapp.views.files import file_browser, file_download, file_raw
from djangoapp.views.manage import manage_api
from djangoapp.views.opencode import opencode_api, opencode_page
from djangoapp.views.users import users_api

urlpatterns = [
    path("", home, name="home"),
    path("", users_api.urls),
    path("", apps_api.urls),
    path("", manage_api.urls),
    path("api/opencode/", opencode_api.urls),
    path("login-for-test/<int:userid>", login_for_test, name="login-for-test"),
    path("agent/", opencode_page, name="opencode"),
    # Superuser-only file browser over the repo tree. Browse/view at /files/...,
    # byte serving on its own endpoints (raw before the browse catch-all).
    # /files (no trailing slash) arrives with rel=None; PathWrapper normalizes it.
    re_path(r"^files-raw/(?P<rel>.*)$", file_raw, name="files-raw"),
    re_path(r"^files-download/(?P<rel>.*)$", file_download, name="files-download"),
    re_path(r"^files(?:/(?P<rel>.*))?$", file_browser, name="files"),
]
