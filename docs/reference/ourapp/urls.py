"""URL routes for this app.

Pages are PLAIN Django views routed below — inertia pages never ride a
ninja Router. Data/file endpoints (JSON APIs, the download serve) live
on each feature's ``router`` in ``views/<feature>.py``, combined into
the one ``NinjaAPI`` (``views/__init__.py``) and mounted here last, so
specific page paths resolve first and API endpoints answer at their
literal URLs.
"""

from django.urls import path

from ourapp.views import api
from ourapp.views.downloads import downloads_page
from ourapp.views.facts import fact_detail_page, fact_topic_page, facts_page
from ourapp.views.home import home_page
from ourapp.views.todos import todos_page

urlpatterns = [
    # Pages — plain Django views (Inertia renders).
    path("", home_page, name="home"),
    path("facts", facts_page, name="facts"),
    path("facts/<str:slug>", fact_topic_page, name="fact-topic"),
    path("fact/<str:public_id>", fact_detail_page, name="fact-detail"),
    path("todos", todos_page, name="todos"),
    path("downloads", downloads_page, name="downloads"),
    # Data/file endpoints — every feature's ninja Router on the one NinjaAPI.
    path("", api.urls),
]
