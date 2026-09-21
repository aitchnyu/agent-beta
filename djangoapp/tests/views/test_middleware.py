from __future__ import annotations

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.utils import timezone

from djangoapp.models import Notification, User
from djangoapp.tests._base import BaseInertiaTestCase


class SharedPropsMiddlewareTests(
    BaseInertiaTestCase,
):
    """SharedPropsMiddleware injects the viewer profile on every Inertia page.

    The shared ``user``/``viewer_is_superuser`` props back the navbar
    (Layout.vue reads them via ``usePage()``); they must reflect the actual
    viewer, be pk-free, and be present even on the public Home route. The
    shared ``login_providers`` list drives the anonymous navbar's Sign-in
    dropdown from the configured SocialApps.

    - test_anonymous_gets_no_user, anonymous request shares user None + flag False
    - test_plain_user_gets_profile_not_superuser, authed non-superuser gets profile, flag False
    - test_superuser_gets_profile_and_flag, superuser gets profile + viewer_is_superuser True
    - test_shared_user_is_pk_free, shared user carries public_id, never an integer id/pk
    - test_anonymous_gets_login_providers, configured providers share id/name/login url
    - test_no_providers_configured_shares_empty_list, no SocialApp rows share an empty list
    - test_stale_provider_row_is_skipped, uninstalled-provider rows never appear
    - test_duplicate_provider_rows_collapse_to_one, same-provider rows share a single entry
    - test_anonymous_unread_count_is_zero, anonymous shares a static 0 (no query)
    - test_unread_count_reflects_read_state, signed-in count is the unread rows only
    - test_just_logged_in_is_one_shot, the flag rides the first rendered page after login only
    - test_just_logged_in_survives_non_page_requests, XHR/JSON responses never burn the one shot
    """

    def _add_social_app(self) -> None:
        """Seed the one configured provider (google), as addoauth does."""
        app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="client-abc",
            secret="secret",
        )
        app.sites.add(Site.objects.get(pk=settings.SITE_ID))

    def test_anonymous_gets_no_user(self) -> None:
        """Anonymous request shares user None and viewer_is_superuser False."""
        self.inertia.get("/")
        props = self.props()
        self.assertIsNone(props["user"])
        self.assertFalse(props["viewer_is_superuser"])

    def test_anonymous_unread_count_is_zero(self) -> None:
        """Anonymous shares a static unread count of 0."""
        self.inertia.get("/")
        self.assertEqual(self.props()["unread_notifications"], 0)

    def test_unread_count_reflects_read_state(self) -> None:
        """Signed-in count covers unread rows only, own rows only."""
        user = User.objects.create_user(username="alice")
        other = User.objects.create_user(username="bob")
        Notification.record(recipient=user, kind="k1", body="unread")
        Notification.record(recipient=user, kind="k2", body="read")
        Notification.record(recipient=user, kind="k3", body="also unread")
        Notification.objects.filter(kind="k2").update(read_at=timezone.now())
        Notification.record(recipient=other, kind="k4", body="not mine")
        self.inertia.force_login(user)
        self.inertia.get("/")
        self.assertEqual(self.props()["unread_notifications"], 2)

    def test_just_logged_in_is_one_shot(self) -> None:
        """The login flag rides the first rendered page after login, then is gone.

        force_login sets it (via the user_logged_in signal, like a real
        login); the landing render — a plain HTML document GET, no
        X-Inertia — carries it in the embedded page props and consumes
        it; a second render does neither. (The inertia test client's
        visits all carry X-Inertia and so never consume — that is the
        point of the scope guard.)
        """
        user = User.objects.create_user(username="alice")
        self.client.force_login(user)
        self.assertIn("just_logged_in", self.client.session)
        first = self.client.get("/")
        self.assertIn(b'"just_logged_in": true', first.content)
        self.assertNotIn("just_logged_in", self.client.session)
        second = self.client.get("/")
        self.assertNotIn(b'"just_logged_in": true', second.content)

    def test_just_logged_in_survives_non_page_requests(self) -> None:
        """XHR/partials and JSON responses must not burn the one shot.

        Only a successfully rendered full page delivers the flag to the
        bell — an Inertia partial (X-Inertia header) and a JSON API
        response both leave it for the real landing to consume.
        """
        user = User.objects.create_user(username="alice")
        self.client.force_login(user)
        self.assertTrue("just_logged_in" in self.client.session)
        # Inertia partial-style request: carries the X-Inertia header.
        self.client.get("/", headers={"x-inertia": "true"})
        self.assertTrue("just_logged_in" in self.client.session)
        # A JSON API response (no X-Inertia, but not an HTML render).
        self.client.post("/notifications/api/test")
        self.assertTrue("just_logged_in" in self.client.session)
        # The full HTML landing consumes it.
        self.client.get("/")
        self.assertFalse("just_logged_in" in self.client.session)

    def test_plain_user_gets_profile_not_superuser(self) -> None:
        """Authenticated non-superuser gets a profile but viewer_is_superuser False."""
        user = User.objects.create_user(
            username="alice",
            first_name="Alice",
            last_name="Smith",
        )
        self.inertia.force_login(user)
        self.inertia.get("/")
        props = self.props()
        self.assertEqual(props["user"], {"public_id": user.public_id, "title": "Alice Smith"})
        self.assertFalse(props["viewer_is_superuser"])
        # Null (not []) — the provider lookup must not even run signed in.
        self.assertIsNone(props["login_providers"])

    def test_superuser_gets_profile_and_flag(self) -> None:
        """Superuser gets a profile and viewer_is_superuser True."""
        user = User.objects.create_user(
            username="root",
            first_name="Root",
            last_name="User",
            is_superuser=True,
            is_staff=True,
        )
        self.inertia.force_login(user)
        self.inertia.get("/")
        props = self.props()
        self.assertEqual(props["user"], {"public_id": user.public_id, "title": "Root User"})
        self.assertTrue(props["viewer_is_superuser"])

    def test_shared_user_is_pk_free(self) -> None:
        """Shared user carries public_id and never an integer id/pk."""
        user = User.objects.create_user(username="alice", first_name="Alice")
        self.inertia.force_login(user)
        self.inertia.get("/")
        shared_user = self.props()["user"]
        assert shared_user is not None
        self.assertEqual(shared_user["public_id"], user.public_id)
        self.assertNotIn("id", shared_user)
        self.assertNotIn("pk", shared_user)

    def test_anonymous_gets_login_providers(self) -> None:
        """Anonymous request shares the configured providers for the Sign-in dropdown."""
        self._add_social_app()
        self.inertia.get("/")
        self.assertEqual(
            self.props()["login_providers"],
            [{"id": "google", "name": "Google", "url": "/accounts/google/login/"}],
        )

    def test_no_providers_configured_shares_empty_list(self) -> None:
        """No SocialApp rows share an empty list (navbar falls back to a plain link)."""
        self.inertia.get("/")
        self.assertEqual(self.props()["login_providers"], [])

    def test_stale_provider_row_is_skipped(self) -> None:
        """A SocialApp row for an uninstalled provider never appears."""
        self._add_social_app()
        # github has no provider module installed — a leftover row like this
        # must be skipped, not 500 every anonymous page.
        stale = SocialApp.objects.create(
            provider="github",
            name="GitHub",
            client_id="client-xyz",
            secret="secret",
        )
        stale.sites.add(Site.objects.get(pk=settings.SITE_ID))
        self.inertia.get("/")
        self.assertEqual(
            self.props()["login_providers"],
            [{"id": "google", "name": "Google", "url": "/accounts/google/login/"}],
        )

    def test_duplicate_provider_rows_collapse_to_one(self) -> None:
        """Two SocialApp rows for the same provider share a single entry."""
        self._add_social_app()
        duplicate = SocialApp.objects.create(
            provider="google",
            name="Google again",
            client_id="client-dupe",
            secret="secret",
        )
        duplicate.sites.add(Site.objects.get(pk=settings.SITE_ID))
        self.inertia.get("/")
        # distinct("provider") — one dropdown entry, not two links to Google.
        self.assertEqual(
            self.props()["login_providers"],
            [{"id": "google", "name": "Google", "url": "/accounts/google/login/"}],
        )
