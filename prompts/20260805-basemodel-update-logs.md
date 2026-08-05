# BaseModel audit fields + `BaseModelUpdateLog` + management-page logs

## Goal
Give every `BaseModel` row standard audit fields and a generic CRUD log, and show
those logs in the superuser models-management UI.

- `BaseModel` gains: `public_id`, `created_by` (nullable User), `created_at`,
  `last_updated_at`, `last_updated_by` (nullable User). (Today these are the
  underscore-prefixed `_public_id`/`_created_by`/`_created_at`/`_edited_at` at
  `djangoapp/models/base.py:354` — renamed + `last_updated_by` added.)
- New model `BaseModelUpdateLog` records create/update/delete per row, with
  typed JSON `old_values`/`new_values`.
- `BaseModel.save_with_logs(user)` / `.delete_with_logs(user)` are the logged
  write paths.
- Models page: `BaseModel` rows sort by `id`/`-id`/`last_updated_at`; a row's
  logs load as a **lazy Inertia prop** on the row-detail page.

## Decisions (locked)
- **`User` is out of scope.** `User` subclasses `AbstractUser` (not `BaseModel`)
  and keeps its own `UserHistory` (`djangoapp/models/base.py:241`). Do not route
  User edits through `BaseModelUpdateLog`; leave `UserHistory`/`User.update` as-is.
- **`last_updated_at` is NOT `auto_now`.** It is a plain `DateTimeField` set
  explicitly in `save_with_logs` together with `last_updated_by`, so the two
  never drift. (`created_at` stays `auto_now_add`.)
- **`performed_by` is `SET_NULL`.** Audit survives the actor's deletion (matches
  `UserHistory.user`; never `CASCADE`).
- **`model_pk` is integer, server-side only, never sent to clients.** The log's
  own `id` is uuid7 (safe to expose); FK values inside `old/new_values` carry the
  target's **`public_id`**, never its integer pk (pk-leak rule).
- **Update diff = changed fields only.** On `updated`, `old_values`/`new_values`
  contain only the supported columns that actually changed (no noise; matches the
  existing `UserSnapshot.difference` behaviour). On `created`, `old_values={}`,
  `new_values`=all supported columns. On `deleted`, `old_values`=supported-column
  snapshot of the deleted row, `new_values={}` (so the audit shows what was
  removed).
- **`model` resolution.** `BaseModel.log_model_name()` (classmethod) returns
  `cls.log_as_name or f"{cls.__module__}.{cls.__name__}"`. `log_as_name:
  ClassVar[str | None] = None`. Same value used on **write and read** (the detail
  view filters logs by `model=<row's class>.log_model_name(), model_pk=row.pk`).
  Because `__module__` differs between prod (`ourapp.models`) and the test fixture
  app, set `log_as_name` on test-app models so tests resolve the same way.
- **Value JSON shapes** (per supported Django field kind):
  - bool → `true`/`false`
  - str (Char/Text/Email/Slug) → `"val"`
  - num (Integer/Decimal/Float/SmallInt/BigInt) → **string** `"123"` (safe for
    big ints / decimals)
  - date/datetime → ISO `"2026-07-21T12:00:00Z"`
  - FK → `{ "id": <target public_id>, "url": <target.get_absolute_url()>, "name": <str(target)> }`
    (only `BaseModel`/`User` targets; `url` for `User` = its profile URL)
  - unsupported (FileField, JSONField, ManyToMany, BinaryField, DurationField,
    UUIDField, DateField-not-datetime) → **omitted** from the diff.
- **Lazy logs = Inertia partial reload.** `RowDetailProps` gains an optional
  `logs` prop; the page omits it on first render and calls
  `router.reload({ only: ["logs"] })` to fetch it. The view returns just `logs`
  when `only` requests it.

## Resolved (from review)
- **Sort options** = `-id` / `id` / `-last_updated_at` / `last_updated_at`. `id`/`-id`
  work for **all** models (BaseModel and non-BaseModel); `last_updated_at`/`-last_updated_at`
  only for `BaseModel`. `created_at` is **not** a sort option.
- **Models page lists non-BaseModel models too** — `_ourapp_models()`
  (`djangoapp/views/manage.py:147`) drops the `issubclass(m, BaseModel)` filter; each
  model's sort set + column set branch on whether it's a `BaseModel` subclass.
- **Builtins are regular columns** — `public_id`/`created_by`/`created_at`/
  `last_updated_at`/`last_updated_by` are NOT special-cased; they appear in the
  `columns` list and render via the standard `RowCell` path (still exclude the
  auto `id` pk — it's a sort key, never a displayed value, and must never reach the
  client). The special `created_by`/`created_at`/`edited_at` props on
  `RowItem`/`RowDetailProps` are removed.

## Phased checklist

### Phase 1 — `BaseModel` field refactor (`_` → public names + `last_updated_by`)
- [ ] `djangoapp/models/base.py:354` — rename fields on `BaseModel`:
    - [ ] `_public_id` → `public_id` (keep `db_index`, `editable=False`, `default=generate_uuid7_id`)
    - [ ] `_created_by` → `created_by`
    - [ ] `_created_at` → `created_at` (keep `auto_now_add`)
    - [ ] `_edited_at` → `last_updated_at` (**drop `auto_now`**; plain DateTimeField)
    - [ ] add `last_updated_by` (FK `User`, `null=True/blank=True`, `on_delete=SET_NULL`, `related_name="+"`)
- [ ] Add `ClassVar[str | None] log_as_name = None` and classmethod `log_model_name()` to `BaseModel`
- [ ] Update `get_absolute_url()` (`base.py:384`) and `__str__` to use `self.public_id`
- [ ] **Treat builtins as regular columns** — `djangoapp/views/manage.py:166`
      `_user_fields` currently hides built-ins via `not f.name.startswith("_")`. Drop
      that exclusion so `public_id`/`created_by`/`created_at`/`last_updated_at`/
      `last_updated_by` flow into `columns` like any user field (still exclude the auto
      `id` pk — pk-leak rule). Remove the special `created_by`/`created_at`/`edited_at`
      props from `RowItem`/`RowDetailProps`; builtins render via `RowCell` inside `values`.
- [ ] Update every `manage.py` reference to the old underscore names:
    - [ ] `_row_item` (`manage.py:268`) — `public_id`/`created_by`/`created_at`; add `last_updated_at`/`last_updated_by`; rename `edited_at` → `last_updated_at`
    - [ ] `_fk_value` (`manage.py:224`) — `_public_id` → `public_id`
    - [ ] `model_rows_page` (`manage.py:312`) — `select_related("_created_by")` → `created_by`, add `last_updated_by`; `order_by("-_public_id")` → `public_id`
    - [ ] `row_detail_page` (`manage.py:356`) — same select_related + `_public_id=` filter → `public_id=`
    - [ ] `RowItem`/`RowDetailProps` pydantic — add `last_updated_at`/`last_updated_by`; rename `edited_at`
- [ ] Migrations:
    - [ ] `./run djangomanage makemigrations djangoapp` (rename fields + add `last_updated_by` to each concrete `BaseModel` subclass)
    - [ ] regenerate/extend the **testapp** fixture migration `djangoapp/tests/testapp/ourapp/migrations/0001_initial.py` (it declares `_edited_at`/`_created_by`) — add a rename migration or regenerate under `checkproject`
    - [ ] use **RenameField** (preserve data + index/default), not drop+add
- [ ] Sweep the repo for the old underscore names and fix all call sites:
    - [ ] `djangoapp/tests/views/test_manage_project.py:77` (`_edited_at=...`)
    - [ ] any other `rg "_public_id|_created_by|_created_at|_edited_at"` hit in code (not `prevproject/`, not migrations being regenerated)

### Phase 2 — `BaseModelUpdateLog` model + value serialization
- [ ] `djangoapp/models/base.py` — add `BaseModelUpdateLog(models.Model)`:
    - [ ] `id = UUIDField(primary_key=True, default=generate_uuid7_id, editable=False)`
    - [ ] `action` CharField choices `created/updated/deleted`
    - [ ] `performed_by` FK `User`, `null=True/blank=True`, `on_delete=SET_NULL`, `related_name="+"`
    - [ ] `performed_at` DateTimeField (`auto_now_add`-style; set on create)
    - [ ] `model` CharField (the `log_model_name()` string)
    - [ ] `model_pk` BigIntegerField (the target row's integer pk; server-side only)
    - [ ] `old_values` / `new_values` JSONField (`default=dict`)
    - [ ] `Meta`: indexes `[model, model_pk]`, `[performed_at]`; ordering `[-performed_at]`
- [ ] Pydantic read models (`...UpdateLogEntryItem`, value-item schemas) for the
      lazy-logs response — FK value as `{id, url, name}`, num as str, date as ISO str
- [ ] A field-kind → JSON-value serializer dispatch (like `manage.py`'s
      `_field_kind`/`_cell_value`, L180-265) reused for log values:
    - [ ] bool/str/num(num-as-str)/datetime-as-ISO/fk-as-{id,url,name}; skip unsupported kinds
- [ ] Register in `djangoapp/models/__init__.py` `__all__`; add migration
- [ ] Export a `BaseModel.supported_log_columns()` helper returning the model's
      serializable own columns (the same set used to build old/new values)

### Phase 3 — `save_with_logs` / `delete_with_logs`
- [ ] `BaseModel.save_with_logs(self, *, user: User | None) -> None`:
    - [ ] create path (`self._state.adding` / `self.pk is None`): set `created_by`/`last_updated_by`=user, `last_updated_at`=now; `super().save()`; write log `action=created`, `old_values={}`, `new_values`=snapshot of supported columns
    - [ ] update path: fetch **old** row from DB (for a true before-diff), apply caller's field changes, set `last_updated_by`/`last_updated_at`; `super().save()`; compute changed-field diff; write log `action=updated` with old/new values (changed fields only); **skip the log row on a no-op** (nothing changed)
    - [ ] wrap save+log in `transaction.atomic()` (no audit-less writes)
- [ ] `BaseModel.delete_with_logs(self, *, user: User | None)`:
    - [ ] snapshot supported columns → `old_values`; write log `action=deleted`, `new_values={}`; then delete (log first so it survives)
    - [ ] `on_delete` for the row's own FKs stays `RESTRICT` (repo default) — no change
- [ ] Both methods take `user` kwarg; never leak `model_pk` to clients
- [ ] Update call sites that currently do bare `.save()` on `BaseModel` rows (ourapp
      CRUD) to use `save_with_logs(user)`; route deletes through `delete_with_logs`

### Phase 4 — Models page: sorting + columns + row-detail logs (backend)
- [ ] `manage.py:142` `_ALLOWED_SORTS` — `{"id", "-id", "last_updated_at", "-last_updated_at"}`;
      the resolver returns the full set for `BaseModel` subclasses, just `{"id","-id"}`
      for non-`BaseModel`; unknown/clamped to `-id`. Drop `created_at`/`edited_at` sorts.
- [ ] `manage.py:312` `model_rows_page` — build `order_by` from the resolved sort;
      add `last_updated_by` to `select_related`; add `last_updated_at`/`last_updated_by`
      to `RowItem`; keep pagination/filters as-is
- [ ] `manage.py:356` `row_detail_page` — add `last_updated_at`/`last_updated_by` to
      `RowDetailProps`; add a **lazy `logs` prop**:
    - [ ] when the request is an Inertia partial reload asking `only=["logs"]`, return just `{ logs: [...] }`
    - [ ] otherwise omit `logs` (initial render) so it loads lazily
    - [ ] logs query: `BaseModelUpdateLog.objects.filter(model=model_cls.log_model_name(), model_pk=instance.pk)` ordered `-performed_at`, serialized via the entry-item schema (pk-free)

### Phase 5 — Frontend (ModelRows + RowDetail)
- [ ] `frontend/src/pages/ModelRows.vue:17` `SORT_OPTIONS` → `id` / `last_updated_at`
      (and their `-` variants via the same value keys); update the `<select>`
- [ ] `ModelRows.vue` table headers (L111-113): `Created by | Created at | Updated at | Updated by`;
      render `last_updated_at`/`last_updated_by` cells; rename "Edited at" → "Updated at"
- [ ] `frontend/src/schemas.ts` — update `ModelRowsPropsSchema`/`RowItemSchema`:
      rename `edited_at`→`last_updated_at`, add `last_updated_by`; add `id` to `SORT` type
- [ ] `frontend/src/pages/RowDetail.vue` — add a **Logs** section:
    - [ ] on mount, `router.reload({ only: ["logs"] })` to fetch lazily
    - [ ] render each entry: action badge, `performed_by` profile, `performed_at`, and the old→new per-field diff (reuse `RowCell`-style rendering; num-as-str, FK-as-link)
    - [ ] show a loading state until `logs` arrives
- [ ] `frontend/src/schemas.ts` — add `RowDetailLogsSchema` + make `logs` optional in `RowDetailPropsSchema`
- [ ] Run frontend lint: `cd frontend && npm run lint:fix && npm run type-check && npm run lint`

### Phase 6 — Tests
- [ ] Unit — `BaseModelUpdateLog`:
    - [ ] `save_with_logs` create → one `created` log, `old_values={}`, `new_values`=all supported columns
    - [ ] `save_with_logs` update → one `updated` log, `old/new_values` contain **only changed** fields
    - [ ] no-op update → no log row written
    - [ ] `delete_with_logs` → one `deleted` log, `old_values`=deleted snapshot, `new_values={}`
    - [ ] `performed_by=None` path works
    - [ ] `log_as_name` override changes the stored `model` string (and the lookup still finds the row's logs)
    - [ ] value JSON shapes: bool/str/num-as-str/datetime-ISO/fk-{id,url,name}; unsupported columns omitted
    - [ ] `last_updated_at`/`last_updated_by` set together on update; `created_at` set once on create
- [ ] Unit — manage views:
    - [ ] `BaseModel` rows sort by `id`/`-id`/`last_updated_at`/`-last_updated_at`
    - [ ] `last_updated_by`/`last_updated_at` present in `RowItem`/`RowDetailProps`
    - [ ] row-detail `logs` prop **omitted** on full load, **present** on `only=["logs"]` partial reload
    - [ ] `model_pk` never appears in any response (pk-leak guard)
- [ ] Update existing tests referencing old underscore field names (`test_manage_project.py:77` etc.)
- [ ] Playwright e2e — `RowDetail` Logs: edit a row, open its detail, see the
      `updated` entry with the field diff rendered (add a stable class hook, e.g.
      `.update-log-entry`, `.update-log-old`, `.update-log-new`)

### Phase 7 — Validate
- [ ] `./run lintfix`
- [ ] `./run typecheck`
- [ ] `./run test`
- [ ] `./run checkproject` (test-app + reference-app overlay cycle, since BaseModel changed)
- [ ] `./run playwrighttest` (or the individual failing test)
- [ ] `./run checkall` green end-to-end
