from __future__ import annotations

from http import HTTPStatus
from typing import ClassVar

from inertia.test import InertiaTestCase

from djangoapp.models import User


class ManageModelsViewTests(InertiaTestCase):
    """Superuser-only models-management pages over ourapp's models.

    ourapp ships empty, so the model list is empty here; the routes, the
    superuser gate, and unknown-model 404s are what's exercised. Row list /
    detail against a real model are covered once ourapp defines one (see
    ``docs/reference/``).

    - test_non_superuser_404 / test_anon_404, access gate → 404
    - test_model_list_empty, /manage/models renders ModelList with no models
    - test_unknown_model_list_404, unknown model /list → 404
    - test_unknown_model_detail_404, unknown model /id → 404
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_non_superuser_404(self) -> None:
        """non-superuser gets 404 on /manage/models."""
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get("/manage/models").status_code, HTTPStatus.NOT_FOUND)

    def test_anon_404(self) -> None:
        """Anonymous viewer gets 404 on /manage/models."""
        self.assertEqual(self.client.get("/manage/models").status_code, HTTPStatus.NOT_FOUND)

    def test_model_list_empty(self) -> None:
        """With no ourapp models, /manage/models renders ModelList (empty)."""
        self.client.force_login(self.superuser)
        self.client.get("/manage/models")
        self.assertComponentUsed("ModelList")
        self.assertEqual(self.props()["props"]["models"], [])

    def test_unknown_model_list_404(self) -> None:
        """An unknown model's /list → 404."""
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get("/manage/models/DoesNotExist/list").status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_unknown_model_detail_404(self) -> None:
        """An unknown model's /id → 404."""
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get("/manage/models/DoesNotExist/id/x").status_code,
            HTTPStatus.NOT_FOUND,
        )
