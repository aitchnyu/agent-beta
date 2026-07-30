"""URL routes for this app.

Mounts this app's django-ninja API (see ``views.py``) at the project root, so
each route declared there is served at its literal URL.
"""

from django.urls import path

from ourapp.views import api

urlpatterns = [
    path("", api.urls),
]
