# Reference app

A complete, copyable example of one feature in the user app: a `Note` model (with
a `User` foreign key), a django-ninja API (a list page + a create endpoint), a
Vue page, and a test. Copy these into the real locations and adapt. The agent
consults this when adding a feature.

## Files → where they go

| Reference file | Copy to |
| --- | --- |
| `ourapp/models.py` | `ourapp/models.py` |
| `ourapp/views.py` | `ourapp/views.py` (the app's django-ninja API) |
| `ourapp/urls.py` | `ourapp/urls.py` (mounts the API) |
| `ourapp/tests.py` | `ourapp/tests.py` or `djangoapp/tests/` |
| `frontend/src/ours/pages/NotesPage.vue` | `frontend/src/ours/pages/NotesPage.vue` |
| `frontend/src/ours/components/NoteForm.vue` | `frontend/src/ours/components/NoteForm.vue` |
| `frontend/src/ours/schemas.ts` | `frontend/src/ours/schemas.ts` (app zod sub-schemas) |
| `frontend/src/ours/style.scss` | `frontend/src/ours/style.scss` (side-effect-imported by the page) |
| `frontend/src/ours/utils/format.ts` | `frontend/src/ours/utils/` (app helpers) |

## The pattern

- **Model**: subclass `djangoapp.models.BaseModel`; give it a docstring (shown in
  `/manage/models`). A `ForeignKey` to the project `User` links to the owner's
  profile; a `ForeignKey` to another `BaseModel` links to that row's detail page
  via its `get_absolute_url()`. Add/change a model →
  `./run djangomanage makemigrations ourapp`.
- **API**: a django-ninja API in `ourapp/views.py`, mounted in `ourapp/urls.py`
  (included at the project root, so each route is served at its literal URL).
  Page responses use `InertiaResponse(request, "ours/<Page>", {"props": …})`;
  data responses are pydantic schemas (ninja validates them). CSRF is handled by
  the host (`X-CSRFTOKEN` set globally in `main.ts`).
- **Frontend**: a self-contained `frontend/src/ours/` module — pages in
  `ours/pages/<Name>.vue` (Inertia component name `ours/<Name>`), components in
  `ours/components/`, helpers in `ours/utils/`, zod sub-schemas in
  `ours/schemas.ts`, and styles in `ours/style.scss` (side-effect-imported by the
  page component, so the feature is self-contained). Parse every server payload with a zod schema; wrap every
  `axios` call in `try/catch` + `showErrorToast`. Keep app code inside `ours/`
  and edit only there where possible.
- **Public ids only**: never send the integer `pk`/`id`; send `_public_id`.

## Response shapes

The API has two response kinds — don't confuse them.

**Page response (Inertia)** — a `GET` that renders a page. The view wraps its
data under a literal `props` key:

```python
InertiaResponse(request, "ours/NotesPage", {"props": {"notes": [...]}})
```

`SharedPropsMiddleware` merges the viewer in, so the client's `page.props` is:

```jsonc
{
  "user": { "public_id": "…", "title": "…" },     // shared — every page
  "viewer_is_superuser": true,                    // shared — every page
  "props": { "notes": [ /* NoteOutSchema[] */ ] } // THIS page's data
}
```

Read the page data from the nested `props` key, not the top level:

```ts
const props = defineProps<{ props: object }>()
const notes = NotesPagePropsSchema.parse(props.props).notes
```

**Data response (JSON)** — a `POST`/`PUT`/`DELETE` returns a flat pydantic
schema as JSON (ninja validates it). No `props` wrapper, no shared props:

```jsonc
// POST /notes/create → NoteOutSchema
{ "public_id": "…", "title": "…", "body": "…",
  "owner_public_id": "…", "owner_title": "…" }
```

Public ids only in both kinds (never the integer `pk`).

## Workflow

Edit in `copy/`, then `./run checkall`; on approval, `main/run mergescratch`
(deploys to `main/`; commit is a separate step). See `agentconfig/steer.md`.

These files are illustrative and excluded from ruff/mypy/eslint — they are not
installed or run as-is.
