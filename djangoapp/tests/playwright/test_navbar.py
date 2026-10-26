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
    - test_user_menu_logout_flow, the user menu's logout POSTs allauth and lands signed-out
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
        """Home is the first nav link (icon-only), before the superuser links."""
        page = self.page
        page.goto(f"{self.live_server_url}/")
        first = page.locator(".layout-navbar .nav-link").first
        expect(first).to_have_attribute("aria-label", "Home")
        expect(first).to_have_attribute("href", "/")

    def test_wide_viewport_shows_flat_links(self) -> None:
        """At desktop width Models and Users render flat; Code is a dropdown."""
        page = self.page
        self._set_viewport(1280, 800)
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-navbar")
        expect(page.get_by_role("link", name="Models", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Users", exact=True)).to_be_visible()
        code = page.locator(".layout-navbar summary", has_text="Code")
        expect(code).to_be_visible()
        code.click()
        expect(page.get_by_role("link", name="Uncommitted", exact=True)).to_be_visible()

    def test_narrow_viewport_collapses_links_to_menu(self) -> None:
        """Below the breakpoint the links fold into the Menu dropdown."""
        page = self.page
        self._set_viewport(375)
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-navmenu")
        expect(page.get_by_role("link", name="Models", exact=True)).to_have_count(0)
        page.click(".layout-navmenu summary")
        # 6 links: Models, the Code summary, Users + the three inside Code.
        expect(page.locator(".layout-navmenu-link")).to_have_count(6)
        page.click(".layout-navmenu-link >> nth=0")
        page.wait_for_url("**/manage/models")
        # A Code link inside the Menu collapses BOTH dropdowns on navigate.
        page.go_back()
        page.click(".layout-navmenu summary")
        page.locator("summary", has_text="Code").click()
        page.get_by_role("link", name="Uncommitted", exact=True).click()
        page.wait_for_url("**/git/uncommitted/")
        expect(page.get_by_role("link", name="Models", exact=True)).to_be_hidden()
        # The Code dropdown itself closed too (not just its parent Menu):
        # reopening the Menu shows Code collapsed — its links stay hidden.
        page.click(".layout-navmenu summary")
        expect(page.get_by_role("link", name="Models", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Uncommitted", exact=True)).to_be_hidden()

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

    def test_user_menu_logout_flow(self) -> None:
        """The user menu's Sign out POSTs allauth and lands signed-out.

        The suite's only click-through of the logout round trip: form POST
        with the CSRF token, allauth redirect to LOGOUT_REDIRECT_URL ("/"),
        signed-out home.
        """
        page = self.page
        page.goto(f"{self.live_server_url}/")
        page.wait_for_selector(".layout-user-menu")
        page.click(".layout-user-menu summary")
        page.wait_for_selector(".layout-user-menu .layout-menu-panel")
        page.click(".user-menu-logout")
        page.wait_for_url(f"{self.live_server_url}/")
        page.wait_for_selector(".home-status-signed-out")
        expect(page.locator(".layout-user-menu")).to_have_count(0)
