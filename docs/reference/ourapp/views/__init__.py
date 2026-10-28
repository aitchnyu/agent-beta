"""Reference app API — one django-ninja ``Router`` per feature, combined into one ``NinjaAPI``.

Each feature's data/file endpoints live in ``views/<feature>.py`` on a
``router``; this module owns the single ``NinjaAPI`` and registers every
router, so each endpoint is served at its literal URL (mounted last in
``urls.py``, after the page paths). PAGES are NOT routers — they are
plain Django views returning Inertia responses, routed directly in
``urls.py`` (see steer.md § View/router shapes).
"""

from ninja import NinjaAPI

from ourapp.views import downloads, todos

api = NinjaAPI(urls_namespace="ourapp-http")

# Register every feature's data/file router. Home and facts are all-pages
# (no router); the todos/downloads pages are plain views in urls.py.
api.add_router("/", todos.router)
api.add_router("/", downloads.router)
