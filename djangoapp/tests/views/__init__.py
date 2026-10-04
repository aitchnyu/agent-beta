"""Shared helpers for the views test package."""

import os
from collections.abc import Callable
from typing import TypeVar
from unittest import skipIf

_C = TypeVar("_C", bound=Callable[..., object])


def skip_unless_env(var: str) -> Callable[[_C], _C]:
    """Skip a test unless the environment variable ``var`` is set.

    ``checkframework1``'s project stage sets ``RUN_PROJECT_TESTS`` so the project
    tests run; its earlier stages leave it unset so they self-skip.
    """
    return skipIf(not os.getenv(var), f"only runs with {var} set")
