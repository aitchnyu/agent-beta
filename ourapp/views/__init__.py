"""User app API — one django-ninja ``Router`` per feature, combined into one API.

Each feature's JSON API lives in ``views/<feature>.py`` and exposes a
``router``; this module combines them onto one ``Router`` and builds the
single ``NinjaAPI`` from it via ``make_ninja_api`` — so the friendly
``ApiError``/404 error handlers and the CSRF guard ride along — then it
is mounted at the project root in ``urls.py`` (pages first, API last).
Each endpoint is served at its literal URL.

Pages are NOT routers — they are plain Django views returning Inertia
responses (see steer.md § View/router shapes); ``home.py`` holds this
app's pages.
"""

from ninja import Router

from djangoapp.ninja_api import make_ninja_api

# Register every feature's JSON-API router here (pages live in views as
# plain Django functions, routed in urls.py).
router = Router()

# prefix="" — the endpoints answer at their literal paths (/<feature>/…).
api = make_ninja_api("ourapp", router, prefix="")
