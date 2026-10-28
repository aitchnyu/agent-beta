"""URL routes for this app.

The page routes (``/`` and the mockup hatch) are PLAIN Django views —
pages never ride a ninja Router (steer.md § View/router shapes). This
module also mounts the app's django-ninja API (``views/__init__.py``)
for the JSON endpoints at their literal URLs.
"""

from django.urls import path

from ourapp.views import api
from ourapp.views.home import home_page, mockup_page

urlpatterns = [
    # Pages — plain Django views.
    path("", home_page, name="home"),
    path("mockup/<str:page>", mockup_page, name="mockup"),
    # JSON APIs — every feature router registered on the NinjaAPI.
    path("", api.urls),
]
