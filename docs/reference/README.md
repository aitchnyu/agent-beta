# Reference app

A complete, copyable example of the user app's multi-file layout, with two
features: **facts** (a `Topic` + `Fact`, a seed command, two pages) and **todos**
(a `Todo` owned by a user, one page). Copy a feature into the real `ourapp/`
locations and adapt. The agent consults this when adding a feature.

> The reference frontend under `docs/reference/frontend/src/ours/` ships only the
> app's own pages/components/schemas/styles — its pages `import` the framework's
> `../../components/Layout.vue` and `../../utils/{csrf,sweetalert}`, which already
> exist in the main `frontend/`. It's meant to be dropped into an existing
> framework frontend, not built standalone.

## Files → where they go

| Reference file | Copy to |
| --- | --- |
| `ourapp/models/<feature>.py` | `ourapp/models/<feature>.py` (import in `models/__init__.py`) |
| `ourapp/views/<feature>.py` | `ourapp/views/<feature>.py` (register in `views/__init__.py`) |
| `ourapp/management/commands/<cmd>.py` | `ourapp/management/commands/<cmd>.py` |
| `ourapp/urls.py` | `ourapp/urls.py` (mounts the API) |
| `ourapp/tests/test_<feature>_<layer>.py` | `ourapp/tests/test_<feature>_<layer>.py` (flat; layer = models/views/commands/playwright) |
| `frontend/src/ours/pages/<Name>.vue` | `frontend/src/ours/pages/<Name>.vue` |
| `frontend/src/ours/schemas.ts` | `frontend/src/ours/schemas.ts` (app zod schemas) |
| `frontend/src/ours/style.scss` | `frontend/src/ours/style.scss` (side-effect-imported by pages) |

## The pattern

- **Models** (`models/<feature>.py`): subclass `djangoapp.models.BaseModel`; give
  each a docstring (shown in `/manage/models`). A `ForeignKey` to the project
  `User` links to the owner's profile; a `ForeignKey` to another `BaseModel`
  links to that row's detail page via its `get_absolute_url()`. **Fat models,
  thin views** — put domain logic (e.g. `Fact.objects.random(...)`,
  `Topic.random_fact()`) on the model/manager, not in views. Import the model in
  `models/__init__.py`; add/change a model → `./run djangomanage makemigrations ourapp`.
- **Views** (`views/<feature>.py`): each feature exposes a django-ninja `Router`;
  `views/__init__.py` owns one `NinjaAPI` and registers every router
  (`api.add_router("/", <feature>.router)`). Page responses use
  `InertiaResponse(request, "ours/<Page>", {"props": …})`; data responses are
  pydantic schemas (ninja validates them). CSRF is handled by the host
  (`X-CSRFTOKEN` set globally in `main.ts`).
- **Commands** (`management/commands/<cmd>.py`): seed/setup commands; one module
  per command, with its seed data inlined at the top of the command.
- **Frontend**: a self-contained `frontend/src/ours/` module — pages in
  `ours/pages/<Name>.vue` (Inertia component name `ours/<Name>`), components in
  `ours/components/`, helpers in `ours/utils/`, zod schemas in `ours/schemas.ts`,
  and styles in `ours/style.scss` (imported as a side-effect by the page).
  Parse every server payload with a zod schema; wrap every `axios` call in
  `try/catch` + `showErrorToast`.
- **Home navigation**: link every feature from the landing page
  (`ours/pages/Home.vue`), shown only when this viewer can use it — hide an
  auth-required feature (e.g. todos, whose `/todos` 404s for anon) from an
  anonymous visitor. A reachable-but-unlinked feature is effectively missing.
- **Tests**: flat under `tests/` — one file per feature + layer, named
  `test_<feature>_<layer>.py` (`models`, `views`, `commands`, `playwright`).
  Playwright files subclass `BasePlaywrightTestCase` (tagged `playwright`), so
  `./run test` skips them and `./run playwrighttest` runs them.
- **Public ids only**: never send the integer `pk`/`id`; send `public_id`.

## Response shapes

The API has two response kinds — don't confuse them.

**Page response (Inertia)** — a `GET` that renders a page. The view wraps its
data under a literal `props` key:

```python
InertiaResponse(request, "ours/FactsPage", {"props": {"fact": ..., "topics": [...]}})
```

`SharedPropsMiddleware` merges the viewer in, so the client's `page.props` is:

```jsonc
{
  "user": { "public_id": "…", "title": "…" },     // shared — every page
  "viewer_is_superuser": true,                    // shared — every page
  "props": { "fact": ..., "topics": [ /* TopicOutSchema[] */ ] } // THIS page's data
}
```

Read the page data from the nested `props` key, not the top level:

```ts
const props = defineProps<{ props: object }>()
const p = FactsPagePropsSchema.parse(props.props)
```

**Data response (JSON)** — a `POST`/`PUT`/`DELETE` returns a flat pydantic
schema as JSON (ninja validates it). No `props` wrapper, no shared props:

```jsonc
// POST /todos/create → TodoOutSchema
{ "public_id": "…", "text": "…", "completed": false, "owner_public_id": "…" }
```

Public ids only in both kinds (never the integer `pk`).

## Features

- [facts](ourapp/docs/facts.md) — random trivia, optionally by topic; seedable.
- [todos](ourapp/docs/todos.md) — a signed-in user's todo list.
- [home](ourapp/docs/home.md) — the landing page.

## Workflow

Edit in `scratch/`, then `./run checkscratch`; on approval, `main/run mergescratch`
(deploys to `main/`; commit is a separate step). See `agentconfig/steer.md` and
its "Checklist — adding or changing a feature".

These files are illustrative and excluded from ruff/mypy/eslint — they are not
installed or run as-is (they are overlaid onto `ourapp/` by `checkproject`).
