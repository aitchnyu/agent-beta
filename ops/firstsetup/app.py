"""app — the SetupApp app and its Menu: the composition root.

The menu shows two-state rows: actionable (incomplete, clickable) or
complete (green). Completed google/provider rows lock (no reconfigure);
the completed Superuser row stays clickable to open its login link.
The provider dropdown dispatches to the right screen (ApiKeyScreen or
OAuthScreen) based on pi's own registry.

All menu state lives on the app behind small methods (record_*, mark_*,
provider_by_id, …) — screens and forms never poke bare attributes, so
the data flow has exactly one owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
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


class Menu(Screen[None]):
    """The setup menu — arrows navigate, Enter delves; statuses refresh."""

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
            yield Button("", id="user", compact=True)
            yield Button("", id="google", compact=True)
            yield Select(
                [], id="provider-select", prompt="configure ai provider…", allow_blank=True
            )
            yield Static("", id="ai-done")
            yield Static("", id="link")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load_provider_catalog(), exclusive=True)
        self.statuses()

    def on_screen_resume(self) -> None:
        # Clear the dropdown so picking the SAME provider again re-opens
        # its config (a left-over selection wouldn't fire Changed).
        self.query_one("#provider-select", Select).clear()
        self.statuses()

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
        self._populate_select_options()

    def _populate_select_options(self) -> None:
        """One option per provider: 'name (id)' → provider id."""
        app = _setup_app(self)
        select = self.query_one("#provider-select", Select)
        options = [
            (
                f"{provider.get('name') or provider.get('id')!s}  ({provider.get('id')!s})",
                str(provider.get("id")),
            )
            for provider in app.providers
        ]
        select.set_options(options)

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
        if _setup_app(self).is_google_configured:
            return  # locked
        _setup_app(self).push_screen(FormScreen(forms.GOOGLE))

    def statuses(self) -> None:
        """Refresh every row from the app's state (UI reads, never writes)."""
        app = _setup_app(self)

        user_button = self.query_one("#user", Button)
        if app.first_user.is_configured:
            user_button.label = f"\u2713 Superuser: {app.first_user.full_name}"
            user_button.add_class("done")
            user_button.disabled = False  # clickable: opens the login link
        else:
            user_button.label = "user    (unconfigured)"
            user_button.remove_class("done")
            user_button.disabled = False

        google_button = self.query_one("#google", Button)
        if app.is_google_configured:
            google_button.label = "\u2713 Google OAuth: configured"
            google_button.add_class("done")
            google_button.disabled = True
        else:
            google_button.label = "google  (unconfigured)"
            google_button.remove_class("done")
            google_button.disabled = False

        verified_names = ", ".join(app.verified_provider_ids())
        self.query_one("#ai-done", Static).update(
            f"\u2713 Provider successful: {verified_names}" if verified_names else ""
        )

        link = app.first_user.login_link
        self.query_one("#link", Static).update(f"login link (24h): {link}" if link else "")


class SetupApp(App[None]):
    """The first-run setup menu app; the screen stack is the navigation."""

    TITLE = "desmo setup"
    THEME = "textual-light"
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+q", "quit", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.first_user = FirstUserSetup()
        self.is_google_configured = False
        self.verified_providers: dict[str, bool] = {}
        self.providers: list[dict[str, object]] = []
        self.provider_auth_kinds: dict[str, str] = {}

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
        self.is_google_configured = True

    def mark_provider_verified(self, provider_id: str) -> None:
        """Mark one ai provider as authenticated and verified."""
        self.verified_providers[provider_id] = True

    def is_provider_verified(self, provider_id: str) -> bool:
        """Return True once a provider's credential passed its model-call check."""
        return self.verified_providers.get(provider_id, False)

    def verified_provider_ids(self) -> list[str]:
        """Return the verified provider ids, sorted for display."""
        return sorted(pid for pid, is_verified in self.verified_providers.items() if is_verified)

    def load_provider_catalog(
        self, provider_list: list[dict[str, object]], auth_kinds: dict[str, str]
    ) -> None:
        """Store the live provider list and its auth-kind registry."""
        self.providers = provider_list
        self.provider_auth_kinds = auth_kinds

    def provider_by_id(self, provider_id: str) -> dict[str, object] | None:
        """Return the provider row from the loaded catalog, or None."""
        return next((p for p in self.providers if str(p.get("id")) == provider_id), None)

    def provider_auth_kind(self, provider_id: str) -> str:
        """Return the provider's auth kind, defaulting to api_key."""
        return providers.auth_kind_of(provider_id, self.provider_auth_kinds)

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
