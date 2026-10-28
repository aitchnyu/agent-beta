"""User app API — one django-ninja ``Router`` per feature, combined into one ``NinjaAPI``.

Each feature's JSON API lives in ``views/<feature>.py`` and exposes a
``router``; this module owns the single ``NinjaAPI`` and registers every
router, so each endpoint is served at its literal URL (mounted at the
project root in ``urls.py``). Pages are NOT routers — they are plain
Django views returning Inertia responses (see steer.md § View/router
shapes); ``home.py`` holds this app's pages.
"""

from ninja import NinjaAPI

api = NinjaAPI(urls_namespace="ourapp-http")

# Register every feature's JSON-API router here (pages live in views as
# plain Django functions, routed in urls.py).
