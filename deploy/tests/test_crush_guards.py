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
            "./run createscratch",
            "./run deployscratch",
            "rm -rf ../scratch",
            "git ls-files",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_rm_single_scratch_files(self) -> None:
        # rm of single FILES inside scratch: bare rm, every operand
        # containment-checked, chainable. Flags (even -f), subtree deletes,
        # escapes, and outside-scratch targets prompt.
        for cmd in (
            "rm ../scratch/ourapp/docs/old.md",
            "rm ../scratch/a.md ../scratch/b.md",  # multiple files, all contained
            "rm ../scratch/a.md && rm ../scratch/b.md",  # the && chain pattern
            "rm scratch/notes.txt",  # repo-relative scratch/ (main/scratch) — contained
            "rm /srv/app/scratch/ourapp/docs/old.md",  # VM absolute path
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_prefix_forms(self) -> None:
        for cmd in (
            "ls -la /srv/app",
            "./run test accounts",
            "./run djangomanage makemigrations ourapp",
            "./run djangomanage findstatic djangoapp/main.js",
            "./run djangomanage hostnames",
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
            "cd scratch && ./run deployscratch",
            "cd ../scratch && ./run deployscratch",
            "( cd scratch && ./run deployscratch )",
            "( cd ../scratch && ./run deployscratch )",
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

    def test_readonly_filters(self) -> None:
        # head/tail/wc prefix rules let inspection pipelines of allowlisted
        # commands run unprompted (2026-08-31 VM-session autopsy: `… | head -5`
        # lines prompted section-wise).
        for cmd in (
            "ls -la /srv/app | head -5",
            "git log | tail -20",
            "git diff | wc -l",
            "head -3 file.txt",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_kilo_mined_inspection_allows(self) -> None:
        # Read-only inspection commands mined from the user's kilo.jsonc
        # allowlist (2026-08-31), filtered for this guard's philosophy.
        for cmd in (
            "ls /srv/app/main/.venv/bin",
            "cat README.md",
            "find . -name uv -type f",
            "grep -n pattern run",
            "git status --porcelain",
            "git grep pattern",
            "git check-ignore .crush/init",
            "git rev-parse HEAD",
            "git ls-tree HEAD",
            "git ls-files -z",
            "sort names.txt",
            "uniq -c",
            "cut -d: -f2",
            "tr a-z A-Z",
            "jq . package.json",
            "diff a.txt b.txt",
            "printf %s hi",
            "stat run",
            "file run",
            "du -sh frontend",
            "date",
            "which uv",
            "ps aux",
            "pgrep granian",
            "lsof -i :8000",
            "bash -n run",
            "zsh -n deploy/vm-bootstrap.sh",
            "echo $HOME",
        ):
            with self.subTest(cmd=cmd):
                self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_kilo_filtered_write_and_exec_prompts(self) -> None:
        # kilo.jsonc also allows these; DELIBERATELY excluded here — they
        # write files or execute subcommands, routing around the edit-scope
        # guard or the bash-tool trust boundary.
        for cmd in (
            "sed -i s/a/b/ run",  # sed -i writes
            'awk BEGIN{system("ls")}',  # awk system() executes
            "echo x | xargs rm",  # xargs executes
            "tee /srv/app/main/run",  # tee writes
            "cp a /srv/app/main/b",  # cp routes around edit scoping
            "mv a b",
            "mkdir /srv/app/main/x",
            "uv run python -c 1",  # arbitrary execution
            "python3 -c 1",
            "npm exec some-package",  # arbitrary package execution
            "printenv",  # would expose the provider key in crush's env
            "find . -exec rm -rf {} ;",  # find's action flags execute
            "find / -delete",
            "find . -fprintf /tmp/out %p",
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_export_form(self) -> None:
        for cmd in (
            "export COPYFILE_DISABLE=1 && ./run test accounts",
            "export RUN_PROJECT_TESTS=1 && ./run deployscratch",
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
    - test_trailing_operator_prompts, a dangling operator (empty section) prompts
    - test_unbalanced_quotes_prompt, unparseable input prompts rather than guessing
    - test_near_miss_prompts, lookalikes of allowlisted forms (git statusx, rm -rf scratchx,
      npm run buildx) prompt
    - test_comment_smuggling_prompts, `#` never starts a comment for the guard
      (shlex commenters disabled): mid-word `git status#; …` and real trailing
      comments both keep their sections off the allowlist — prompt
    - test_comment_forms_degrade_safely, word-initial `#…` comments allow like bash
      (bare command); mid-word `rg#` denies conservatively
    - test_rm_operand_containment_prompts, rm subtree deletes, normpath escapes,
      and out-of-scratch targets prompt (only single contained files allow)
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
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git log | nl")
        )

    def test_semicolon_prompts(self) -> None:
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status; rm -rf /")
        )

    def test_redirect_prompts(self) -> None:
        # EVERY redirect prompts — including the discard forms (2>/dev/null,
        # 2>&1): policy is fail-closed on redirects, and steer.md tells the
        # agent not to append them unless truly necessary.
        for cmd in (
            "git log > /tmp/x",
            "ls -la >> out.txt",
            "./run test x 2>&1",
            "ls /tmp/x 2>/dev/null",
            "./run test x 2>/tmp/err",
        ):
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
                CRUSH_TOOL_INPUT_COMMAND="cd ../scratch && ./run deployscratch && rm -rf /",
            )
        )

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
            "lsx -la",  # lookalike BASE (flags after a real base are just args)
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
            "cat file; rm -rf /",  # second section smuggled after an allowed base
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_comment_forms_degrade_safely(self) -> None:
        # With commenters disabled, `#` is a literal token. Word-initial
        # `#…` IS a bash comment — bash drops it, so `ls -la #x` runs bare
        # `ls -la`; the guard's allow matches what bash executes. Same for
        # prefix bases: `git status # rm -rf /` runs bare `git status` in
        # bash (comment dropped), so allowing it matches bash semantics.
        # Mid-word `rg#` splits to `rg` + `#` — deny fires on the rg word;
        # bash would only run `rg#` (not found), so the deny is conservative.
        self.assert_allows(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="ls -la #x"))
        self.assert_allows(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git status # rm -rf /")
        )
        self.assert_denies(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="rg# foo"))

    def test_rm_operand_containment_prompts(self) -> None:
        # rm forms the single-file rule refuses: subtree deletes (-r/-rf
        # with operands), escapes after normpath, and targets outside
        # scratch. Only bare `rm -rf ../scratch` and contained single
        # files allow.
        for cmd in (
            "rm -rf scratch/ /etc",
            "rm -rf scratch/etc /etc",
            "rm -rf scratch/../main",
            "rm -rf scratch/..",
            "rm -rf scratch/a/../../..",
            "rm -rf scratch /abs/path",
            "rm -rf ../scratch/ourapp",  # subtree inside scratch — not a single file
            "rm -f ../scratch/a.md",  # any flag (even -f) prompts
            "rm ../scratch/a.md /etc/passwd",  # one contained + one escape
            "rm ../scratch/../main/x.py",  # escapes after normpath
            "rm -fr ../scratch/a.md",  # -fr is a subtree flag shape
            "rm /etc/passwd",
        ):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))

    def test_unknown_prompts(self) -> None:
        for cmd in ("rm -rf /", "curl https://evil.example", ""):
            with self.subTest(cmd=cmd):
                self.assert_prompts(run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd))


class BashGuardDenies(GuardAssertions):
    """The bash hook hard-denies rg, perl, and env-prefixed commands with a stderr reason.

    Denial applies anywhere in a compound, and deny beats prompt.

    - test_rg_denied, `rg` bare or with args exits 2 and names the alternative
    - test_perl_denied, `perl` bare or with args exits 2 and names the alternative
    - test_env_prefix_denied, `VAR=value command …` is denied with the export-form
      pointer (a prompt round-trip per wrong attempt wasted operator time)
    - test_git_dash_c_denied, `git -C <dir> …` is denied with the cd-instead pointer
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

    def test_env_prefix_denied(self) -> None:
        for cmd in (
            "FOO=1 ./run test x",  # the exact wrong form steer.md warns about
            "COPYFILE_DISABLE=1 tar czf /tmp/x.tgz .crushrc",  # tar isn't allowed either way
            "RUN_PROJECT_TESTS=1 ./run checkproject",  # even a fully-allowed command under a prefix
            "FOO=1",  # a lone assignment is the same mistake half-made
            "FOO=1 git status && pwd",  # deny beats the allowed sections around it
        ):
            with self.subTest(cmd=cmd):
                proc = run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd)
                self.assert_denies(proc)
                self.assertIn("export", proc.stderr)

    def test_git_dash_c_denied(self) -> None:
        for cmd in (
            "git -C ../scratch status",
            "git -C /srv/app/scratch log --oneline -3",
            "git status && git -C /tmp diff",  # deny wins inside a compound
        ):
            with self.subTest(cmd=cmd):
                proc = run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND=cmd)
                self.assert_denies(proc)
                self.assertIn("cd into the directory", proc.stderr)

    def test_git_dash_lowercase_c_not_denied(self) -> None:
        # `git -c name=value` is git's per-invocation config option, not -C
        self.assert_prompts(
            run_hook("crush_bash_guard.py", CRUSH_TOOL_INPUT_COMMAND="git -c core.pager=cat status")
        )

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
