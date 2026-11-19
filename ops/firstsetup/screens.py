"""screens — the setup app's screens.

ONE generic FormScreen driven by a FormSpec (forms.py), two provider
auth screens — ApiKeyScreen (password field → store → real model call
to verify) and OAuthScreen (pi's own device-code login fullscreen, then
the same verification) — and LoginLinkScreen (the copyable one-time
login link). Panel holds the shared compact chrome.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from ops.firstsetup import authstore, forms

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from ops.firstsetup.app import SetupApp

# The pi credential store (debian's) — the ApiKeyScreen writes here.
CREDENTIAL_STORE = authstore.AuthStore("/home/debian/.pi/agent/auth.json")

VERIFY_PROMPT = "Reply with just: ok"
MAX_ERROR_CHARS = 120
MIN_TABLE_COLUMNS = 2  # provider + model
# pi's provider-side error bodies look like: 401: {"code":"401", ...}
# (and exit 0) — the body shape must fail the verify even on rc=0.
ERROR_REPLY_RE = re.compile(r"^\d{3}:\s*\{")


def _setup_app(screen: Screen[None]) -> SetupApp:
    """Return the enclosing app, typed.

    No runtime import — screens and app are mutually recursive at
    import time; the object is always a SetupApp.
    """
    return screen.app  # type: ignore[return-value]


def describe_failure(argv: tuple[str, ...], exit_code: int, output: str) -> str:
    """One clear line for a failed command — its own last error line.

    Never just "failed": the operator needs the command's own message
    (a traceback, a psql error, a missing binary).
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = lines[-1][:MAX_ERROR_CHARS] if lines else "no output"
    return f"{argv[2]} failed (rc={exit_code}): {detail}"


async def run_command(*argv: str, stdin: bytes | None = None) -> tuple[int, str]:
    """Run argv and capture stdout+stderr merged: (returncode, text).

    Streams are merged because some pi messages (the provider list in
    the unknown-provider error) arrive on stderr.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _err = await proc.communicate(stdin if stdin is not None else b"")
    return proc.returncode or 0, out.decode(errors="replace")


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


class FormScreen(Panel):
    """THE form engine: renders any FormSpec, validates it, dispatches."""

    def __init__(self, spec: forms.FormSpec) -> None:
        super().__init__()
        self.spec = spec
        self.title = spec.title

    def body(self) -> ComposeResult:
        for spec_field in self.spec.fields:
            yield field_row(
                spec_field.label,
                spec_field.id,
                password=spec_field.password,
                placeholder=spec_field.placeholder,
            )
        with Horizontal(id="actions"):
            yield Button(self.spec.apply_label, id="apply", compact=True)
            yield Button("Back", id="back", compact=True)

    @on(Button.Pressed, "#apply")
    def _apply(self) -> None:
        app = _setup_app(self)
        values = {
            field.id: self.query_one(f"#{field.id}", Input).value.strip()
            for field in self.spec.fields
        }
        if self.spec.optional and not any(values.values()):
            app.pop_screen()  # skip: nothing filled
            return
        if self.spec.validate is not None:
            error = self.spec.validate(values)
            if error:
                app.flash(error)
                return
        self.run_worker(self._dispatch_actions(values), exclusive=True)

    async def _dispatch_actions(self, values: forms.Values) -> None:
        """Run the spec's actions in order; any failure toasts and stops."""
        app = _setup_app(self)
        captured = ""
        try:
            for action in self.spec.actions:
                argv = action.argv(values)
                exit_code, output = await run_command(
                    *argv,
                )
                if exit_code != 0:
                    app.flash(describe_failure(argv, exit_code, output))
                    return
                if action.capture:
                    lines = [ln for ln in output.splitlines() if action.capture in ln]
                    if lines:
                        captured = lines[-1]
            self.spec.success(app, values, captured)
            app.pop_screen()
        except Exception as error:  # noqa: BLE001 — a worker failure must not crash the app
            app.flash(f"{self.spec.id} failed: {error}"[:80])


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

    async def verify_credential(self) -> tuple[bool, str]:
        """Run a cheap model call — the only real credential test.

        ``pi auth check`` reports storage, not validity (a fake API key
        is "ready"); a one-turn ``--print`` exercises the credential.
        """
        _exit_code, models_table = await run_command(
            "sudo",
            "-u",
            "debian",
            "-H",
            "pi",
            "--list-models",
        )
        model_id = self._first_model_id(models_table)
        if not model_id:
            return False, f"no models listed for provider {self.provider_id}"
        exit_code, output = await run_command(
            "sudo",
            "-u",
            "debian",
            "-H",
            "pi",
            "--print",
            VERIFY_PROMPT,
            "--provider",
            self.provider_id,
            "--model",
            model_id,
        )
        reply = output.strip()
        # pi exits 0 even for provider-side errors (e.g. an unknown model
        # or a 401 body), so the body shape is the verdict too.
        if exit_code == 0 and reply and not ERROR_REPLY_RE.match(reply):
            return True, reply
        return False, reply[:MAX_ERROR_CHARS] or f"pi exited rc={exit_code}"

    def _first_model_id(self, models_table: str) -> str:
        """Extract THIS provider's first model from the list-models table."""
        for line in models_table.splitlines():
            columns = line.split()
            if len(columns) >= MIN_TABLE_COLUMNS and columns[0] == self.provider_id:
                return columns[1]
        return ""

    def _report_result(self, *, verified: bool, detail: str) -> None:
        """Report the shared success/error path both screens end with."""
        app = _setup_app(self)
        if verified:
            app.mark_provider_verified(self.provider_id)
            self._set_status(f"Provider successful: {self.title}", state="ok")
            app.flash(f"Provider successful: {self.title}")
        else:
            self._set_status(f"verification failed — {detail}", state="err")
            app.flash(f"verification failed: {detail[:60]}")
        self._refresh_menu()

    def _refresh_menu(self) -> None:
        from ops.firstsetup.app import Menu  # noqa: PLC0415 — breaks the app↔screens cycle

        screen = self.app.screen
        if isinstance(screen, Menu):
            screen.statuses()


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
            await CREDENTIAL_STORE.set_credential(
                self.provider_id, {"type": "api_key", "key": api_key}
            )
            self._set_status("saved — verifying with a model call…")
            verified, detail = await self.verify_credential()
            self._report_result(verified=verified, detail=detail)
        except Exception as error:  # noqa: BLE001
            self._set_status(f"error: {error}", state="err")
            app.flash(f"error: {error}"[:80])
            self._refresh_menu()


class OAuthScreen(_ProviderAuthScreen):
    """OAuth provider auth: pi's own login dance, then verify with a prompt.

    ``pi auth login <provider> --no-browser`` runs pi's device-code
    flow fullscreen (suspend) — the operator opens the URL on their
    laptop, enters the code, and pi stores the credential. On return,
    a one-turn ``pi --print`` verifies the credential actually works.
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
                # owns the screen while suspended. stderr is captured so
                # a failure surfaces pi's own message, not just an rc.
                proc = await asyncio.create_subprocess_exec(
                    "sudo",
                    "-u",
                    "debian",
                    "-H",
                    "pi",
                    "auth",
                    "login",
                    self.provider_id,
                    "--no-browser",
                    stderr=asyncio.subprocess.PIPE,
                )
                _out, err = await proc.communicate()
            if proc.returncode != 0:
                detail = describe_failure(
                    ("pi", "auth", "login"),
                    proc.returncode or 0,
                    (err or b"").decode(errors="replace"),
                )
                self._set_status(f"{detail} — retry or Back", state="err")
                app.flash("login cancelled or failed")
                return
            self._set_status("login done — verifying with a model call…")
            verified, detail = await self.verify_credential()
            self._report_result(verified=verified, detail=detail)
        except Exception as error:  # noqa: BLE001
            self._set_status(f"error: {error}", state="err")
            app.flash(f"error: {error}"[:80])
            self._refresh_menu()


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
