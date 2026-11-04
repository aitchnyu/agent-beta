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
3. **Generate the frontend contract from ninja's OpenAPI.** Tools:
   export via ninja's builtin (`api.get_openapi_schema()` in a
   `dumpopenapi` management command — no third-party export tool),
   then **`@hey-api/openapi-ts` + its Zod plugin** into a committed
   `generated.ts` (keeps zod 4 and the parse-every-payload
   invariant; can later also emit a typed SDK client). Fallback if
   we ever drop runtime parsing: `openapi-typescript` (types only,
   zero runtime). NOT `zod-openapi` — that is the reverse direction
   (zod → OpenAPI). `./run genschemas` runs export + codegen;
   deployscratch drift-checks the committed file. Dates stay
   strings (today's wire format); Decimal-as-string is now in
   steer's model checklist; zod remains for form inputs only.
   Kills the per-feature dual schema and its naming slips;
   pydanticErrors is unaffected (422 handling is independent of
   schema parsing).
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

- [ ] `useAppPage(FeatureSchema)` composable + `feature_props()`
      test helper; migrate 14 system pages, 6 reference pages,
      `_base.py`, 7 test files, repo-map §5/§9 (~29 files)
- [ ] Fix the reload-safe idiom in the reference exemplar +
      §9 skeleton (`computed(() => Schema.parse(...))`, 7 files)
- [ ] `./run genschemas` (dumpopenapi + @hey-api/openapi-ts zod
      plugin) + deployscratch drift gate
- [ ] Decimal → string on the wire: steer rule added (Nov 4);
      apply `field_serializer` to existing Decimal Out schemas +
      `format: decimal` when codegen lands
- [ ] Frontend tool dedup (package.json scripts + devDeps)
- [ ] Ruff curated select; mypy tests override + drop
      `disallow_any_decorated`
- [ ] `<uuid:public_id>` in §5 skeleton + repo-map sync test
- [ ] Re-run a feature; compare orientation + verify-tail minutes
      against the Nov 3/Nov 4 runs

## Not doing

Dropping Inertia or ninja — neither appears in the transcripts as a
cost; the hand-rolled two-level props read and the hand-maintained
schema mirror do, and items 1–3 remove both.
