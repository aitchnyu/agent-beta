from __future__ import annotations

from inertia.test import InertiaTestCase

from djangoapp.models import User


class SharedPropsMiddlewareTests(
    InertiaTestCase,
):
    """SharedPropsMiddleware injects the viewer profile on every Inertia page.

    The shared ``user``/``viewer_is_superuser`` props back the navbar
    (Layout.vue reads them via ``usePage()``); they must reflect the actual
    viewer, be pk-free, and be present even on the public Home route.

    - test_anonymous_gets_no_user, anonymous request shares user None + flag False
    - test_plain_user_gets_profile_not_superuser, authed non-superuser gets profile, flag False
    - test_superuser_gets_profile_and_flag, superuser gets profile + viewer_is_superuser True
    - test_shared_user_is_pk_free, shared user carries public_id, never an integer id/pk
    """

    def test_anonymous_gets_no_user(self) -> None:
        """Anonymous request shares user None and viewer_is_superuser False."""
        self.inertia.get("/")
        props = self.props()
        assert props["user"] is None
        assert props["viewer_is_superuser"] is False

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
        assert props["user"] == {"public_id": user.public_id, "title": "Alice Smith"}
        assert props["viewer_is_superuser"] is False

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
        assert props["user"] == {"public_id": user.public_id, "title": "Root User"}
        assert props["viewer_is_superuser"] is True

    def test_shared_user_is_pk_free(self) -> None:
        """Shared user carries public_id and never an integer id/pk."""
        user = User.objects.create_user(username="alice", first_name="Alice")
        self.inertia.force_login(user)
        self.inertia.get("/")
        shared_user = self.props()["user"]
        assert shared_user is not None
        assert shared_user["public_id"] == user.public_id
        assert "id" not in shared_user
        assert "pk" not in shared_user
