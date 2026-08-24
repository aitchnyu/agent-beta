from __future__ import annotations

from http import HTTPStatus
from typing import ClassVar

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase


class AgentAuthViewTests(BaseInertiaTestCase):
    """The caddy forward_auth verdict endpoint for /agent/* (ttyd console).

    The gate mirrors the house pattern (require_superuser → 404 for
    anonymous AND non-superuser — existence stays hidden, never 403);
    only a superuser session yields the 2xx caddy needs to proxy to ttyd.

    - test_anon_404 / test_non_superuser_404, gate → 404
    - test_superuser_200, superuser session → 200 with an empty body
    - test_slashed_404, the slashed form must NOT exist (APPEND_SLASH
      would 301 it; caddy doesn't follow redirects and would relay the
      301 to the client as the auth verdict)
    """

    superuser: ClassVar[User]
    plain: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_user(username="admin", is_superuser=True, is_staff=True)
        cls.plain = User.objects.create_user(username="plain")

    def test_anon_404(self) -> None:
        response = self.client.get("/agent/auth")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_non_superuser_404(self) -> None:
        self.client.force_login(self.plain)
        response = self.client.get("/agent/auth")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_superuser_200(self) -> None:
        self.client.force_login(self.superuser)
        response = self.client.get("/agent/auth")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"")

    def test_slashed_404(self) -> None:
        self.client.force_login(self.superuser)
        response = self.client.get("/agent/auth/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
