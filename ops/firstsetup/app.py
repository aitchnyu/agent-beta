"""app — the SetupApp app and its Menu: the composition root.

The menu shows two-state rows: actionable (incomplete, clickable) or
complete (green). Completed google/provider rows lock (no reconfigure);
the completed Superuser row stays clickable to open its login link.
The provider dropdown dispatches to the right screen (ApiKeyScreen or
OAuthScreen) based on pi's own registry.

All menu state lives on the app as reactives behind small methods
(record_*, mark_*, load_*). Each row is a widget that follows the app
reactive it renders — assignment on the app IS the UI update, so no
screen ever queries or refreshes another (statuses() is gone). Rows
follow via ``watch`` rather than ``data_bind`` because data_bind binds
to the active message pump — from a screen's compose that is the
screen, not the app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Select, Static

from ops.command import Command
from ops.firstsetup import forms, providers
from ops.firstsetup.screens import (
    ApiKeyScreen,
    FormScreen,
    LoginLinkScreen,
    OAuthScreen,
    _setup_app,
)

if TYPE_CHECKING:
    from textual.widget import Widget


@dataclass
class FirstUserSetup:
    """The first superuser the wizard created, plus its login link."""

    first_name: str = ""
    last_name: str = ""
    email: str = ""
    login_link: str = ""

    @property
    def is_configured(self) -> bool:
        """True once a user was created (the email is the marker)."""
        return bool(self.email)

    @property
    def full_name(self) -> str:
        """The display name for the completed Superuser row."""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class ProviderCatalog:
    """The live provider list plus its auth-kind registry, as one value."""

    providers: tuple[dict[str, object], ...] = ()
    auth_kinds: dict[str, str] = field(default_factory=dict)


def follow_app_reactive(widget: Widget, name: str) -> None:
    """Make one of the widget's reactives follow the app reactive of the same name.

    The current value syncs immediately, and every later assignment on
    the app re-renders the follower — the declarative replacement for
    query_one-and-refresh. (``data_bind`` can't do this: from a screen's
    compose it may only bind to the screen, its active message pump.)
    """
    widget.watch(widget.app, name, lambda value: setattr(widget, name, value))


class UserRow(Button):
    """The Superuser row: renders itself from the app's first user.

    Complete → green with the full name, still clickable (opens the
    login-link screen); unconfigured → actionable.
    """

    # init=True (reactive()'s default, kept explicit): the first set of
    # a reactive fires its watcher even on an equal value — the
    # mount-time app sync is that first set, painting the row.
    first_user: reactive[FirstUserSetup] = reactive(FirstUserSetup(), init=True)

    def watch_first_user(self, user: FirstUserSetup) -> None:
        if user.is_configured:
            self.label = f"\u2713 Superuser: {user.full_name}"
        else:
            self.label = "user    (unconfigured)"
        self.set_class(user.is_configured, "done")

    def on_mount(self) -> None:
        follow_app_reactive(self, "first_user")


class GoogleRow(Button):
    """The google row: locks (disabled, green) once configured."""

    google_configured: reactive[bool] = reactive(default=False, init=True)

    def watch_google_configured(
        self,
        configured: bool,  # noqa: FBT001 — textual's watcher protocol fixes this signature
    ) -> None:
        self.label = "\u2713 Google OAuth: configured" if configured else "google  (unconfigured)"
        self.set_class(configured, "done")
        self.disabled = configured  # locked — no reconfigure

    def on_mount(self) -> None:
        follow_app_reactive(self, "google_configured")


class VerifiedSummary(Static):
    """The green 'providers verified' line (empty until one is)."""

    verified: reactive[frozenset[str]] = reactive(frozenset[str]())

    def watch_verified(self, verified: frozenset[str]) -> None:
        names = ", ".join(sorted(verified))
        self.update(f"\u2713 Provider successful: {names}" if names else "")

    def on_mount(self) -> None:
        follow_app_reactive(self, "verified")


class LoginLinkLine(Static):
    """The one-line login link, shown once a superuser exists."""

    first_user: reactive[FirstUserSetup] = reactive(FirstUserSetup())

    def watch_first_user(self, user: FirstUserSetup) -> None:
        link = user.login_link
        self.update(f"login link (24h): {link}" if link else "")

    def on_mount(self) -> None:
        follow_app_reactive(self, "first_user")


class ProviderSelect(Select[str]):
    """The provider dropdown: its options ARE the app's catalog."""

    catalog: reactive[ProviderCatalog] = reactive(ProviderCatalog())

    def watch_catalog(self, catalog: ProviderCatalog) -> None:
        self.set_options(
            (
                f"{provider.get('name') or provider.get('id')!s}  ({provider.get('id')!s})",
                str(provider.get("id")),
            )
            for provider in catalog.providers
        )

    def on_mount(self) -> None:
        follow_app_reactive(self, "catalog")


class Menu(Screen[None]):
    """The setup menu — arrows navigate, Enter delves; rows render from app state."""

    DEFAULT_CSS = """
    Menu { align: center middle; }
    #panel { width: 100%; max-width: 64; height: auto; border: round $primary;
             padding: 0 1; }
    #panel Button { width: 100%; margin: 0 0 1 0; }
    Select { width: 100%; margin: 0 0 1 0; }
    #ai-done { margin: 0 0 1 0; color: $success; }
    #link { margin: 1 0 0 0; }
    .done { color: $success; }
    """
    title = "desmo setup"

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("down", "app.focus_next", "next", show=False),
        Binding("up", "app.focus_previous", "prev", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="panel"):
            yield UserRow("", id="user", compact=True)
            yield GoogleRow("", id="google", compact=True)
            yield ProviderSelect(
                [], id="provider-select", prompt="configure ai provider…", allow_blank=True
            )
            yield VerifiedSummary("", id="ai-done")
            yield LoginLinkLine("", id="link")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load_provider_catalog(), exclusive=True)

    def on_screen_resume(self) -> None:
        # Clear the dropdown so picking the SAME provider again re-opens
        # its config (a left-over selection wouldn't fire Changed).
        self.query_one("#provider-select", ProviderSelect).clear()

    async def _load_provider_catalog(self) -> None:
        """Load providers + auth kinds into the app; surface failures."""
        app = _setup_app(self)
        try:
            provider_list = await providers.list_providers()
        except (RuntimeError, ValueError) as error:
            provider_list = []
            app.flash(f"providers unavailable — {error}"[:80])
        try:
            auth_kinds = await providers.query_auth_kinds()
        except (RuntimeError, ValueError) as error:
            # Not swallowed: without kinds the OAuth screens are
            # unreachable, so say so and keep the api-key default.
            auth_kinds = {}
            app.flash(f"auth kinds unavailable — {error}"[:80])
        app.load_provider_catalog(provider_list, auth_kinds)

    def open_provider(self, provider_id: str) -> None:
        """Dispatch to the right screen by the provider's auth kind."""
        app = _setup_app(self)
        provider = app.provider_by_id(provider_id)
        if provider is None or app.is_provider_verified(provider_id):
            return  # unknown, or locked — no reconfigure
        if app.provider_auth_kind(provider_id) == "oauth":
            app.push_screen(OAuthScreen(provider))
        else:
            app.push_screen(ApiKeyScreen(provider))

    @on(Select.Changed, "#provider-select")
    def _provider_chosen(self, event: Select.Changed) -> None:
        # Select.NULL (not the long-removed Select.BLANK, and never
        # None) is the blank/cleared state — nothing was chosen.
        if event.value is Select.NULL:
            return
        self.open_provider(str(event.value))

    @on(Button.Pressed, "#user")
    def _open_user_form(self) -> None:
        app = _setup_app(self)
        if app.first_user.is_configured:
            # Completed: clicking the green Superuser row opens the
            # login-link screen (the link is copyable there).
            app.push_screen(LoginLinkScreen())
            return
        app.push_screen(FormScreen(forms.USER))

    @on(Button.Pressed, "#google")
    def _open_google_form(self) -> None:
        if _setup_app(self).google_configured:
            return  # locked
        _setup_app(self).push_screen(FormScreen(forms.GOOGLE))


class SetupApp(App[None]):
    """The first-run setup menu app; the screen stack is the navigation.

    Menu state lives in reactives — the menu's rows follow them, so an
    assignment through the setters below re-renders every row by itself.
    """

    TITLE = "desmo setup"
    THEME = "textual-light"
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+q", "quit", "quit"),
    ]

    first_user: reactive[FirstUserSetup] = reactive(FirstUserSetup())
    google_configured: reactive[bool] = reactive(default=False)
    verified: reactive[frozenset[str]] = reactive(frozenset[str]())
    catalog: reactive[ProviderCatalog] = reactive(ProviderCatalog())

    # ── state setters/readers — the only mutation surface ────────────────

    def record_first_user(
        self, *, first_name: str, last_name: str, email: str, login_link: str
    ) -> None:
        """Store the created superuser and its one-time login link."""
        self.first_user = FirstUserSetup(
            first_name=first_name,
            last_name=last_name,
            email=email,
            login_link=login_link,
        )

    def record_google_configured(self) -> None:
        """Mark the Google OAuth client credentials as stored."""
        self.google_configured = True

    def mark_provider_verified(self, provider_id: str) -> None:
        """Mark one ai provider as authenticated and verified."""
        self.verified = self.verified | frozenset({provider_id})

    def is_provider_verified(self, provider_id: str) -> bool:
        """Return True once a provider's credential passed its model-call check."""
        return provider_id in self.verified

    def verified_provider_ids(self) -> list[str]:
        """Return the verified provider ids, sorted for display."""
        return sorted(self.verified)

    def load_provider_catalog(
        self, provider_list: list[dict[str, object]], auth_kinds: dict[str, str]
    ) -> None:
        """Store the live provider list and its auth-kind registry."""
        self.catalog = ProviderCatalog(providers=tuple(provider_list), auth_kinds=auth_kinds)

    def provider_by_id(self, provider_id: str) -> dict[str, object] | None:
        """Return the provider row from the loaded catalog, or None."""
        return next((p for p in self.catalog.providers if str(p.get("id")) == provider_id), None)

    def provider_auth_kind(self, provider_id: str) -> str:
        """Return the provider's auth kind, defaulting to api_key."""
        return providers.auth_kind_of(provider_id, self.catalog.auth_kinds)

    def on_mount(self) -> None:
        self.push_screen(Menu())

    def flash(self, message: str) -> None:
        self.notify(message, severity="warning", timeout=10)


class SetupCommand(Command):
    """The first-run setup menu (user, google oauth, ai providers)."""

    name = "firstsetup"

    @staticmethod
    def run(_args: object, _extra: list[str]) -> None:
        SetupApp().run()
