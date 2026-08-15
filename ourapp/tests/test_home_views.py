"""Tests for the home view (``GET /``)."""

from http import HTTPStatus

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase


class HomeViewTests(BaseInertiaTestCase):
    """The landing page renders for anonymous and authenticated viewers (pk-free).

    - test_anonymous_home, anon GET / has ours/Home component, is_authenticated False
    - test_authenticated_home, authed GET / has display_name and public_id set
    - test_home_issues_csrftoken_cookie, GET / sets a csrftoken cookie so logout can POST
    - test_no_integer_pk_in_props, public_id present but no integer id/pk leaks
    """

    def test_anonymous_home(self) -> None:
        """Anon GET / has ours/Home with is_authenticated False and empty display_name."""
        self.inertia.get("/")
        self.assertComponentUsed("ours/Home")
        self.assertHasExactProps(
            {
                "props": {
                    "is_authenticated": False,
                    "display_name": "",
                    "public_id": "",
                },
                # Shared viewer props (SharedPropsMiddleware) are anonymous here.
                "user": None,
                "viewer_is_superuser": False,
            },
        )

    def test_authenticated_home(self) -> None:
        """Authed GET / has display_name and public_id set."""
        user = User.objects.create_user(
            username="alice",
            first_name="Alice",
            last_name="Smith",
        )
        self.inertia.force_login(user)
        self.inertia.get("/")
        self.assertComponentUsed("ours/Home")
        self.assertHasExactProps(
            {
                "props": {
                    "is_authenticated": True,
                    "display_name": "Alice Smith",
                    "public_id": user.public_id,
                },
                "user": {"public_id": user.public_id, "title": "Alice Smith"},
                "viewer_is_superuser": False,
            },
        )

    def test_home_issues_csrftoken_cookie(self) -> None:
        """GET / sets a csrftoken cookie so the logout form can POST."""
        # {% csrf_token %} in the inertia layout calls get_token(), so the
        # csrftoken cookie is issued on every GET - without it the logout
        # form would post an empty token -> 403.
        response = self.client.get("/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("csrftoken", response.cookies)

    def test_no_integer_pk_in_props(self) -> None:
        """public_id present but no integer id/pk leaks through props."""
        user = User.objects.create_user(username="alice")
        self.inertia.force_login(user)
        self.inertia.get("/")
        page = self.props()["props"]
        self.assertEqual(page["public_id"], user.public_id)
        self.assertNotIn("id", page)
        self.assertNotIn("pk", page)
