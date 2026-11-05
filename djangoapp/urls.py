from django.urls import include, path

from djangoapp.views import files, git, manage, notifications, users
from djangoapp.views.client_errors import client_errors_api
from djangoapp.views.notifications import notifications_api
from djangoapp.views.users import redeem_login_key, users_api

urlpatterns = [
    # App first: it owns "/" (a ninja API's default_home would 404 it).
    path("", include("ourapp.urls")),
    # Pages before APIs — files first (imports the "relpath" converter).
    *files.page_urls,
    *git.page_urls,
    *manage.page_urls,
    *notifications.page_urls,
    *users.page_urls,
    path("", client_errors_api.urls),  # Frontend error capture sink
    path("", users_api.urls),
    path("", notifications_api.urls),
    path("login-for-test/<str:key>/", redeem_login_key, name="login-for-test"),
]
