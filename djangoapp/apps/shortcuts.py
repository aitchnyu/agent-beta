"""One-import surface for app authors.

Importing ``*`` (or the names explicitly) from this module pulls in every
decorator, helper, model, and column class an app's ``app.py`` needs, so an app
has a single import:

.. code-block:: python

    from djangoapp.apps.shortcuts import *  # noqa: F403
    # setup, get_endpoint, post_endpoint, put_endpoint, delete_endpoint,
    # backend_test, playwright_test, a_test_request, InertiaPage, BaseModel,
    # HttpRequest, Application, CharColumn, TextColumn, IntegerColumn,
    # BooleanColumn, DecimalColumn, DateTimeColumn, UserColumn,
    # ForeignKeyColumn, dynamic_models

Re-exports only; this module adds no logic.
"""

from __future__ import annotations

from django.http import HttpRequest
from pydantic import BaseModel

from djangoapp.apps.dynamic_module import (
    InertiaPage,
    a_test_request,
    backend_test,
    delete_endpoint,
    get_endpoint,
    playwright_test,
    post_endpoint,
    put_endpoint,
    setup,
)
from djangoapp.models import Application
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    Column,
    DateTimeColumn,
    DecimalColumn,
    ForeignKeyColumn,
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
    "ForeignKeyColumn",
    "HttpRequest",
    "InertiaPage",
    "IntegerColumn",
    "TextColumn",
    "UserColumn",
    "a_test_request",
    "backend_test",
    "delete_endpoint",
    "dynamic_models",
    "get_endpoint",
    "playwright_test",
    "post_endpoint",
    "put_endpoint",
    "setup",
]
