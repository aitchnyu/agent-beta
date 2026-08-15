"""Meta-tests guarding conventions of the test suites themselves.

``BaseTestCase`` (``djangoapp/tests/_base.py``) swaps in the fast MD5 hasher;
a new class that quietly roots at plain ``TestCase``/``InertiaTestCase``
re-imposes ~0.1s of PBKDF2 per created user — tens of seconds across the
suite — with no visible signal. This guard walks both test packages and
fails naming the offenders instead.
"""

from __future__ import annotations

import importlib
import pkgutil

from django.test import SimpleTestCase

from djangoapp.tests._base import BaseTestCase

_MD5_HASHER = "django.contrib.auth.hashers.MD5PasswordHasher"
_PACKAGES = ("djangoapp.tests", "ourapp.tests")


def _db_backed_test_classes() -> set[type[SimpleTestCase]]:
    """Every Django ``SimpleTestCase`` descendant defined in the suites.

    Deliberately broader than ``TestCase``: ``SimpleTestCase`` also catches
    ``TransactionTestCase``/``StaticLiveServerTestCase`` roots (the whole
    playwright tree) and helper-module bases (``query_budget``,
    ``playwright/_base``) — the hasher override matters anywhere users with
    passwords get created. Plain-``unittest.TestCase`` mixins (e.g.
    ``GitRepoMixin``) are not Django test classes and are skipped by design.
    """
    found: set[type[SimpleTestCase]] = set()
    for package_name in _PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
            module = importlib.import_module(info.name)
            for obj in vars(module).values():
                if (
                    isinstance(obj, type)
                    and issubclass(obj, SimpleTestCase)
                    and obj.__module__ == info.name
                ):
                    found.add(obj)
    return found


class TestSuiteConventionTests(BaseTestCase):
    """The fast-hasher inheritance convention holds across both suites.

    - test_every_db_class_uses_fast_hasher, each test class carries the MD5 override
    """

    def test_every_db_class_uses_fast_hasher(self) -> None:
        """Each Django test class carries the MD5 PASSWORD_HASHERS override."""
        # ``or {}``: Django pre-declares ``_overridden_settings = None`` on
        # undecorated classes, so getattr's default never kicks in for them.
        missing = sorted(
            f"{cls.__module__}.{cls.__qualname__}"
            for cls in _db_backed_test_classes()
            if _MD5_HASHER
            not in (getattr(cls, "_overridden_settings", None) or {}).get("PASSWORD_HASHERS", [])
        )
        self.assertEqual(missing, [], "classes missing the BaseTestCase hasher override")
