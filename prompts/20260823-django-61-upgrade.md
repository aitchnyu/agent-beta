# Django 6.1 upgrade (+ django-stubs 6.1)

Planned 2026-08-23, NOT yet implemented. Extracted from
prompts/20260818-vm-provisioning-multipass.md Part 6 (VM-provisioning
file) into its own home — different concern, different work.

Django 6.1 released 2026-08-05 (6.1.x latest); django-stubs 6.1.0 released
2026-08-12 (Django 6.1 support; 6.0/5.2 partial). Current: django 6.0.6,
django-stubs 6.0.5, mypy 2.1.0, python 3.14 (in 6.1's supported set).

## Risk audit (verified by grep over djangoapp/ourapp/djangoproject)

ZERO hits on every 6.1 breaking/deprecated pattern:
- No bare `select_related()`, no `values_list(flat=True)` without a field,
  no `.first()/.last()` after cleared `order_by()`, no queryset
  union/difference/intersection, no `RawSQL`, no `salted_hmac`/signing
  (TestLoginKey uses hashlib.sha256 directly), no `transaction.savepoint`
  in app code, no `from_db` override, no EMAIL_* settings (the
  ACCOUNT_EMAIL_* lines are allauth's), `finders.find` used positionally.
- JSONField usage is storage-only (no top-level `None` queries) → the
  JSONNull deprecation is irrelevant.
- Signed cookies not used; DB cache not used (Redis); RemoteUserMiddleware
  not used.
- Floors: Django 6.1 needs PG 15+ — dev runs PG 18.0, VM 18.6. OK.
- Admin: cosmetic changes only (we barely use /admin).
- Removed-in-6.1 items: none referenced (auth.login always gets an
  explicit user; no postgres ArrayAgg ordering).

## Features useful to THIS codebase

- **FETCH_PEERS / FETCH_RAISE fetch modes** (`QuerySet.fetch_mode()`): the
  genuinely interesting one — opt-in N+1 elimination for list endpoints
  (UserList, ModelRows) and a guard for hot paths. FOLLOW-UP material,
  not part of the upgrade.
- **UUID7 db function**: no-op for us — BaseModel already generates UUID7
  pks Python-side (`generate_uuid7_id`, base.py:16).
- **argparse `suggest_on_error` on py3.14**: free UX win for our four
  management commands, automatic.
- **assertContains repeatable on StreamingHttpResponse; SessionBase
  __bool__**: minor test niceties.
- Not useful now: Mailers (no email flows), DB_CASCADE (we rely on
  Python-level cascade semantics; note DB_CASCADE skips pre/post_delete
  signals — check base.py hooks before EVER switching), admin/CSP/GIS.

## Dependencies

- allauth 65.18 → 65.19.1 (pins Django>=4.2.16 — fine; bump with the rest)
- ninja 1.6.2 → 1.6.3 (Django>=3.1 — fine)
- inertia-django 2.0.0 (django>=5.2 — fine as-is)
- psycopg2-binary, huey, structlog: unaffected.

## django-stubs 6.0.5 → 6.1.0: what actually changes for us

The jump crosses the whole 6.0.6–6.1.0 strictness line (6.0.8 was the big
one). Audited against our code:

Likely-touched (verified patterns):
- `objects = UserManager()  # type: ignore[misc]` (base.py:49) — manager
  resolution was REWORKED (6.0.7 as_manager fix; 6.0.8 synthetic manager
  classes): the ignore may become unnecessary (unused-ignore) or need a
  different code. Check after bump; 8 total type-ignores repo-wide, so the
  sweep is small either way.
- `save(update_fields=…)` typecheck against model fields (6.0.6) — only
  relevant if base.py's `update()` passes update_fields; grep says it
  doesn't (it saves whole instances).
- Field generics (6.0.8: `Field` now takes type args; bare annotations
  flagged) — our fields are inline assignments (`models.JSONField(default=
  dict)`), not annotations; should pass untouched.
- `get_or_create`/`update_or_create` kwargs typecheck (6.0.3) — used in
  tests/fixtures only; failures there are quick fixes.
- mypy cache invalidation on INSTALLED_APPS changes (6.0.8) — no action,
  just faster re-runs after settings edits.
- View/TemplateView response generics, Client headers Mapping, middleware
  composition typing — zero hits (function views + ninja; no header dicts
  in our test base).

New in 6.1.0 proper: stubs for fetch modes + DB_CASCADE + mailers (only
useful if/when we adopt those features); implicit M2M through default
manager (no implicit M2M in our models); queryset `update()` custom
arguments (we don't subclass).

Expectation: U3 is a SHORT pass — the dominant risk is the one manager
ignore plus incidental test-fixture kwargs fixes. mypy CAN ride the same
upgrade: stubs 6.1.0's compatible-mypy extra pins `mypy>=1.13,<2.4` and
the stubs project tests against 2.3 — bump mypy 2.1.0 → 2.3.1 together
(U1 adds `mypy>=2.3.1,<2.4`); expect at most a few new strictness errors
of mypy's own (the 2.x line tightened inference around generics/overloads
— same likely spots as the stubs items above).

## Upgrade plan (when GO)

- [ ] U1 `uv add "django>=6.1,<6.2" "django-stubs[compatible-mypy]>=6.1.0,<6.2"`
      (allauth/ninja ride along to latest within existing floors).
- [ ] U2 Deprecation sweep: `./run python -Wa manage.py test
      djangoapp ourapp` — surface anything the grep audit missed before
      it becomes a 7.0 removal.
- [ ] U3 Fix NEW mypy errors from stubs 6.0.5→6.1.0 strictness jumps
      (expected small; likely spots: base.py custom manager/QuerySet
      generics, View response-type generics, get_or_create kwargs
      typecheck added in stubs 6.0.3-6.0.8 line).
- [ ] U4 `./run djangomanage makemigrations --check` (expect: no changes).
- [ ] U5 Full gates: `./run checkall` (ruff, mypy, backend+Playwright,
      frontend untouched).
- [ ] U6 Live VM: sync + restart app_granian/app_huey (uv sync on next
      provision picks 6.1 automatically; no unit/template changes needed).
- [ ] U7 Record as-built; note the FETCH_PEERS follow-up candidate.
