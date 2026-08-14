"""Test-app API — one django-ninja ``Router`` per feature, combined into one ``NinjaAPI``.

Each feature lives in ``views/<feature>.py`` and exposes a ``router``; this
module owns the single ``NinjaAPI`` and registers every router, so each route
is served at its literal URL (the API is mounted at the project root in
``urls.py``). Page responses render via Inertia (``InertiaResponse``,
component ``ours/<Page>``).
"""

from ninja import NinjaAPI

from ourapp.views import books, home

api = NinjaAPI(urls_namespace="ourapp-http")

# Register every feature's router. Home owns the landing page at ``/``.
api.add_router("/", home.router)
api.add_router("/", books.router)
