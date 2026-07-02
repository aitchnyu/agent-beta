from http import HTTPStatus

from inertia.test import InertiaTestCase

from djangoapp.models import User


class HomeViewTests(InertiaTestCase):
    """Inertia Home page renders for anonymous and authenticated users.

    The Home page is the single public-facing route in the foundation
    scaffold; it must show login state without leaking the integer pk.

    - test_anonymous_home, anon GET / has Home component, is_authenticated False
    - test_authenticated_home, authed GET / has display_name and public_id set
    - test_home_issues_csrftoken_cookie, GET / sets a csrftoken cookie so logout can POST
    """

    def test_anonymous_home(self) -> None:
        """Anon GET / has Home component with is_authenticated False and empty display_name."""
        self.inertia.get("/")
        self.assertComponentUsed("Home")
        self.assertHasExactProps(
            {
                "is_authenticated": False,
                "display_name": "",
                "public_id": "",
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
        self.assertHasExactProps(
            {
                "is_authenticated": True,
                "display_name": "Alice Smith",
                "public_id": user.public_id,
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
        assert response.status_code == HTTPStatus.OK
        assert "csrftoken" in response.cookies


class NoPkLeakTests(InertiaTestCase):
    """The home response must never expose the integer pk.

    - test_no_integer_pk_in_props, public_id is present but no integer id/pk leaks through props
    """

    def test_no_integer_pk_in_props(self) -> None:
        """public_id is present but no integer id/pk leaks through props."""
        user = User.objects.create_user(username="alice")
        self.inertia.force_login(user)
        self.inertia.get("/")
        props = self.props()
        assert props["public_id"] == user.public_id
        assert "id" not in props
        assert "pk" not in props
