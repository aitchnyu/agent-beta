#!/usr/bin/env python3
"""Crush PreToolUse hook for file-editing tools — scratch path scoping.

Wired from .crushrc via `hook add PreToolUse --matcher "^(edit|write|multiedit)$"`.
Crush passes the target file in CRUSH_TOOL_INPUT_FILE_PATH; this hook
auto-approves edits anywhere under a `scratch/` tree (and the VM's
`/srv/app/scratch/`) and stays silent for everything else, so non-scratch
edits fall through to the permission prompt. Ports the `edit:
{"scratch/**": "allow"}` half of agentconfig/opencode.json.

Paths are normalized first so `scratch/../main/x.py` (a traversal out of
scratch) cannot ride the scratch patterns.

Unit tests: deploy/tests/test_crush_guards.py.
"""

import fnmatch
import json
import os
import sys

SCRATCH_PATTERNS = ("scratch/*", "*/scratch/*", "/srv/app/scratch/*")


def main() -> int:
    path = os.environ.get("CRUSH_TOOL_INPUT_FILE_PATH", "")
    normalized = os.path.normpath(path)
    if any(fnmatch.fnmatchcase(normalized, pattern) for pattern in SCRATCH_PATTERNS):
        print(json.dumps({"decision": "allow"}))
    return 0  # no opinion (or allowed above) — non-scratch paths prompt


if __name__ == "__main__":
    sys.exit(main())
