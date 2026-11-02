"""Test-app API — one django-ninja ``Router`` per feature, combined into one API.

Each feature lives in ``views/<feature>.py`` and exposes a ``router``; this
module combines them onto one ``Router`` and builds the single ``NinjaAPI``
from it via ``make_ninja_api`` — so the friendly ``ApiError``/404 error
handlers and the CSRF guard ride along — then it is mounted at the project
root in ``urls.py`` (pages first, API last). Each endpoint is served at its
literal URL. Page responses render via Inertia (``InertiaResponse``,
component ``<Page>``).
"""

from ninja import Router

from djangoapp.ninja_api import make_ninja_api
from ourapp.views import home, media

# Register every feature's router. Home owns the landing page at ``/``.
router = Router()
router.add_router("/", home.router)
router.add_router("/", media.router)

# prefix="" — the endpoints answer at their literal paths (/media/…).
api = make_ninja_api("ourapp", router, prefix="")
