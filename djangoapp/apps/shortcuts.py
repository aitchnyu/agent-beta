"""One-import surface for app authors.

Importing ``*`` (or the names explicitly) from this module pulls in every
decorator, helper, model, and column class an app's ``app.py`` needs, so an app
has a single import:

.. code-block:: python

    from djangoapp.apps.shortcuts import *  # noqa: F403
    # setup, get_endpoint, inertia_endpoint, backend_test, playwright_test,
    # RequestContext, fake_context, InertiaPage, BaseModel, Application,
    # CharColumn, TextColumn, IntegerColumn, BooleanColumn, DecimalColumn,
    # DateTimeColumn, UserColumn, dynamic_models

Re-exports only; this module adds no logic.
"""

from __future__ import annotations

from pydantic import BaseModel

from djangoapp.apps.dynamic_module import (
    InertiaPage,
    RequestContext,
    backend_test,
    fake_context,
    get_endpoint,
    inertia_endpoint,
    playwright_test,
    setup,
)
from djangoapp.models import Application
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    Column,
    DateTimeColumn,
    DecimalColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)
from djangoapp.models.dynamic import dynamic_models

__all__ = [
    "Application",
    "BaseModel",
    "BooleanColumn",
    "CharColumn",
    "Column",
    "DateTimeColumn",
    "DecimalColumn",
    "InertiaPage",
    "IntegerColumn",
    "RequestContext",
    "TextColumn",
    "UserColumn",
    "backend_test",
    "dynamic_models",
    "fake_context",
    "get_endpoint",
    "inertia_endpoint",
    "playwright_test",
    "setup",
]
