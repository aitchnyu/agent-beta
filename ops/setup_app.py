"""setup_app — ``desmosetup``'s one screen: domain, first superuser, Google, pi provider.

The screen collects values. One choice acts at once: a pi provider that
only signs in hands the terminal to pi's own login. Every other step runs
on the terminal once the screen is gone (ops/setup.py). The first run is
the only run: nothing here looks for what the machine already holds, and
no key leaves the screen — Next is the only way out.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import ClassVar, cast

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalGroup
from textual.screen import Screen
from textual.widgets import Button, Header, Input, Label, Select, Static

from ops import googleoauth, piauth
from ops.superuserloginlink import EMAIL_HINT, EMAIL_MAX, EMAIL_RE, NAME_HINT, NAME_RE

REPO_ROOT = Path(__file__).resolve().parent.parent
# The provisioner's credentials env — the one place the site's origin lives.
CREDS_ENV = Path("/etc/credentials/desmo/.env.vm")
LOCAL_DOMAIN = "https://localhost:8443"
PROVIDER_PROMPT = "choose a provider…"
READY_HINT = "Fill the fields, then press Next"
# The domain is typed either as a domain name — dot-separated labels, at
# least two: a domain or a subdomain — or as the local origin, literally.
DOMAIN_NAME_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"
)
DOMAIN_HINT = f"a domain, a subdomain, or literally {LOCAL_DOMAIN}"
GOOGLE_HALF_HINT = "fill both Google fields, or neither"
API_KEY_HINT = "paste the provider's API key"
# Every field in screen order, with the label its message names. The
# inputs are read by id; ``<id>-msg`` is the line under each.
LABELS: dict[str, str] = {
    "domain": "Domain",
    "first": "Super user first name",
    "last": "Super user last name",
    "email": "Super user email",
    "google_key": "Google key",
    "google_secret": "Google secret",
    "provider": "Pi provider",
    "api_key": "API key",
}
FIELD_IDS = ("domain", "first", "last", "email", "google_key", "google_secret", "api_key")


class DomainError(Exception):
    """The provisioner refused the new origin; the message is its own last line."""


@dataclass(frozen=True, kw_only=True)
class Answers:
    """The screen's fields as they were typed."""

    domain: str
    first: str
    last: str
    email: str
    google_key: str
    google_secret: str
    provider: str
    api_key: str


@dataclass(frozen=True, kw_only=True)
class Values:
    """What the screen hands to the terminal steps.

    ``homepage`` is the origin to serve, ``set_domain`` says whether it
    differs from the one in effect, and ``provider`` is the pi provider
    the id named.
    """

    homepage: str
    set_domain: bool
    first: str
    last: str
    email: str
    google_key: str
    google_secret: str
    provider: piauth.Provider
    api_key: str


def setup_app(screen: Screen[None]) -> SetupApp:
    """Return the app a screen belongs to, typed.

    Screens and app are mutually recursive at import time, so the class
    is only named here; at runtime the object is always a SetupApp.
    """
    return cast("SetupApp", screen.app)


def parse_env_origin(text: str) -> str:
    """Return the first origin in an env file's BASE_URLS line ('' when there is none)."""
    for line in text.splitlines():
        if line.startswith("BASE_URLS="):
            origins = line.split("=", 1)[1].strip().strip("\"'").split(",")
            return origins[0].strip().rstrip("/")
    return ""


def current_domain() -> str:
    """Return the origin the site serves now: BASE_URLS in the credentials env.

    A machine without that file (dev) serves the local origin.
    """
    if CREDS_ENV.is_file():
        origin = parse_env_origin(CREDS_ENV.read_text(encoding="utf-8"))
        if origin:
            return origin
    return LOCAL_DOMAIN


def is_domain_name(text: str) -> bool:
    """Return True when the text is a domain name: dot-separated labels, at least two."""
    return DOMAIN_NAME_RE.match(text) is not None


def is_typed_domain(text: str) -> bool:
    """Return True when the text is what the Domain field takes.

    A domain, a subdomain, or the local origin, literally.
    """
    typed = text.strip()
    return typed == LOCAL_DOMAIN or is_domain_name(typed)


def typed_origin(text: str) -> str:
    """Return the https origin a typed domain means.

    A domain name means ``https://`` plus that name; the local origin
    means itself. Anything else raises ValueError; the screen refuses it
    before.
    """
    typed = text.strip()
    if typed == LOCAL_DOMAIN:
        return LOCAL_DOMAIN
    if not is_domain_name(typed):
        raise ValueError(DOMAIN_HINT)
    return f"https://{typed}"


def _name_refusals(answers: Answers) -> list[tuple[str, str]]:
    """Return the refusals of the three superuser fields, in screen order."""
    refusals: list[tuple[str, str]] = []
    if not NAME_RE.match(answers.first):
        refusals.append(("first", NAME_HINT))
    if not NAME_RE.match(answers.last):
        refusals.append(("last", NAME_HINT))
    if not EMAIL_RE.match(answers.email) or len(answers.email) > EMAIL_MAX:
        refusals.append(("email", EMAIL_HINT))
    return refusals


def _google_refusals(answers: Answers) -> list[tuple[str, str]]:
    """Return the refusals of the Google pair: the empty one of a half pair, or the wrong one."""
    if bool(answers.google_key) != bool(answers.google_secret):
        return [("google_secret" if answers.google_key else "google_key", GOOGLE_HALF_HINT)]
    if not answers.google_key:
        return []
    problem = googleoauth.check_values(answers.google_key, answers.google_secret)
    if problem is None:
        return []
    wrong = "google_key" if problem == googleoauth.CLIENT_ID_HINT else "google_secret"
    return [(wrong, problem)]


def _pi_refusals(answers: Answers, provider: piauth.Provider | None) -> list[tuple[str, str]]:
    """Return the refusals of the pi fields: a missing provider, or a missing key."""
    if provider is None:
        return [("provider", PROVIDER_PROMPT)]
    if provider.api_key and not answers.api_key.strip():
        return [("api_key", API_KEY_HINT)]
    return []


def validate(answers: Answers, provider: piauth.Provider | None) -> list[tuple[str, str]]:
    """Return every refusal as (field id, message), in screen order; [] when all can go on.

    The domain is required: a domain, a subdomain, or the local origin.
    The names, the email and the provider are required. Google needs both
    of its fields or neither. A provider that takes a key needs the key.
    """
    refusals: list[tuple[str, str]] = []
    if not is_typed_domain(answers.domain):
        refusals.append(("domain", DOMAIN_HINT))
    refusals += _name_refusals(answers)
    refusals += _google_refusals(answers)
    refusals += _pi_refusals(answers, provider)
    return refusals


def apply_domain(origin: str) -> None:
    """Set the site's origin through the provisioner's set-domain step.

    The step runs as root and restarts the app's services; a refusal
    raises with its own last line.
    """
    proc = subprocess.run(
        ["sudo", "-n", "bash", str(REPO_ROOT / "deploy" / "inside-vm.sh"), "set-domain", origin],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        lines = [line.strip() for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
        raise DomainError(lines[-1] if lines else "no output")


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
    """The one screen: four boxes, and Next hands the values on.

    A refused field gets its message under it, a toast at the bottom lists
    them all, and the first one refused is scrolled to. Inputs keep Textual's standard look, below
    their label, so a long key shows whole and a selection stays visible.
    An override that shrinks or borders the input loses to Textual's own
    focused-input rule: the field then has no row left for its text.

    The boxes are taller than a small terminal, so they sit at the top
    and the screen scrolls; centred, the first rows would be cut off.
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
        self.domain = current_domain()
        self.providers: list[piauth.Provider] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with section("Domain"):
            yield Input(id="domain")
            yield Static("", id="domain-msg", classes="fmsg")
        with section("First superuser details"):
            yield field_row("Super user first name", "first")
            yield field_row("Super user last name", "last")
            yield field_row("Super user email", "email")
        with section("Google login (can skip)"):
            yield field_row("Google key", "google_key")
            yield field_row("Google secret", "google_secret", password=True)
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
        """Show the key field for a key provider; start pi's sign-in at once for a sign-in-only one."""
        provider = self._chosen()
        self.query_one("#api_key-row", Vertical).display = provider is not None and provider.api_key
        # A key typed for the previous provider must not be saved under
        # this one: the field starts empty on every change.
        self.query_one("#api_key", Input).value = ""
        self._set_message("provider", "")
        self._set_message("api_key", "")
        if provider is not None and not provider.api_key:
            self._start_sign_in(provider)

    def _start_sign_in(self, provider: piauth.Provider) -> None:
        """Hand the terminal to pi's own sign-in; the screen comes back once pi exits."""
        self._set_status(
            f"pi's sign-in for {provider.id} takes the terminal — back here once it is done"
        )
        with self.app.suspend():
            piauth.login_on_terminal(provider)
        self._set_status(READY_HINT)

    def _answers(self) -> Answers:
        """Return the screen's fields as they were typed."""
        typed = {
            input_id: self.query_one(f"#{input_id}", Input).value.strip() for input_id in FIELD_IDS
        }
        provider = self._chosen()
        return Answers(**typed, provider="" if provider is None else provider.id)

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
        """Hand the collected values to the terminal steps, or refuse the fields that are not ready."""
        answers = self._answers()
        provider = self._chosen()
        for input_id in FIELD_IDS:
            self._set_message(input_id, "")
        refusals = validate(answers, provider)
        if refusals:
            self._refuse(refusals)
            return
        origin = typed_origin(answers.domain)  # validate refused anything else
        assert provider is not None  # validate refused a missing provider
        app = setup_app(self)
        app.values = Values(
            homepage=origin,
            set_domain=origin != self.domain,
            first=answers.first,
            last=answers.last,
            email=answers.email,
            google_key=answers.google_key,
            google_secret=answers.google_secret,
            provider=provider,
            api_key=answers.api_key,
        )
        app.exit()


class SetupApp(App[None]):
    """The one screen.

    ``values`` is what the screen handed on, None when it ended without
    Next. No key leaves it: the first run is the only run.
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
        self.values: Values | None = None

    def action_stay(self) -> None:
        """Do nothing: no key leaves the first run."""

    def on_mount(self) -> None:
        # textual 8 has no App.THEME classvar (the old one silently did
        # nothing) — the reactive is set here, before the first screen.
        self.theme = "textual-light"
        self.push_screen(SetupScreen())
