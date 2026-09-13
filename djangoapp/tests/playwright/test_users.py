from __future__ import annotations

from http import HTTPStatus

from djangoapp.models import User
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class LoginForTestGateE2eTestCase(BasePlaywrightTestCase):
    """Auth-infrastructure gates.

    - test_set_up_injects_session_cookie, ensures login_as works (cookie in context)
    """

    def test_set_up_injects_session_cookie(self) -> None:
        """Ensure login_as works as expected: an authenticated round trip.

        Every e2e test assumes the harness's in-process cookie injection is
        sound; if it ever breaks (session engine change, cookie rename,
        add_cookies semantics), this fails loudly by name instead of as 20+
        baffling 404s across unrelated feature tests. A real page load (not
        just the cookie's presence) proves the server accepts the session.
        """
        self.page.goto(f"{self.live_server_url}/")
        self.page.wait_for_selector(".home-status-signed-in")
        self.assertIn(
            self.user.username,
            self.page.locator(".home-status-signed-in").inner_text(),
        )


class UserEditE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the superuser user-edit page.

    Verifies the edit form loads for a superuser, a field change is saved
    via POST, the page redirects to the profile, and the DB reflects the
    edit (which also records a UserHistory entry).

    - test_edit_page_saves_first_name, change first name, submit, redirect, DB updated
    - test_edit_page_updates_description, type into the rich-text editor, submit, DB updated
    - test_edit_page_requires_superuser, anonymous viewer gets 404 on the edit form
    """

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Old",
            last_name="Name",
            email="old@example.com",
        )
        self.login_as(self.superuser)

    def test_edit_page_saves_first_name(self) -> None:
        """Change first name on the edit form; submit redirects and persists."""
        # 2s budget: the post-save client-side redirect flaked at the 1s
        # default under VM load.
        self.page.set_default_timeout(2000)
        page = self.page
        page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
        page.wait_for_selector(".user-edit-first-name")

        page.locator(".user-edit-first-name").fill("NewFirst")
        page.locator(".user-edit-save").click()
        page.wait_for_url(f"**/users/id/{self.target.public_id}")

        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, "NewFirst")

    def test_edit_page_updates_description(self) -> None:
        """Type into the rich-text editor; submit persists the description."""
        # 2s budget: same VM-load flake on the post-save redirect as the
        # first-name test above; setUp's per-test reset keeps the raise local.
        self.page.set_default_timeout(2000)
        page = self.page
        page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
        page.wait_for_selector(".ql-editor")

        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        quill_editor.type("Updated about text")

        page.locator(".user-edit-save").click()
        page.wait_for_url(f"**/users/id/{self.target.public_id}")

        self.target.refresh_from_db()
        self.assertIn("Updated about text", self.target.description)

    def test_edit_page_requires_superuser(self) -> None:
        """Anonymous viewer of the edit form gets a 404."""
        with self.anon_page() as page:
            response = page.goto(f"{self.live_server_url}/users/edit/{self.target.public_id}")
            assert response is not None
            self.assertEqual(response.status, HTTPStatus.NOT_FOUND)


class UserHistoryE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the superuser user-history page.

    Verifies the history timeline renders after an edit, showing the
    "Edited" badge and the per-field diff. (User "created" history is not
    recorded yet, so the timeline is seeded by an explicit edit.)

    - test_history_page_shows_edit_diff, after an edit the timeline shows the first-name diff
    - test_history_page_requires_superuser, anonymous viewer gets 404
    """

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Before",
            last_name="Name",
            email="before@example.com",
        )
        self.login_as(self.superuser)

    def test_history_page_shows_edit_diff(self) -> None:
        """After an edit, the history timeline shows the first-name diff."""
        self.target.update(
            first_name="After",
            last_name=self.target.last_name,
            email=self.target.email,
            description=self.target.description,
            has_public_profile=self.target.has_public_profile,
            is_active=self.target.is_active,
            is_staff=self.target.is_staff,
            is_superuser=self.target.is_superuser,
            user=self.superuser,
        )

        page = self.page
        page.goto(f"{self.live_server_url}/users/history/{self.target.public_id}")
        page.wait_for_selector(".user-history-entry")

        self.assertGreaterEqual(page.locator("text=Edited").count(), 1)
        self.assertGreaterEqual(page.locator(".user-history-old", has_text="Before").count(), 1)
        self.assertGreaterEqual(page.locator(".user-history-new", has_text="After").count(), 1)

    def test_history_page_requires_superuser(self) -> None:
        """Anonymous viewer of the history page gets a 404."""
        with self.anon_page() as page:
            response = page.goto(f"{self.live_server_url}/users/history/{self.target.public_id}")
            assert response is not None
            self.assertEqual(response.status, HTTPStatus.NOT_FOUND)


class UserDetailsAdminActionsE2eTestCase(BasePlaywrightTestCase):
    """E2E for the details page admin action (login link).

    The admin issues a one-time link on the details page and an anonymous
    browser redeems it — the target is then signed in there — and
    "Log out everywhere" ends that session from the admin side.

    - test_login_link_issues_and_redeems, issue on the details page, redeem in a 2nd browser
    - test_logout_everywhere_ends_session, the admin button kills the redeemed session
    - test_details_requires_no_superuser_rows, non-superuser viewer sees no admin actions/attrs
    """

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Link",
            last_name="Target",
            email="target@example.com",
        )
        self.login_as(self.superuser)

    def test_login_link_issues_and_redeems(self) -> None:
        """Issue on the details page, redeem in a second browser."""
        # Sweetalert renders in-DOM and toasts are fire-and-forget; the e2e
        # budget covers the chunk loads under VM load.
        self.page.set_default_timeout(4000)
        page = self.page
        page.goto(f"{self.live_server_url}/users/id/{self.target.public_id}")
        page.wait_for_selector(".user-details-login-link-btn")

        page.locator(".user-details-login-link-btn").click()
        page.locator(".user-details-generate-link-btn").click()
        page.wait_for_selector(".user-details-link-url")
        url = page.locator(".user-details-link-url").input_value()

        with self.anon_page() as anon:
            anon.goto(url)
            anon.wait_for_selector(".home-status-signed-in")
            self.assertIn("Link Target", anon.locator(".home-status-signed-in").inner_text())

    def test_logout_everywhere_ends_session(self) -> None:
        """The admin button kills a session redeemed in a second browser."""
        self.page.set_default_timeout(4000)
        page = self.page
        page.goto(f"{self.live_server_url}/users/id/{self.target.public_id}")
        page.locator(".user-details-login-link-btn").click()
        page.locator(".user-details-generate-link-btn").click()
        page.wait_for_selector(".user-details-link-url")
        url = page.locator(".user-details-link-url").input_value()

        with self.anon_page() as anon:
            anon.goto(url)
            anon.wait_for_selector(".home-status-signed-in")

            page.locator(".user-details-logout-btn").click()
            page.locator(".swal2-confirm").click()
            page.wait_for_selector(".user-details-logout-btn:not([disabled])")

            anon.goto(f"{self.live_server_url}/")
            anon.wait_for_selector(".home-status-signed-out")

    def test_details_requires_no_superuser_rows(self) -> None:
        """Non-superuser viewer sees no admin actions/attrs."""
        with self.anon_page() as page:
            page.goto(f"{self.live_server_url}/users/id/{self.target.public_id}")
            page.wait_for_selector(".user-details-page")
            self.assertEqual(page.locator(".user-details-login-link-btn").count(), 0)
            self.assertEqual(page.locator(".user-details-attrs").count(), 0)
