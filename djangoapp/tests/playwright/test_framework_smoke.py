"""Framework-subset browser smoke — the checkscratch extra pass.

When scratch/ edits touch framework files (anything outside ``ourapp/`` +
``frontend/src/ours/``), ``./run checkscratch`` runs the
``framework-subset``-tagged tests: the tagged view methods plus this ONE
browser class — a single browser launch (~5-10s total) proving the
framework's user-facing surfaces still render end-to-end. An early-warning
fraction of checkframework1's full browser pass, not a replacement.

The files browser is deliberately absent: its tests hardcode ``main/ourapp``
targets, and the browse root (BASE_DIR.parent — the shared parent of main/
and scratch/) resolves those to main/'s LIVE tree, so a scratch run would
false-green against main/'s unedited code. That feature stays covered by
checkframework1 in main/.
"""

from __future__ import annotations

from django.test import tag

from djangoapp.models import User
from djangoapp.tests._git_fixtures import GitRepoMixin
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


@tag("framework-subset")
class FrameworkSmokeE2e(GitRepoMixin, BasePlaywrightTestCase):
    """One smoke per framework feature, one browser launch (superuser session).

    - test_users_edit_smoke, the superuser edit form renders (users feature)
    - test_git_commits_smoke, /git/commits lists the fixture's commits (git feature)
    - test_client_errors_smoke, an uncaught error POSTs to /client-errors (error pipeline)
    """

    def setUp(self) -> None:
        super().setUp()  # auth + the class-scoped repo fixture (GitRepoMixin)
        self.smoke_root = User.objects.create_user(
            username="smokeroot",
            password="x",
            is_staff=True,
            is_superuser=True,
        )
        self.smoke_target = User.objects.create_user(
            username="smoketarget",
            password="x",
            first_name="Smoke",
            last_name="Target",
        )
        self.login_as(self.smoke_root)

    def test_users_edit_smoke(self) -> None:
        """The superuser edit form renders for a target user."""
        page = self.page
        page.goto(f"{self.live_server_url}/users/edit/{self.smoke_target.public_id}")
        page.wait_for_selector(".user-edit-first-name")

    def test_git_commits_smoke(self) -> None:
        """/git/commits lists the fixture's commits with the count."""
        page = self.page
        page.goto(f"{self.live_server_url}/git/commits")
        page.get_by_role("link", name=self.short_b).wait_for(state="visible")
        self.assertIn("3 commits", page.inner_text("body"))

    def test_client_errors_smoke(self) -> None:
        """An uncaught window error is captured and POSTed to /client-errors."""
        self.expect_console_errors()  # the handler logs the error before reporting it
        page = self.page
        page.goto(f"{self.live_server_url}/")
        with page.expect_request(
            lambda req: req.method == "POST" and "/client-errors" in req.url
        ) as req_info:
            page.evaluate("() => setTimeout(() => { throw new Error('framework smoke boom') }, 0)")
        self.assertIn("/client-errors", req_info.value.url)
