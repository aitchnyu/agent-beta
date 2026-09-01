#!/usr/bin/env python3
"""Crush PreToolUse hook for the bash tool — the allowlist, compound-aware.

Wired from .crushrc via `hook add PreToolUse --matcher "^bash$"`. Crush
passes the raw command in CRUSH_TOOL_INPUT_COMMAND and reads the verdict
from stdout / exit code:
- allow — print {"decision": "allow"}: the call runs with no permission
  prompt
- deny — reason on stderr + exit 2: the call is blocked, the model sees
  the reason
- no opinion — silent exit 0: Crush falls through to its permission prompt

Compound commands (`a && b`, `a; b`, `a | b`, subshell parens, newlines)
are split into SECTIONS with shlex and every section is classified; the
overall verdict is the strictest one:
- any section DENIED   -> deny (the reason names the denied section)
- any section PROMPT   -> no opinion (the permission prompt takes it)
- all sections ALLOWED -> allow

A section is allowed if it is an `export NAME=VALUE…` assignment or
matches the exact/prefix allowlist ported from opencode.json. Redirects
(`>` `<` `>>`…, INCLUDING the discard forms `2>/dev/null` / `2>&1`) and
command substitution (`$(…)` / backticks) always prompt their section —
steer.md tells the agent not to append redirects unless truly needed. An
`ENV=VAL command` prefix is DENIED outright (it can never match the
allowlist; the passing form is `export ENV=VAL && command` — steer.md
documents both). Two readability rules are likewise DENIED, not advised:
any LINE over 80 characters (commands must stay human-readable and
reviewable — split chains across lines), and `git -C <dir> …` (cd into
the directory, then git).

Standalone-testable: CRUSH_TOOL_INPUT_COMMAND="git status" ./deploy/crush_bash_guard.py
Unit tests: deploy/tests/test_crush_guards.py.
"""

import json
import os
import posixpath
import re
import shlex
import sys
from typing import NamedTuple

EXIT_DENY = 2

# Readability cap: a longer LINE is denied outright — commands must stay
# human-readable and reviewable in the permission prompt (chains still get
# as long as they need via `\` continuations/newlines, one command per line).
MAX_LINE = 80

# Operators that separate one section from the next: bash command
# separators plus subshell parens (splitting on parens lets the sanctioned
# `( cd ../scratch && ./run deployscratch )` form decompose into its inner
# sections). Quoted spans stay whole — shlex never splits inside quotes.
SPLIT_OPS = frozenset({"&&", "||", ";", "|", "&", "(", ")", "|&", ";;"})

# A redirect token forces its whole section to prompt: an allowlisted
# command with `>`/`<`/`>>`/`>&` still reads/writes an arbitrary file.
REDIRECT_RE = re.compile(r"^[<>&]+$")

# Command substitution anywhere in a token forces the section to prompt.
SUBST_RE = re.compile(r"\$\(|`")

# `export FOO=bar` assignments (bare names allowed too — both harmless).
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ALLOW_EXACT = frozenset(
    {
        "pwd",
        "cd scratch",
        "cd ../scratch",
        "./run createscratch",
        "./run deployscratch",
        "./run cleanscratch",
        "./run djangomanage migrate",
        "./run checkproject",
        "./run typecheck",
        "./run lintfix",
        "./run playwrighttest",
        "npm run build",
        "rm -rf ../scratch",
        "git diff",
        "git log",
        "git show",
    }
)

# A prefix rule allows the bare base and `base <args...>` (word boundary).
# NOTE: bases must NOT end in "/" — a bare startswith match has no word
# boundary (`rm -rf scratch/ /etc` would ride `rm -rf scratch/`); path
# operands like rm's get dedicated containment checks instead.
ALLOW_PREFIX = (
    "ls",
    "./run djangomanage migrate",
    "./run test",
    "./run playwrighttest",
    "./run djangomanage makemigrations",
    "./run djangomanage findstatic",
    "./run djangomanage hostnames",
    "cd scratch",
    "cd ../scratch",
    "git diff",
    "git log",
    "git show",
    "git blame",
    "git status",
    "git grep",
    "git check-ignore",
    "git rev-parse",
    "git ls-tree",
    "git ls-files",
    "cat",
    "find",  # guarded by FIND_DANGEROUS below (-exec/-delete write/execute)
    "grep",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "cut",
    "tr",
    "jq",
    "diff",
    "echo",  # redirects/substitution still force a prompt (REDIRECT/SUBST)
    "printf",
    "stat",
    "file",
    "du",
    "date",
    "which",
    "ps",
    "pgrep",
    "lsof",
    "bash -n",  # syntax-check only — parses, never executes
    "zsh -n",  # syntax-check only — parses, never executes
)


# find's action flags execute commands or write files from INSIDE its
# argument list (no shell operators for the section splitter to see), so a
# prefix rule alone would let `find . -exec rm {} \;` ride through.
FIND_DANGEROUS_EXACT = frozenset({"-exec", "-execdir", "-ok", "-okdir", "-delete"})
FIND_DANGEROUS_PREFIX = ("-fprint", "-fprintf", "-fls")

DENY_PREFIX = ("rg", "perl")


def _sections(cmd: str) -> list[list[str]] | None:
    """Tokenize into operator-separated sections; None if unparseable."""
    # Newlines separate commands in bash exactly like ';' — normalize so a
    # second command can never hide inside one allowed-looking section.
    text = cmd.replace("\r", ";").replace("\n", ";")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        # shlex's default commenters='#' strips `#…` to end-of-line EVEN
        # MID-WORD (`git status#; rm -rf /` would tokenize as just `git
        # status` → allow, while bash runs `git status#` + `rm -rf /`).
        # Bash only starts comments at a word boundary; disabling comment
        # stripping keeps `#` as a literal token, so any section carrying
        # one fails closed to prompt.
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None  # unbalanced quotes etc. — no opinion
    # A dangling command separator (`a &&`, `; b`) is a bash syntax error —
    # don't guess; parens are exempt (subshells legitimately open/close).
    separators = SPLIT_OPS - {"(", ")"}
    if tokens and (tokens[0] in separators or tokens[-1] in separators):
        return None
    sections: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SPLIT_OPS:
            if current:
                sections.append(current)
            current = []
        else:
            current.append(token)
    if current:
        sections.append(current)
    return sections


def _prefix_match(section: str) -> bool:
    return any(section == base or section.startswith(base + " ") for base in ALLOW_PREFIX)





def _rm_scratch_files(tokens: list[str]) -> bool:
    """``rm <file…>`` deleting only single FILES inside scratch.

    No flags at all (bare ``rm``); every operand must be scratch-contained
    after normpath — ``scratch/../main`` collapses out and fails. Recursive
    deletes and the whole tree are separate rules (``rm -rf ../scratch``,
    ``./run cleanscratch``); everything else rm-shaped prompts.
    """
    def _within_scratch(path: str) -> bool:
        """Path stays inside a scratch tree after normpath (no `..` escape)."""
        norm = posixpath.normpath(path)
        return norm.startswith(("scratch/", "../scratch/", "/srv/app/scratch/"))

    return (
        tokens[0] == "rm"
        and len(tokens) > 1
        and all(_within_scratch(operand) for operand in tokens[1:])
    )


class Verdict(NamedTuple):
    """One section's outcome. ``reason`` is only surfaced on deny (stderr)."""

    action: str  # "allow" | "prompt" | "deny"
    reason: str


def _deny_reason(tokens: list[str]) -> str:
    if ASSIGN_RE.match(tokens[0]):
        return (
            f"env-prefixed command ({tokens[0]} …) is denied by policy —"
            " use the export form: export VAR=value && <command>"
        )
    if tokens[0] == "git" and tokens[1:2] == ["-C"]:
        return "git -C is denied by policy — cd into the directory, then git …"
    return f"{tokens[0]} is denied by policy — use the grep tool or Python instead."


def _classify(tokens: list[str]) -> Verdict:
    if any(REDIRECT_RE.fullmatch(token) or SUBST_RE.search(token) for token in tokens):
        return Verdict("prompt", "redirect or command substitution")
    if tokens[0] == "export" and all(
        ASSIGN_RE.match(token) or NAME_RE.match(token) for token in tokens[1:]
    ):
        return Verdict("allow", "export assignment")
    # find's action flags execute/write from inside its argument list —
    # check them BEFORE the prefix rule can match the bare `find` base.
    if tokens[0] == "find" and any(
        token in FIND_DANGEROUS_EXACT or token.startswith(FIND_DANGEROUS_PREFIX)
        for token in tokens[1:]
    ):
        return Verdict("prompt", "find action flag (-exec/-delete/…)")
    section = " ".join(tokens)
    if section in ALLOW_EXACT or _prefix_match(section) or _rm_scratch_files(tokens):
        return Verdict("allow", "matches the allowlist")
    # `VAR=value command …` can never match the allowlist — deny it with the
    # export-form pointer instead of burning a prompt round-trip per attempt
    # (the passing form is `export VAR=value && command …`; steer.md documents both).
    # `git -C <dir> …` is the same shape: never allowlistable, always a
    # readability loss — deny with the cd-instead pointer.
    if (
        ASSIGN_RE.match(tokens[0])
        or tokens[0] in DENY_PREFIX
        or (tokens[0] == "git" and tokens[1:2] == ["-C"])
    ):
        return Verdict("deny", _deny_reason(tokens))
    return Verdict("prompt", "not on the allowlist")


def main() -> int:
    cmd = os.environ.get("CRUSH_TOOL_INPUT_COMMAND", "")
    # Readability gate first, before any parsing: ONE line over the cap
    # denies the whole command — long chains stay fine split across lines.
    overlong = next((line for line in cmd.splitlines() if len(line) > MAX_LINE), None)
    if overlong is not None:
        print(
            f"a {len(overlong)}-character line is denied by policy (max {MAX_LINE}) —"
            " commands must stay human-readable and reviewable;"
            " split chains across lines with \\ continuations or newlines",
            file=sys.stderr,
        )
        return EXIT_DENY
    sections = _sections(cmd) if cmd.strip() else None
    if not sections:
        return 0  # empty or unparseable — the permission prompt takes it
    verdicts = [(section, _classify(section)) for section in sections]
    # Deny wins over prompt: check ALL sections for a deny first, so
    # `foo && rg x` denies even though `foo` alone would only prompt.
    for _, verdict in verdicts:
        if verdict.action == "deny":
            print(verdict.reason, file=sys.stderr)
            return EXIT_DENY
    if any(verdict.action == "prompt" for _, verdict in verdicts):
        return 0  # one unknown section is enough — no opinion
    print(json.dumps({"decision": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
