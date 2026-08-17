"""Shared bases for the test suites — the fast password hasher.

Every DB-backed test class inherits one of these roots (directly, via
``QueryBudgetMixin`` in ``query_budget.py``, or via ``BasePlaywrightTestCase``
which carries the same override). PBKDF2, the default hasher, costs ~0.1s per
hash and the suites create password-bearing users in nearly every setUp —
``test_users`` alone hashes 100+ times per run — while no test authenticates
by password (all ``force_login`` or the DEBUG-only ``/login-for-test/<pk>``
e2e view), so swapping ``PASSWORD_HASHERS`` for MD5 is pure saved runtime.
Class-scoped (the documented ``@override_settings`` idiom) rather than
sniffing ``manage.py test`` in settings.py, so production settings stay pure;
``test_test_conventions.py`` fails the run if a new class forgets to inherit.
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from inertia.test import InertiaTestCase


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaseTestCase(TestCase):
    """``TestCase`` + the fast MD5 test hasher; root of the unit suites."""


class BaseInertiaTestCase(BaseTestCase, InertiaTestCase):  # type: ignore[misc]
    """Same, for inertia-prop view tests — the one lineage-merge point."""
