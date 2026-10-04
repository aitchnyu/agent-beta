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
                # Shared viewer props (SharedPropsMiddleware) are anonymous
                # here; no SocialApps configured → empty provider list.
                "user": None,
                "viewer_is_superuser": False,
                "login_providers": [],
                "unread_notifications": 0,
                "just_logged_in": False,
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
                # Signed-in requests get null — no provider lookup runs.
                "login_providers": None,
                "unread_notifications": 0,
                # force_login IS a login: the first render after it
                # carries the one-shot rebind flag.
                "just_logged_in": True,
            },
        )

    def test_home_issues_csrftoken_cookie(self) -> None:
        """GET / sets a csrftoken cookie so CSRF-needing POSTs can send it."""
        # {% csrf_token %} in the inertia layout calls get_token(), so the
        # csrftoken cookie is issued on every GET — without it the navbar
        # user menu's logout form (and any other POSTing layer) would fail
        # its token check -> 403.
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


class MockupTodosTests(BaseInertiaTestCase):
    """The permanent mockup demo route: superuser-only, no data plumbing.

    - test_superuser_sees_mockup, superuser GET /mockup-todos renders ours/MockupTodos, empty props
    - test_anonymous_gets_404, anyone else never learns the page exists (404, not 403)
    - test_non_superuser_gets_404, a logged-in regular user gets 404 too
    """

    def test_superuser_sees_mockup(self) -> None:
        """Superuser sees the demo component with no props (nothing fetched)."""
        root = User.objects.create_user(username="root", password="pw", is_superuser=True)
        self.inertia.force_login(root)
        self.inertia.get("/mockup-todos")
        self.assertComponentUsed("ours/MockupTodos")
        self.assertEqual(self.props()["props"], {})

    def test_anonymous_gets_404(self) -> None:
        """Anonymous never learns the page exists (404, not 403)."""
        response = self.client.get("/mockup-todos")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_non_superuser_gets_404(self) -> None:
        """A logged-in regular user gets 404 too — the page stays superuser-only."""
        user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/mockup-todos").status_code, HTTPStatus.NOT_FOUND)
