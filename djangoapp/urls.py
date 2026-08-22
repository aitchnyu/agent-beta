from django.urls import include, path

from djangoapp.views import login_for_test, login_for_test_by_key
from djangoapp.views.client_errors import client_errors_api
from djangoapp.views.files import files_api
from djangoapp.views.git import git_api
from djangoapp.views.manage import manage_api
from djangoapp.views.users import users_api

urlpatterns = [
    # The user app is included FIRST so it owns the landing page at "/" — every
    # django-ninja API also registers a `default_home` at "" that raises 404, so
    # the app's home route must be tried before the framework NinjaAPIs. The app
    # has no framework-prefixed routes, so it never shadows /users, /manage,
    # /files, /git (those fall through past it). (The web console is /agent
    # under caddy on the VM — not a Django route.)
    path("", include("ourapp.urls")),
    path("", client_errors_api.urls),  # Frontend error capture sink
    path("", users_api.urls),
    path("", manage_api.urls),
    path("", git_api.urls),
    path("", files_api.urls),
    path("login-for-test/<int:userid>", login_for_test, name="login-for-test"),
    path("login-for-test/by-key/<str:key>/", login_for_test_by_key, name="login-for-test-by-key"),
]
