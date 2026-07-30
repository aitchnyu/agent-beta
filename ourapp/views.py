"""User app API.

A django-ninja API for this app's endpoints — page responses render via Inertia
(``InertiaResponse``), data responses are pydantic schemas. Mount it in
``urls.py`` (included from the project root, so routes are served at their
literal URLs). See ``docs/reference/`` for a copyable example with routes.
"""

from ninja import NinjaAPI

api = NinjaAPI(urls_namespace="ourapp-http")
