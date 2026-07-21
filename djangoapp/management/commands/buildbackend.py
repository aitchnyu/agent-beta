"""Install (or update) an app by running its ``app.py`` setups + self-tests.

Usage: ``./run djangomanage buildbackend <app>``

Resolves the app's ``app.py`` from the apps root
(``<apps_root>/<app>/app.py``), imports it
(``app_modules.load(..., force_reload=True)`` so re-runs pick up edits), then
runs its ``@setup`` functions. An app may declare several ``@setup``s; they
run in source order, and the run **resumes from the last completed one**:
``Application.executed_setups`` records the ``__name__``s of setups that have
already finished, and this command runs only the pending ones (forward-only,
like DB migrations). After the setups, every ``@backend_test`` runs in-process.

The remaining setups are printed before running.

Resume safety: the loaded module's setup ``__name__``s must be an exact prefix
of ``executed_setups`` (same names, same order, same-or-longer). A rename,
reorder, mid-list deletion, or downgrade is refused with a ``CommandError``
naming both lists.

If any setup or test fails, the whole run is rolled back — the transaction
(Postgres transactional DDL) reverts every created app/table and the
dynamic-model registry cache is reset — so a failed install leaves nothing
behind (and ``executed_setups`` is unchanged). Exits non-zero on failure so an
agent can use it as a feedback loop.

The core logic lives in :func:`build_backend` (callable directly, e.g. from
tests); :class:`Command` is a thin wrapper that styles output.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from djangoapp.apps.dynamic_module import app_modules, apps_root
from djangoapp.models.applications import Application, AppsGeneration
from djangoapp.models.dynamic import dynamic_models

if TYPE_CHECKING:
    from collections.abc import Callable


def _stderr_line(msg: str) -> None:
    """Default failure line-writer for :func:`build_backend` (plain stderr, no style)."""
    sys.stderr.write(f"{msg}\n")


def _stdout_line(msg: str) -> None:
    """Default progress line-writer for :func:`build_backend` (plain stdout, no style)."""
    sys.stdout.write(f"{msg}\n")


def _remaining_setups(
    identity: str,
    executed: list[str],
    setups: list[Callable[..., object]],
) -> list[Callable[..., object]]:
    """Return the setups still to run — the slice past the executed prefix.

    buildbackend resumes forward-only: the ``@setup`` functions that already ran
    must stay at the top of ``app.py`` with the same names in the same order.
    This verifies that and returns the suffix to run; any drift raises
    :class:`CommandError` with a human-readable diff naming both lists. Returns
    ``setups[len(executed):]`` on success — exactly the callables
    ``build_backend`` prints + runs.
    """
    setup_names = [fn.__name__ for fn in setups]

    def rule() -> str:
        """State the shared, human-readable resume invariant."""
        return (
            f"buildbackend {identity}: cannot resume @setup.\n"
            "The @setup functions that already ran must stay in "
            "app.py — every previous name preserved, in the original order "
            "(forward-only, like DB migrations). To change earlier work, append "
            "a new @setup; don't rename, reorder, or remove the ones that "
            "already ran.\n"
            f"  already ran: {executed}\n"
            f"  app.py now:  {setup_names}"
        )

    if len(setup_names) < len(executed):
        missing = len(executed) - len(setup_names)
        msg = (
            f"{rule()}\n"
            f"app.py has fewer @setups ({len(setup_names)}) than already ran "
            f"({len(executed)}) — {missing} setup(s) went missing."
        )
        raise CommandError(msg)
    if setup_names[: len(executed)] != executed:
        first_diff = next(
            i
            for i, (ran, now) in enumerate(zip(executed, setup_names, strict=False))
            if ran != now
        )
        msg = (
            f"{rule()}\n"
            f"First mismatch at position {first_diff + 1}: "
            f"was {executed[first_diff]!r}, now {setup_names[first_diff]!r}."
        )
        raise CommandError(msg)
    return setups[len(executed):]


def _run_backend_tests(
    identity: str,
    tests: list[Callable[..., object]],
    err_write: Callable[[str], object],
) -> None:
    """Run each ``@backend_test`` in its own rolled-back savepoint.

    A test's writes never leak into the installed app or affect the next test.
    The first failing test halts the run: its name + traceback go through
    ``err_write`` (Django prints only the ``CommandError`` message), then a
    :class:`CommandError` is raised so the caller's atomic rolls everything back.
    """
    for test in tests:
        sid = transaction.savepoint()
        try:
            try:
                test()
            except Exception as test_exc:
                err_write(f"buildbackend {identity}: @backend_test {test.__name__} failed")
                err_write(traceback.format_exc().rstrip())
                msg_0 = f"buildbackend {identity} failed in @backend_test {test.__name__}"
                raise CommandError(msg_0) from test_exc
        finally:
            transaction.savepoint_rollback(sid)
            transaction.savepoint_commit(sid)


def build_backend(
    identity: str,
    *,
    out_write: Callable[[str], object] | None = None,
    err_write: Callable[[str], object] | None = None,
) -> int:
    """Install/update ``<app>``: resume setups from the last completed, then run ``@backend_test``s.

    Raises :class:`CommandError` on any failure (after writing the failing
    setup/test's name + traceback via ``err_write``, so the detail isn't lost —
    Django prints only the ``CommandError`` message). Progress (the remaining
    setups + per-step lines) is written via ``out_write``. Returns the number
    of ``@backend_test``s run. ``out_write``/``err_write`` default to
    :func:`_stdout_line`/:func:`_stderr_line`; the command passes styled writers.
    """
    if out_write is None:
        out_write = _stdout_line
    if err_write is None:
        err_write = _stderr_line
    if "/" in identity:
        msg = f"Expected '<app>' (a single name), got {identity!r}."
        raise CommandError(msg)
    app_name = identity
    # Derived from apps_root + name: no Application row need exist yet (the
    # first @setup is what creates it on a fresh install), so
    # Application.script_path() can't be used here — only after install.
    script_path = (apps_root() / app_name / "app.py").resolve()

    # force_reload: even though buildbackend is a fresh CLI process,
    # build_backend() is called in-process by tests, so a second install of
    # the same path must re-import (picks up edits / re-runs @setup registration)
    # rather than reuse the cached module. A missing/empty app.py raises
    # FileNotFoundError/ValueError from load — let those propagate (a clean
    # non-zero exit) instead of wrapping them in CommandError.
    dynamic_module = app_modules.load(script_path, force_reload=True)

    try:
        with transaction.atomic():
            # Resume decision: read the recorded prefix and verify the loaded
            # module extends it (pure check in _remaining_setups, which returns
            # the setups still to run). Read + write are in one atomic so a
            # concurrent install can't race the executed_setups update
            # (best-effort: the command is CLI-run).
            existing = Application.objects.filter(name=app_name).first()
            executed: list[str] = list(existing.executed_setups) if existing else []
            remaining_functions = _remaining_setups(identity, executed, dynamic_module.setups)

            names = [fn.__name__ for fn in remaining_functions]
            remaining = ", ".join(names) or "(none — already complete)"
            out_write(f"Remaining setups for {identity}: {remaining}")
            for function in remaining_functions:
                out_write(f"  running {function.__name__}")
                try:
                    function()
                except Exception as setup_exc:
                    err_write(f"buildbackend {identity}: @setup {function.__name__} failed")
                    err_write(traceback.format_exc().rstrip())
                    msg_1 = f"buildbackend {identity} failed in @setup {function.__name__}"
                    raise CommandError(msg_1) from setup_exc
                # Append this setup's name to executed_setups and persist
                # through the model layer (.save, not a raw .update) so
                # Application.save hooks fire — the same path create_application
                # writes through. Inside the atomic, a later step's failure
                # rolls the list back to the pre-run value (and a fresh-install
                # failure rolls back the row entirely), so executed_setups only
                # advances on real progress.
                executed.append(function.__name__)
                application = Application.objects.get(name=app_name)
                application.executed_setups = executed
                application.save()

            _run_backend_tests(identity, dynamic_module.backend_tests, err_write)
            # Bump the apps generation so running server workers invalidate their
            # dynamic-model/app-module caches (no restart needed).
            AppsGeneration.bump()
    except CommandError:
        # A setup/test/resume failure above (already reported) — roll back + reset.
        dynamic_models.reset()
        raise
    except Exception as exc:
        # DDL is transactional, so the atomic rollback drops every created
        # physical table; reset the registry so no in-memory model leaks.
        # Wrap any failure (setup error, bad column, assertion) in
        # CommandError so the command exits non-zero with one clear cause.
        dynamic_models.reset()
        msg = f"buildbackend {identity} failed: {exc}"
        raise CommandError(msg) from exc

    return len(dynamic_module.backend_tests)


class Command(BaseCommand):
    """``djangomanage buildbackend <app>`` — resume setups + self-test an app."""

    help = "Install (or update) an app: resume its @setup functions, then run @backend_tests."

    def add_arguments(self, parser: Any) -> None:  # noqa: ANN401 # Django parser is untyped
        parser.add_argument(
            "app",
            help="App identity as '<app>' (e.g. HappyPathApp).",
        )

    def handle(self, *_args: Any, **options: Any) -> None:  # noqa: ANN401 # Django options is untyped
        identity: str = options["app"]
        count = build_backend(
            identity,
            out_write=self.stdout.write,
            err_write=lambda msg: self.stderr.write(self.style.ERROR(msg)),
        )
        self.stdout.write(self.style.SUCCESS(f"Installed {identity}: ran {count} test(s)."))
