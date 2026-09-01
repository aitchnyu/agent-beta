"""Tests for the home view (``GET /``)."""

from http import HTTPStatus

from djangoapp.models import User
from djangoapp.tests._base import BaseInertiaTestCase
from ourapp.models import Fact, FactOfTheDay, Topic


class HomeViewTests(BaseInertiaTestCase):
    """The landing page renders for anonymous and authenticated viewers (pk-free).

    - test_anonymous_home, anon GET / has ours/Home component, is_authenticated False
    - test_authenticated_home, authed GET / has display_name and public_id set
    - test_home_issues_csrftoken_cookie, GET / sets a csrftoken cookie so logout can POST
    - test_no_integer_pk_in_props, public_id present but no integer id/pk leaks
    - test_home_get_does_not_create_pick, GET / with facts but no cron write leaves fact_of_day None (GET never writes)
    - test_home_shows_fact_of_the_day, once the cron has picked, GET / carries it in props (pk-free)
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
                    "fact_of_day": None,
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
                    "fact_of_day": None,
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

    def test_home_shows_fact_of_the_day(self) -> None:
        """Once the cron has picked, GET / carries it as fact_of_day (pk-free)."""
        topic = Topic.objects.create(name="cars", slug="cars")
        fact = Fact.objects.create(text="VW Beetle ran 65 years.", topic=topic)
        FactOfTheDay.choose_for_today()  # the cron's write — a GET never writes
        page = self.client.get("/", HTTP_X_INERTIA="true").json()
        props = page["props"]["props"]
        self.assertEqual(props["fact_of_day"]["public_id"], fact.public_id)
        self.assertNotIn("id", props["fact_of_day"])  # pk-free

    def test_home_get_does_not_create_pick(self) -> None:
        """A GET alone never creates the pick, even when facts exist (read-only)."""
        topic = Topic.objects.create(name="cars", slug="cars")
        Fact.objects.create(text="VW Beetle ran 65 years.", topic=topic)
        page = self.client.get("/", HTTP_X_INERTIA="true").json()
        self.assertIsNone(page["props"]["props"]["fact_of_day"])
        self.assertEqual(FactOfTheDay.objects.count(), 0)
