# Nov 5 — `generatesdk`: pydantic → zod + typed client, no OpenAPI

Supersedes the contract-codegen items in
`prompts/20261104-stack-load-reduction.md` (dumpopenapi/hey-api/EJS/tsx
deleted, not evolved). Operator-confirmed decisions are baked in below.

## Command

    ./run djangomanage generatesdk <module> <out-file-under-frontend/>
    e.g. ./run djangomanage generatesdk djangoapp.views.users src/system/schemas/users_sdk.ts

Walks `<module>` (package → submodules) for `BaseModel` children with
the `ExportedSchemaMixin` marker and emits one TypeScript file: zod
schemas + typed client functions. No OpenAPI, no hey-api, no EJS/tsx,
no `_DocumentedApi`.

## Naming

- Zod exports use the exact pydantic class name:
  `export const LogoutResponse = z.object(…)`.
- Nested/referenced models are emitted too (by class name, not inlined).
- Client functions: `{method}_{view_function}` in snake_case —
  `mark_all_read` under `@router.post` → `post_mark_all_read`;
  same name twice ⇒ generator error.

## Types (pydantic → zod)

str → `z.string()` · int → `z.number().int()` · float → `z.number()` ·
bool → `z.boolean()` · **Decimal → `z.string()`** · `Literal[…]` →
`z.enum(…)` · `X | None` → `z.x().nullable()` · `list[T]` →
`z.array(zT)` · model ref → `zModel` · `dict[str, X]` → `z.record(zX)`.
Field names verbatim. `Field(default/ge/le/min_length/max_length)` →
matching zod constraints; a default ⇒ `.optional()`.

**Decimal:** generator maps to `z.string()`; backend models shipping
Decimals should also serialize Decimal → string (documented convention,
not policed).

## Client functions

- Wrap `ninjaPost`/`ninjaGet` (CSRF + 422→`NinjaError` result, response
  zod-parsed). Return `Promise<z.infer<typeof Response> | NinjaError>`.
- Name from the DECORATED function, not the URL.
- Path params are leading args: POST `/api/{public_id}/logout` →
  `post_force_logout(publicId)`; GET `Query[UserListFilters]` becomes a
  typed trailing object arg → query string, response via `ninjaGet`.
- Skips emit `// skipped:` comments: page ops (`response=None`),
  redirect flows, and operations whose schemas aren't flagged.
- Emission is plain Python string building — formatting doesn't matter,
  lint owns it.

## Removals

- `_DocumentedApi` + `_document_error_responses` + the openapi tests in
  `djangoapp/tests/test_ninja_api.py` (plain `NinjaAPI` again; the
  frontend `NinjaError` class is untouched).
- `dumpopenapi.py`, `dumpschemas.py`, `frontend/scripts/gensdk.ts`,
  `gensdk.template.ejs`, devDeps `@hey-api/openapi-ts`/`ejs`/`tsx`.
- `run`'s `genschemas()` wrapper + its help entry; repo-map §2 and
  steer conventions updated to the `manage generatesdk` form.

## Migration (same pass)

1. Flag `export = True`: users.py (props models, UserUpdateSchema,
   MessageResponse, LoginLink*, Logout*, UserSearch*), notifications.py,
   manage.py, client_errors.py, and the reference exemplar (todos).
2. Generate `<feature>_sdk.ts` per module; pages import zod + client
   functions from the sdk (UserDetails calls renamed to snake_case;
   schema names to `zLogoutResponse` style).
3. Delete `frontend/src/system/schemas/users.ts` + the
   `users/generated/`-era leftovers.

## Tests

Unit test with a synthetic module (api + BaseModels: Decimal field,
Literal, nullable, nested ref, GET with Query model, POST with body,
`response=None` op, unflagged-schema op) asserting the emitted
TypeScript. Then the battery: ruff/mypy, build + lint, users and
notifications suites, manual UserDetails smoke.

## Checklist

- [ ] `generatesdk` command + Decimal mapping + skips
- [ ] Unit test on the synthetic module
- [ ] Removals (dumpopenapi/dumpschemas/gensdk/template/_DocumentedApi/
      devDeps/run wrapper) + docs updated
- [ ] Flag modules; generate + migrate; delete schemas/users.ts
- [ ] VM battery green
