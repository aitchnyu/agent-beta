"""Reference app API — one django-ninja ``Router`` per feature, combined into one API.

Each feature's data/file endpoints live in ``views/<feature>.py`` on a
``router``; this module combines them onto one ``Router`` and builds the
single ``NinjaAPI`` from it via ``make_ninja_api`` — so the friendly
``ApiError``/404 error handlers and the CSRF guard ride along — then
mounts it at the project root in ``urls.py`` (pages first, API last).
Each endpoint is served at its literal URL.

PAGES are NOT routers — they are plain Django views returning Inertia
responses, routed directly in ``urls.py`` (see steer.md § View/router
shapes).
"""

# MAINTAIN-CONSISTENCY repo-map: excerpted in .pi/repo-map.md §9 — change both together.

from ninja import Router

from djangoapp.ninja_api import make_ninja_api
from ourapp.views import downloads, todos

# Register every feature's data/file router. Home and facts are all-pages
# (no router); the todos/downloads pages are plain views in urls.py.
router = Router()
router.add_router("/", todos.router)
router.add_router("/", downloads.router)

# prefix="" — the endpoints answer at their literal paths (/todos/create …).
api = make_ninja_api("ourapp", router, prefix="")
