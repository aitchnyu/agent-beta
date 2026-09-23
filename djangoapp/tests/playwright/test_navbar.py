"""E2e for the app navbar: home link, responsive collapse, hide-on-scroll.

Layout.vue owns the navbar: a Home link, the superuser links (flat when
wide, folded into a native ``<details>`` Menu below 768px), the user badge
outside the collapse, and a sticky bar that slides away while scrolling
down and returns on any upward scroll.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from djangoapp.models import User
from djangoapp.tests.playwright._base import BasePlaywrightTestCase


class NavbarE2e(BasePlaywrightTestCase):
    """Navbar shape and scroll behaviour, end-to-end.

    - test_home_link_present, Home is the first nav link for a signed-in user
    - test_wide_viewport_shows_flat_links, at 1280px the superuser links render flat
    - test_narrow_viewport_collapses_links_to_menu, at 375px they fold into the Menu dropdown
    - test_user_badge_stays_outside_collapse, the badge button renders in narrow mode too
    - test_navbar_hides_on_scroll_down_and_returns, scrolling down hides the bar; up restores it
    """

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(
            username="navadmin", password="x", is_staff=True, is_superuser=True
        )
        self.login_as(self.admin)

    def _set_viewport(self, width: int, height: int = 800) -> None:
        """Set a non-default viewport; addCleanup restores it after the test.

        The suite shares ONE page for the whole process, so a leaked
        viewport would change every later module's layout — the restore
        runs even when the test fails.
        """
        default = self.page.viewport_size or {"width": 1280, "height": 720}
        self.page.set_viewport_size({"width": width, "height": height})
        self.addCleanup(self.page.set_viewport_size, default)

    def _goto_tall_page(self) -> None:
        """Open a page with guaranteed scroll room.

        The notifications list has no fixed height at every width, so the
        room is generated explicitly.
        """
        page = self.page
        page.goto(f"{self.live_server_url}/notifications")
        # The bar (HideOnScroll wrapper) is present on every page.
        page.wait_for_selector(".hide-on-scroll")
        # Deterministic scroll room, independent of seeded rows.
        page.evaluate("() => { document.body.style.minHeight = '3000px' }")

    def test_home_link_present(self) -> None:
        """Home is the first nav link, before the superuser links."""
        page = self.page
        page.goto(f"{self.live_server_url}/")
        first = page.locator(".layout-navbar .nav-link").first
        expect(first).to_have_text("Home")
        self.assertEqual(first.get_attribute("href"), "/")

    def test_wide_viewport_shows_flat_links(self) -> None:
        """At desktop width the superuser links render as flat nav links."""
        page = self.page
        self._set_viewport(1280, 800)
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-navbar")
        expect(page.get_by_role("link", name="Models", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Code", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Users", exact=True)).to_be_visible()
        expect(page.locator(".layout-navmenu")).to_have_count(0)

    def test_narrow_viewport_collapses_links_to_menu(self) -> None:
        """Below the breakpoint the links fold into the Menu dropdown."""
        page = self.page
        self._set_viewport(375)
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-navmenu")
        expect(page.get_by_role("link", name="Models", exact=True)).to_have_count(0)
        page.click(".layout-navmenu summary")
        expect(page.locator(".layout-navmenu-link")).to_have_count(3)
        page.click(".layout-navmenu-link >> nth=0")
        page.wait_for_url("**/manage/models")

    def test_user_badge_stays_outside_collapse(self) -> None:
        """The user badge button renders in narrow mode, outside the menu."""
        page = self.page
        self._set_viewport(375)
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-user-menu")
        expect(page.locator(".notifications-badge")).to_be_visible()

    def test_navbar_hides_on_scroll_down_and_returns(self) -> None:
        """Scrolling down hides the navbar; scrolling up brings it back."""
        page = self.page
        self._goto_tall_page()
        expect(page.locator(".layout-navbar")).to_be_visible()
        page.evaluate("() => window.scrollTo({ top: 800, behavior: 'instant' })")
        expect(page.locator(".layout-navbar")).to_have_class(re.compile(r"hide-on-scroll-hidden"))
        page.evaluate("() => window.scrollTo({ top: 400, behavior: 'instant' })")
        expect(page.locator(".layout-navbar")).not_to_have_class(
            re.compile(r"hide-on-scroll-hidden")
        )
