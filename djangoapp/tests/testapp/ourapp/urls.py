"""Test-app URL routes — the page plus the django-ninja API.

The home page is a plain Django view (pages never ride a Router); the API
keeps the ninja mount at the project root, after the page.
"""

from django.urls import path

from ourapp.views import api
from ourapp.views.home import home_page

urlpatterns = [
    path("", home_page, name="home"),
    path("", api.urls),
]
