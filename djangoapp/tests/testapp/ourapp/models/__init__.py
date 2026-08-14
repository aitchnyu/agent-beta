"""Test-app models — one module per feature, imported here so Django finds them.

Concrete models subclass ``djangoapp.models.BaseModel`` (which gives each row a
URL-safe ``public_id``, audit fields, ``get_absolute_url()``, and the
``save_with_logs``/``delete_with_logs`` hooks). Add a feature's model in
``models/<feature>.py`` and import it below (with ``__all__``, so mypy's
``--no-implicit-reexport`` allows ``from ourapp.models import <Model>``); every
model defined here appears in the superuser models-management UI at
``/manage/models``.

Overlaid onto ``scratch/ourapp/`` by ``checkproject``; not installed in ``main/``.
"""

from ourapp.models.books import Author, Book

__all__ = ["Author", "Book"]
