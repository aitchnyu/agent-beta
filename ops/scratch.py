"""The scratch lifecycle: createscratch, deployscratch, cleanscratch.

scratch/ is the agent's edit tree — a copy of main/ sharing its git
history under a frozen ``scratch-baseline`` ref. createscratch builds
it, deployscratch checks the edits in scratch and ships them to main/
live (nothing deploys red), cleanscratch discards it. ``./run``'s
trio commands are thin wrappers over this module's CLI (ops.cli).

The exact guard/refusal/hint message strings are load-bearing: the VM
gate and steer.md assert them.

Design notes:

- the changed-set vs the baseline is computed once and reused;
- check steps invoke uv/manage.py directly, with the isolated test-redis
  environment applied here;
- a failed step prints the exact command to re-run in scratch;
- deployscratch and createscratch are single linear pipelines — section
  comments, not helper hops, carry their phases.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ops import shell

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# main/ is this package's parent; scratch/ is its sibling (both under
# parent/).
MAIN_DIR = Path(__file__).resolve().parent.parent
SCRATCH_DIR = MAIN_DIR.parent / "scratch"

VM_ENV_FILE = Path("/etc/credentials/desmo/.env.vm")
TEST_REDIS_URL = "redis://127.0.0.1:6379/2"

# The app surface is every path a feature edit may touch (`ourapp/` plus
# `frontend/src/app/`); everything else is framework files.
APP_SURFACE = re.compile(r"^(ourapp/|frontend/src/app/)")
# Fast-path-safe changes: any frontend file, or a top-level feature doc.
FAST_PATH_SAFE = re.compile(r"^(frontend/|ourapp/docs/[^/]+\.md$)")
FRONTEND = re.compile(r"^frontend/")
DOCS_MD = re.compile(r"^ourapp/docs/[^/]+\.md$")
# rsync --exclude-from would misparse these — a hostile ignored name must
# ride as harmless junk, never silently exclude an unrelated tracked file.
RULE_PREFIX = re.compile(r"^[-+!;#] ")
GLOB_META = re.compile(r"[*?\[]")
# A quoted .env value: KEY="value" — sourcing strips the matching quotes.
QUOTED_VALUE = re.compile(r"^(['\"]).*\1$")

# Color policy: keep it in a real terminal, strip it when captured so
# ANSI escapes don't pollute agent logs. Set by configure_output() at CLI
# startup — importing the module (the test runner does) must not mutate
# the process environment.
RUFF_COLOR: tuple[str, ...] = ()
MYPY_COLOR: tuple[str, ...] = ()
DJANGO_NO_COLOR: tuple[str, ...] = ()


def configure_output() -> None:
    """Set the color flags and the NO_COLOR contract for this process."""
    global RUFF_COLOR, MYPY_COLOR, DJANGO_NO_COLOR
    if sys.stdout.isatty():
        return
    RUFF_COLOR = ("--color=never",)
    MYPY_COLOR = ("--no-color-output",)
    DJANGO_NO_COLOR = ("--no-color",)
    os.environ["NO_COLOR"] = "1"
    # FORCE_COLOR (injected by e.g. concurrently) makes chalk ignore NO_COLOR
    os.environ.pop("FORCE_COLOR", None)


def _require_main_run(command: str) -> None:
    """Refuse scratch's own ./run for lifecycle commands.

    From scratch's copy both dirs resolve to scratch (deploy rsyncs
    scratch onto itself; create removes its own tree).
    """
    if MAIN_DIR == SCRATCH_DIR:
        shell.die(
            f"Refusing: this is scratch's own ./run — run '{command}' from main/'s ./run instead."
        )


def is_running_on_vm() -> bool:
    """Report whether this is the VM.

    /etc/credentials/desmo/.env.vm is staged at provisioning and exists
    nowhere else — the de facto "am I on the VM?" marker.
    """
    return VM_ENV_FILE.is_file()


def test_redis_env() -> dict[str, str]:
    """Build the test-process redis environment.

    The isolated DB (not the live DB 0) plus the marker clear_redis
    requires before flushing.
    """
    env = dict(os.environ)
    env["REDIS_URL"] = TEST_REDIS_URL
    env["DESMO_TEST_REDIS"] = "1"
    return env


# ── Pure decision logic (unit-tested in ops/tests/test_scratch.py) ──────


def framework_files(lines: Iterable[str]) -> list[str]:
    """Filter a changed-file listing to its framework files.

    Framework files are the lines OUTSIDE the app surface (`ourapp/` +
    `frontend/src/app/`).
    """
    return [path for path in lines if not APP_SURFACE.match(path)]


@dataclass(frozen=True)
class FastPath:
    """The deployscratch fast-path classification of a changed-set."""

    docs_or_frontend_only: bool
    frontend_changed: bool
    frontend_framework_changed: bool


def classify_changed_files(changed: Sequence[str]) -> FastPath:
    """Classify a changed-set for the deploy fast path.

    docs_or_frontend_only = the set is nonempty and every line is
    frontend/** or ourapp/docs/*.md; framework frontend files (outside
    the app surface) keep the browser smoke.
    """
    if not changed or any(not FAST_PATH_SAFE.match(path) for path in changed):
        return FastPath(
            docs_or_frontend_only=False,
            frontend_changed=False,
            frontend_framework_changed=False,
        )
    frontend_changed = any(FRONTEND.match(path) for path in changed)
    outside = [path for path in framework_files(changed) if FRONTEND.match(path)]
    return FastPath(
        docs_or_frontend_only=True,
        frontend_changed=frontend_changed,
        frontend_framework_changed=bool(outside),
    )


def share_url_base(raw: str) -> str:
    """Extract the share-URL base from BASE_URLS.

    The FIRST entry, all spaces removed, trailing slashes dropped — the
    links the deploy prints add their own.
    """
    first = raw.split(",", 1)[0].replace(" ", "")
    return first.rstrip("/")


def rsync_exclude_lines(lines: Iterable[str], direction_filter: str) -> list[str]:
    """Filter gitignored listings down to rsync --exclude-from lines.

    Drop the directional carries (the filter), then rule prefixes and
    glob metachars rsync would misparse — a hostile ignored name must
    ride as harmless junk, never silently exclude an unrelated tracked
    file.
    """
    directional_carries = re.compile(direction_filter)
    return [
        path
        for path in lines
        if path
        and not directional_carries.search(path)
        and not RULE_PREFIX.match(path)
        and not GLOB_META.search(path)
    ]


# ── Git/rsync plumbing ──────────────────────────────────────────────────


def rsync_excludes_file(direction_filter: str, *dirs: Path) -> Path:
    """Build the scratch rsyncs' exclude set from .gitignore at call time.

    Keeping a new junk/artifact/runtime dir out of the scratch loop is a
    .gitignore-only change. The deploy passes BOTH trees — plain --delete
    never removes excluded files on the receiver, so main-only runtime
    data (media/, dbbackups/, staticfiles/) survives only if MAIN's
    listing carries the exclude; createscratch passes just the sender.
    """
    lines: list[str] = []
    for tree_dir in dirs:
        exit_code, ignored_listing = shell.capture(
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            cwd=tree_dir,
        )
        if exit_code != 0:
            shell.die(f"REFUSING: git ls-files failed in {tree_dir} — no rsync without excludes.")
        lines += ignored_listing.splitlines()
    exclude_file = tempfile.NamedTemporaryFile(  # noqa: SIM115 — opened without a context manager: rsync needs a path; the caller unlinks it
        "w", suffix=".excludes", encoding="utf-8", delete=False
    )
    exclude_file.write("\n".join(rsync_exclude_lines(lines, direction_filter)) + "\n")
    exclude_file.close()
    return Path(exclude_file.name)


# ── createscratch / cleanscratch ───────────────────────────────────────


def _link_or_copy_tree(src: Path, dst: Path) -> None:
    """Hardlink-copy a tree when the OS allows it, plain copy otherwise.

    Dev on the Mac: same owner — instant, zero extra disk. On the VM,
    Linux's protected_hardlinks blocks the default user from hardlinking
    files it can only read — bare cp -al dies halfway and leaves a
    HOLLOW .venv that uv then refuses.
    """
    if (
        subprocess.run(
            ["cp", "-al", str(src), str(dst)], stderr=subprocess.DEVNULL, check=False
        ).returncode
        != 0
    ):
        shutil.rmtree(dst, ignore_errors=True)
        shell.run("cp", "-a", str(src), str(dst))


def createscratch() -> None:
    """Create a fresh scratch/ of main/ for the agent to edit + diff.

    Tree rsync INCLUDING .git (shared history), main's HEAD frozen as
    the `scratch-baseline` ref, and .venv + node_modules hardlink-copied
    so the bootstrap runs incremental.
    """
    _require_main_run("createscratch")
    # Fail fast if the old tree can't be wiped: proceeding would layer a
    # plain (no --delete) rsync over a half-wiped tree and call it "fresh".
    try:
        shutil.rmtree(SCRATCH_DIR)
    except OSError as error:
        shell.die(f"REFUSING: failed to wipe {SCRATCH_DIR} — {error}. Fix the cause, then re-run.")
    # Sender-only excludes (no --delete; the receiver was just wiped).
    # The filter keeps .env and the built bundle riding to scratch — the
    # deploy re-excludes .env.
    excludes = rsync_excludes_file(r"^\.env$|^djangoapp/static/", MAIN_DIR)
    shell.run("rsync", "-a", f"--exclude-from={excludes}", f"{MAIN_DIR}/", f"{SCRATCH_DIR}/")
    excludes.unlink(missing_ok=True)
    # The baseline ref is load-bearing — every deploy diffs against it.
    # Silencing git's "Updated tag" notice; a failure must abort here,
    # not surface later as a confusing deploy refusal.
    exit_code, _tag_notice = shell.capture(
        "git", "tag", "-f", "scratch-baseline", "HEAD", cwd=SCRATCH_DIR
    )
    if exit_code != 0:
        shell.die(f"REFUSING: failed to tag scratch-baseline in {SCRATCH_DIR}.")
    # npm install rewrites package-lock format-normalized — it reads as
    # a diff vs the baseline, tripping the framework-file watch. Pin it
    # back before AND after install so the baseline stays clean.
    shell.run("git", "checkout", "--", "frontend/package-lock.json", cwd=SCRATCH_DIR, check=False)
    if (MAIN_DIR / ".venv").is_dir():
        _link_or_copy_tree(MAIN_DIR / ".venv", SCRATCH_DIR / ".venv")
    if (MAIN_DIR / "frontend" / "node_modules").is_dir():
        _link_or_copy_tree(
            MAIN_DIR / "frontend" / "node_modules", SCRATCH_DIR / "frontend" / "node_modules"
        )
    shell.run("uv", "sync", cwd=SCRATCH_DIR)
    shell.run("npm", "install", cwd=SCRATCH_DIR / "frontend")
    shell.run("git", "checkout", "--", "frontend/package-lock.json", cwd=SCRATCH_DIR, check=False)
    print(
        f"scratch/ ready at {SCRATCH_DIR}. Edit there, then deploy with: ./run deployscratch (from main/)"
    )


def cleanscratch() -> None:
    """Remove scratch/ outright (discard the scratch tree)."""
    if SCRATCH_DIR.is_dir():
        shutil.rmtree(SCRATCH_DIR)
        print(f"Removed {SCRATCH_DIR}.")
    else:
        print(f"No scratch/ at {SCRATCH_DIR} to remove.")


# ── deployscratch ───────────────────────────────────────────────────────


def step_banner(label: str) -> None:
    """Print the wall-clock stamp for the just-finished deploy step."""
    print(f"    [{label} {time.strftime('%H:%M:%S')}]")


def run_smoke_tests() -> None:
    """Run the scratch-test-subset smoke in scratch (the browser pass)."""
    shell.run_step(
        "uv run manage.py test --tag=scratch-test-subset",
        "uv",
        "run",
        "manage.py",
        "test",
        *DJANGO_NO_COLOR,
        "--noinput",
        "--tag=scratch-test-subset",
        cwd=SCRATCH_DIR,
        env=test_redis_env(),
    )


def deployscratch() -> None:
    """Deploy: check battery in scratch, then rsync → main/, live.

    Nothing deploys red; frontend/docs-only diffs take a fast path (no
    backend checks, backup, migrate, or restarts); a backend diff runs
    the pre-migration backup, migrate, collectstatic + granian/huey
    restarts. VM ONLY — the scratch loop needs the VM's units and
    pgbackrest. Never commits.
    """
    # ── environment ──
    # Plain KEY="value" lines + comments only — no command substitution,
    # by convention. main/'s .env (dev) first, else the VM's single
    # credentials file.
    env_path = MAIN_DIR / ".env"
    if not env_path.is_file() and is_running_on_vm():
        env_path = VM_ENV_FILE
    if not env_path.is_file():
        print(
            "Warning: no .env (dev) or /etc/credentials/desmo/.env.vm (VM) — relying on ambient environment.",
            file=sys.stderr,
        )
    else:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not QUOTED_VALUE.fullmatch(value):
                # A ` #` starts a trailing comment — strip it, then let
                # the quote strip below see the clean value.
                value = value.split(" #", 1)[0].strip()
            if QUOTED_VALUE.fullmatch(value):
                value = value[1:-1]
            os.environ[key] = value

    # ── guards ──
    _require_main_run("deployscratch")
    if not is_running_on_vm():
        shell.die("Refusing: deployscratch deploys the VM's main.")
    if not SCRATCH_DIR.is_dir():
        shell.die(f"Refusing: {SCRATCH_DIR} not found. Run createscratch first.")
    # Refuse the moment a backup is in flight — pgbackrest's own lock
    # report, verified live (a probe failure reads as not-running; a
    # deploy must not stall on a broken probe). The pre-migration backup
    # below would COALESCE with a running one (the safety copy silently
    # never runs).
    backup_held = False
    exit_code, probe_output = shell.capture(
        "sudo", "-u", "postgres", "pgbackrest", "--stanza=desmo", "info", "--output=json"
    )
    if exit_code == 0:
        try:
            backup_held = bool(json.loads(probe_output)[0]["status"]["lock"]["backup"]["held"])
        except ValueError, IndexError, KeyError, TypeError:
            backup_held = False
    if backup_held:
        shell.die("Refusing: a backup is running — let it finish, then re-run deployscratch.")

    # ── changed-set vs the frozen baseline + untracked files ──
    # One listing, computed once — the fast-path gate and the framework
    # watch below both classify this same set.
    exit_code, baseline = shell.capture(
        "git", "rev-parse", "--verify", "scratch-baseline", cwd=SCRATCH_DIR
    )
    if exit_code != 0 or not baseline:
        shell.die("REFUSING: no scratch-baseline ref — re-run ./run createscratch")
    exit_code, diff_files = shell.capture(
        "git", "diff", "--name-only", baseline, cwd=SCRATCH_DIR, quiet_stderr=False
    )
    if exit_code != 0:
        shell.die(
            f"REFUSING: git diff failed in {SCRATCH_DIR} — no deploy on a partial changed-set."
        )
    exit_code, untracked_files = shell.capture(
        "git", "ls-files", "--others", "--exclude-standard", cwd=SCRATCH_DIR, quiet_stderr=False
    )
    if exit_code != 0:
        shell.die(
            f"REFUSING: git ls-files failed in {SCRATCH_DIR} — no deploy on a partial changed-set."
        )
    changed = sorted({*diff_files.splitlines(), *untracked_files.splitlines()})
    fast_path = classify_changed_files(changed)

    # ── checks ──
    if fast_path.docs_or_frontend_only:
        print(
            "Fast path: frontend/docs-only changes — no backend checks, backup, migrate, or restarts."
        )
        if fast_path.frontend_changed:
            # Lint + build the SPA in scratch; the bundle rides the rsync.
            shell.run_step("npm run lint", "npm", "run", "lint", cwd=SCRATCH_DIR / "frontend")
            shell.run_step("npm run build", "npm", "run", "build", cwd=SCRATCH_DIR / "frontend")
            # Real pages in a real browser — lint and build cannot catch
            # runtime breakage; the smoke pass can (kept for framework
            # frontend edits — the app-surface classification decides).
            if fast_path.frontend_framework_changed:
                run_smoke_tests()
            else:
                print(
                    "No framework-file changes (outside the app surface) — skipping scratch-test-subset smoke."
                )
        # Design docs: validate every d2 fence in each changed file.
        # Deleted/renamed-away paths list here too — nothing to validate,
        # rsync --delete carries the removal.
        for relative_path in [path for path in changed if DOCS_MD.match(path)]:
            doc_path = SCRATCH_DIR / relative_path
            if not doc_path.is_file():
                continue
            shell.run_step(
                f"node deploy/checkmarkdownd2.mjs {relative_path}",
                "node",
                str(MAIN_DIR / "deploy" / "checkmarkdownd2.mjs"),
                str(doc_path),
            )
        step_banner("check battery (fast)")
    else:
        # The scratch/ fast loop: the agent's edits checked without the
        # unchanged framework suite or the slow browser pass — those stay
        # in main/'s checkframework1.
        print("Running ruff format --check (formatting drift)")
        shell.run_step(
            "uv run ruff format --check",
            "uv",
            "run",
            "ruff",
            "format",
            *RUFF_COLOR,
            "--check",
            cwd=SCRATCH_DIR,
        )
        print("Running ruff check (lint)")
        shell.run_step(
            "uv run ruff check", "uv", "run", "ruff", "check", *RUFF_COLOR, cwd=SCRATCH_DIR
        )
        print("Running mypy for type checking")
        shell.run_step("uv run mypy .", "uv", "run", "mypy", *MYPY_COLOR, ".", cwd=SCRATCH_DIR)
        print("Running ourapp tests (scoped; the framework suite runs in main/)")
        shell.run_step(
            "./run test ourapp --noinput",
            "uv",
            "run",
            "manage.py",
            "test",
            *DJANGO_NO_COLOR,
            "--exclude-tag",
            "playwright",
            "ourapp",
            "--noinput",
            cwd=SCRATCH_DIR,
            env=test_redis_env(),
        )
        print("Running frontend linting")
        shell.run_step("npm run lint", "npm", "run", "lint", cwd=SCRATCH_DIR / "frontend")
        print("Running frontend build (type-check + vite in one pass)")
        shell.run_step("npm run build", "npm", "run", "build", cwd=SCRATCH_DIR / "frontend")
        # Framework-file watch: edits outside the app surface mean framework
        # code changed → run the scratch-test-subset smoke (an early-warning
        # fraction of checkframework1; the full suite still gates in main/).
        outside = framework_files(changed)
        if outside:
            print("=== framework files changed — running scratch-test-subset smoke tests ===")
            print(f"  {len(outside)} files:")
            for changed_path in outside:
                print(f"  {changed_path}")
            run_smoke_tests()
        else:
            print(
                "No framework-file changes (outside the app surface) — skipping scratch-test-subset smoke."
            )
        step_banner("check battery")

    # ── deploy files ──
    print(
        f"Deploying {SCRATCH_DIR}/ → {MAIN_DIR}/ (--delete, excluding .git + gitignored/runtime dirs)…"
    )
    # sudo rsync: non-root can't preserve attrs on desmo-owned files
    # (exit 23), and scratch's files are default-user-owned. `.git` never
    # rides a deploy: scratch only borrowed main's history (git never
    # lists it, so no derived exclude covers it).
    excludes = rsync_excludes_file(r"^djangoapp/static/", SCRATCH_DIR, MAIN_DIR)
    shell.run(
        "sudo",
        "rsync",
        "-a",
        "--delete",
        "--exclude=.git/",
        f"--exclude-from={excludes}",
        f"{SCRATCH_DIR}/",
        f"{MAIN_DIR}/",
    )
    excludes.unlink(missing_ok=True)
    step_banner("rsync")
    # Own the tree as desmo AND group-write it (scratch's files arrive
    # default-user-owned; chown alone leaves rsync's 644/755 without g+w
    # — the next default-user build dies on desmo-owned dirs). dbbackups/
    # stays postgres-owned and mode 700; .venv/ + frontend/node_modules/
    # never ride the deploy rsync, so re-owning ~50k files of build
    # state would be pure waste — both PRUNED, on both sweeps.
    prune_paths = [
        "-path",
        str(MAIN_DIR / "dbbackups"),
        "-o",
        "-path",
        str(MAIN_DIR / ".venv"),
        "-o",
        "-path",
        str(MAIN_DIR / "frontend" / "node_modules"),
    ]
    shell.run(
        "sudo",
        "find",
        str(MAIN_DIR),
        "(",
        *prune_paths,
        ")",
        "-prune",
        "-o",
        "-exec",
        "chown",
        "desmo:desmo",
        "{}",
        "+",
    )
    shell.run(
        "sudo",
        "find",
        str(MAIN_DIR),
        "(",
        *prune_paths,
        ")",
        "-prune",
        "-o",
        "-exec",
        "chmod",
        "g+w",
        "{}",
        "+",
    )
    step_banner("own")

    # ── backend tail ──
    # Backup + migrate only when backend code changed; collectstatic when
    # the bundle changed; restart only for backend — static chunks and
    # tree-served docs need no service restart.
    if not fast_path.docs_or_frontend_only:
        # Pre-migration snapshot through the real unit — the DB state to
        # restore to if this deploy's migrate goes wrong.
        shell.run("sudo", "systemctl", "start", "desmo_pgbackrest.service")
        step_banner("backup")
        shell.run(
            "uv", "run", "--no-sync", "python", "manage.py", "migrate", "--noinput", cwd=MAIN_DIR
        )
        step_banner("migrate")
    if not fast_path.docs_or_frontend_only or fast_path.frontend_changed:
        print("collectstatic…")
        shell.run(
            "uv",
            "run",
            "--no-sync",
            "python",
            "manage.py",
            "collectstatic",
            "--noinput",
            "--clear",
            cwd=MAIN_DIR,
        )
        step_banner("collectstatic")
    if not fast_path.docs_or_frontend_only:
        print("restarting services…")
        # Huey's unit always exists on provisioned VMs (HUEY_WORKERS ≥ 1
        # is enforced at provisioning).
        shell.run("sudo", "systemctl", "daemon-reload")
        shell.run("sudo", "systemctl", "restart", "desmo_granian.service", "desmo_huey.service")
        step_banner("restart")

    # ── closing ──
    url_base = share_url_base(os.environ.get("BASE_URLS", ""))
    print("App is available under:")
    shell.run("uv", "run", "--no-sync", "python", "manage.py", "baseurls", cwd=MAIN_DIR)
    step_banner("baseurls")
    print("Deployed scratch/ → main/ (uncommitted, services live). Commit in main/ when ready.")
    print(
        "Share absolute URLs you verified exist in main/ at the BOTTOM of your message (with the summary):"
    )
    print(f"  docs: {url_base}/files/main/ourapp/docs/<feature>.md · pages: {url_base}/<page-url>")
