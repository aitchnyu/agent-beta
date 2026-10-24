"""Tests for the home view (``GET /``)."""

import base64
import json
from http import HTTPStatus

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase


class HomeViewTests(BaseInertiaTestCase):
    """The landing page renders for anonymous and authenticated viewers (pk-free).

    - test_anonymous_home, anon GET / has ours/Home component, no page props
    - test_authenticated_home, authed GET / carries identity via the shared user prop
    - test_home_issues_csrftoken_cookie, GET / sets a csrftoken cookie so logout can POST
    - test_no_integer_pk_in_props, public_id present but no integer id/pk leaks
    """

    def test_anonymous_home(self) -> None:
        """Anon GET / has ours/Home with no page props (shared viewer anonymous)."""
        # Full payload for reference (not asserted — features add props):
        # {
        #     "props": {},
        #     # Shared viewer props (SharedPropsMiddleware) are anonymous
        #     # here; no SocialApps configured → empty provider list.
        #     "user": None,
        #     "viewer_is_superuser": False,
        #     "login_providers": [],
        #     "unread_notifications": 0,
        #     "just_logged_in": False,
        # }
        self.inertia.get("/")
        self.assertComponentUsed("ours/Home")
        page = self.props()
        self.assertEqual(page["props"], {})
        self.assertIsNone(page["user"])

    def test_authenticated_home(self) -> None:
        """Authed GET / carries identity via the shared user prop (pk-free)."""
        # Full payload for reference (not asserted — features add props):
        # {
        #     "props": {},
        #     "user": {"public_id": "<…>", "title": "Alice Smith"},
        #     "viewer_is_superuser": False,
        #     # Signed-in requests get null — no provider lookup runs.
        #     "login_providers": None,
        #     "unread_notifications": 0,
        #     # force_login IS a login: the first render after it
        #     # carries the one-shot rebind flag.
        #     "just_logged_in": True,
        # }
        user = User.objects.create_user(
            username="alice",
            first_name="Alice",
            last_name="Smith",
        )
        self.inertia.force_login(user)
        self.inertia.get("/")
        self.assertComponentUsed("ours/Home")
        page = self.props()
        self.assertEqual(page["props"], {})
        # The shared viewer prop carries the identity the page gates on.
        self.assertEqual(page["user"]["public_id"], user.public_id)
        self.assertEqual(page["user"]["title"], "Alice Smith")
        # The one-shot rebind flag force_login produces.
        self.assertIs(page["just_logged_in"], True)  # noqa: FBT003

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
        viewer = self.props()["user"]
        self.assertEqual(viewer["public_id"], user.public_id)
        self.assertNotIn("id", viewer)
        self.assertNotIn("pk", viewer)


class MockupTodosTests(BaseInertiaTestCase):
    """The permanent mockup demo route: superuser-only, no data plumbing.

    - test_superuser_sees_mockup, superuser GET /mockup/MockupTodos renders
      ours/MockupTodos, empty props
    - test_props_url_param_presets_props, ?props=<base64url JSON> becomes
      the page props
    - test_bad_props_param_is_422, a non-decodable props param is the standard 422
    - test_deeply_nested_props_param_is_422, deeply-nested JSON is a 422 too
      (json.loads RecursionError must not escape as a 500)
    - test_anonymous_gets_404, anyone else never learns the page exists (404, not 403)
    - test_non_superuser_gets_404, a logged-in regular user gets 404 too
    """

    def test_superuser_sees_mockup(self) -> None:
        """Superuser sees the demo component with no props (nothing fetched)."""
        root = User.objects.create_user(username="root", password="pw", is_superuser=True)
        self.inertia.force_login(root)
        self.inertia.get("/mockup/MockupTodos")
        self.assertComponentUsed("ours/MockupTodos")
        self.assertEqual(self.props()["props"], {})

    def test_props_url_param_presets_props(self) -> None:
        """?props=<base64url JSON object> rides through as the page props."""
        root = User.objects.create_user(username="root", password="pw", is_superuser=True)
        self.inertia.force_login(root)
        encoded = base64.urlsafe_b64encode(json.dumps({"items": 3}).encode()).decode().rstrip("=")
        self.inertia.get(f"/mockup/MockupTodos?props={encoded}")
        self.assertEqual(self.props()["props"], {"items": 3})

    def test_bad_props_param_is_422(self) -> None:
        """A props param that is not base64url JSON gets the standard 422."""
        root = User.objects.create_user(username="root", password="pw", is_superuser=True)
        self.client.force_login(root)
        response = self.client.get("/mockup/MockupTodos?props=not-b64-json")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_deeply_nested_props_param_is_422(self) -> None:
        """Deeply-nested JSON stays a 422 (RecursionError must not 500)."""
        root = User.objects.create_user(username="root", password="pw", is_superuser=True)
        self.client.force_login(root)
        deep = base64.urlsafe_b64encode(("[" * 2000 + "]" * 2000).encode()).decode()
        response = self.client.get(f"/mockup/MockupTodos?props={deep}")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_anonymous_gets_404(self) -> None:
        """Anonymous never learns the page exists (404, not 403)."""
        response = self.client.get("/mockup/MockupTodos")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_non_superuser_gets_404(self) -> None:
        """A logged-in regular user gets 404 too — the page stays superuser-only."""
        user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/mockup/MockupTodos").status_code, HTTPStatus.NOT_FOUND)
