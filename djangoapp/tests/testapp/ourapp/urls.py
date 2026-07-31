"""Test-app URL routes — mounts the django-ninja API at the project root."""

from django.urls import path

from ourapp.views import api

urlpatterns = [
    path("", api.urls),
]
