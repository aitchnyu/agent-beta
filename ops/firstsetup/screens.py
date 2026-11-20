"""screens — the setup app's screens: thin shells over flow.py's verbs.

Two self-contained form screens (UserScreen, GoogleScreen — each owns
its fields, validation, and its flow verb), two provider auth screens
(ApiKeyScreen: password field → store → verify; OAuthScreen: pi's own
device-code login, then the same verification), and LoginLinkScreen
(the copyable one-time login link). Panel holds the shared compact
chrome. Every command, rc nuance, and capture lives in flow.py; these
classes only map results to pop/flash/status.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from ops.firstsetup import authstore
from ops.firstsetup.flow import (
    Outcome,
    create_superuser_with_link,
    run_pi_oauth_login,
    store_google_oauth,
    verify_provider,
)

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from ops.firstsetup.app import SetupApp

# The pi credential store (debian's) — the ApiKeyScreen writes here.
CREDENTIAL_STORE = authstore.AuthStore("/home/debian/.pi/agent/auth.json")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_MAX = 254  # the RFC 5321 forward-path limit
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'-]{0,49}$")
CLIENT_ID_RE = re.compile(r"^\d+-[A-Za-z0-9]+\.apps\.googleusercontent\.com$")
MIN_SECRET_LEN = 20


def validate_user_values(values: dict[str, str]) -> str | None:
    """Return the first-user form's refusal, or None when well-formed."""
    email = values.get("email", "")
    first = values.get("first_name", "")
    last = values.get("last_name", "")
    if not email and not first and not last:
        return "fill all three fields (or press Back to skip)"
    if not EMAIL_RE.match(email) or len(email) > EMAIL_MAX:
        return "that email doesn't parse"
    if not (first and last):
        return "first + last name needed with an email"
    if not NAME_RE.match(first):
        return "first name: letters only (hyphen/apostrophe ok), starting with one"
    if not NAME_RE.match(last):
        return "last name: letters only (hyphen/apostrophe ok), starting with one"
    return None


def validate_google_values(values: dict[str, str]) -> str | None:
    """Return the google form's refusal, or None when well-formed."""
    client_id = values.get("client_id", "")
    secret = values.get("client_secret", "")
    if not client_id and not secret:
        return "fill both client key and secret (or press Back to skip)"
    if bool(client_id) != bool(secret):
        return "fill BOTH client key and secret"
    if not CLIENT_ID_RE.match(client_id):
        return "client key should look like 1234567890-abc123.apps.googleusercontent.com"
    if len(secret) < MIN_SECRET_LEN or " " in secret:
        return "client secret looks wrong (Google secrets are ~35 chars, no spaces)"
    return None


def _setup_app(screen: Screen[None]) -> SetupApp:
    """Return the enclosing app, typed.

    No runtime import — screens and app are mutually recursive at
    import time; the object is always a SetupApp.
    """
    return screen.app  # type: ignore[return-value]


class StrippedInput(Input):
    """An input that never carries whitespace — typed spaces vanish."""

    def watch_value(self, value: str) -> None:
        cleaned = value.replace(" ", "").replace("\t", "")
        if cleaned != value:
            self.value = cleaned


def field_row(
    label: str, input_id: str, *, password: bool = False, placeholder: str = ""
) -> Horizontal:
    """One line: label left, input right — the whole form stays short."""
    return Horizontal(
        Label(f"{label}:", classes="flabel"),
        StrippedInput(id=input_id, password=password, placeholder=placeholder or ""),
        classes="frow",
    )


class Panel(Screen[None]):
    """Shared compact chrome: label/input lines + one action row.

    Inputs are single-line (height 1, no border) — the whole form fits a
    cramped terminal with no scrollbars.
    """

    DEFAULT_CSS = """
    Panel { align: center middle; }
    #panel { width: 100%; max-width: 64; height: auto; border: round $primary;
             padding: 0 1; }
    #panel Label.h { margin: 0 0 1 0; }
    .frow { height: 1; margin: 0 0 1 0; }
    .flabel { width: 13; height: 1; padding: 0; }
    .frow Input { width: 1fr; height: 1; border: none; padding: 0; }
    #actions { height: 1; margin-top: 1; align-horizontal: right; }
    #actions Button { margin-left: 1; }
    """
    title = "panel"

    def body(self) -> ComposeResult:
        raise NotImplementedError

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="panel"):
            yield Label(f"[b]{self.title}[/b]", classes="h")
            yield from self.body()
        yield Footer()

    @on(Button.Pressed, "#back")
    def _back(self) -> None:
        _setup_app(self).pop_screen()

    def _values(self, *input_ids: str) -> dict[str, str]:
        """Return the named inputs' values, whitespace-stripped."""
        return {
            input_id: self.query_one(f"#{input_id}", Input).value.strip() for input_id in input_ids
        }


class UserScreen(Panel):
    """The first-user form: create the superuser, mint the login link."""

    title = "first user"

    def body(self) -> ComposeResult:
        yield field_row("first name", "first_name")
        yield field_row("last name", "last_name")
        yield field_row("email", "email", placeholder="you@example.com")
        with Horizontal(id="actions"):
            yield Button("Apply", id="apply", compact=True)
            yield Button("Back", id="back", compact=True)

    @on(Button.Pressed, "#apply")
    def _apply(self) -> None:
        app = _setup_app(self)
        values = self._values("first_name", "last_name", "email")
        error = validate_user_values(values)
        if error:
            app.flash(error)
            return
        self.run_worker(self._create(values), exclusive=True)

    async def _create(self, values: dict[str, str]) -> None:
        app = _setup_app(self)
        try:
            result = await create_superuser_with_link(
                values["first_name"], values["last_name"], values["email"]
            )
            app.record_first_user(
                first_name=values["first_name"],
                last_name=values["last_name"],
                email=values["email"],
                login_link=result.login_link,
            )
            app.flash("user created — the login link is on the menu")
            app.pop_screen()
        except Exception as error:  # noqa: BLE001 — a worker failure must not crash the app
            app.flash(f"user failed: {error}"[:80])


class GoogleScreen(Panel):
    """The google oauth form: store the client key and secret."""

    title = "google oauth"

    def body(self) -> ComposeResult:
        yield field_row("client key", "client_id", placeholder="xxxx.apps.googleusercontent.com")
        yield field_row("secret", "client_secret", password=True)
        with Horizontal(id="actions"):
            yield Button("Apply", id="apply", compact=True)
            yield Button("Back", id="back", compact=True)

    @on(Button.Pressed, "#apply")
    def _apply(self) -> None:
        app = _setup_app(self)
        values = self._values("client_id", "client_secret")
        error = validate_google_values(values)
        if error:
            app.flash(error)
            return
        self.run_worker(self._store(values), exclusive=True)

    async def _store(self, values: dict[str, str]) -> None:
        app = _setup_app(self)
        try:
            await store_google_oauth(values["client_id"], values["client_secret"])
            app.record_google_configured()
            app.flash("google oauth stored")
            app.pop_screen()
        except Exception as error:  # noqa: BLE001 — a worker failure must not crash the app
            app.flash(f"google failed: {error}"[:80])


class _ProviderAuthScreen(Panel):
    """Shared chrome for provider auth screens: panel + status + log."""

    DEFAULT_CSS = """
    #panel Button { width: 100%; margin: 0 0 1 0; }
    #status { height: auto; margin: 1 0 0 0; }
    #status.ok { color: $success; }
    #status.err { color: $error; }
    #log { height: 6; }
    """

    def __init__(self, provider: dict[str, object]) -> None:
        super().__init__()
        self.provider_id = str(provider.get("id", ""))
        self.title = str(provider.get("name") or provider.get("id") or "provider")

    def _set_status(self, text: str, *, state: str = "") -> None:
        """Write the status line (and log it); state styles it ok/err."""
        status = self.query_one("#status", Static)
        status.update(text)
        if state:
            status.set_classes(state)
        self.query_one("#log", RichLog).write(text)

    def _report_result(self, outcome: Outcome) -> None:
        """Report the shared success/error path both screens end with."""
        app = _setup_app(self)
        if outcome.is_ok:
            app.mark_provider_verified(self.provider_id)
            self._set_status(f"Provider successful: {self.title}", state="ok")
            app.flash(f"Provider successful: {self.title}")
        else:
            self._set_status(f"verification failed — {outcome.error}", state="err")
            app.flash(f"verification failed: {outcome.error[:60]}")
        # No menu refresh here: the menu's rows follow the app's
        # reactives, so mark_provider_verified re-renders them.


class ApiKeyScreen(_ProviderAuthScreen):
    """API-key provider auth: password field → store → verify with a prompt.

    The credential is written directly to pi's store (merge-preserving),
    then a one-turn ``pi --print`` exercises the real credential —
    401/403 surfaces as a readable error for retry.
    """

    def body(self) -> ComposeResult:
        yield Button("Back", id="back", compact=True)
        yield field_row("api key", "api_key", password=True, placeholder="paste key")
        yield Button("Save & Verify", id="save")
        yield Static("", id="status")
        yield RichLog(id="log")

    @on(Button.Pressed, "#save")
    def _save_key(self) -> None:
        api_key = self.query_one("#api_key", Input).value.strip()
        if not api_key:
            _setup_app(self).flash("paste the api key first")
            return
        self.run_worker(self._save_and_verify(api_key), exclusive=True)

    async def _save_and_verify(self, api_key: str) -> None:
        app = _setup_app(self)
        try:
            self._set_status("saving…")
            credential: dict[str, object] = {"type": "api_key", "key": api_key}
            await CREDENTIAL_STORE.set_credential(self.provider_id, credential)
            self._set_status("saved — verifying with a model call…")
            self._report_result(await verify_provider(self.provider_id))
        except Exception as error:  # noqa: BLE001
            self._set_status(f"error: {error}", state="err")
            app.flash(f"error: {error}"[:80])


class OAuthScreen(_ProviderAuthScreen):
    """OAuth provider auth: pi's own login dance, then verify with a prompt.

    ``pi auth login <provider> --no-browser`` runs pi's device-code flow
    fullscreen (suspend) — the operator opens the URL on their laptop,
    enters the code, and pi stores the credential. On return, a
    one-turn ``pi --print`` verifies the credential actually works.
    """

    def body(self) -> ComposeResult:
        yield Button("Back", id="back", compact=True)
        yield Button(f"login {self.provider_id} (device code)", id="login")
        yield Static("", id="status")
        yield RichLog(id="log")

    @on(Button.Pressed, "#login")
    def _start_login(self) -> None:
        self.run_worker(self._login_and_verify(), exclusive=True)

    async def _login_and_verify(self) -> None:
        app = _setup_app(self)
        try:
            self._set_status("opening pi login…")
            with self.app.suspend():
                # stdout/stdin stay on the terminal: pi's device-code UI
                # owns the screen while suspended.
                result: Outcome = await run_pi_oauth_login(self.provider_id)
            if not result.is_ok:
                self._set_status(f"{result.error} — retry or Back", state="err")
                app.flash("login cancelled or failed")
                return
            self._set_status("login done — verifying with a model call…")
            self._report_result(await verify_provider(self.provider_id))
        except Exception as error:  # noqa: BLE001
            self._set_status(f"error: {error}", state="err")
            app.flash(f"error: {error}"[:80])


class LoginLinkScreen(Panel):
    """The one-time login link (24h): copyable text + a copy button."""

    DEFAULT_CSS = """
    #panel { border: round $success; max-width: 72; }
    #link-line { margin: 1 0 0 0; color: $success; }
    #hint { margin: 1 0 0 0; }
    """

    title = "login link"

    def body(self) -> ComposeResult:
        app = _setup_app(self)
        yield Label(app.first_user.login_link or "(no link issued)", id="link-line")
        yield Label("single use, 24 hours — open it in a browser to sign in.", id="hint")
        with Horizontal(id="actions"):
            yield Button("Copy link", id="copy", compact=True)
            yield Button("Back", id="back", compact=True)

    @on(Button.Pressed, "#copy")
    def _copy_link(self) -> None:
        """Copy the link to the terminal's clipboard."""
        app = _setup_app(self)
        if app.first_user.login_link:
            self.app.copy_to_clipboard(app.first_user.login_link)
            app.flash("link copied to clipboard")
