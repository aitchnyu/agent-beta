## Minimize `# noqa` across the backend

Find every `# noqa` in the Python codebase and reduce the count. Keep the ones that are genuinely necessary (framework internals, circular imports), remove the ones that are avoidable (missing annotations, magic numbers, shadowed builtins), and replace repeated patterns with scoped `per-file-ignores`. RUF100 must stay as the guardrail that flags mechanically-redundant `# noqa` going forward.

References: `TODO.md` lines 16-22 (PLR0913, RUF100, ARG002 ninja signature, PLC0415 imports).

### Current state (audit)

- Total: ~139 `# noqa` across ~20 files (counts below are approximate; verify before editing).
- RUF100 is **already enabled** via `select = ["ALL"]` (`pyproject.toml:38`). A normal `uv run ruff check` reports `All checks passed!`, which means there are **no** mechanically-redundant `# noqa` right now.
- Gotcha: `uv run ruff check --select RUF100` (standalone) reports ~146 false "unused noqa (non-enabled)" errors because every other rule is deselected. Do **not** trust that output; only the full-config run is authoritative. This addresses the `RUF100` note in `TODO.md:17`.

Approximate breakdown by rule:

| Rule | Count | Where | Why |
|------|-------|-------|-----|
| ANN401 (`Any` annotation) | ~53 | serializers.py (~33), responses.py (~11), common_filters.py (2), views/base.py (2), models/base.py (5) | Django/Pydantic field values are genuinely `Any` |
| SLF001 (private access) | ~26 | views/base.py, models/base.py, serializers.py, many `djangoapp/tests/**` | Django `_meta`, Ninja `_routers`, internal fields in tests |
| ARG002 (unused arg) | ~20 | serializers.py base methods, models/base.py, models/app.py | Template Method base signatures; overridden in subclasses |
| ARG001 (unused arg) | ~3 | views/articles.py (2), views/base.py (1) | Ninja requires `request` param |
| PLC0415 (late import) | ~5 | models/base.py (3), views/app.py, manage.py | Circular-import avoidance, inner-class import |
| PLR0913 (too many args) | 3 | models/base.py (1349, 1872, 1915) | `User.update`, `Article.create`, `Article.update` |
| E501 / W505 (long lines/docs) | 4 / 2 | models/base.py (1198, 1210, 1500, 1501) | Long docstrings + commented mypy errors |
| DTZ001 (naive datetime) | 2 | tests/views/test_views.py (198, 266) | Intentional input to `make_aware` |
| PLR2004 (magic value) | 2 | tests/test_createrows.py (24), tests/playwright/test_playwright.py (3799) | Test counts |
| ANN001 (missing annotation) | 2 | tests/views/test_views.py (1252), tests/playwright/test_notifications.py (16) | `user` param |
| D105 (missing `__str__` docstring) | 2 | models/base.py (1710, 1780) | Intentionally undocumented dunder |
| N802 (naming, stubs) | 5 | stubs/inertia/test.pyi | Third-party API names |
| ANN401 (stubs) | 2 | stubs/prison/__init__.pyi | Stub return `Any` |
| Others (1-2 each) | ~10 | S308 (mark_safe), S105 (settings), TC003 (responses), PLW0603/02 (views/base), DJ001 (models/app), A001 (test_filters), ARG003/ANN002/ANN003 (createrows) | Mixed |

### Constraint

AGENTS.md forbids editing `tool.ruff.lint.ignore` to suppress errors. Therefore the minimization uses three levers only:

1. **Refactor** the code so the lint no longer fires (preferred where cheap).
2. **`[tool.ruff.lint.per-file-ignores]`** for a pattern that is intentional and repeated across one file/directory (scoped, not global).
3. **Threshold config under the rule's own section** (e.g. `max-args`) — this is not `lint.ignore`.

A handful of `# noqa` stay inline where they explain a one-off framework quirk (circular import, `mark_safe`).

### Plan

- **Phase 1 - Guardrail**: confirm RUF100 is active via `ALL` (already true); document the standalone-`--select RUF100` gotcha so nobody chases phantom errors.
- **Phase 2 - Cheap refactors** (one-line or near-one-line, high signal): annotate `user` params, rename `filter`, annotate `handle(*args, **options)`, reformat long docstrings/commented lines, extract magic numbers, fix naive datetimes.
- **Phase 3 - Pervasive intentional patterns -> `per-file-ignores`**: move `ANN401` (serializers/responses/common_filters/views-base), `ARG002` (serializers base methods), `SLF001` (tests + Django/Ninja internal access), `S308` (templatetags), `D105` (models dunder) off inline noqa into scoped per-file config. This deletes the bulk of the noqa in one controlled edit.
- **Phase 4 - Thresholds / structural**: bump `max-args` for the 3 `PLR0913` manager methods (or, the proper fix, bundle params into the context classes mentioned in `TODO.md` "Simplify context classes" — separate task).
- **Phase 5 - Keep & document**: the unavoidable ones (`PLC0415` circular imports, `TC003` pydantic runtime import, `PLW0603` module singletons, `S105`, `DJ001` test fixture).
- **Phase 6 - Stubs**: decide whether `stubs/**` should be linted at all (likely `per-file-ignores` or excluded).
- **Phase 7 - Prevent regression**: add an AGENTS.md note that repeated noqa should become `per-file-ignores`, and that the full `ruff check` (not standalone RUF100) is the source of truth.

### Checklist

#### Phase 1: RUF100 guardrail

- [ ] confirm `select = ["ALL"]` keeps RUF100 active (`pyproject.toml:38`) — no edit needed
- [ ] add a one-line note (AGENTS.md or this file) that `ruff check --select RUF100` alone is misleading; only full-config run is authoritative

#### Phase 2: Cheap refactors (inline noqa removed by fixing the code)

- [x] annotate the untyped `user` parameter in
    - [x] `djangoapp/tests/views/test_views.py:1252`
    - [x] `djangoapp/tests/playwright/test_notifications.py:16`
- [x] rename shadowing builtin `filter = RowUpdateFilter()` at `djangoapp/tests/test_filters.py:1606` -> `row_update_filter`
- [x] annotate `Command.handle` to drop `no-untyped-def`/`ANN002`/`ANN003` at
    - [x] `djangoapp/management/commands/createrows.py:23` (`*args: Any, **options: Any`; `# noqa: ANN401, ARG002` stays inline)
    - [x] `djangoapp/management/commands/deletenotifications.py:9` (same pattern; found during impl - was in the truncated tail of the audit)
- [x] reformat long docstrings to remove `E501` at
    - [x] `djangoapp/models/base.py:1198`
    - [x] `djangoapp/models/base.py:1210`
- [~] `djangoapp/models/base.py:1500,1501` (`E501, W505`) **kept inline** - these are user comments documenting a mypy quirk; AGENTS.md says do not reformat/delete comments
- [~] `PLR2004` at `djangoapp/tests/test_createrows.py:24` and `djangoapp/tests/playwright/test_playwright.py:3799` **kept inline** (2 explained test counts; not worth weakening the rule for tests)
- [~] `DTZ001` at `djangoapp/tests/views/test_views.py:198,266` **kept inline** - `make_aware` intentionally takes a naive datetime

#### Phase 3: Pervasive intentional patterns -> `per-file-ignores`

- [x] add `per-file-ignores` entry to drop `ANN401` noqa from
    - [x] `djangoapp/serializers.py` (~33)
    - [x] `djangoapp/responses.py` (~11)
    - [x] `djangoapp/templatetags/common_filters.py` (2)
    - [x] `djangoapp/views/base.py` (2)
    - [x] `djangoapp/models/base.py` (5)
- [x] add `per-file-ignores` entry to drop `ARG002` noqa from `djangoapp/serializers.py` base Template-Method methods (~14)
- [x] add `per-file-ignores` entry for `SLF001` on the whole `djangoapp/tests/**` tree (legitimate internal access in tests)
- [x] prod `SLF001` policy: per-file-ignore `SLF001` for `djangoapp/views/base.py` + `djangoapp/models/base.py` (Django `_meta` / Ninja internals)
- [x] add `per-file-ignores` `S308` for `djangoapp/templatetags/common_filters.py` (intentional `mark_safe`)
- [x] add `per-file-ignores` `D105` for `djangoapp/models/base.py` dunder `__str__` (1710, 1780) — no docstrings wanted unless explicitly asked

#### Phase 4: PLR0913 (3 noqa in manager create/update)

- [~] **kept inline** - decided NOT to bump `max-args` (would weaken `PLR0913` everywhere) nor per-file-ignore it for one file. The 3 noqa (`models/base.py:1349,1872,1915`) are well-explained ("all needed for ... update"); the proper fix (bundle params into context objects) is tracked in `TODO.md` "Simplify context classes".

#### Phase 5: Keep inline (unavoidable), comment explains why

- [x] keep `PLC0415` circular-import noqa at
    - [x] `djangoapp/models/base.py:1088`
    - [x] `djangoapp/models/base.py:1451`
    - [x] `djangoapp/models/base.py:1676`
    - [x] `djangoapp/views/app.py:265`
    - [x] `manage.py:12`
- [x] keep `TC003` at `djangoapp/responses.py:9` and `djangoapp/filters.py:3` (pydantic runtime import)
- [x] keep `PLW0603, PLW0602` at `djangoapp/views/base.py:300` (module singletons)
- [x] keep `S105` at `djangoproject/settings.py:29` (comparison, not assignment)
- [x] keep `DJ001` at `djangoapp/models/app.py:223` (test-fixture model)
- [x] keep single-instance `SLF001` (`djangoapp/serializers.py:689`, `djangoapp/filters.py:336`) and `ARG002`/`ARG001` interface params (`filters.py:372`, `models/app.py:86,95`, `views/articles.py:628,640`, `views/base.py:89`) inline - 1-2 each, not worth broadening ignores
- [x] keep `maintain.py:12` `ARG002` inline (already annotated)

#### Phase 6: Stubs

- [x] policy: `per-file-ignores` `["ANN401", "N802"]` for `stubs/**/*.pyi`
    - [x] `stubs/inertia/test.pyi` (N802 x5)
    - [x] `stubs/prison/__init__.pyi` (ANN401 x2)

#### Phase 7: Prevent regression

- [~] add AGENTS.md note: repeated noqa of the same rule in one file -> prefer `per-file-ignores`; full `ruff check` (incl. RUF100) is the source of truth — **not applied (user declined AGENTS.md edit)**; guidance lives in this prompts file and the `per-file-ignores` comment block in `pyproject.toml` instead
- [x] after edits, ran `./run checkall` -> green (ruff + mypy + 548 backend tests + frontend lint/type-check + 176 playwright tests)

### Outcome

Reduced from **~139** inline noqa to **31**, all justified and explained. Mechanism: 5 cheap refactors + `per-file-ignores` for 7 intentional patterns (ANN401/ARG002/SLF001/S308/D105 across serializers, responses, common_filters, views/base, models/base, tests/**, stubs/**). RUF100 (already active via `select = ["ALL"]`) auto-stripped the 111 noqa that the per-file-ignores made redundant, and remains the guardrail against future redundant noqa. The remaining 31 are: framework signatures (Ninja `request`, Django `handle`), circular imports (`PLC0415`), runtime imports (`TC003`), module singletons (`PLW0603/02`), well-explained `PLR0913` manager methods, test-specific (`DTZ001`/`PLR2004`), and user comments (`E501, W505`).

### Refinement (follow-up): drop exemptions that cover < 10 instances

Re-audited each `per-file-ignores` rule by instance count. A blanket exemption on a large first-party file is overkill when only a handful of spots need it (it silences the rule for the whole file). Removed the entries where every rule was < 10 instances, and handled each spot directly:

- **`djangoapp/views/base.py`** — REMOVED. ANN401 (2), ARG002 (2), SLF001 (8). Restored inline `# noqa` (framework internals: Django `_meta`, Ninja `_routers`/`_frozen`; no public API / interface params).
- **`djangoapp/models/base.py`** — REMOVED. ANN401 (5), ARG002 (2), SLF001 (4) restored inline; **D105 (2) FIXED with docstrings** on the two `__str__` methods (`models/base.py:1710`, `:1780`) instead of noqa.
- Kept `serializers.py` (ANN401 ~33, ARG002 ~14), `responses.py` (ANN401 10), `tests/**` (SLF001 12) — all >= 10.
- Kept `stubs/**/*.pyi` (ANN401 2, N802 5): these mirror third-party APIs (inertia camelCase, prison `Any` returns) and are unfixable; the glob is already scoped to stub files only, so it is not a blanket silence over first-party code.

Net inline noqa now ~55 (was 31): the trade for re-enabling ANN401/ARG002/SLF001/D105 lint coverage across the rest of `views/base.py` and `models/base.py`. `ruff check`, `mypy`, and the 548-test backend suite are green.
