# Minimal type stubs for the bits of ``huey`` this app uses.
#
# huey has no ``py.typed`` marker; these stubs keep its imports typed under
# strict mypy. Scoped to the surface the app touches — widen as new call sites
# appear. Found via ``mypy_path = "stubs"`` in pyproject.toml (sibling of
# ``stubs/inertia/``).

def crontab(*args: object, **kwargs: object) -> object: ...
