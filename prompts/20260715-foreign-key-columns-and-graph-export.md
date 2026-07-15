# Foreign-key columns between tables + graph export

Add a `ForeignKeyColumn` so one application table can reference another, with
invariants enforced over the resulting table graph: no cycles, and a referenced
table can't be dropped out from under its referencers. A read-only command
exports the graph (tables = nodes, FK columns = edges) for visualization.

The FK points at a **specific table**, identified by `(collection, app, table)`.
It is resolved at column-creation time and stored against the target's immutable
`physical_name`, so renaming a collection/app/table display name never breaks the
FK. Cycle detection and creation ordering use the stdlib `graphlib`; the export
emits DOT (default) or Mermaid.

---

## Decisions

- **Target shape** is `(collection, app, table)`. Apps can hold multiple tables
  (`create_application(tables={...})` is a dict), so the FK must name the exact
  table. Resolved to the target `ApplicationTable` row at bind time.
- **Target identity is `physical_name`** (immutable). The dynamic field references
  the target by its generated model class (keyed on `physical_name`), and the
  definition row stores a Django FK to `ApplicationTable` — both survive
  collection/app/table display-name renames.
- **Two relations, one column type**:
  - `ApplicationTableColumn.fk_target_table` is the *metadata* FK to
    `ApplicationTable` (`on_delete=RESTRICT`) — drives the delete guard, the cycle
    graph, and the export.
  - the dynamic field's `on_delete=RESTRICT` is the *row-level* backstop (any ORM
    delete of a referenced row raises `ProtectedError`). No row-delete endpoint
    exists in views today; `RESTRICT` is the backstop regardless.
- **Graph library = stdlib `graphlib`**. `TopologicalSorter` for creation order +
  cycle detection (`CycleError`); a small DFS reports the exact cycle path in the
  error message. The graph is small (app tables), so no new dependency.
- **Export = DOT (default) + Mermaid** via `--format {dot,mermaid}`. DOT is the
  classic Graphviz shape; Mermaid renders natively in GitHub/VS Code.
- **Self-referential FK is allowed** (e.g. a tree `parent` column). It is excluded
  from cycle detection and built with `to="self"` so it can't recurse through
  `get_model` while its own class is being built.

---

## Detailed plan

### Data model + migration

- [x] add `FOREIGN_KEY = "foreign_key"` to `ColumnType` [djangoapp/models/applications.py:44]
- [x] add nullable `fk_target_table = models.ForeignKey(ApplicationTable, null=True, blank=True, on_delete=models.RESTRICT, related_name="referencing_columns")` on `ApplicationTableColumn` [djangoapp/models/applications.py:350]
- [x] `ApplicationTableColumn.clean()`: `type == FOREIGN_KEY` requires `fk_target_table`; every other type forbids it [djangoapp/models/applications.py:406]
- [x] migration `0014_applicationtablecolumn_fk_target` (nullable field, no data migration)

### `ForeignKeyColumn` (`models/columns.py`)

- [x] `@dataclass(frozen=True) ForeignKeyColumn(Column)` with `target: tuple[str, str, str]` (kw-only) and `column_type: ClassVar[ColumnType] = ColumnType.FOREIGN_KEY` [djangoapp/models/columns.py:23]
- [x] `_validate()`: `target` is a 3-tuple of non-empty strings — **no DB access**, so column tests stay `SimpleTestCase` [djangoapp/models/columns.py:48]
- [x] add a `Column.bind()` hook returning relation overrides (default `{}`); `ForeignKeyColumn` exposes its target tuple for the registry to resolve. `row()` (plain fields) stays DB-free [djangoapp/models/columns.py:51]
- [x] register in `_ALL_COLUMNS` + `column_class_for` + `columns.__all__` [djangoapp/models/columns.py:211,222,231]
- [x] export `ForeignKeyColumn` from `apps/shortcuts.py.__all__` [djangoapp/apps/shortcuts.py:33,45]

### Registry (`models/dynamic.py`)

- [x] `_foreign_key_field(col)`:
    - [x] self-ref (`col.fk_target_table_id == col.application_table_id`) → `to="self"`
    - [x] else → `to=dynamic_models.get_model(col.fk_target_table.physical_name)` (registered target class; present because creation is topo-ordered and the graph is acyclic)
    - [x] `on_delete=RESTRICT`, `related_name="+"` (disables reverse accessors so multiple FKs to one table can't clash), `null=col.nullable`, `blank=col.nullable`
- [x] add `FOREIGN_KEY` → `_foreign_key_field` to `_COLUMN_FIELD_BUILDERS` [djangoapp/models/dynamic.py:137,148]
- [x] `create_application`: topologically order the **new** tables by in-set FK deps via `graphlib.TopologicalSorter` (self-loops excluded) before creating, so a target table's physical table + registered model exist before the referencer's `create_model` [djangoapp/models/dynamic.py:341]
- [x] `_assert_acyclic(...)`: build the full graph from the DB (`ApplicationTableColumn` FK edges, by `physical_name`) plus the new declared edges; detect via `graphlib` `static_order()`; on `CycleError` run a DFS and raise `ValidationError` with a readable path (e.g. `inv/orders → inv/items → inv/orders`); self-edges excluded [djangoapp/models/dynamic.py:341,460]
- [x] call `_assert_acyclic` from `create_application` (whole graph + new edges) and `add_application_table_columns` (current graph + the new column's edge) [djangoapp/models/dynamic.py:460]
- [x] `_create_column_row`: resolve the target tuple → `fk_target_table` row. Forward refs within one `create_application` resolve because topo order created the target first; cross-app targets must pre-exist (else `TableNotFoundError`) [djangoapp/models/dynamic.py:593]

### Delete guard

- [x] `_drop_application_table(app_table, *, also_dropping: set[str] | None = None)`: before DDL, query columns on **other** tables referencing it
      (`ApplicationTableColumn.objects.filter(fk_target_table=app_table).exclude(application_table=app_table)`),
      drop any whose table's `physical_name` is in `also_dropping`; if survivors remain, raise `ValidationError` listing `referencer.column → this table`. The `fk_target_table` RESTRICT is the DB backstop [djangoapp/models/dynamic.py:524]
- [x] `delete_application_table` (single): passes no `also_dropping` → any external reference blocks [djangoapp/models/dynamic.py:548]
- [x] `delete_application` (whole app): passes the app's own tables' `physical_name`s as `also_dropping`, so internal cross-refs don't falsely block the cascade [djangoapp/models/dynamic.py:385]

### Export command (`management/commands/applications.py`)

- [x] `export_fk_graph` subcommand: `--format {dot,mermaid}` (default `dot`) [djangoapp/management/commands/applications.py:49]
- [x] Graphviz (DOT) emitter (default):
      ```
      digraph fk {
        "inv:orders" [label="orders"];
        "inv:items" [label="items"];
        "inv:orders" -> "inv:items" [label="item"];
      }
      ```
- [x] Mermaid emitter:
      ```
      graph LR
        inv:orders["inv:orders"]
        inv:items["inv:items"]
        inv:orders -->|item| inv:items
      ```
- [x] shared node/edge builder: nodes = all tables; edges = FK columns (source table → `fk_target_table`, label = column name). Label is `collection:app:table` (`:` is Mermaid-id-safe)

### README

- [x] "Foreign keys between tables" section:
    - [x] usage `ForeignKeyColumn("parent", target=(collection, app, table), nullable=...)`
    - [x] self-referential FK allowed; cross-app target must pre-exist
    - [x] cycles are rejected and reported (example path)
    - [x] referenced tables can't be dropped (clean message); `RESTRICT` backstop for rows
    - [x] `./run djangomanage applications export_fk_graph [--format dot|mermaid]`

### Tests (add as each lands)

- [x] `tests/models/test_columns.py` (SimpleTestCase)
    - [x] target-shape validation (3-tuple of non-empty strings)
    - [x] `column_type` is `FOREIGN_KEY`; `name` positional, `target`+`nullable` kw-only
- [x] `tests/models/test_dynamic.py` (schema/DDL)
    - [x] FK column creates a physical `REFERENCES` + RESTRICT
    - [x] self-referential FK builds (`to="self"`) and round-trips a parent row
    - [x] cross-table FK within one `create_application` (forward ref) — topo order
    - [x] add an FK column via `add_application_table_columns`
    - [x] cycle rejected on create with readable path (A → B → A)
    - [x] cycle rejected on add-column
    - [x] drop a referenced table is refused (clean message); drop a referencer is allowed
    - [x] `delete_application` over internally-cross-referenced tables succeeds
- [x] `tests/management/test_applications_command.py`
    - [x] DOT output (default): nodes + labelled edges
    - [x] `--format mermaid` output
- [x] app fixture exercising an FK + `@backend_test` (extend `Tests/AllTypes` or add `Tests/Relations`)

### Risks / notes

- Acyclicity (enforced) + `to="self"` for self-refs ⇒ no infinite recursion in
  `_build_model_class` (building a model only recurses into its FK targets, which
  are guaranteed registered and acyclic).
- `related_name="+"` ⇒ multiple FK columns targeting the same table can't clash.
- Renames are safe: the dynamic field keys on immutable `physical_name`; the
  definition row uses the `ApplicationTable` FK.
- Lint/typecheck/test gates in order: `./run lintfix` → `./run typecheck` →
  `./run test` → `./run checkall`.

---

## Deferred: swap graphlib for networkx (done)

`networkx` is a dependency (`pyproject.toml`). It replaces the stdlib `graphlib`
+ the bespoke DFS for a neater interface (the library reports the cycle path
directly). Behaviour is identical: self-loops excluded, and the
`foreign-key cycle: A -> B -> A` message unchanged.

- [x] replace the DFS cycle finder with `nx.find_cycle(...)` (raises
      `NetworkXNoCycle` when acyclic); the result is exposed as `_cycle_nodes`
      [djangoapp/models/dynamic.py]
- [x] replace `_creation_order`'s `graphlib.TopologicalSorter(...).static_order()`
      with `list(nx.topological_sort(...))` [djangoapp/models/dynamic.py]
- [x] swap `import graphlib` → `import networkx as nx` [djangoapp/models/dynamic.py]
- [x] drop the bespoke DFS; keep `_cycle_error` (the readable cycle string formatter)

Gotcha: networkx ships no `py.typed`, so under `strict` + `disallow_any_unimported`
its objects are `Any`. The graph helpers annotate them as explicit `Any` with
`# noqa: ANN401`, and `Callable` moved under `if TYPE_CHECKING:`. Because of this,
`./run lintfix` (which runs `ruff check --fix --unsafe-fixes`) must only be run
once `ruff check` is already clean — otherwise the unsafe TC003 import move can
destroy the import block.

## Pending code markers (collected) (done)

Review feedback left as in-code `# aihere` markers. Address each, then delete the
comment from the code.

- [x] no need for scoping — dropped `--appcollection`/`--app` from `export_fk_graph`
      [djangoapp/management/commands/applications.py]
- [x] removed the `bind` hook — FK target resolution is inlined in
      `_create_column_row` [djangoapp/models/columns.py]
- [x] inlined the `3` (no `FK_TARGET_PARTS` constant); `_validate` is shape-only
      (3-tuple) — name/existence of the target is checked at resolve time, not in
      the DB-free column class [djangoapp/models/columns.py]
- [x] added `Application.get_table(name)`; the registry's
      `_get_application_table_for` (and `_resolve_target_table`) now go through it
      in all cases [djangoapp/models/applications.py, djangoapp/models/dynamic.py]

## Round-2 code markers (done)

Review feedback added after the networkx swap; addressed and removed.

- [x] `export_fk_graph` node label inlined (it was used once) and the separator
      switched to `:` (Mermaid-id-safe, so DOT/Mermaid share one id/text)
      [djangoapp/management/commands/applications.py]
- [x] `_emit_dot` → `_emit_graphviz` (clearer than "dot")
      [djangoapp/management/commands/applications.py]
- [x] added a project-local `stubs/networkx/__init__.pyi` (node-generic `DiGraph`,
      `find_cycle`, `topological_sort`, `NetworkXNoCycle`); the graph helpers now
      use real `nx.DiGraph[...]` types instead of `Any`/`# noqa: ANN401`. mypy
      resolves the stub the same way it resolves `stubs/inertia` (no `mypy_path`
      change). `N818` added to the stubs per-file-ignore (names mirror networkx)
      [stubs/networkx/__init__.pyi, djangoapp/models/dynamic.py, pyproject.toml]

## Round-3 code markers

Review feedback addressed in a follow-up pass.

- [x] removed the three stateless resolver wrappers `_resolve_application`,
      `_get_application_table_for`, `_resolve_target_table` — inlined
      `Application.get_by_names(...)` / `application.get_table(...)` at the call
      sites and let Django's `DoesNotExist` propagate (these paths no longer raise
      `TableNotFoundError`; `_resolve_collection` + the physical-name lookup still do)
      [djangoapp/models/dynamic.py]
- [x] renamed `_create_column_row` → `_create_column` (call sites updated)
      [djangoapp/models/dynamic.py]
- [x] nested `_graph_label` inside `_handle_export_fk_graph` as `label` (its only
      caller) [djangoapp/management/commands/applications.py]
- [x] expanded the `_emit_graphviz` / `_emit_mermaid` docstrings to explain the
      node id vs. display-label convention (DOT shows the bare table name; Mermaid
      shows the full `collection:app:table`) [djangoapp/management/commands/applications.py]

## Round-4 code markers

Review feedback on the uncommitted FK code; addressed and removed.

- [x] `export_fk_graph` orphan-FK guard removed — `clean()` guarantees a target
      for every `foreign_key` column, so the `if target is None: warn; continue`
      handling and its `test_orphaned_fk_column_warns_on_stderr` were dead
      defensive code; replaced with an invariant `assert`
      [djangoapp/management/commands/applications.py, djangoapp/tests/management/test_applications_command.py]
- [x] `export_fk_graph` abbreviated identifiers expanded — `fk_cols`→`fk_columns`,
      `col`→`column`, `fmt` inlined as `options["format"]`, and the emitter
      tuple-unpacks `src/dst/colname`→`source/destination/column_name`
      [djangoapp/management/commands/applications.py]
- [x] `test_cycle_rejected_on_add_column` now captures the `ValidationError`
      context and asserts the `foreign-key cycle` message (not just the type)
      [djangoapp/tests/models/test_dynamic.py]
- [x] `test_foreign_key_target_is_keyword_only` removed (superfluous — keyword-
      only-ness is already covered by the other column-class tests)
      [djangoapp/tests/models/test_columns.py]

### Deferred (done)

- [x] `Tests/Relations/app.py:70` — "we already have an app that exercises all
      relationships. Use that app. Also test the rows list and details with
      relationship." Resolved as a feature-scope change:

      **FK cells in the row views.** The row list/detail serializer
      (`_cell_value`) had no `FOREIGN_KEY` branch (would `ValueError`), and the
      frontend `RowColumnTypeSchema` omitted `foreign_key` (would fail
      `RowListPropsSchema.parse`). Added: a `_cell_value` foreign_key branch
      returning a pk-free `{public_id}` (or null); an `FkTarget`
      `{collection_name, app_name, table_name}` on `RowListColumnDef` (built by
      a shared `_column_def` helper at both the list and detail sites); the
      `foreign_key` enum value + `FkTargetSchema`/`FkCellValueSchema` in the
      frontend; and a `RowCell.vue` branch that links the cell to the
      referenced row's detail page [djangoapp/views/applications.py,
      frontend/src/schemas.ts, frontend/src/components/RowCell.vue].
      **Fixtures:** added a `category` target table + `ForeignKeyColumn` to
      `Tests/AllTypes` (now spans every type incl. FK). `Tests/Relations` was
      dropped — its 2-table FK + creation-order + endpoint resolution is now
      fully covered by AllTypes (creation order, `category_id` physical column,
      and `out.category` resolution), so the separate fixture was redundant
      [djangoapp/tests/appfixtures/Tests/AllTypes/app.py].
      **View tests:** `RowValuesViewTests` now seeds a `targets` table + an FK
      column, asserts the `{public_id}` cell in list and detail, and that the
      FK column def carries `fk_target` [djangoapp/tests/views/test_row_views.py].
      `test_install_alltypes` now fetches the `row` table by name (AllTypes has
      two tables) and asserts the `category_id` physical column
      [djangoapp/tests/appfixtures/test_buildbackend.py].
