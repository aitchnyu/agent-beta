"""Tests for ops/piauth.py — the pi engine behind desmosetup.

No Textual pilots (operator decision 2026-11-20). Each verb runs its own
commands; tests script the subprocess spawn and assert what comes back.
pi's own files are exercised on a temp directory.

Class inventory:

- ParseTests, the registry's JSON becomes plain Python
- ParseModelTableTests, the model table's column positions come from its
  header, never assumed
- LoginCommandTests, pi's own login command per provider
- PiFilesTests, pi's credential file and the analytics opt-out in its settings
- StoreKeyTests, a typed API key lands in pi's credential file, private
- LoginOnTerminalTests, pi's own login on the terminal for a sign-in-only provider
- CatalogTests, every provider comes back with how it authenticates
- ListModelsTests, a provider's live list, read after authentication
"""

from __future__ import annotations

import asyncio
import json
import signal
import stat
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest import mock

from ops import piauth

if TYPE_CHECKING:
    from collections.abc import Callable

# Shaped like pi 1.6.1's --list-models table: the columns as captured on
# a machine with one zai key (Nov 26). The rows are a sample for the parser.
MODELS_TABLE = (
    "provider       model              context  max-out  thinking  images\n"
    "zai            glm-4.7            204.8K   131.1K   yes       no\n"
    "zai            glm-5.3            1M       131.1K   yes       yes\n"
    "zai            glm-5.4            1M       131.1K   yes       yes\n"
    "openai-codex   gpt-5-codex        400K     128K     yes       no\n"
)
REGISTRY_JSON = json.dumps(
    {
        "zai": {"oauth": False, "api_key": True},
        "openai": {"oauth": True, "api_key": True},
    }
)


def completed(
    exit_code: int = 0, stdout_bytes: bytes = b"", stderr_bytes: bytes = b""
) -> mock.AsyncMock:
    """Return a finished subprocess: communicate() → (out, err), rc set."""
    proc = mock.AsyncMock()
    proc.communicate.return_value = (stdout_bytes, stderr_bytes)
    proc.returncode = exit_code
    return proc


def spawn_with(*responses: mock.AsyncMock) -> mock.AsyncMock:
    """Return a create_subprocess_exec stand-in answering scripted results."""
    return mock.AsyncMock(side_effect=list(responses))


class ParseTests(unittest.TestCase):
    """The registry's JSON becomes plain Python.

    Tests feed the exact text the node registry prints and compare whole structures.

    - test_registry_json, the registry's flags become booleans per provider
    """

    def test_registry_json(self) -> None:
        """Each provider's oauth and api_key flags come back as booleans.

        - a false flag stays false
        """
        self.assertEqual(
            piauth.parse_auth_support(REGISTRY_JSON),
            {
                "zai": {"oauth": False, "api_key": True},
                "openai": {"oauth": True, "api_key": True},
            },
        )


class ParseModelTableTests(unittest.TestCase):
    """The model table's column positions come from its header.

    Tests feed whole tables and compare the model ids per provider.

    - test_ids_in_listed_order, each provider's model ids come back in
      table order
    - test_columns_follow_the_header, a reordered header still lands each
      cell in the right field
    - test_no_header_no_rows, a table without a header parses to {}
    """

    def test_ids_in_listed_order(self) -> None:
        """Each provider's model ids come back in table order.

        - other providers' rows never mix in
        """
        table = piauth.parse_model_table(MODELS_TABLE)
        self.assertEqual(table["zai"], ["glm-4.7", "glm-5.3", "glm-5.4"])
        self.assertEqual(table["openai-codex"], ["gpt-5-codex"])

    def test_columns_follow_the_header(self) -> None:
        """A reordered header (model, provider, thinking, context) parses the same ids.

        - each id comes from its named column
        """
        table = piauth.parse_model_table(
            "model         provider  thinking  context\n"
            "glm-5.3       zai       yes       1M\n"
            "glm-5.2       zai       no        1M\n"
        )
        self.assertEqual(table["zai"], ["glm-5.3", "glm-5.2"])

    def test_no_header_no_rows(self) -> None:
        """A table with no header line parses to {}.

        - nothing is guessed from column positions
        """
        self.assertEqual(piauth.parse_model_table("zai  glm-5.3  1M  131.1K  yes  no\n"), {})


class LoginCommandTests(unittest.TestCase):
    """pi's own login command per provider.

    Tests read the argv each provider builds.

    - test_key_provider_gets_api_key, a provider that takes a key gets
      --api-key, so pi asks for it itself
    - test_provider_with_both_starts_with_the_key, key and sign-in both
      offered still starts with --api-key
    - test_sign_in_only_provider_gets_no_browser, a provider with only a
      sign-in gets --no-browser
    """

    def test_key_provider_gets_api_key(self) -> None:
        """A key-only provider gets --api-key.

        - the command is pi auth login <provider> --api-key
        """
        provider = piauth.Provider(id="zai", api_key=True)
        self.assertEqual(
            piauth.login_command(provider), ["pi", "auth", "login", "zai", "--api-key"]
        )

    def test_provider_with_both_starts_with_the_key(self) -> None:
        """A provider offering both a key and a sign-in starts with the key.

        - --api-key, not --no-browser
        """
        provider = piauth.Provider(id="openai", oauth=True, api_key=True)
        self.assertEqual(
            piauth.login_command(provider),
            ["pi", "auth", "login", "openai", "--api-key"],
        )

    def test_sign_in_only_provider_gets_no_browser(self) -> None:
        """A sign-in-only provider gets --no-browser.

        - the remote machine has no browser to open
        """
        provider = piauth.Provider(id="github-copilot", oauth=True)
        self.assertEqual(
            piauth.login_command(provider),
            ["pi", "auth", "login", "github-copilot", "--no-browser"],
        )


class PiFilesTests(unittest.TestCase):
    """pi's credential and settings files merge without loss.

    Tests point AUTH_JSON and SETTINGS_JSON at a temp directory and
    read the files back after each write.

    - test_opt_out_keeps_pi_settings, the opt-out merges into pi's indented
      settings file and leaves the rest alone
    - test_opt_out_on_a_fresh_machine, a missing settings file is created
      holding the opt-out alone
    - test_missing_file_reads_empty, a missing file is {} (a fresh machine)
    - test_unparsable_file_raises_json_error, a file that is not JSON
      raises the raw decoder error and stays untouched
    - test_json_array_refuses, a JSON array raises, naming the file
    """

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for patch in (
            mock.patch.object(piauth, "AUTH_JSON", root / "auth.json"),
            mock.patch.object(piauth, "SETTINGS_JSON", root / "settings.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def test_opt_out_keeps_pi_settings(self) -> None:
        """The opt-out merges into pi's indented settings file.

        - pi's own settings survive: nothing about models is written
        - an existing file keeps its mode
        """
        piauth.SETTINGS_JSON.write_text(
            json.dumps({"lastChangelogVersion": "1.6.1"}, indent=2), encoding="utf-8"
        )
        piauth.SETTINGS_JSON.chmod(0o664)
        piauth.opt_out_of_analytics()
        saved = json.loads(piauth.SETTINGS_JSON.read_text())
        self.assertEqual(saved, {"lastChangelogVersion": "1.6.1", "enableAnalytics": False})
        self.assertIn("\n  ", piauth.SETTINGS_JSON.read_text())
        self.assertEqual(stat.S_IMODE(piauth.SETTINGS_JSON.stat().st_mode), 0o664)

    def test_opt_out_on_a_fresh_machine(self) -> None:
        """A missing settings file is created, holding the opt-out alone.

        - no model keys: pi picks its own model
        - a settings file means pi never shows its first-time dialog
        """
        piauth.opt_out_of_analytics()
        self.assertEqual(json.loads(piauth.SETTINGS_JSON.read_text()), {"enableAnalytics": False})

    def test_missing_file_reads_empty(self) -> None:
        """A missing file reads as {} — the fresh machine.

        - nothing is guessed
        """
        self.assertEqual(piauth.read_json(piauth.AUTH_JSON), {})

    def test_unparsable_file_raises_json_error(self) -> None:
        """A file that is not JSON raises the raw decoder error, and stays untouched.

        - no PiError wraps it: the handler in setup.py prints the traceback
        - the file's content is exactly what it was
        """
        piauth.SETTINGS_JSON.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(json.JSONDecodeError, r"^Expecting property name"):
            piauth.opt_out_of_analytics()
        self.assertEqual(piauth.SETTINGS_JSON.read_text(), "{not json")

    def test_json_array_refuses(self) -> None:
        """A JSON array raises, naming the file and the refusal to overwrite.

        - nothing is written
        """
        piauth.AUTH_JSON.write_text("[1, 2]", encoding="utf-8")
        with self.assertRaisesRegex(
            piauth.PiError,
            r"^auth\.json is not a JSON object — fix it by hand; refusing to overwrite it$",
        ):
            piauth.read_json(piauth.AUTH_JSON)
        self.assertEqual(piauth.AUTH_JSON.read_text(), "[1, 2]")


class StoreKeyTests(unittest.TestCase):
    """A typed API key lands in pi's credential file, in pi's own shape.

    Tests point AUTH_JSON at a temp directory and read the file back.

    - test_key_is_saved_in_pi_s_shape, {type: "api_key", key} under the
      provider id
    - test_other_credentials_survive, an entry already there stays beside
      the new one, and an empty key is replaced
    - test_file_is_private, the directory 0700 and the file 0600
    """

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        patch = mock.patch.object(piauth, "AUTH_JSON", Path(temp.name) / "agent" / "auth.json")
        patch.start()
        self.addCleanup(patch.stop)

    def test_key_is_saved_in_pi_s_shape(self) -> None:
        """The key is saved as pi's own login writes it.

        - a missing file is created
        """
        piauth.store_key("zai", "sk-pilot")
        self.assertEqual(
            json.loads(piauth.AUTH_JSON.read_text()),
            {"zai": {"type": "api_key", "key": "sk-pilot"}},
        )

    def test_other_credentials_survive(self) -> None:
        """An entry already there stays beside the new one, and an empty key is replaced.

        - the key prompt left empty once wrote that empty key
        """
        piauth.AUTH_JSON.parent.mkdir(mode=0o700)
        piauth.AUTH_JSON.write_text(
            json.dumps(
                {"zai": {"type": "api_key", "key": ""}, "openai": {"type": "oauth", "access": "x"}}
            )
        )
        piauth.store_key("zai", "sk-pilot")
        saved = json.loads(piauth.AUTH_JSON.read_text())
        self.assertEqual(saved["zai"], {"type": "api_key", "key": "sk-pilot"})
        self.assertEqual(saved["openai"], {"type": "oauth", "access": "x"})

    def test_file_is_private(self) -> None:
        """The directory is 0700 and the file 0600.

        - an existing file loses any wider mode
        """
        piauth.store_key("zai", "sk-pilot")
        self.assertEqual(stat.S_IMODE(piauth.AUTH_JSON.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(piauth.AUTH_JSON.stat().st_mode), 0o600)
        piauth.AUTH_JSON.chmod(0o644)
        piauth.store_key("zai", "sk-other")
        self.assertEqual(stat.S_IMODE(piauth.AUTH_JSON.stat().st_mode), 0o600)


class LoginOnTerminalTests(unittest.TestCase):
    """pi's own login on the terminal, for a provider that only signs in.

    Tests stand in for the process and read SIGINT's disposition around it.

    - test_argv_is_pi_s_login, pi auth login <provider> --no-browser, in the
      repo
    - test_ctrl_c_reaches_pi_alone, SIGINT is ignored here while pi runs,
      and restored after
    - test_disposition_restored_when_pi_fails_to_start
    """

    CODEX = piauth.Provider(id="openai-codex", oauth=True)

    def test_argv_is_pi_s_login(self) -> None:
        """The command is pi auth login <provider> --no-browser, run in the repo.

        - pi starts with SIGINT's default
        """
        with mock.patch("subprocess.run") as login:
            piauth.login_on_terminal(self.CODEX)
        login.assert_called_once_with(
            ["pi", "auth", "login", "openai-codex", "--no-browser"],
            cwd=piauth.REPO_ROOT,
            check=False,
            preexec_fn=piauth._default_sigint,
        )

    def test_ctrl_c_reaches_pi_alone(self) -> None:
        """SIGINT is ignored here while pi runs, and restored after.

        - pi is handed SIGINT's default, since a child inherits an ignore
        """
        before = signal.getsignal(signal.SIGINT)
        seen: list[object] = []

        def run(argv: list[str], **kwargs: object) -> mock.Mock:
            """Record SIGINT's disposition around the call."""
            self.assertEqual(argv, ["pi", "auth", "login", "openai-codex", "--no-browser"])
            seen.append(signal.getsignal(signal.SIGINT))
            cast("Callable[[], None]", kwargs["preexec_fn"])()
            seen.append(signal.getsignal(signal.SIGINT))
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=run):
            piauth.login_on_terminal(self.CODEX)
        self.assertEqual(seen, [signal.SIG_IGN, signal.SIG_DFL])
        self.assertIs(signal.getsignal(signal.SIGINT), before)

    def test_disposition_restored_when_pi_fails_to_start(self) -> None:
        """A login that cannot start still restores SIGINT.

        - the error is not swallowed
        """
        before = signal.getsignal(signal.SIGINT)
        with (
            mock.patch("subprocess.run", side_effect=FileNotFoundError("no pi")),
            self.assertRaisesRegex(FileNotFoundError, r"^no pi$"),
        ):
            piauth.login_on_terminal(self.CODEX)
        self.assertIs(signal.getsignal(signal.SIGINT), before)


class CatalogTests(unittest.TestCase):
    """Every provider comes back with how it authenticates.

    Tests script the one node call and compare the whole catalog.

    - test_catalog, ids and capabilities from the registry at its
      hardcoded path, in one call
    - test_registry_failure_raises, an unreadable registry raises with its
      own last line
    - test_registry_bad_json_propagates, a registry that prints no JSON
      raises the raw decoder error
    """

    def test_catalog(self) -> None:
        """The catalog carries both ways to authenticate per provider.

        - zai takes a key only; openai takes a key and a sign-in
        - one node call imports pi's library entry at its hardcoded path
        """
        exec_mock = spawn_with(completed(stdout_bytes=REGISTRY_JSON.encode()))
        with mock.patch("ops.piauth.asyncio.create_subprocess_exec", exec_mock) as spawn:
            self.assertEqual(
                asyncio.run(piauth.catalog()),
                [
                    piauth.Provider(id="zai", oauth=False, api_key=True),
                    piauth.Provider(id="openai", oauth=True, api_key=True),
                ],
            )
        self.assertEqual(len(spawn.await_args_list), 1)
        assert spawn.await_args is not None
        self.assertEqual(spawn.await_args.args[:3], ("node", "--input-type=module", "-e"))
        self.assertIn(
            f'import * as pi from "{piauth.PI_ENTRY}";',
            spawn.await_args.args[3],
        )

    def test_registry_failure_raises(self) -> None:
        """A failing node registry raises — defaulting would offer the wrong way in.

        - the message is the registry command's own failure line
        """
        exec_mock = spawn_with(completed(exit_code=1, stderr_bytes=b"node: cannot find module"))
        with (
            mock.patch("ops.piauth.asyncio.create_subprocess_exec", exec_mock),
            self.assertRaisesRegex(
                piauth.PiError, r"^auth registry failed \(exit code 1\): node: cannot find module$"
            ),
        ):
            asyncio.run(piauth.catalog())

    def test_registry_bad_json_propagates(self) -> None:
        """A registry that prints no JSON raises the raw decoder error.

        - nothing wraps it
        """
        exec_mock = spawn_with(completed(stdout_bytes=b"not json"))
        with (
            mock.patch("ops.piauth.asyncio.create_subprocess_exec", exec_mock),
            self.assertRaisesRegex(json.JSONDecodeError, r"^Expecting value"),
        ):
            asyncio.run(piauth.catalog())


class ListModelsTests(unittest.TestCase):
    """A provider's live list, read after authentication.

    Tests script pi --list-models and compare the model ids.

    - test_ids_in_listed_order, every model of the provider comes back in
      table order
    - test_absent_provider_is_empty, no row means []
    - test_listing_failure_raises, a failed listing raises with pi's last line
    """

    def test_ids_in_listed_order(self) -> None:
        """The provider's own model ids come back in table order.

        - pi --list-models is the command, run in a session of its own:
          no signal from the terminal reaches it
        """
        exec_mock = spawn_with(completed(stdout_bytes=MODELS_TABLE.encode()))
        with mock.patch("ops.piauth.asyncio.create_subprocess_exec", exec_mock) as spawn:
            models = asyncio.run(piauth.list_models("zai"))
        self.assertEqual(models, ["glm-4.7", "glm-5.3", "glm-5.4"])
        assert spawn.await_args is not None
        self.assertEqual(spawn.await_args.args, ("pi", "--list-models"))
        self.assertIs(spawn.await_args.kwargs["start_new_session"], True)

    def test_absent_provider_is_empty(self) -> None:
        """A provider absent from the table reads as [].

        - no error: an authenticated neighbor's rows are simply not its own
        """
        exec_mock = spawn_with(completed(stdout_bytes=MODELS_TABLE.encode()))
        with mock.patch("ops.piauth.asyncio.create_subprocess_exec", exec_mock):
            self.assertEqual(asyncio.run(piauth.list_models("together")), [])

    def test_listing_failure_raises(self) -> None:
        """A failed listing raises with pi's own last error line.

        - the regex pins the raise to pi --list-models
        """
        exec_mock = spawn_with(completed(exit_code=1, stderr_bytes=b"no credentials"))
        with (
            mock.patch("ops.piauth.asyncio.create_subprocess_exec", exec_mock),
            self.assertRaisesRegex(
                piauth.PiError, r"^pi --list-models failed \(exit code 1\): no credentials$"
            ),
        ):
            asyncio.run(piauth.list_models("zai"))


if __name__ == "__main__":
    unittest.main()
