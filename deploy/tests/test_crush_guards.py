"""Unit tests for the Crush PreToolUse guard hooks (deploy/crush_*_guard.py).

The hooks are executed as subprocesses with CRUSH_TOOL_INPUT_* env vars set —
the same contract Crush uses (stdout JSON = allow, exit 2 + stderr = deny,
silent exit 0 = fall through to the permission prompt).

Run: uv run python -m unittest discover -s deploy/tests -v
"""

import json
import os
import subprocess
import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent


def run_hook(script: str, **env: str) -> subprocess.CompletedProcess[str]:
    """Run one guard hook with the given CRUSH_* env vars, capture everything."""
    return subprocess.run(
        [str(DEPLOY / script)],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        check=False,
    )


class GuardAssertions(unittest.TestCase):
    """Shared three-outcome assertions for the hook protocol."""

    def assert_allows(self, proc: subprocess.CompletedProcess[str]) -> None:
        """Exit 0 + {"decision": "allow"} on stdout = runs unprompted."""
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout or ""), {"decision": "allow"})

    def assert_prompts(self, proc: subprocess.CompletedProcess[str]) -> None:
        """Silent exit 0 = no opinion; Crush shows the permission prompt."""
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def assert_denies(self, proc: subprocess.CompletedProcess[str]) -> None:
        """Exit 2 + a stderr reason = blocked; the model sees the reason."""
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(proc.stderr)


class BashGuardAllows(GuardAssertions):
    """The bash hook auto-allows the ported allowlist, per section.

    - test_exact_forms, exact allowlist entries run unprompted
    - test_prefix_forms, `base args...` forms of the prefix rules run unprompted
    - test_bare_prefix_bases, the bare base of each prefix rule (e.g. `git diff`) runs unprompted
    - test_scratch_loop_compound, the scratch-loop compounds (bare AND parenthesized) run unprompted
    - test_compound_generalizes, any compound whose sections are ALL allowlisted runs unprompted
      (shlex sections — not just the sanctioned forms)
    - test_pipe_of_allowed, a pipe of two allowlisted commands runs unprompted
    - test_export_form, `export VAR=VAL && <allowed>` runs unprompted; bare/`export`-only too
    - test_quoted_operator_is_arg, a quoted `&&` is an argument, not an operator
      — still prefix-allowed
    """

    def test_exact_forms(self) -> None:
        for cmd in (
            "pwd",
            "ls -la",
            "cd ../scratch",
            "npm run build",
            "rm -rf scratch",
            "git ls-files",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_prefix_forms(self) -> None:
        for cmd in (
            "ls -la /srv/app",
            "./run test accounts",
            "./run djangomanage makemigrations ourapp",
            "./run djangomanage findstatic djangoapp/main.js",
            "cd scratch subdir",
            "git diff HEAD~1",
            "git blame README.md",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_bare_prefix_bases(self) -> None:
        for cmd in ("git diff", "git log", "git show", "cd scratch", "./run djangomanage migrate"):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_scratch_loop_compound(self) -> None:
        for cmd in (
            "cd scratch && ./run checkscratch",
            "cd ../scratch && ./run checkscratch",
            "( cd scratch && ./run checkscratch )",
            "( cd ../scratch && ./run checkscratch )",
            "cd ../scratch && git diff",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_compound_generalizes(self) -> None:
        for cmd in (
            "cd ../scratch && git diff HEAD~1",  # extra args — every section still allowed
            "cd ../scratch && git status && git diff",
            "git log; git show",
            "./run typecheck && ./run lintfix",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_pipe_of_allowed(self) -> None:
        self.assert_allows(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status | pwd")
        )

    def test_export_form(self) -> None:
        for cmd in (
            "export COPYFILE_DISABLE=1 && ./run test accounts",
            "export RUN_PROJECT_TESTS=1 && ./run checkscratch",
            "export FOO=1 BAR=2 && git status",  # multiple assignments
            "export FOO",  # bare name export — harmless
            "export",  # no-op
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_quoted_operator_is_arg(self) -> None:
        self.assert_allows(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="./run test 'a && b'")
        )

    def test_rm_with_args_prompts(self) -> None:
        # Only the BARE `rm -rf scratch` / `rm -rf ../scratch` forms are
        # allowlisted (ALLOW_EXACT); any operands prompt — `./run cleanscratch`
        # is the preferred scratch-removal command anyway.
        for cmd in (
            "rm -rf scratch/a",
            "rm -rf scratch/a scratch/b",
            "rm -rf scratch/*",
            "rm -rf ../scratch/x",
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))


class BashGuardFailsClosed(GuardAssertions):
    """Compound verdicts are the strictest section verdict (prompt, never deny).

    - test_compound_prompts, one unallowlisted section in a compound prompts
    - test_pipe_prompts, a pipe into an unallowlisted command prompts
    - test_semicolon_prompts, `a; b` with `b` unknown prompts
    - test_redirect_prompts, redirects (`>`, `>>`, `2>&1`) prompt their section
    - test_substitution_prompts, `$(...)` and backticks prompt
    - test_newline_prompts, multi-line commands are split like `;` — unknown line prompts
    - test_extended_compound_prompts, a sanctioned compound extended by a third section prompts
    - test_env_prefix_prompts, `ENV=VAL command` does NOT match the allowlist — prompts
      (the passing form is `export ENV=VAL && command`)
    - test_trailing_operator_prompts, a dangling operator (empty section) prompts
    - test_unbalanced_quotes_prompt, unparseable input prompts rather than guessing
    - test_near_miss_prompts, lookalikes of allowlisted forms (git statusx, rm -rf scratchx,
      npm run buildx) prompt
    - test_comment_smuggling_prompts, `#` never starts a comment for the guard
      (shlex commenters disabled): mid-word `git status#; …` and real trailing
      comments both keep their sections off the allowlist — prompt
    - test_comment_forms_degrade_safely, word-initial `#…` comments allow like bash
      (bare command); mid-word `rg#` denies conservatively
    - test_rm_operand_containment_prompts, every `rm -rf` form WITH operands
      prompts (only the bare scratch forms are allowlisted)
    - test_unknown_prompts, unknown or empty commands prompt
    """

    def test_compound_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status && rm -rf /")
        )

    def test_pipe_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="ls -la x | sh")
        )
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git log | head")
        )

    def test_semicolon_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status; rm -rf /")
        )

    def test_redirect_prompts(self) -> None:
        for cmd in ("git log > /tmp/x", "ls -la >> out.txt", "./run test x 2>&1"):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_substitution_prompts(self) -> None:
        for cmd in ("echo $(rm -rf /)", "echo `rm -rf /`"):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_newline_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status\nrm -rf /")
        )

    def test_extended_compound_prompts(self) -> None:
        self.assert_prompts(
            run_hook(
                "crush_bash_guard.py",
                CRUSH_TOOL_INPUT_COMMAND="cd ../scratch && ./run checkscratch && rm -rf /",
            )
        )

    def test_env_prefix_prompts(self) -> None:
        for cmd in (
            "FOO=1 ./run test x",  # wrong form — steer.md documents the export form
            "COPYFILE_DISABLE=1 tar czf /tmp/x.tgz .crushrc",  # tar isn't allowed either way
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_trailing_operator_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status &&")
        )

    def test_unbalanced_quotes_prompt(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status '")
        )

    def test_near_miss_prompts(self) -> None:
        for cmd in (
            "git statusx",
            "./run testx foo",
            "rm -rf scratchx",
            "npm run buildx",
            "ls -lab",
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_comment_smuggling_prompts(self) -> None:
        # shlex's default comment stripping eats `#…` even mid-word, which
        # let `git status#; rm -rf /` tokenize to bare `git status` → allow
        # while bash runs the rm. commenters is disabled — `#` splits out
        # as a literal token, so smuggled operators surface as their own
        # sections and prompt.
        for cmd in (
            "git status#; rm -rf /",
            "git status# ; rm -rf /",
            "git status # rm -rf /",  # trailing tokens keep the section off the allowlist
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_comment_forms_degrade_safely(self) -> None:
        # With commenters disabled, `#` is a literal token. Word-initial
        # `#…` IS a bash comment — bash drops it, so `ls -la #x` runs bare
        # `ls -la`; the guard's allow matches what bash executes. Mid-word
        # `rg#` splits to `rg` + `#` — deny fires on the rg word; bash
        # would only run `rg#` (not found), so the deny is conservative.
        self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="ls -la #x"))
        self.assert_denies(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="rg# foo"))

    def test_rm_operand_containment_prompts(self) -> None:
        # Prefix matching alone can't bound path operands — every form here
        # starts with an allowlisted-looking `rm -rf scratch…` prefix yet
        # escapes scratch after normpath.
        for cmd in (
            "rm -rf scratch/ /etc",
            "rm -rf scratch/etc /etc",
            "rm -rf scratch/../main",
            "rm -rf scratch/..",
            "rm -rf scratch/a/../../..",
            "rm -rf scratch /abs/path",
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_unknown_prompts(self) -> None:
        for cmd in ("rm -rf /", "curl https://evil.example", ""):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))


class BashGuardDenies(GuardAssertions):
    """The bash hook hard-denies rg and perl with a stderr reason.

    Denial applies anywhere in a compound, and deny beats prompt.

    - test_rg_denied, `rg` bare or with args exits 2 and names the alternative
    - test_perl_denied, `perl` bare or with args exits 2 and names the alternative
    - test_deny_inside_compound, `allowed && rg …` denies; deny wins even when another
      section would only prompt (`rg … && rm -rf /`)
    - test_lookalike_not_denied, `rgit`/`perlix` are not denied (they prompt)
    """

    def test_rg_denied(self) -> None:
        for cmd in ("rg", "rg foo"):
            with self.subTest(cmd=cmd):
                proc = run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd)
                self.assert_denies(proc)
                self.assertIn("grep", proc.stderr)

    def test_perl_denied(self) -> None:
        for cmd in ("perl", "perl -e print"):
            with self.subTest(cmd=cmd):
                proc = run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd)
                self.assert_denies(proc)
                self.assertIn("grep", proc.stderr)

    def test_deny_inside_compound(self) -> None:
        for cmd in ("git status && rg foo", "rg foo && rm -rf /"):
            with self.subTest(cmd=cmd):
                proc = run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd)
                self.assert_denies(proc)
                self.assertIn("rg", proc.stderr)

    def test_lookalike_not_denied(self) -> None:
        for cmd in ("rgit foo", "perlix -e x"):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))


class EditGuardScratch(GuardAssertions):
    """The edit hook auto-allows any scratch-tree path.

    - test_relative_scratch, repo-relative and parent-relative scratch paths are allowed
    - test_nested_scratch, scratch at any depth (matching */scratch/*) is allowed
    - test_vm_scratch, the VM's /srv/app/scratch/ prefix is allowed
    """

    def test_relative_scratch(self) -> None:
        for path in ("scratch/a.py", "../scratch/frontend/src/x.vue"):
            with self.subTest(path=path):
                self.assert_allows(run_hook("crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH=path))

    def test_nested_scratch(self) -> None:
        self.assert_allows(
            run_hook("crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH="deep/dir/scratch/a.py")
        )

    def test_vm_scratch(self) -> None:
        self.assert_allows(
            run_hook("crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH="/srv/app/scratch/a.py")
        )


class EditGuardNonScratch(GuardAssertions):
    """The edit hook stays silent outside scratch, and closes traversals.

    - test_non_scratch_prompts, repo files, absolute paths, and .env prompt
    - test_traversal_prompts, scratch/../main/x.py normalizes outside scratch and prompts
    - test_lookalike_prompts, scratchfoo/a.py does not match the scratch patterns
    - test_empty_prompts, an empty path prompts
    """

    def test_non_scratch_prompts(self) -> None:
        for path in (
            "ourapp/models/facts.py",
            "/etc/passwd",
            ".env",
            "frontend/src/ours/pages/Home.vue",
        ):
            with self.subTest(path=path):
                self.assert_prompts(
                    run_hook("crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH=path)
                )

    def test_traversal_prompts(self) -> None:
        self.assert_prompts(
            run_hook(
                "crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH="scratch/../main/ourapp/x.py"
            )
        )

    def test_lookalike_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH="scratchfoo/a.py")
        )

    def test_empty_prompts(self) -> None:
        self.assert_prompts(run_hook("crush_edit_guard.py", CRUSH_TOOL_INPUT_FILE_PATH=""))


class HookWiring(unittest.TestCase):
    """Both hooks are executable with a python3 shebang (Crush runs them by path).

    - test_hooks_are_executable, the executable bit is set so Crush's command dispatch works
    """

    def test_hooks_are_executable(self) -> None:
        for script in ("crush_bash_guard.py", "crush_edit_guard.py"):
            with self.subTest(script=script):
                self.assertTrue(os.access(DEPLOY / script, os.X_OK))


if __name__ == "__main__":
    unittest.main()
