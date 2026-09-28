"""Reference app models — one module per feature, imported here so Django finds them.

The reference app demonstrates the multi-file layout with three features:
``facts`` (a ``Topic`` + ``Fact`` with a self-FK relationship), ``todos``
(a ``Todo`` owned by a user), and ``downloads`` (a time-limited shared
``Download`` — the media illustration). Each lives in its own module and is
imported below; every model appears in the superuser models-management UI at
``/manage/models``.
"""

from ourapp.models.downloads import DEFAULT_DOWNLOAD_WINDOW, Download
from ourapp.models.facts import Fact, FactOfTheDay, Topic
from ourapp.models.todos import Todo

__all__ = ["DEFAULT_DOWNLOAD_WINDOW", "Download", "Fact", "FactOfTheDay", "Topic", "Todo"]
