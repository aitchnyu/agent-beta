"""setup_app — ``desmosetup``'s one screen: pi's provider.

The screen collects one choice: pi's provider and, for a provider that
takes a key, the key. The site's origin, the first superuser and Google
came on the installer's command line (ops/setup.py); every step runs on
the terminal once the screen is gone. The first run is the only run:
nothing here looks for what the machine already holds, and no key leaves
the screen — Next is the only way out.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import ClassVar, cast

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalGroup
from textual.screen import Screen
from textual.widgets import Button, Header, Input, Label, Select, Static

from ops import piauth

PROVIDER_PROMPT = "choose a provider…"
READY_HINT = "Fill the fields, then press Next"
SIGN_IN_HINT = "pi's sign-in for {provider} starts after Next"
API_KEY_HINT = "paste the provider's API key"
# Every field, with the label its message names. The input is read by
# id; ``<id>-msg`` is the line under it.
LABELS: dict[str, str] = {"provider": "Pi provider", "api_key": "API key"}
MESSAGE_IDS = ("provider", "api_key")


@dataclass(frozen=True, kw_only=True)
class Answers:
    """The screen's fields as they were typed."""

    provider: str
    api_key: str


@dataclass(frozen=True, kw_only=True)
class PiChoice:
    """What the screen hands to the terminal steps: the provider and the key typed for it."""

    provider: piauth.Provider
    api_key: str


def setup_app(screen: Screen[None]) -> SetupApp:
    """Return the app a screen belongs to, typed.

    Screens and app are mutually recursive at import time, so the class
    is only named here; at runtime the object is always a SetupApp.
    """
    return cast("SetupApp", screen.app)


def validate(answers: Answers, provider: piauth.Provider | None) -> list[tuple[str, str]]:
    """Return every refusal as (field id, message), in screen order; [] when all can go on.

    The provider is required, and a provider that takes a key needs the
    key.
    """
    if provider is None:
        return [("provider", PROVIDER_PROMPT)]
    if provider.api_key and not answers.api_key.strip():
        return [("api_key", API_KEY_HINT)]
    return []


def field_row(label: str, input_id: str, *, password: bool = False) -> Vertical:
    """Three lines: the label, its input, and the message a refusal writes under it."""
    return Vertical(
        Label(f"{label}:", classes="flabel"),
        Input(id=input_id, password=password),
        Static("", id=f"{input_id}-msg", classes="fmsg"),
        id=f"{input_id}-row",
        classes="frow",
    )


def section(title: str) -> VerticalGroup:
    """Return a box per section: the border carries its title, so the eye tells them apart."""
    box = VerticalGroup(classes="section")
    box.border_title = title
    return box


class SetupScreen(Screen[None]):
    """The one screen: a box for pi's provider, and Next hands the choice on.

    A refused field gets its message under it, a toast at the bottom lists
    them all, and the first one refused is scrolled to. Inputs keep Textual's standard look, below
    their label, so a long key shows whole and a selection stays visible.
    An override that shrinks or borders the input loses to Textual's own
    focused-input rule: the field then has no row left for its text.
    """

    DEFAULT_CSS = """
    SetupScreen { align: center top; }
    .section { width: 100%; height: auto; margin: 0 0 1 0; padding: 0 1;
               border: round $primary; border-title-style: bold; border-title-color: $text; }
    .section > .frow { margin-top: 1; }
    .section > .frow:first-of-type { margin-top: 0; }
    .section Input, .section Select { width: 100%; margin: 0; }
    .frow { height: auto; }
    .flabel { width: 100%; height: 1; padding: 0; margin: 0; }
    .fmsg { display: none; }
    .fmsg.show { display: block; height: auto; color: $error; }
    #next { margin: 0 0 1 1; }
    #status { height: auto; margin: 0 0 0 1; }
    #status.ok { color: $success; }
    #status.err { color: $error; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.providers: list[piauth.Provider] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with section("Pi provider"):
            yield Vertical(
                Label("Pi provider:", classes="flabel"),
                Select([], id="provider", prompt=PROVIDER_PROMPT, allow_blank=True),
                Static("", id="provider-msg", classes="fmsg"),
                id="provider-row",
                classes="frow",
            )
            key_row = field_row("API key", "api_key", password=True)
            key_row.display = False
            yield key_row
        yield Button("Next", id="next", disabled=True)
        yield Static("", id="status")
        # No Footer status bar: the last line is the status.

    def _set_status(self, text: str, *, state: str = "") -> None:
        """Write the status line as plain text; state styles it ok/err, or clears it.

        Plain text on purpose: a str is parsed as console markup, and pi's
        words may hold brackets.
        """
        status = self.query_one("#status", Static)
        status.update(Text(text))
        status.set_classes(state)

    def _set_message(self, input_id: str, message: str) -> None:
        """Write a field's message line, or hide it when the message is empty."""
        line = self.query_one(f"#{input_id}-msg", Static)
        line.update(Text(message))
        line.set_classes("fmsg show" if message else "fmsg")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        """Offer pi's providers, then let the operator fill the screen."""
        self._set_status("listing providers…")
        catalog = await piauth.catalog()
        # A provider with no way in (no key, no sign-in in pi's registry)
        # would only stall the login: it is not offered.
        offered = [provider for provider in catalog if provider.api_key or provider.oauth]
        if not offered:
            message = "pi lists no provider that takes a key or a sign-in"
            raise piauth.PiError(message)
        self.providers = offered
        self.query_one("#provider", Select).set_options(
            (provider.id, provider.id) for provider in offered
        )
        self.query_one("#next", Button).disabled = False
        self._set_status(READY_HINT)

    def _chosen(self) -> piauth.Provider | None:
        """Return the provider the dropdown names, None while none is chosen."""
        value = self.query_one("#provider", Select).value
        if value is Select.NULL:
            return None
        return next((provider for provider in self.providers if provider.id == str(value)), None)

    @on(Select.Changed, "#provider")
    def _provider_chosen(self, _event: Select.Changed) -> None:
        """Show the key field for a key provider; say when a sign-in-only one signs in."""
        provider = self._chosen()
        self.query_one("#api_key-row", Vertical).display = provider is not None and provider.api_key
        # A key typed for the previous provider must not be saved under
        # this one: the field starts empty on every change.
        self.query_one("#api_key", Input).value = ""
        self._set_message("provider", "")
        self._set_message("api_key", "")
        if provider is not None and not provider.api_key:
            self._set_status(SIGN_IN_HINT.format(provider=provider.id))
        else:
            self._set_status(READY_HINT)

    def _answers(self) -> Answers:
        """Return the screen's fields as they were typed."""
        provider = self._chosen()
        return Answers(
            api_key=self.query_one("#api_key", Input).value.strip(),
            provider="" if provider is None else provider.id,
        )

    def _refuse(self, refusals: list[tuple[str, str]]) -> None:
        """Show every refusal under its field and in a toast at the bottom; go to the first one.

        The toast stays visible when the view scrolls up to that first
        field, so it names each field with its message.
        """
        for input_id, message in refusals:
            self._set_message(input_id, message)
        first = self.query_one(f"#{refusals[0][0]}")
        first.focus()
        self.call_after_refresh(partial(first.scroll_visible, animate=False))
        names = ", ".join(LABELS[input_id] for input_id, _message in refusals)
        self._set_status(f"These fields need a look: {names}", state="err")
        self.notify(
            "\n".join(f"{LABELS[input_id]}: {message}" for input_id, message in refusals),
            title="These fields need a look",
            severity="error",
            timeout=10,
            markup=False,
        )

    @on(Button.Pressed, "#next")
    def _next(self) -> None:
        """Hand the choice to the terminal steps, or refuse the fields that are not ready."""
        answers = self._answers()
        provider = self._chosen()
        for input_id in MESSAGE_IDS:
            self._set_message(input_id, "")
        refusals = validate(answers, provider)
        if refusals:
            self._refuse(refusals)
            return
        assert provider is not None  # validate refused a missing provider
        app = setup_app(self)
        app.choice = PiChoice(provider=provider, api_key=answers.api_key)
        app.exit()


class SetupApp(App[None]):
    """The one screen.

    Next is the only way the screen ends: ctrl+q and ctrl+c do nothing.
    ``choice`` is what Next handed on; None means the screen ended
    without it (a crash, or a terminal that closed).
    """

    TITLE = "desmosetup"

    # Textual's own keys are replaced: ctrl+q quits there, and ctrl+c
    # points at it. Next is the only way the screen ends.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+q", "stay", show=False, priority=True),
        Binding("ctrl+c", "stay", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.choice: PiChoice | None = None

    def action_stay(self) -> None:
        """Do nothing: no key leaves the first run."""

    def on_mount(self) -> None:
        # textual 8 has no App.THEME classvar (the old one silently did
        # nothing) — the reactive is set here, before the first screen.
        self.theme = "textual-light"
        self.push_screen(SetupScreen())
