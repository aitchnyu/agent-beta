"""README screenshot generation — the ``screenshots``-tagged Playwright pass.

Each test produces one committed PNG under ``docs/screenshots/`` (referenced
from README.md). The pass SELF-GATES on ``GENERATE_SCREENSHOTS`` (set only by
``./run screenshots``), so the module needs no ``run``-script wiring to stay
out of the normal passes: ``./run test`` never collects it (it carries the
inherited ``playwright`` tag, which ``test`` excludes) and
``./run playwrighttest`` collects it as skips — committed files are only ever
written on demand. Regenerate with ``./run screenshots``.

The remaining skip gates key off the environment, mirroring the project
tests: ``RUN_PROJECT_TESTS`` set → the testapp overlay is active → the
models-management shots run but the mockup shot skips (the overlay replaces
``ourapp/`` wholesale, dropping the ``/mockup-todos`` route); unset (plain
main) → the reverse. The models shots therefore regenerate via the manual
overlay recipe in ``docs/screenshots/README.md`` (plain ``main/`` has no
models to show).
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest import skipIf

from django.apps import apps
from django.conf import settings
from django.test import tag
from django.utils import timezone

from djangoapp.models import Notification, User
from djangoapp.tests._git_fixtures import GitRepoMixin
from djangoapp.tests.playwright._base import BasePlaywrightTestCase
from djangoapp.tests.views import skip_unless_env

if TYPE_CHECKING:
    from playwright.sync_api import ViewportSize

# PNGs are committed artifacts of the repo, not test scratch: they live under
# docs/ next to the README that references them (BASE_DIR = repo root).
_SCREENSHOT_DIR = Path(str(settings.BASE_DIR)) / "docs" / "screenshots"

# The README's screenshot viewport: desktop width (the git diff renders its
# side-by-side view at ≥768px) with a modest height — cards taller than the
# viewport are still captured whole (Playwright element screenshots scroll
# and stitch).
_SCREENSHOT_VIEWPORT: ViewportSize = {"width": 1280, "height": 960}
# The shared suite context's creation default (restored after each shot).
_DEFAULT_VIEWPORT: ViewportSize = {"width": 1280, "height": 720}


@skip_unless_env("GENERATE_SCREENSHOTS")
@tag("screenshots")
class BaseScreenshotTestCase(BasePlaywrightTestCase):
    """Base for the screenshot pass — env-gated, tagged, viewport-sized.

    The ``GENERATE_SCREENSHOTS`` gate (set only by ``./run screenshots``) is
    what keeps the pass out of the regular suites without any
    ``--exclude-tag`` wiring in the ``run`` script's existing commands: the
    class keeps the inherited ``playwright`` tag (``./run test`` skips it) but
    self-skips in ``./run playwrighttest`` unless the env var is set. The
    shared page is resized to the README viewport for the test and restored
    afterwards (the page outlives the class).

    - _shot, element screenshot of a page's main content container
    - _shot_below_navbar, clip screenshot of everything under the app navbar
      (for the fragment-rooted git/files pages that have no container div)
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def setUp(self) -> None:
        super().setUp()
        default_viewport = self.page.viewport_size or _DEFAULT_VIEWPORT
        self.page.set_viewport_size(_SCREENSHOT_VIEWPORT)
        self.addCleanup(lambda: self.page.set_viewport_size(default_viewport))

    def _shot(self, name: str, selector: str) -> None:
        """Screenshot the page's main content container → ``<name>.png``."""
        locator = self.page.locator(selector)
        locator.wait_for(state="visible")
        locator.screenshot(path=str(_SCREENSHOT_DIR / f"{name}.png"))

    def _shot_below_navbar(self, name: str, max_height: float | None = None) -> None:
        """Clip-screenshot everything under ``.layout-navbar`` → ``<name>.png``.

        The git/files pages render as fragments (no container div to target),
        so their "specific area" is the document minus the app navbar: a
        full-page screenshot clipped to below the navbar's box, the full body
        width and height (taller-than-viewport content included).
        ``max_height`` crops from the top for pages whose full document is
        too tall to embed (the file viewer renders its markdown twice —
        rendered view + raw source block).
        """
        navbar = self.page.locator(".layout-navbar").bounding_box()
        body = self.page.locator("body").bounding_box()
        assert navbar is not None
        assert body is not None
        top = navbar["y"] + navbar["height"]
        height = body["y"] + body["height"] - top
        if max_height is not None:
            height = min(height, max_height)
        self.page.screenshot(
            path=str(_SCREENSHOT_DIR / f"{name}.png"),
            full_page=True,
            clip={"x": 0.0, "y": top, "width": body["width"], "height": height},
        )


class NotificationScreenshotTests(BaseScreenshotTestCase):
    """The notifications page shot (docs/screenshots/notifications.png).

    Seeds the plain test user's list with representative rows — varied kinds
    (the free-form bucket the frontend groups by), staggered ages so the
    humanized times differ, and a mix of read/unread — then captures the
    page's container card (browser-push card included: that state —
    "not configured" — is the honest dev default).

    - test_notifications_page, /notifications with mixed kinds/ages/read states
    """

    def test_notifications_page(self) -> None:
        """/notifications renders the seeded list; container card is captured."""
        now = timezone.now()
        rows = [
            # (kind, body, url, minutes_old, read)
            ("backup.done", "Nightly backup finished — 1.2 GB uploaded", "", 12, False),
            (
                "comment.new",
                "Grace commented on Central tasks: 'due date?'",
                "/users/list",
                47,
                False,
            ),
            ("invoice.paid", "Invoice #142 paid — €180.00 from Acme Corp", "", 3 * 60, True),
            ("task.done", "Fact of the Day published to the homepage", "/", 26 * 60, True),
            ("system", "Session idle deadline extended by your activity", "", 3 * 24 * 60, True),
        ]
        for kind, body, url, minutes_old, read in rows:
            notification = Notification.objects.create(
                recipient=self.user, kind=kind, body=body, url=url
            )
            Notification.objects.filter(pk=notification.pk).update(
                created_at=now - timedelta(minutes=minutes_old),
                read_at=now - timedelta(minutes=minutes_old - 1) if read else None,
            )
        self.page.goto(f"{self.live_server_url}/notifications")
        self.page.wait_for_selector(".notification-item")
        self._shot("notifications", ".notifications-page")


class UserScreenshotTests(BaseScreenshotTestCase):
    """User list + detail shots (docs/screenshots/users*.png).

    Seeds a realistic roster (the fields the table shows: name, username,
    email, public/staff/superuser flags) and one featured profile with a
    public description so the detail shot shows the rich-text viewer.

    - test_user_list, /users/list with a page of realistic profiles
    - test_user_detail, /users/id/<pid> of a public-profile user (admin panel)
    """

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(
            username="admin",
            password="x",
            first_name="Site",
            last_name="Admin",
            email="admin@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.login_as(self.admin)
        roster = [
            ("ada", "Ada", "Lovelace"),
            ("alan", "Alan", "Turing"),
            ("barbara", "Barbara", "Liskov"),
            ("donald", "Donald", "Knuth"),
            ("edsger", "Edsger", "Dijkstra"),
            ("katherine", "Katherine", "Johnson"),
            ("margaret", "Margaret", "Hamilton"),
            ("radia", "Radia", "Perlman"),
        ]
        for username, first_name, last_name in roster:
            User.objects.create_user(
                username=username,
                password="x",
                first_name=first_name,
                last_name=last_name,
                email=f"{username}@example.com",
            )
        self.featured = User.objects.create_user(
            username="grace",
            password="x",
            first_name="Grace",
            last_name="Hopper",
            email="grace@example.com",
            is_staff=True,
        )
        self.featured.description = (
            "<p>Runs the compiler group. Ask her about <strong>nanoseconds</strong> "
            "— she carries the wire to prove the point.</p>"
            "<ul><li>COBOL steering committee</li>"
            "<li>prefers issues over hallway decisions</li></ul>"
        )
        self.featured.has_public_profile = True
        self.featured.last_login = timezone.now() - timedelta(hours=2)
        self.featured.save()

    def test_user_list(self) -> None:
        """/users/list renders the roster; the container card is captured."""
        self.page.goto(f"{self.live_server_url}/users/list")
        self.page.wait_for_selector(".users-table")
        self._shot("users", ".users-page")

    def test_user_detail(self) -> None:
        """The featured profile renders with the admin panel + rich text."""
        self.page.goto(f"{self.live_server_url}/users/id/{self.featured.public_id}")
        self.page.wait_for_selector(".user-details-attrs")
        self.page.wait_for_selector(".rich-text-display")
        self._shot("user-detail", ".user-details-page")


class CodeScreenshotTests(GitRepoMixin, BaseScreenshotTestCase):
    """Code-viewer shots: git uncommitted/commits/commit/diff + files (docs/screenshots/…).

    The git pages ride the shared ``GitRepoMixin`` fixture (real temp repos —
    main with 3 commits + uncommitted changes, a scratch sibling) exactly like
    the git e2e suite; ``/files`` browses the REAL repo tree (its root is the
    project parent, so ``main/…`` paths resolve both in main/ and in
    checkproject's scratch copy).

    - test_git_uncommitted, /git/uncommitted/ both worktrees' folder trees
    - test_git_commits, /git/commits the fixture's 3-commit list
    - test_git_commit, /git/commits/<short_b> the commit's changed-file list
    - test_git_diff, an uncommitted diff rendered side-by-side (diff2html)
    - test_files_browser, /files/main/ourapp directory listing + breadcrumb
    - test_file_viewer, /files/main/docs/social-providers.md rendered markdown
    """

    def setUp(self) -> None:
        super().setUp()  # auth only — the repo fixture is class-scoped
        self.admin = User.objects.create_user(
            username="codeadmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(self.admin)

    def test_git_uncommitted(self) -> None:
        """The uncommitted page's two worktree sections are captured."""
        self.page.goto(f"{self.live_server_url}/git/uncommitted/")
        self.page.get_by_role("link", name="app.py").wait_for(state="visible")
        self._shot_below_navbar("git-uncommitted")

    def test_git_commits(self) -> None:
        """The commit list's 3 fixture commits are captured."""
        self.page.goto(f"{self.live_server_url}/git/commits")
        self.page.get_by_role("link", name="Add create endpoint").wait_for(state="visible")
        self._shot_below_navbar("git-commits")

    def test_git_commit(self) -> None:
        """A commit page's changed-file list is captured."""
        self.page.goto(f"{self.live_server_url}/git/commits/{self.short_b}")
        self.page.get_by_role("link", name="endpoints.py").wait_for(state="visible")
        self._shot_below_navbar("git-commit")

    def test_git_diff(self) -> None:
        """An uncommitted diff renders add/del rows; the page is captured."""
        self.page.goto(f"{self.live_server_url}/git/uncommitted/main/TodoApp/app.py")
        self.page.wait_for_selector("[data-split-diff] .d2h-ins")
        self._shot_below_navbar("git-diff")

    def test_files_browser(self) -> None:
        """The file browser's listing + breadcrumb are captured."""
        self.page.goto(f"{self.live_server_url}/files/main/ourapp")
        self.page.get_by_role("link", name="urls.py").wait_for(state="visible")
        self._shot_below_navbar("files")

    def test_file_viewer(self) -> None:
        """The markdown viewer renders prose + outline; the page is captured."""
        self.page.goto(f"{self.live_server_url}/files/main/docs/social-providers.md")
        self.page.wait_for_selector('[data-files-state="rendered"]')
        self.page.wait_for_selector(".files-markdown")
        # Cropped to the top of the document: the viewer's page repeats the
        # markdown as rendered view + raw source, so the full clip (~3000px)
        # is too tall to embed — the outline + rendered prose are the point.
        self._shot_below_navbar("file-viewer", max_height=1600)


@skip_unless_env("RUN_PROJECT_TESTS")
class ModelScreenshotTests(BaseScreenshotTestCase):
    """Models-management shots (docs/screenshots/{models,model-rows,row-detail}.png).

    Only meaningful under the testapp overlay (``checkproject`` sets
    ``RUN_PROJECT_TESTS`` and replaces ``ourapp/`` with the test app's
    ``Author``/``Book`` models — plain ``main/`` has no models to show, so
    the class self-skips there). Rows are written via ``save_with_logs`` so
    the row-detail shot includes a real audit history; the featured book gets
    an update on top of its create so the history shows a diff.

    - test_models_list, /manage/models Author + Book with docstrings/counts
    - test_model_rows, /manage/models/Book/list FK cells and pagination
    - test_row_detail, /manage/models/Book/id/<pid> columns + audit history
    """

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(
            username="modeladmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(self.admin)
        # Like the project tests: resolve the overlaid models lazily (in
        # plain main/ this class is skipped before setUp ever runs). Locally
        # typed type[Any]: get_model returns type[Model], which would fail
        # the .objects/.save_with_logs accesses below.
        ourapp = apps.get_app_config("ourapp")
        author_model: type[Any] = ourapp.get_model("Author")
        book_model: type[Any] = ourapp.get_model("Book")
        authors = [
            author_model.objects.create(name=name, bio=bio, rating=rating, active=True)
            for name, bio, rating in [
                ("Ada Lovelace", "Mathematician, first programmer.", "4.50"),
                ("Grace Hopper", "Compiler pioneer.", "4.80"),
                ("Alan Turing", "Computability, Enigma.", "4.70"),
            ]
        ]
        titles = [
            ("Notes on the Analytical Engine", 340, 0),
            ("The Universal Machine", 412, 2),
            ("Programming the ENIAC", 268, 1),
            ("On Computable Numbers", 96, 2),
            ("Compilers and Beyond", 384, 1),
            ("Rear Admiral's Notes", 220, 1),
        ]
        featured = None
        for title, pages, author_ix in titles:
            book = book_model(
                title=title,
                description=f"{title} — reviewed copy.",
                pages=pages,
                published=timezone.now() - timedelta(days=30 * (author_ix + 1)),
                author=authors[author_ix],
                reviewer=self.admin,
            )
            book.save_with_logs(actor=self.admin)
            if featured is None:
                featured = book
        assert featured is not None
        featured.pages += 8
        featured.save_with_logs(actor=self.admin)
        self.featured_public_id = featured.public_id

    def test_models_list(self) -> None:
        """/manage/models lists the test app's models; the card is captured."""
        self.page.goto(f"{self.live_server_url}/manage/models")
        self.page.wait_for_selector(".manage-modellist-page")
        self._shot("models", ".manage-modellist-page")

    def test_model_rows(self) -> None:
        """The Book row list's columns + FK cells are captured."""
        self.page.goto(f"{self.live_server_url}/manage/models/Book/list")
        self.page.wait_for_selector(".manage-modelrows-page")
        self._shot("model-rows", ".manage-modelrows-page")

    def test_row_detail(self) -> None:
        """The featured book's detail renders (audit history loaded)."""
        self.page.goto(f"{self.live_server_url}/manage/models/Book/id/{self.featured_public_id}")
        self.page.wait_for_selector(".manage-rowdetail-page")
        # logs are a deferred Inertia prop landing via partial reload — wait
        # for a rendered entry so the history section isn't caught "Loading".
        self.page.wait_for_selector(".update-log-entry")
        self._shot("row-detail", ".manage-rowdetail-page")


@skipIf(
    os.getenv("RUN_PROJECT_TESTS"),
    "the testapp overlay (RUN_PROJECT_TESTS) replaces ourapp/ and its mockup route",
)
class MockupScreenshotTests(BaseScreenshotTestCase):
    """The mockup demo shots (docs/screenshots/{mockup-todos,todos-final}.png).

    Inverse gate of the models shots: /mockup-todos lives in main's ourapp/,
    which the checkproject overlay deletes (rsync --delete), so the shots run
    only in a plain-main pass.

    - test_mockup_todos, /mockup-todos static todo list under the crosshatch
    - test_todos_final, /mockup-todos?final renders the same page WITHOUT the
      crosshatch (the contrast shot for the README's mockup→final pair)
    - test_mockup_hidden_from_anonymous, an anonymous viewer gets 404
    """

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(
            username="mockupadmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(self.admin)

    def test_mockup_todos(self) -> None:
        """/mockup-todos renders the todo mockup; the card is captured."""
        self.page.goto(f"{self.live_server_url}/mockup-todos")
        self.page.wait_for_selector(".ours-mockup-todos.mockup")
        self._shot("mockup-todos", ".ours-mockup-todos")

    def test_todos_final(self) -> None:
        """/mockup-todos?final drops the crosshatch wrapper; captured as-is."""
        self.page.goto(f"{self.live_server_url}/mockup-todos?final=1")
        root = self.page.locator(".ours-mockup-todos")
        root.wait_for(state="visible")
        # The hatch rides the .mockup class (its ::before) — its absence is
        # the point of this variant.
        self.assertNotIn("mockup", (root.get_attribute("class") or "").split())
        self._shot("todos-final", ".ours-mockup-todos")

    def test_mockup_hidden_from_anonymous(self) -> None:
        """An anonymous viewer of the mockup route gets a 404 (the gate holds)."""
        with self.anon_page() as page:
            response = page.goto(f"{self.live_server_url}/mockup-todos")
            assert response is not None
            self.assertEqual(response.status, 404)
