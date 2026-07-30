"""Example URL routes — copy into ``ourapp/urls.py``.

Mounts this app's django-ninja API at the project root (``include``), so each
route is served at its literal URL.
"""

from django.urls import path

from ourapp.views import api

urlpatterns = [
    path("", api.urls),
]
