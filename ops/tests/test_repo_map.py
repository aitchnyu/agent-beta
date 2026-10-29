""".pi/repo-map.md must name only repo paths that exist.

Sessions read the map to know where everything is — a dangling path
sends them hunting. When this test fails, refresh the map (read the
repo, edit the file) instead of trusting it blindly.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_MAP = (_REPO / ".pi" / "repo-map.md").read_text(encoding="utf-8")

# Repo-relative paths the map references (backticks delimit them).
_PATH_LINE = re.compile(
    r"`([a-zA-Z0-9_][a-zA-Z0-9_/.]*\.(?:py|md|vue|ts|sh|json)(?![a-zA-Z0-9])|.pi/|ourapp/|frontend/src/|djangoapp/|docs/reference/)"
)


class RepoMapPathTests(unittest.TestCase):
    """Every repo path named in repo-map.md exists on disk.

    - test_named_repo_paths_exist, no dangling references
    """

    def test_named_repo_paths_exist(self) -> None:
        candidates: set[str] = set()
        for match in _PATH_LINE.finditer(_MAP):
            candidate = match.group(1).rstrip("/")
            candidates.add(candidate)
        missing = [
            candidate for candidate in sorted(candidates) if not (_REPO / candidate).exists()
        ]
        self.assertEqual(missing, [], f"repo-map.md references paths that do not exist: {missing}")
