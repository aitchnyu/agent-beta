"""Tests for ops/firstsetup — the setup menu's underlying system.

No Textual pilots here (operator decision 2026-11-20): anything that
needs a running app or a widget tree is untested shell. The engine
lives in flow.py and has its own test module
(test_firstsetup_flow.py); this file covers the screen validators, the
provider catalog parsing, the auth store, and the app's state surface.

Class inventory:

- ProviderCatalogTests: parsing pi's CLI output for the provider list
  (the unknown-provider error's "Providers:" line; the --list-models
  fallback table)
- ListProvidersFlowTests: the loader's two-source flow — the Providers
  line short-circuits, the fallback engages only without it
- QueryAuthKindsTests: the node registry probe — parse, rc failure,
  empty output
- GoogleFormValidationTests: the google form's client-id/secret shape
  rules; the empty pair refuses (argv and outcome live in flow.py's
  verbs — test_firstsetup_flow.py)
- UserFormValidationTests: the first-user form's all-three-required
  rule, email RFC limits, and name charset
- FailureDescriptionTests: describe_failure turns any failed command
  into one line carrying the command's own error
- AuthKindDispatchTests: auth_kind_of decides API-key vs OAuth screen —
  only an explicit "oauth" from the live registry beats the api_key
  default
- SetupAppStateTests: SetupApp's reactive state + setters/readers (first
  user, verified providers, provider catalog) — the only menu-state
  mutation surface
- SetupCommandTests: the ops.cli verb boots the app
- AuthStoreRoundTripTests: pi's auth.json read/merge/write as debian —
  merge-preserving writes, loud failures, empty only when truly fresh

No real pi/node/sudo: subprocess seams are faked or patched.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import ClassVar
from unittest import mock

from ops.firstsetup import SetupApp, providers
from ops.firstsetup.app import SetupCommand
from ops.firstsetup.authstore import AuthStore
from ops.firstsetup.flow import _describe_failure
from ops.firstsetup.screens import validate_google_values, validate_user_values

FAKE_PROVIDERS: list[dict[str, object]] = [
    {"id": "openai-codex", "name": "OpenAI Codex", "authKind": "oauth"},
    {"id": "zai", "name": "Z.AI", "authKind": "api_key"},
]


def completed(
    exit_code: int = 0, stdout_bytes: bytes = b"", stderr_bytes: bytes = b""
) -> mock.AsyncMock:
    """Return a finished subprocess: communicate() → (out, err), rc set."""
    proc = mock.AsyncMock()
    proc.communicate.return_value = (stdout_bytes, stderr_bytes)
    proc.returncode = exit_code
    return proc


class ProviderCatalogTests(unittest.TestCase):
    """The provider catalog: pi CLI output parsing + load failure.

    The menu's dropdown is only as good as pi's own error text —
    these parsers are what turn that text into rows.

    - test_providers_line_parses: the unknown-provider error's
      'Providers: a, b, c' line parses
    - test_missing_line_returns_empty: an absent Providers line yields []
    - test_table_parses_unique_providers: --list-models rows collapse to
      unique providers, header dropped
    - test_list_providers_raises_when_empty: a powerless dropdown raises
    """

    def test_providers_line_parses(self) -> None:
        """The unknown-provider error's 'Providers: a, b, c' line parses.

        - the rows carry id and name for each listed provider
        """
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
        """An absent Providers line yields [] — the fallback path's cue.

        - an unparseable probe reads as empty, engaging the table fallback
        """
        self.assertEqual(providers.parse_providers_line("something else"), [])

    def test_table_parses_unique_providers(self) -> None:
        """--list-models rows collapse to unique providers, header dropped.

        - one row per provider id, first-seen order
        - the header row never becomes a provider
        """
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
        """Both dead provider sources raise — an empty dropdown is never ok.

        - the error names the provider list as unavailable
        - the message is pinned, not just the exception class
        """
        with (
            mock.patch(
                "ops.firstsetup.providers.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=completed(),
            ),
            self.assertRaisesRegex(RuntimeError, r"^provider list unavailable"),
        ):
            asyncio.run(providers.list_providers())


class ListProvidersFlowTests(unittest.TestCase):
    """The loader's two-source flow.

    Two probes because pi hides the provider list inside a login
    error, with the model table as the fallback.

    - test_providers_line_short_circuits: a Providers line in the login
      error returns without ever running --list-models
    - test_table_fallback_engages: a dead Providers line falls through
      to the --list-models table
    """

    def test_providers_line_short_circuits(self) -> None:
        """The Providers line wins; --list-models never runs.

        - create_subprocess_exec is called exactly once (the login probe)
        - the returned rows come from the Providers line
        """
        exec_mock = mock.AsyncMock(
            side_effect=[completed(stdout_bytes=b"Providers: zai, openai-codex\n")]
        )
        with mock.patch("ops.firstsetup.providers.asyncio.create_subprocess_exec", exec_mock):
            rows = asyncio.run(providers.list_providers())
        self.assertEqual([row["id"] for row in rows], ["zai", "openai-codex"])
        self.assertEqual(exec_mock.await_count, 1)

    def test_table_fallback_engages(self) -> None:
        """No Providers line means the --list-models table decides.

        - the login probe runs first and yields nothing parseable
        - the table call runs second and its rows are the answer
        """
        exec_mock = mock.AsyncMock(
            side_effect=[
                completed(stdout_bytes=b"nothing useful"),
                completed(stdout_bytes=b"provider  model\nzai  glm-5.3\n"),
            ]
        )
        with mock.patch("ops.firstsetup.providers.asyncio.create_subprocess_exec", exec_mock):
            rows = asyncio.run(providers.list_providers())
        self.assertEqual([row["id"] for row in rows], ["zai"])
        self.assertEqual(exec_mock.await_count, 2)


class QueryAuthKindsTests(unittest.TestCase):
    """The node registry probe behind the OAuth/API-key dispatch.

    A broken probe must fail loudly — defaulting every provider to
    api_key would send OAuth users into a dead-end screen.

    - test_parses_registry: the JSON line becomes the kinds dict
    - test_probe_failure_raises: a nonzero rc raises naming the rc
    - test_empty_output_raises: no output is a broken registry, not {}
    """

    def test_parses_registry(self) -> None:
        """The last JSON line parses into {id: kind}.

        - noise lines before the JSON are skipped
        - kinds map provider id to api_key/oauth verbatim
        """
        with mock.patch(
            "ops.firstsetup.providers.asyncio.create_subprocess_exec",
            new_callable=mock.AsyncMock,
            return_value=completed(
                stdout_bytes=b'noise\n{"zai": "api_key", "openai-codex": "oauth"}'
            ),
        ):
            kinds = asyncio.run(providers.query_auth_kinds())
        self.assertEqual(kinds, {"zai": "api_key", "openai-codex": "oauth"})

    def test_probe_failure_raises(self) -> None:
        """A nonzero exit code raises with the code in the message.

        - the refusal names the registry and the exit code
        """
        with (
            mock.patch(
                "ops.firstsetup.providers.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=completed(exit_code=3),
            ),
            self.assertRaisesRegex(RuntimeError, r"auth-kind registry failed \(exit code 3\)"),
        ):
            asyncio.run(providers.query_auth_kinds())

    def test_empty_output_raises(self) -> None:
        """Empty output raises rather than reading as an empty registry.

        - silence is a broken registry, never a default-to-api_key verdict
        """
        with (
            mock.patch(
                "ops.firstsetup.providers.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=completed(),
            ),
            self.assertRaisesRegex(RuntimeError, r"auth-kind registry returned no output"),
        ):
            asyncio.run(providers.query_auth_kinds())


class GoogleFormValidationTests(unittest.TestCase):
    """The google form's client-id/secret shape rules.

    A malformed pair must never reach addoauth (the operator would get
    an opaque Django OAuth failure instead of a field message). Empty
    refuses like malformed — Back is the only skip.

    - test_rejects_empty_pair: both fields blank is a fill refusal
    - test_rejects_malformed_client_id: must look like
      1234567890-abc123.apps.googleusercontent.com
    - test_rejects_short_secret: Google secrets are ~35 chars, no spaces
    - test_accepts_well_formed_pair: the real shape passes
    """

    def test_rejects_empty_pair(self) -> None:
        """Both fields blank refuses with the fill message.

        - the message tells the operator to fill both fields
        """
        error = validate_google_values({"client_id": "", "client_secret": ""})
        assert error is not None
        self.assertIn("fill both client key and secret", error)

    def test_rejects_malformed_client_id(self) -> None:
        """A client key that isn't the apps.googleusercontent.com shape refuses.

        - the message shows the expected client-key shape
        """
        error = validate_google_values(
            {"client_id": "not-a-key", "client_secret": "GOCSPX-" + "x" * 28}
        )
        assert error is not None
        self.assertIn("apps.googleusercontent.com", error)

    def test_rejects_short_secret(self) -> None:
        """A too-short secret refuses (Google secrets are ~35 chars).

        - the message names the secret as the problem
        """
        error = validate_google_values(
            {"client_id": "1234567890-abc123.apps.googleusercontent.com", "client_secret": "short"}
        )
        assert error is not None
        self.assertIn("secret", error)

    def test_rejects_partial_fill(self) -> None:
        """Exactly one filled field of the pair refuses.

        - secret alone → the BOTH message
        - client key alone → the BOTH message
        """
        for values in (
            {"client_id": "", "client_secret": "GOCSPX-" + "x" * 28},
            {"client_id": "1234567890-abc123.apps.googleusercontent.com", "client_secret": ""},
        ):
            with self.subTest(values=values):
                error = validate_google_values(values)
                assert error is not None
                self.assertIn("BOTH", error)

    def test_accepts_well_formed_pair(self) -> None:
        """A well-formed pair passes.

        - the real Google shapes validate to None
        """
        ok = {
            "client_id": "1234567890-abc123.apps.googleusercontent.com",
            "client_secret": "GOCSPX-" + "x" * 28,
        }
        self.assertIsNone(validate_google_values(ok))


class UserFormValidationTests(unittest.TestCase):
    """The first-user form's validator: all three fields, or none.

    The user is created via createuser --superuser, so a bad shape
    would surface as a Django error; validation catches it first. A
    completely blank form refuses — Back is the skip.

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
        """A well-formed user passes; all-BLANK refuses (not a skip).

        - the three valid fields validate to None
        - the all-blank form refuses with the fill message
        """
        self.assertIsNone(validate_user_values(self.VALID))
        blank_error = validate_user_values({"first_name": "", "last_name": "", "email": ""})
        assert blank_error is not None
        self.assertIn("fill", blank_error)

    def test_rejects_bad_email(self) -> None:
        """An unparseable or over-long email refuses.

        - a missing @ or TLD refuses
        - the RFC forward-path limit (254) refuses
        """
        bad = dict(self.VALID, email="not-an-email")
        assert validate_user_values(bad) is not None
        long_email = "a" * 250 + "@x.io"
        assert validate_user_values(dict(self.VALID, email=long_email)) is not None

    def test_rejects_partial_fills(self) -> None:
        """Email without names refuses; names without email also refuses.

        - names missing → the message names the names
        - email missing → the message names the email
        """
        no_names = {"first_name": "", "last_name": "", "email": "jane@example.com"}
        error = validate_user_values(no_names)
        assert error is not None
        self.assertIn("name", error)
        no_email = {"first_name": "Jane", "last_name": "Doe", "email": ""}
        error = validate_user_values(no_email)
        assert error is not None  # partial fills refuse
        self.assertIn("email", error)

    def test_rejects_bad_name_shape(self) -> None:
        """Names must be letters (hyphen/apostrophe ok), starting with one.

        - digits refuse with the field named
        - an apostrophe survives (O'Brien)
        """
        error = validate_user_values(dict(self.VALID, first_name="123"))
        assert error is not None
        self.assertIn("first name", error)
        self.assertIsNone(validate_user_values(dict(self.VALID, last_name="O'Brien")))


class FailureDescriptionTests(unittest.TestCase):
    """describe_failure: one clear line for any failed command.

    A toast saying only "failed (exit code 3)" hides the cause; the helper
    carries the command's own last error line (a traceback, a psql
    error, a missing binary).

    - test_describe_failure_includes_command_output: command name,
      exit code, and the final non-empty output line
    """

    def test_rejects_bad_last_name_shape(self) -> None:
        """A malformed last name refuses naming the last name.

        - the message names the last-name field, not the first
        """
        error = validate_user_values(
            {
                "first_name": "Jane",
                "last_name": "123",
                "email": "jane@example.com",
            }
        )
        assert error is not None
        self.assertIn("last name", error)

    def test_describe_failure_includes_command_output(self) -> None:
        """The toast carries the command's own last error line.

        - the command name, the exit code, and the last output line all ride the message
        """
        message = _describe_failure(
            "createuser",
            1,
            "Traceback (most recent call last):\nValueError: bad email",
        )
        self.assertIn("createuser", message)
        self.assertIn("exit code 1", message)
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
        """Providers in the live registry's oauth set dispatch OAuthScreen.

        - registry oauth → oauth
        - registry api_key → api_key
        """
        auth_kinds = {"anthropic": "oauth", "zai": "api_key"}
        self.assertEqual(providers.auth_kind_of("anthropic", auth_kinds), "oauth")
        self.assertEqual(providers.auth_kind_of("zai", auth_kinds), "api_key")

    def test_unknown_kind_defaults_to_api_key(self) -> None:
        """A missing kinds registry or unknown id defaults to api_key.

        - no registry → api_key
        - empty registry → api_key
        """
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
        """Recording a user makes it configured with its display name.

        - is_configured flips and full_name renders
        - the login link round-trips
        """
        app = SetupApp()
        self.assertFalse(app.first_user.is_configured)
        app.record_first_user(
            first_name="Jane", last_name="Doe", email="jane@example.com", login_link="https://x/"
        )
        self.assertTrue(app.first_user.is_configured)
        self.assertEqual(app.first_user.full_name, "Jane Doe")
        self.assertEqual(app.first_user.login_link, "https://x/")

    def test_provider_verified_roundtrip(self) -> None:
        """Marking a provider verified exposes it (sorted).

        - unmarked reads False, marked reads True
        - verified_provider_ids lists the marked ids
        """
        app = SetupApp()
        self.assertFalse(app.is_provider_verified("zai"))
        app.mark_provider_verified("zai")
        self.assertTrue(app.is_provider_verified("zai"))
        self.assertEqual(app.verified_provider_ids(), ["zai"])

    def test_catalog_lookup(self) -> None:
        """provider_by_id finds rows; auth kind defaults to api_key.

        - a known id returns its row
        - an unknown id returns None
        - auth kind prefers the registry, defaulting to api_key
        """
        app = SetupApp()
        app.load_provider_catalog(FAKE_PROVIDERS, {"openai-codex": "oauth"})
        self.assertEqual(app.provider_by_id("zai")["name"], "Z.AI")  # type: ignore[index]
        self.assertIsNone(app.provider_by_id("nope"))
        self.assertEqual(app.provider_auth_kind("openai-codex"), "oauth")
        self.assertEqual(app.provider_auth_kind("zai"), "api_key")


class SetupCommandTests(unittest.TestCase):
    """The ops.cli verb.

    The only seam between the CLI dispatch and the TUI app.

    - test_run_boots_the_app: SetupCommand.run runs SetupApp
    """

    def test_run_boots_the_app(self) -> None:
        """The verb boots SetupApp.run.

        - exactly one App.run call
        """
        with mock.patch("ops.firstsetup.app.SetupApp.run") as run:
            SetupCommand.run({}, [])
        run.assert_called_once()


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
        """A new credential merges into the store; others survive.

        - the read returns the existing store (cat)
        - the write receives the merged store as compact JSON
        - the other provider's credential is intact in what was written
        """
        existing = {"openai-codex": {"type": "oauth", "access": "keep-me"}}
        read_proc = completed(stdout_bytes=json.dumps(existing).encode())
        write_proc = completed()
        exec_mock = mock.AsyncMock(side_effect=[read_proc, write_proc])
        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with mock.patch("ops.firstsetup.authstore.asyncio.create_subprocess_exec", exec_mock):
            asyncio.run(store.set_credential("zai", {"type": "api_key", "key": "sk-new"}))
        written = write_proc.communicate.await_args.args[0]
        result = json.loads(written.decode())
        self.assertEqual(result["openai-codex"]["access"], "keep-me")
        self.assertEqual(result["zai"]["key"], "sk-new")

    def test_write_failure_raises(self) -> None:
        """A nonzero write exits loudly instead of returning a bare rc."""
        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with (
            mock.patch(
                "ops.firstsetup.authstore.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=completed(exit_code=1),
            ),
            self.assertRaisesRegex(
                RuntimeError, r"^credential store write failed \(exit code 1\)$"
            ),
        ):
            asyncio.run(store.write({}))

    def test_read_missing_store_is_empty(self) -> None:
        """A fresh machine (cat: No such file) reads as {} — not an error.

        - only the expected fresh-state stderr reads as empty
        """
        missing = completed(
            exit_code=1,
            stderr_bytes=b"cat: /home/debian/.pi/agent/auth.json: No such file or directory",
        )
        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with mock.patch(
            "ops.firstsetup.authstore.asyncio.create_subprocess_exec",
            new_callable=mock.AsyncMock,
            return_value=missing,
        ):
            self.assertEqual(asyncio.run(store.read()), {})

    def test_read_other_failure_raises(self) -> None:
        """A permission/sudo failure surfaces.

        A silent empty store would let the next write clobber every
        credential that could not be read.
        """
        denied = completed(exit_code=1, stderr_bytes=b"sudo: a password is required")
        store = AuthStore("/home/debian/.pi/agent/auth.json")
        with (
            mock.patch(
                "ops.firstsetup.authstore.asyncio.create_subprocess_exec",
                new_callable=mock.AsyncMock,
                return_value=denied,
            ),
            self.assertRaisesRegex(
                RuntimeError, r"^credential store read failed: sudo: a password is required$"
            ),
        ):
            asyncio.run(store.read())
