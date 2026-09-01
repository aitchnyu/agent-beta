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
`ENV=VAL command` prefix does NOT match the allowlist — the passing form
is `export ENV=VAL && command` (steer.md documents both).

Standalone-testable: CRUSH_TOOL_INPUT_COMMAND="git status" ./deploy/crush_bash_guard.py
Unit tests: deploy/tests/test_crush_guards.py.
"""

import json
import os
import re
import shlex
import sys

EXIT_DENY = 2

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
        "rm -rf scratch",
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


def _classify(tokens: list[str]) -> str:
    """Return "allow", "prompt", or "deny" for one section."""
    if any(REDIRECT_RE.fullmatch(token) or SUBST_RE.search(token) for token in tokens):
        return "prompt"
    if tokens[0] == "export" and all(
        ASSIGN_RE.match(token) or NAME_RE.match(token) for token in tokens[1:]
    ):
        return "allow"
    # find's action flags execute/write from inside its argument list —
    # check them BEFORE the prefix rule can match the bare `find` base.
    if tokens[0] == "find" and any(
        token in FIND_DANGEROUS_EXACT or token.startswith(FIND_DANGEROUS_PREFIX)
        for token in tokens[1:]
    ):
        return "prompt"
    section = " ".join(tokens)
    if section in ALLOW_EXACT or _prefix_match(section):
        return "allow"
    if tokens[0] in DENY_PREFIX:
        return "deny"
    return "prompt"


def main() -> int:
    cmd = os.environ.get("CRUSH_TOOL_INPUT_COMMAND", "")
    sections = _sections(cmd) if cmd.strip() else None
    if not sections:
        return 0  # empty or unparseable — the permission prompt takes it
    verdicts = [(section, _classify(section)) for section in sections]
    # Deny wins over prompt: check ALL sections for a deny first, so
    # `foo && rg x` denies even though `foo` alone would only prompt.
    for section, verdict in verdicts:
        if verdict == "deny":
            print(
                f"{section[0]} is denied by policy — use the grep tool or Python instead.",
                file=sys.stderr,
            )
            return EXIT_DENY
    if any(verdict == "prompt" for _, verdict in verdicts):
        return 0  # one unknown section is enough — no opinion
    print(json.dumps({"decision": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
