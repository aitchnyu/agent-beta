"""forms — the setup forms as DATA.

Adding one is an entry here, not a new Screen class: FormScreen
(screens.py) is the single engine that renders any spec, validates it,
dispatches its actions, and applies its success hook.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from textual.app import App

Values = dict[str, str]
Argv = Callable[[Values], tuple[str, ...]]
Validator = Callable[[Values], str | None]
Success = Callable[[App[None], Values, str], None]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Field:
    """One label/input line."""

    id: str
    label: str
    password: bool = False
    placeholder: str = ""


@dataclass(frozen=True)
class Action:
    """One dispatched command; argv is built from the form's values.

    capture: a marker substring — the last stdout line containing it is
    kept and handed to the success hook (the login link rides this).
    """

    argv: Argv
    capture: str | None = None


@dataclass(frozen=True)
class FormSpec:
    """Everything FormScreen needs to run one form."""

    id: str
    title: str
    fields: tuple[Field, ...]
    actions: tuple[Action, ...]
    success: Success
    validate: Validator | None = None
    apply_label: str = "Apply"
    # Optional: every field empty ⇒ Apply just goes Back (skip).
    optional: bool = True


# ── the first-user form ───────────────────────────────────────────────────


def _user_argv(values: Values) -> tuple[str, ...]:
    return (
        "./run",
        "djangomanage",
        "createuser",
        values["first_name"],
        values["last_name"],
        values["email"],
        "--superuser",
        "--if-absent",
    )


def _link_argv(values: Values) -> tuple[str, ...]:
    return ("./run", "djangomanage", "makeloginlink", values["email"], "--minutes", "1440")


def _user_success(app: App[None], values: Values, captured: str) -> None:
    from ops.firstsetup.app import SetupApp  # noqa: PLC0415 — breaks the app↔forms cycle

    assert isinstance(app, SetupApp)
    app.record_first_user(
        first_name=values["first_name"],
        last_name=values["last_name"],
        email=values["email"],
        login_link=captured,
    )
    app.flash("user created — the login link is on the menu")


NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'-]{0,49}$")
EMAIL_MAX = 254  # the RFC 5321 forward-path limit


def _user_validate(values: Values) -> str | None:
    email = values.get("email", "")
    first = values.get("first_name", "")
    last = values.get("last_name", "")
    if not any((email, first, last)):
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


USER = FormSpec(
    id="user",
    title="first user",
    fields=(
        Field("first_name", "first name"),
        Field("last_name", "last name"),
        Field("email", "email", placeholder="you@example.com"),
    ),
    actions=(
        Action(_user_argv),
        Action(_link_argv, capture="login-with-secret"),
    ),
    success=_user_success,
    validate=_user_validate,
    optional=False,  # blank Apply refuses — Back is the skip path
)


# ── the google sign-in form ───────────────────────────────────────────────


def _google_argv(values: Values) -> tuple[str, ...]:
    return (
        "./run",
        "djangomanage",
        "addoauth",
        "google",
        values["client_id"],
        values["client_secret"],
    )


def _google_success(app: App[None], _values: Values, _captured: str) -> None:
    from ops.firstsetup.app import SetupApp  # noqa: PLC0415 — breaks the app↔forms cycle

    assert isinstance(app, SetupApp)
    app.record_google_configured()
    app.flash("google oauth stored")


CLIENT_ID_RE = re.compile(r"^\d+-[A-Za-z0-9]+\.apps\.googleusercontent\.com$")
MIN_SECRET_LEN = 20


def _google_validate(values: Values) -> str | None:
    client_id = values.get("client_id", "")
    secret = values.get("client_secret", "")
    if bool(client_id) != bool(secret):
        return "fill BOTH client key and secret, or neither"
    if not client_id:
        return None  # skip
    if not CLIENT_ID_RE.match(client_id):
        return "client key should look like 1234567890-abc123.apps.googleusercontent.com"
    if len(secret) < MIN_SECRET_LEN or " " in secret:
        return "client secret looks wrong (Google secrets are ~35 chars, no spaces)"
    return None


GOOGLE = FormSpec(
    id="google",
    title="google oauth — both empty = skip",
    fields=(
        Field("client_id", "client key", placeholder="xxxx.apps.googleusercontent.com"),
        Field("client_secret", "secret", password=True),
    ),
    actions=(Action(_google_argv),),
    success=_google_success,
    validate=_google_validate,
)

MENU_FORMS: tuple[FormSpec, ...] = (USER, GOOGLE)
