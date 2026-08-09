"""URL routes for this app.

Mounts this app's django-ninja API (see ``views/__init__.py``) at the project
root, so each route declared there is served at its literal URL — including the
landing page at ``/`` (owned by this app, not the framework).
"""

from django.urls import path

from ourapp.views import api

urlpatterns = [
    path("", api.urls),
]
