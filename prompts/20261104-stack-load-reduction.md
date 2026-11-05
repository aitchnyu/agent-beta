# Nov 4 — stack changes to cut agent load

From the Nov 3 + Nov 4 chores transcripts and the stack review.
Goal: shrink what the agent must STUDY before writing and SATISFY
after writing, per feature.

## Evidence

- Nov 3 coder: ~11 min orientation studying the contract surface
  (OutSchema pairs, the 349-line pydanticErrors mirror), then a
  12–15 min ruff/mypy/build tail after the last feature write —
  more than any layer took to write.
- Nov 4 coder: tail down to ~5 min (the PREP-reads-pyproject lever
  works), but the stack still taxed:
  - props.props cost a 4.5-min e2e spiral (static ref vs computed)
    and caused the session's only shipped bug — the blank homepage
    was two pages reading the payload at different depths. The
    wrapper itself is right (it namespaces feature data away from
    shared props); the cost is that every page hand-rolls the
    two-level read.
  - A `ChoreSchema` vs `ChoreOut` slip broke the frontend build
    twice — every payload is hand-written twice (ninja Schema +
    zod), so naming is agent-invented per feature.
  - Page route `chores/<public_id>` shadowed `POST /chores/create`
    — 5 min to rediscover the UUID-converter fix.
- The toolchain doubles the satisfaction matrix: oxlint + eslint,
  vue-tsc + vue-tsgo, typescript 6 + 7; ruff runs `select=ALL` with
  a 25-entry ignore list; mypy strict adds friction in exactly the
  places the coder trips (tests, validators).

## Changes

1. **One typed accessor for the two-level read.** The wrapper stays
   on the wire — it namespaces feature data away from the shared
   props (`user`, `notifications`, …) that Inertia merges at the top
   level. But pages should never hand-roll the two parses
   (`FeatureSchema.parse(props.props)` + `SharedPropsSchema.parse(
   usePage().props)`) — one composable, `useAppPage(FeatureSchema)`,
   does both and returns `{ shared, data }`, reactive; pages stop
   knowing the wire shape. `BaseInertiaTestCase` gets the matching
   `feature_props()` helper so tests stop writing
   `self.props()["props"]`. **Scope: ~29 files** — 1 new composable,
   14 system pages, 6 reference pages, `djangoapp/tests/_base.py`,
   7 test files, repo-map §5/§9. All mechanical; backend untouched.
2. **Make the reload-safe parse the only parse.** Inertia mutates
   props in place on `router.reload()` — a setup-time snapshot
   (`const p = Schema.parse(props.props)`) goes stale after the
   first mutation. Only 2 of the 14 system pages use the computed
   form; the reference exemplar and the §9 skeleton teach the BUG
   (`TodosPage.vue:19` — its own toggle leaves a stale list; the
   Nov 4 coder copied it and paid the 4.5-min e2e spiral).
   `useAppPage()` computes internally, so the choice disappears;
   until it lands, fix the exemplar + skeleton to `computed(() =>
   Schema.parse(...))`. **Scope: 7 files** — TodosPage.vue + 5
   other reference pages, repo-map §9 (the 14 system pages fold
   into item 1's migration).
3. **Generate the frontend contract from ninja's OpenAPI.**
   `./run genschemas <module.attr>` — a dotted path to ANY NinjaAPI
   instance (`ourapp.views.api`, `djangoapp.views.users.users_api`),
   resolved via importlib → `api.get_openapi_schema()` → codegen
   with **`@hey-api/openapi-ts` + its Zod plugin** (zod 4, keeps
   the parse-every-payload invariant). No args = the configured
   target list (the seven live instances: ourapp, users, manage,
   git, files, notifications, clienterrors); the reference app's
   API rides checkframework1's staged overlay. No registry, no
   merged spec. **One generated.ts per API**, next to its consumers
   (`system/schemas/<api>/generated.ts`, `app/schemas/
   generated.ts`) — self-contained, no cross-API $refs, per-file
   drift diffs. **Drift check = checkframework2**: the in-VM gate's
   battery regenerates every target and diffs (checkframework1 runs
   the same list dev-side, so drift fails before the VM);
   `--check` also rides deployscratch. Fallback if we ever drop
   runtime parsing: `openapi-typescript` (types only). NOT
   `zod-openapi` — reverse direction (zod → OpenAPI).
   **Own SDK template — yes, two ways**: (a) a hey-api custom
   plugin (in-repo JS module, full control of emitted code), or
   (b) preferred: a thin generator in ops/ that reads the dumped
   spec and emits an sdk.ts wrapping the EXISTING ninjaPost — one
   typed function per operation (`create_todo` → `createTodo(body)
   : Promise<TodoOut | NinjaError>`); CSRF + 422→pydanticErrors
   mapping stay in http.ts. Adopt after schemas prove out. Dates
   stay strings; Decimal-as-string is in steer's model checklist;
   zod remains for form inputs only; §9's copy-me schema step
   becomes "import from generated", not "write todos.ts".
4. **Verify-tail diet.** One linter (oxlint + prettier, drop
   eslint), one type-checker (vue-tsgo, drop vue-tsc), one
   typescript major. Ruff: curated set (`E,W,F,I,B,UP,DJ,RUF`)
   instead of `ALL` + 25 ignores. Mypy: strict for prod code stays;
   broaden the tests override; drop `disallow_any_decorated`.
5. **Teach the conventions in the skeleton.** §5: any page path
   param holding a public_id uses `<uuid:public_id>` (route
   shadowing lesson). Update repo-map sync test.

## Questions (one at a time)

1. Wrap props.props in a typed `useAppPage()` accessor (or leave
   raw reads and rely on skeleton teaching)?
2. Codegen flavor: types-only, or generated zod (keeps the
   parse-every-payload invariant)?
3. Tool dedup + ruff/mypy trims: one bundled change or separate?

## Checklist

- [x] `useAppPage(FeatureSchema)` composable + `feature_props()` +
      `feature_props_of()` test helpers; migrated 14 system pages,
      6 reference pages, `_base.py`, 7 test files + 4 reference
      test files, repo-map §5/§9, steer (DONE Nov 4 — VM-verified:
      ruff/mypy/eslint/build green, 158 framework tests + reference
      suites OK; not yet committed)
- [x] Reload-safe idiom: useAppPage computes internally; TodosPage
      exemplar + §9 skeleton now teach it (DONE Nov 4)
- [x] `./run genschemas <module:api> [out]` — ON DEMAND, no target
      list, no drift gate (nothing imports generated files yet; revisit
      `--check` only when adoption is real). Emits `zod.gen.ts` (hey-api
      zod plugin) + `sdk.gen.ts` via OUR OWN TEMPLATE:
      `frontend/scripts/gensdk.template.ejs` (EJS — verbatim output
      shape with `<%- %>` holes, real backticks/`${}`) rendered by the
      typed `frontend/scripts/gensdk.ts` (tsx + ejs devDeps); one typed
      function per JSON operation wrapping `ninjaPost`, named from
      method+path; pages/inline-schema ops skipped with a comment.
      ADOPTED: UserDetails.vue's loginlink/logout now call the
      generated client; the hand schemas in schemas/users.ts are
      deleted (DONE Nov 4 — VM-verified; not committed)
- [x] Decimal → string on the wire: steer rule added (Nov 4);
      `field_serializer` applies when a Decimal field first ships
- [x] Frontend tool dedup: vue-tsc + typescript@6 dropped; eslint
      rescoped to TEMPLATE rules only (3 devDeps: eslint +
      eslint-plugin-vue + vue-eslint-parser, parser:false skips
      scripts; vue-tsgo owns expressions) — verified the essential
      rules (v-if+v-for, missing v-for key) fire and the build does NOT
      catch them; lint = oxlint + prettier + eslint templates (DONE Nov 4)
- [x] Ruff curated select (`E,F,W,I,B,UP,DJ,RUF` + 3 ignores, no
      per-file-ignores — also clears ops/scratch.py's pre-existing
      0.17.1 drift); mypy dropped `disallow_any_decorated` (DONE Nov 4)
- [x] `<uuid:public_id>` rule in §5 skeleton (DONE Nov 4)
- [ ] Re-run a feature; compare orientation + verify-tail minutes
      against the Nov 3/Nov 4 runs

## Not doing

Dropping Inertia or ninja — neither appears in the transcripts as a
cost; the hand-rolled two-level props read and the hand-maintained
schema mirror do, and items 1–3 remove both.
