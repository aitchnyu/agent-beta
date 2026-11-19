"""Tests for ops/firstsetup — the first-run setup menu.

Class inventory:

- ProviderCatalogTests: parsing pi's CLI output for the provider list
  (the unknown-provider error's "Providers:" line; the --list-models
  fallback table), and the loud failure when both sources are dead
- CredentialVerificationTests: the only real credential test — a
  one-turn pi --print, including pi's habit of exiting 0 on 4xx bodies
- GoogleFormValidationTests: the google form's client-id/secret shape
  rules; the both-empty skip
- UserFormValidationTests: the first-user form's all-three-required
  rule, email RFC limits, and name charset
- FailureDescriptionTests: describe_failure turns any failed command
  into one line carrying the command's own error
- AuthKindDispatchTests: auth_kind_of decides API-key vs OAuth screen —
  only an explicit "oauth" from the live registry beats the api_key
  default
- SetupAppStateTests: SetupApp's setters/readers (first user, verified
  providers, provider catalog) — the only menu-state mutation surface
- AuthStoreRoundTripTests: pi's auth.json read/merge/write as debian —
  merge-preserving writes, loud failures, empty only when truly fresh
- SetupMenuPilotTests: headless textual pilots at 80x24 — navigation,
  two-state rows, the Superuser row opening the login link

No real pi/node/sudo: subprocess seams are faked or patched.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import ClassVar
from unittest import mock

from textual.widgets import Button, Select, Static
from textual.widgets import Input as TextInput

from ops.firstsetup import Menu, SetupApp, providers
from ops.firstsetup.authstore import AuthStore
from ops.firstsetup.forms import USER, _google_validate, _user_validate
from ops.firstsetup.screens import (
    ApiKeyScreen,
    FormScreen,
    LoginLinkScreen,
    describe_failure,
)

FAKE_PROVIDERS: list[dict[str, object]] = [
    {"id": "openai-codex", "name": "OpenAI Codex", "authKind": "oauth"},
    {"id": "zai", "name": "Z.AI", "authKind": "api_key"},
]


class FakeProc:
    """Stands in for a captured subprocess (communicate-shaped)."""

    def __init__(self, out: bytes = b"", returncode: int = 0) -> None:
        self._out = out
        self.returncode = returncode

    async def communicate(self, _data: bytes = b"") -> tuple[bytes, bytes]:
        return self._out, b""


class ProviderCatalogTests(unittest.TestCase):
    """The provider catalog: pi CLI output parsing + load failure.

    - test_providers_line_parses: the unknown-provider error's
      'Providers: a, b, c' line parses
    - test_missing_line_returns_empty: an absent Providers line yields []
    - test_table_parses_unique_providers: --list-models rows collapse to
      unique providers, header dropped
    - test_list_providers_raises_when_empty: a powerless dropdown raises
    """

    def test_providers_line_parses(self) -> None:
        """The unknown-provider error's 'Providers: a, b, c' line parses."""
        text = 'Unknown provider "bogus".\nProviders: zai, openai-codex, google\n'
        self.assertEqual(
            providers.parse_providers_line(text),
            [
                {"id": "zai", "name": "zai"},
                {"id": "openai-codex", "name": "openai-codex"},
                {"id": "google", "name": "google"},
            ],
        )

    def test_missing_line_returns_empty(self) -> None:
        """An absent Providers line yields [] — the fallback path's cue."""
        self.assertEqual(providers.parse_providers_line("something else"), [])

    def test_table_parses_unique_providers(self) -> None:
        """--list-models rows collapse to unique providers, header dropped."""
        table = (
            "provider       model              context\n"
            "zai            glm-5.3            1M\n"
            "zai            glm-5.3-flash      1M\n"
            "openai-codex   gpt-5-codex        400K\n"
        )
        self.assertEqual(
            providers.parse_models_table(table),
            [
                {"id": "zai", "name": "zai"},
                {"id": "openai-codex", "name": "openai-codex"},
            ],
        )

    def test_list_providers_raises_when_empty(self) -> None:
        """Both dead provider sources raise — an empty dropdown is never ok."""
        with (
            mock.patch(
                "ops.firstsetup.providers.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=FakeProc(out=b""),
            ),
            self.assertRaises(RuntimeError),
        ):
            asyncio.run(providers.list_providers())


class CredentialVerificationTests(unittest.TestCase):
    """verify_credential: the only real credential test.

    A stored key proves nothing (pi auth check reports "ready" for a
    fake one), so the screen runs one cheap model call. Real behavior
    (probed in the VM with a real zai key):
    - real key: rc=0, output "ok" → (True, "ok")
    - fake key: rc=1, output '401: {"code":"401",...}' → (False, error)
    - pi exits 0 even on provider errors (an unknown model returns a
      400 body) — the body shape must fail the verify too.

    - test_real_key_succeeds: working credential → verified
    - test_fake_key_captures_provider_error: rc=1 → error surfaced
    - test_error_body_fails_even_with_rc0: '400: {...}' with rc=0 →
      NOT verified (the wrong-model trap)
    - test_picks_model_for_its_own_provider: the first row for THIS
      provider, not the first row of the whole table
    - test_no_models_returns_error: a provider absent from the table
    """

    def _make_screen(self) -> ApiKeyScreen:
        return ApiKeyScreen({"id": "zai", "name": "Z.AI"})

    def test_real_key_succeeds(self) -> None:
        """A working credential returns (True, model output)."""

        async def fake_run_command(*argv: str, **_kwargs: object) -> tuple[int, str]:
            if "--list-models" in argv:
                return 0, "provider  model\nzai  glm-5.3-flash\n"
            return 0, "ok"

        screen = self._make_screen()
        with mock.patch("ops.firstsetup.screens.run_command", side_effect=fake_run_command):
            verified, detail = asyncio.run(screen.verify_credential())
        self.assertTrue(verified)
        self.assertEqual(detail, "ok")

    def test_fake_key_captures_provider_error(self) -> None:
        """A bad credential returns (False, the provider's own error line)."""
        error_line = '401: {"code":"401","message":"token expired or incorrect"}'

        async def fake_run_command(*argv: str, **_kwargs: object) -> tuple[int, str]:
            if "--list-models" in argv:
                return 0, "provider  model\nzai  glm-5.3-flash\n"
            return 1, error_line

        screen = self._make_screen()
        with mock.patch("ops.firstsetup.screens.run_command", side_effect=fake_run_command):
            verified, detail = asyncio.run(screen.verify_credential())
        self.assertFalse(verified)
        self.assertIn("401", detail)
        self.assertIn("token expired or incorrect", detail)

    def test_error_body_fails_even_with_rc0(self) -> None:
        """A 4xx body fails the verify even when pi exits 0."""

        async def fake_run_command(*argv: str, **_kwargs: object) -> tuple[int, str]:
            if "--list-models" in argv:
                return 0, "provider  model\nzai  glm-5.3-flash\n"
            return 0, '400: {"code":"1211","message":"Unknown Model"}'

        screen = self._make_screen()
        with mock.patch("ops.firstsetup.screens.run_command", side_effect=fake_run_command):
            verified, detail = asyncio.run(screen.verify_credential())
        self.assertFalse(verified)
        self.assertIn("400", detail)

    def test_picks_model_for_its_own_provider(self) -> None:
        """The model comes from THIS provider's row, not the table's first."""
        screen = self._make_screen()
        table = (
            "provider  model                         context\n"
            "together  deepseek-ai/DeepSeek-V4-Pro   1.0M\n"
            "zai       glm-5.3-flash                 1M\n"
        )
        self.assertEqual(screen._first_model_id(table), "glm-5.3-flash")

    def test_no_models_returns_error(self) -> None:
        """A provider absent from the table returns an explicit error."""

        async def fake_run_command(*argv: str, **_kwargs: object) -> tuple[int, str]:
            if "--list-models" in argv:
                return 0, "provider  model\ntogether  deepseek-ai/x\n"
            return 0, ""

        screen = self._make_screen()
        with mock.patch("ops.firstsetup.screens.run_command", side_effect=fake_run_command):
            verified, detail = asyncio.run(screen.verify_credential())
        self.assertFalse(verified)
        self.assertIn("no models", detail)


class GoogleFormValidationTests(unittest.TestCase):
    """The google form's client-id/secret shape rules.

    A malformed pair must never reach addoauth (the operator would get
    an opaque Django OAuth failure instead of a field message).
    Both-empty is the deliberate skip (Back is the other).

    - test_rejects_malformed_client_id: must look like
      1234567890-abc123.apps.googleusercontent.com
    - test_rejects_short_secret: Google secrets are ~35 chars, no spaces
    - test_accepts_well_formed_pair: the real shape passes; empty = skip
    """

    def test_rejects_malformed_client_id(self) -> None:
        """A client key that isn't the apps.googleusercontent.com shape refuses."""
        error = _google_validate({"client_id": "not-a-key", "client_secret": "GOCSPX-" + "x" * 28})
        assert error is not None
        self.assertIn("apps.googleusercontent.com", error)

    def test_rejects_short_secret(self) -> None:
        """A too-short secret refuses (Google secrets are ~35 chars)."""
        error = _google_validate(
            {"client_id": "1234567890-abc123.apps.googleusercontent.com", "client_secret": "short"}
        )
        assert error is not None
        self.assertIn("secret", error)

    def test_accepts_well_formed_pair(self) -> None:
        """A well-formed pair passes; both-empty passes (skip)."""
        ok = {
            "client_id": "1234567890-abc123.apps.googleusercontent.com",
            "client_secret": "GOCSPX-" + "x" * 28,
        }
        self.assertIsNone(_google_validate(ok))
        self.assertIsNone(_google_validate({"client_id": "", "client_secret": ""}))


class UserFormValidationTests(unittest.TestCase):
    """The first-user form: all three fields, or none.

    The user is created via createuser --superuser, so a bad shape
    would surface as a Django error; validation catches it first. A
    completely blank form refuses (unlike google) — Back is the skip.

    - test_accepts_well_formed_user: the happy path; blank refuses
    - test_rejects_bad_email: unparseable or over the 254-char limit
    - test_rejects_partial_fills: email without names; names without email
    - test_rejects_bad_name_shape: digits refused; apostrophes allowed
    """

    VALID: ClassVar[dict[str, str]] = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
    }

    def test_accepts_well_formed_user(self) -> None:
        """A well-formed user passes; all-BLANK refuses (not a skip)."""
        self.assertIsNone(_user_validate(self.VALID))
        blank_error = _user_validate({"first_name": "", "last_name": "", "email": ""})
        assert blank_error is not None
        self.assertIn("fill", blank_error)

    def test_rejects_bad_email(self) -> None:
        """An unparseable or over-long email refuses."""
        bad = dict(self.VALID, email="not-an-email")
        assert _user_validate(bad) is not None
        long_email = "a" * 250 + "@x.io"
        assert _user_validate(dict(self.VALID, email=long_email)) is not None

    def test_rejects_partial_fills(self) -> None:
        """Email without names refuses; names without email also refuses."""
        no_names = {"first_name": "", "last_name": "", "email": "jane@example.com"}
        error = _user_validate(no_names)
        assert error is not None
        self.assertIn("name", error)
        no_email = {"first_name": "Jane", "last_name": "Doe", "email": ""}
        error = _user_validate(no_email)
        assert error is not None  # partial fills refuse — Back is the skip
        self.assertIn("email", error)

    def test_rejects_bad_name_shape(self) -> None:
        """Names must be letters (hyphen/apostrophe ok), starting with one."""
        error = _user_validate(dict(self.VALID, first_name="123"))
        assert error is not None
        self.assertIn("first name", error)
        self.assertIsNone(_user_validate(dict(self.VALID, last_name="O'Brien")))


class FailureDescriptionTests(unittest.TestCase):
    """describe_failure: one clear line for any failed command.

    A toast saying only "failed (rc=3)" hides the cause; the helper
    carries the command's own last error line (a traceback, a psql
    error, a missing binary).

    - test_describe_failure_includes_command_output: command name,
      exit code, and the final non-empty output line
    """

    def test_describe_failure_includes_command_output(self) -> None:
        """The toast carries the command's own last error line."""
        message = describe_failure(
            ("./run", "djangomanage", "createuser"),
            1,
            "Traceback (most recent call last):\nValueError: bad email",
        )
        self.assertIn("createuser", message)
        self.assertIn("rc=1", message)
        self.assertIn("ValueError: bad email", message)


class AuthKindDispatchTests(unittest.TestCase):
    """auth_kind_of: API-key screen vs OAuth screen.

    The menu dispatches a provider's config screen from this answer.
    Only an explicit "oauth" in the live registry (queried from pi's
    own runtime) beats the default; an unknown or missing kind takes
    the API-key screen, whose verify step surfaces any OAuth-only
    provider as a readable error.

    - test_oauth_providers_dispatch_oauth: registry "oauth" wins;
      "api_key" stays api_key
    - test_unknown_kind_defaults_to_api_key: missing/empty registry
      defaults safely
    """

    def test_oauth_providers_dispatch_oauth(self) -> None:
        """Providers in the live registry's oauth set dispatch OAuthScreen."""
        auth_kinds = {"anthropic": "oauth", "zai": "api_key"}
        self.assertEqual(providers.auth_kind_of("anthropic", auth_kinds), "oauth")
        self.assertEqual(providers.auth_kind_of("zai", auth_kinds), "api_key")

    def test_unknown_kind_defaults_to_api_key(self) -> None:
        """A missing kinds registry or unknown id defaults to api_key."""
        self.assertEqual(providers.auth_kind_of("anything"), "api_key")
        self.assertEqual(providers.auth_kind_of("anything", {}), "api_key")


class SetupAppStateTests(unittest.TestCase):
    """SetupApp's menu state behind small setters/readers.

    All state lives on the app so screens and forms never poke bare
    attributes — this class pins that surface.

    - test_first_user_roundtrip: record → configured, full name, link
    - test_provider_verified_roundtrip: mark → is → sorted ids
    - test_catalog_lookup: provider_by_id, auth-kind defaulting, and
      the None for an unknown id
    """

    def test_first_user_roundtrip(self) -> None:
        """Recording a user makes it configured with its display name."""
        app = SetupApp()
        self.assertFalse(app.first_user.is_configured)
        app.record_first_user(
            first_name="Jane", last_name="Doe", email="jane@example.com", login_link="https://x/"
        )
        self.assertTrue(app.first_user.is_configured)
        self.assertEqual(app.first_user.full_name, "Jane Doe")
        self.assertEqual(app.first_user.login_link, "https://x/")

    def test_provider_verified_roundtrip(self) -> None:
        """Marking a provider verified exposes it (sorted) until reset."""
        app = SetupApp()
        self.assertFalse(app.is_provider_verified("zai"))
        app.mark_provider_verified("zai")
        self.assertTrue(app.is_provider_verified("zai"))
        self.assertEqual(app.verified_provider_ids(), ["zai"])

    def test_catalog_lookup(self) -> None:
        """provider_by_id finds rows; auth kind defaults to api_key."""
        app = SetupApp()
        app.load_provider_catalog(FAKE_PROVIDERS, {"openai-codex": "oauth"})
        self.assertEqual(app.provider_by_id("zai")["name"], "Z.AI")  # type: ignore[index]
        self.assertIsNone(app.provider_by_id("nope"))
        self.assertEqual(app.provider_auth_kind("openai-codex"), "oauth")
        self.assertEqual(app.provider_auth_kind("zai"), "api_key")


class AuthStoreRoundTripTests(unittest.TestCase):
    """pi's auth.json read/merge/write, as debian.

    The one-time setup must never lose a credential another provider
    login stored, and must never pretend an unreadable store is empty
    (that would clobber on the next write).

    - test_set_credential_keeps_other_providers: merge never clobbers
    - test_write_failure_raises: a failed write surfaces, no silent rc
    - test_read_missing_store_is_empty: the expected fresh state
    - test_read_other_failure_raises: sudo/permission errors surface
    """

    def test_set_credential_keeps_other_providers(self) -> None:
        """A new credential merges into the store; others survive."""
        existing = {"openai-codex": {"type": "oauth", "access": "keep-me"}}
        written: list[bytes] = []

        class CapturingProc(FakeProc):
            async def communicate(self, data: bytes = b"") -> tuple[bytes, bytes]:
                written.append(data)
                return b"", b""

        async def fake_exec(*argv: str, **_kwargs: object) -> FakeProc:
            if "cat" in argv:
                return FakeProc(out=json.dumps(existing).encode())
            return CapturingProc()

        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with mock.patch(
            "ops.firstsetup.authstore.asyncio.create_subprocess_exec", side_effect=fake_exec
        ):
            asyncio.run(store.set_credential("zai", {"type": "api_key", "key": "sk-new"}))
        result = json.loads(written[0].decode())
        self.assertEqual(result["openai-codex"]["access"], "keep-me")
        self.assertEqual(result["zai"]["key"], "sk-new")

    def test_write_failure_raises(self) -> None:
        """A nonzero write exits loudly instead of returning a bare rc."""
        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with (
            mock.patch(
                "ops.firstsetup.authstore.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=FakeProc(returncode=1),
            ),
            self.assertRaises(RuntimeError),
        ):
            asyncio.run(store.write({}))

    def test_read_missing_store_is_empty(self) -> None:
        """A fresh machine (cat: No such file) reads as {} — not an error."""

        class MissingStoreProc(FakeProc):
            async def communicate(self, _data: bytes = b"") -> tuple[bytes, bytes]:
                return b"", b"cat: /home/debian/.pi/agent/auth.json: No such file or directory"

        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with mock.patch(
            "ops.firstsetup.authstore.asyncio.create_subprocess_exec",
            new_callable=mock.AsyncMock,
            return_value=MissingStoreProc(returncode=1),
        ):
            self.assertEqual(asyncio.run(store.read()), {})

    def test_read_other_failure_raises(self) -> None:
        """A permission/sudo failure surfaces.

        A silent empty store would let the next write clobber every
        credential that could not be read.
        """

        class DeniedProc(FakeProc):
            async def communicate(self, _data: bytes = b"") -> tuple[bytes, bytes]:
                return b"", b"sudo: a password is required"

        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with (
            mock.patch(
                "ops.firstsetup.authstore.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=DeniedProc(returncode=1),
            ),
            self.assertRaises(RuntimeError),
        ):
            asyncio.run(store.read())


class SetupMenuPilotTests(unittest.IsolatedAsyncioTestCase):
    """Headless textual pilots of the menu at a cramped 80x24.

    These drive the real widget tree (clicks, key presses) without a
    terminal — the regression guard for layout and focus behavior.

    - test_menu_renders_and_navigates: dropdown rows from the catalog,
      arrow focus, delve/back, whitespace-stripping inputs
    - test_statuses_refresh_summary_and_link: the two-state rows show
      the verified-provider summary and the login link
    - test_superuser_click_opens_login_link: the completed Superuser
      row stays clickable and opens the copyable link
    """

    async def test_menu_renders_and_navigates(self) -> None:
        """Headless pilot at cramped 80x24.

        The provider dropdown carries the catalog, arrow focus moves
        within the visible controls, delve/back navigates, and inputs
        strip whitespace.
        """
        app = SetupApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()  # warm-up: mounts before the first tick drop
            menu = app.screen
            assert isinstance(menu, Menu)
            app.load_provider_catalog(FAKE_PROVIDERS, {})
            menu._populate_select_options()
            await pilot.pause()
            select = menu.query_one("#provider-select", Select)
            # blank sentinel + the two catalog providers
            self.assertEqual(len(select._options), 3)
            # focus stays on the visible controls
            await pilot.press("down")
            self.assertIs(app.focused, menu.query_one("#google"))
            # provider delve via the menu's handler, back returns to the menu
            menu.open_provider("zai")
            await pilot.pause()
            self.assertIsInstance(app.screen, ApiKeyScreen)
            await pilot.click("#back")
            assert isinstance(app.screen, Menu)
            # form delve: fields strip whitespace, back returns
            await pilot.click("#user")
            screen = app.screen
            assert isinstance(screen, FormScreen)
            self.assertIs(screen.spec, USER)
            await pilot.click("#first_name")
            await pilot.press(*"  Jane  ")
            self.assertEqual(screen.query_one("#first_name", TextInput).value, "Jane")
            await pilot.click("#back")
            assert isinstance(app.screen, Menu)

    async def test_statuses_refresh_summary_and_link(self) -> None:
        """Statuses refresh the ready-provider summary and the login link."""
        app = SetupApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            menu = app.screen
            assert isinstance(menu, Menu)
            app.mark_provider_verified("zai")
            app.record_first_user(
                first_name="Jane",
                last_name="Doe",
                email="jane@example.com",
                login_link="https://localhost:8443/login-with-secret/abc/",
            )
            menu.statuses()
            await pilot.pause()
            self.assertIn("zai", str(menu.query_one("#ai-done", Static).content))
            self.assertIn("login-with-secret/abc", str(menu.query_one("#link", Static).content))

    async def test_superuser_click_opens_login_link(self) -> None:
        """Clicking the completed Superuser row opens the login-link screen."""
        app = SetupApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            menu = app.screen
            assert isinstance(menu, Menu)
            app.record_first_user(
                first_name="Jane",
                last_name="Doe",
                email="jane@example.com",
                login_link="https://localhost:8443/login-with-secret/xyz/",
            )
            menu.statuses()
            await pilot.pause()
            user_button = menu.query_one("#user", Button)
            self.assertIn("Superuser: Jane Doe", str(user_button.label))
            self.assertFalse(user_button.disabled)  # clickable, not locked
            await pilot.click("#user")
            await pilot.pause()
            self.assertIsInstance(app.screen, LoginLinkScreen)
            self.assertIn(
                "login-with-secret/xyz",
                str(app.screen.query_one("#link-line", Static).content),
            )
            await pilot.click("#back")
            assert isinstance(app.screen, Menu)


if __name__ == "__main__":
    unittest.main()
