"""Reference app models — one module per feature, imported here so Django finds them.

The reference app demonstrates the multi-file layout with two features:
``facts`` (a ``Topic`` + ``Fact`` with a self-FK relationship) and ``todos``
(a ``Todo`` owned by a user). Each lives in its own module and is imported
below; every model appears in the superuser models-management UI at
``/manage/models``.
"""

from ourapp.models.facts import Fact, Topic
from ourapp.models.todos import Todo

__all__ = ["Fact", "Topic", "Todo"]
