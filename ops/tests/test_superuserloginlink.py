"""Tests for ops/superuserloginlink.py — the desmosuperuserloginlink command.

No Django, no VM. The djangomanage verbs are scripted through ``_run``;
tests assert the printed text, the commands run, and the exit code.

Class inventory:

- FirstSuperuserTests, ``first_superuser()`` reads the oldest superuser
  off one listusers page
- MainTests, the whole command — a link, or the way to make a superuser
- SetupVerbsTests, the two verbs desmosetup calls: create the first
  superuser, mint the login link
- SuperuserDataclassTests, the name the link line prints
"""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from typing import TYPE_CHECKING, ClassVar, cast
from unittest import mock

from ops import superuserloginlink

if TYPE_CHECKING:
    from collections.abc import Iterator

NO_SUPERUSER = {"page": 1, "pages": 1, "total": 0, "users": []}
JANE_ROW = {"first": "Jane", "last": "Doe", "email": "jane@example.com"}
JOHN_ROW = {"first": "John", "last": "Smith", "email": "john@example.com"}
ONE_SUPERUSER = {"page": 1, "pages": 1, "total": 1, "users": [JANE_ROW]}
TWO_SUPERUSERS = {"page": 1, "pages": 1, "total": 2, "users": [JANE_ROW, JOHN_ROW]}
CREATED = {"created": True, "email": "jane@example.com"}
LINK: dict[str, object] = {"login_url": "https://example.test/login-with-secret/abc/"}
JANE = superuserloginlink.Superuser(first="Jane", last="Doe", email="jane@example.com")
LIST = ("listusers", "--superusers", "--page", "1")
CREATE = (
    "createuser",
    "Jane",
    "Doe",
    "jane@example.com",
    "--superuser",
    "--if-absent",
)


def call(*argv: str, prints: dict[str, object] | None = None, fails: str = "") -> dict[str, object]:
    """Describe one scripted djangomanage call: its argv and what it answered.

    ``prints`` is the JSON line it printed; ``fails`` is the last stderr
    line of a call that exited 1.
    """
    return {"argv": argv, "prints": prints, "fails": fails}


def scripted(test: unittest.TestCase, script: list[dict[str, object]]) -> mock.Mock:
    """Return an ``_run`` stand-in that answers exactly the scripted calls.

    Each call must match the next scripted argv. Every scripted call must
    be used, so a wrong command fails the test instead of silently
    answering.
    """
    queue: Iterator[dict[str, object]] = iter(script)

    def answer(*argv: str) -> tuple[int, str, str]:
        """Answer one call with its scripted JSON line, or its scripted failure."""
        step = next(queue)
        expected = cast("tuple[str, ...]", step["argv"])
        test.assertEqual(argv, expected, "unexpected call")
        if step["fails"]:
            return 1, "", f"{step['fails']}\n"
        return 0, json.dumps(step["prints"]) + "\n", ""

    test.addCleanup(lambda: test.assertEqual(list(queue), [], "scripted call never made"))
    return mock.Mock(side_effect=answer)


def run_main(test: unittest.TestCase, script: list[dict[str, object]]) -> tuple[int, str]:
    """Run main() with scripted djangomanage calls.

    Returns the exit code and what was printed.
    """
    out = io.StringIO()
    with (
        mock.patch.object(superuserloginlink, "_run", scripted(test, script)),
        contextlib.redirect_stdout(out),
    ):
        code = superuserloginlink.main()
    return code, out.getvalue()


class FirstSuperuserTests(unittest.TestCase):
    """``first_superuser()`` reads the oldest superuser off one listusers page.

    Tests script listusers' JSON line and compare what comes back.

    - test_oldest_row_comes_back, the first row becomes a Superuser
    - test_only_the_first_page_is_asked_for, exactly one listusers call
    - test_empty_store_reads_none, zero superusers become None
    - test_no_users_list_raises, a listing without rows is a SetupError
    """

    def test_oldest_row_comes_back(self) -> None:
        """The first row of the listing becomes a Superuser.

        - listusers runs with --superusers
        - later rows are never looked at
        """
        run = scripted(self, [call(*LIST, prints=TWO_SUPERUSERS)])
        with mock.patch.object(superuserloginlink, "_run", run):
            self.assertEqual(superuserloginlink.first_superuser(), JANE)

    def test_only_the_first_page_is_asked_for(self) -> None:
        """Exactly one listusers call is made, for page 1.

        - no page is walked: the answer is the first row
        """
        run = scripted(self, [call(*LIST, prints=ONE_SUPERUSER)])
        with mock.patch.object(superuserloginlink, "_run", run):
            superuserloginlink.first_superuser()
        self.assertEqual(run.call_count, 1)

    def test_empty_store_reads_none(self) -> None:
        """Zero superusers become None.

        - the command then says how to make one
        """
        run = scripted(self, [call(*LIST, prints=NO_SUPERUSER)])
        with mock.patch.object(superuserloginlink, "_run", run):
            self.assertIsNone(superuserloginlink.first_superuser())

    def test_no_users_list_raises(self) -> None:
        """A listing without a users list is a SetupError naming the command.

        - nothing is guessed
        """
        run = scripted(self, [call(*LIST, prints={"page": 1, "pages": 1})])
        with (
            mock.patch.object(superuserloginlink, "_run", run),
            self.assertRaisesRegex(
                superuserloginlink.SetupError, r"^listusers printed no users list$"
            ),
        ):
            superuserloginlink.first_superuser()


class MainTests(unittest.TestCase):
    """The whole command: a link, or the way to make a superuser.

    Tests script every djangomanage call and read what main() prints.

    - test_existing_superuser_gets_a_link, no question, just the link
    - test_other_superusers_are_ignored, the link is minted for the
      first-listed superuser only
    - test_no_superuser_says_how_to_make_one, nothing is created; exit 1
    - test_djangomanage_failure_exits_1, a failing verb exits 1 with its line
    """

    MINT_JANE = call("makeloginlink", "jane@example.com", "--minutes", "1440", prints=LINK)

    def test_existing_superuser_gets_a_link(self) -> None:
        """One superuser already exists: just the link.

        - the line carries first name, last name and email
        - the link line carries the 24-hour note
        - createuser never runs: exactly two djangomanage calls
        """
        run = scripted(self, [call(*LIST, prints=ONE_SUPERUSER), self.MINT_JANE])
        out = io.StringIO()
        with (
            mock.patch.object(superuserloginlink, "_run", run),
            contextlib.redirect_stdout(out),
        ):
            code = superuserloginlink.main()
        self.assertEqual(code, 0)
        self.assertIn("Superuser: Jane Doe (jane@example.com)", out.getvalue())
        self.assertIn(str(LINK["login_url"]), out.getvalue())
        self.assertIn("valid 24 hours, single use", out.getvalue())
        self.assertEqual(run.call_count, 2)

    def test_other_superusers_are_ignored(self) -> None:
        """The link is minted for the first-listed superuser only.

        - nobody is asked to pick
        """
        code, out = run_main(self, [call(*LIST, prints=TWO_SUPERUSERS), self.MINT_JANE])
        self.assertEqual(code, 0)
        self.assertIn("Superuser: Jane Doe (jane@example.com)", out)
        self.assertNotIn("john@example.com", out)

    def test_no_superuser_says_how_to_make_one(self) -> None:
        """No superuser: the command says how to make one, and exits 1.

        - it creates nothing: listusers is the only djangomanage call
        - no link is printed
        """
        run = scripted(self, [call(*LIST, prints=NO_SUPERUSER)])
        out = io.StringIO()
        with (
            mock.patch.object(superuserloginlink, "_run", run),
            contextlib.redirect_stdout(out),
        ):
            code = superuserloginlink.main()
        self.assertEqual(code, 1)
        self.assertIn(superuserloginlink.NO_SUPERUSER_MESSAGE, out.getvalue())
        self.assertNotIn(str(LINK["login_url"]), out.getvalue())
        self.assertEqual(run.call_count, 1)

    def test_djangomanage_failure_exits_1(self) -> None:
        """A failing listusers exits 1 with its own last error line.

        - the operator never sees a link
        """
        broken = call(*LIST, fails="database is unreachable")
        code, out = run_main(self, [broken])
        self.assertEqual(code, 1)
        self.assertIn("listusers failed (exit code 1): database is unreachable", out)
        self.assertNotIn(str(LINK["login_url"]), out)


class SetupVerbsTests(unittest.TestCase):
    """The two verbs desmosetup calls without prompts: create_first and login_link.

    Tests script every djangomanage call and read what comes back.

    - test_superuser_is_created_without_looking_first, createuser runs
      with --superuser --if-absent and the given details; listusers
      never runs
    - test_existing_email_refuses, an email that already exists raises
      with the way forward
    - test_link_is_minted_for_24_hours, makeloginlink runs with --minutes
      1440 and its URL comes back
    - test_missing_url_raises, an answer with no login_url raises
    """

    def test_superuser_is_created_without_looking_first(self) -> None:
        """The createuser call runs as a superuser with the given details; no one asks first.

        - the first run is the only run: listusers never runs
        - the given details come back as the new superuser
        """
        run = scripted(self, [call(*CREATE, prints=CREATED)])
        with mock.patch.object(superuserloginlink, "_run", run):
            created = superuserloginlink.create_first("Jane", "Doe", "jane@example.com")
        self.assertEqual(created, JANE)

    def test_existing_email_refuses(self) -> None:
        """An email that already exists raises with the way forward.

        - the message names promotetosuperuser
        """
        skipped = call(*CREATE, prints={"created": False, "email": "jane@example.com"})
        run = scripted(self, [skipped])
        with (
            mock.patch.object(superuserloginlink, "_run", run),
            self.assertRaisesRegex(
                superuserloginlink.SetupError,
                r"^jane@example\.com already exists, so no superuser was created\. Run these two lines:",
            ),
        ):
            superuserloginlink.create_first("Jane", "Doe", "jane@example.com")

    def test_link_is_minted_for_24_hours(self) -> None:
        """The makeloginlink call runs with --minutes 1440, and its URL comes back.

        - the lookup is by email
        """
        run = scripted(
            self, [call("makeloginlink", "jane@example.com", "--minutes", "1440", prints=LINK)]
        )
        with mock.patch.object(superuserloginlink, "_run", run):
            url = superuserloginlink.login_link("jane@example.com")
        self.assertEqual(url, LINK["login_url"])

    def test_missing_url_raises(self) -> None:
        """An answer with no login_url raises.

        - the message names the command that printed it
        """
        run = scripted(
            self, [call("makeloginlink", "jane@example.com", "--minutes", "1440", prints={})]
        )
        with (
            mock.patch.object(superuserloginlink, "_run", run),
            self.assertRaisesRegex(
                superuserloginlink.SetupError, r"^makeloginlink printed no login_url$"
            ),
        ):
            superuserloginlink.login_link("jane@example.com")


class SuperuserDataclassTests(unittest.TestCase):
    """The Superuser row's display name.

    The link line prints this name, so a row with blank names must still
    show something sensible.

    - test_name_is_first_and_last, a filled row shows both names
    - test_name_falls_back_to_email, blank names show the email
    """

    ROWS: ClassVar[list[superuserloginlink.Superuser]] = [JANE]

    def test_name_is_first_and_last(self) -> None:
        """A filled row shows both names.

        - separated by one space
        """
        self.assertEqual(self.ROWS[0].name, "Jane Doe")

    def test_name_falls_back_to_email(self) -> None:
        """Blank names show the email.

        - nothing else is invented
        """
        blank = superuserloginlink.Superuser(first="", last="", email="jane@example.com")
        self.assertEqual(blank.name, "jane@example.com")


if __name__ == "__main__":
    unittest.main()
