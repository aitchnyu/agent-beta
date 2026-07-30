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
| `frontend/pages/ours/NotesPage.vue` | `frontend/src/pages/ours/NotesPage.vue` |
| `frontend/components/ours/NoteForm.vue` | `frontend/src/components/ours/NoteForm.vue` |

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
- **Frontend**: pages in `frontend/src/pages/ours/<Name>.vue` (Inertia component
  name `ours/<Name>`), components in `frontend/src/components/ours/`. Parse every
  server payload with a zod schema; wrap every `axios` call in `try/catch` +
  `showErrorToast`.
- **Public ids only**: never send the integer `pk`/`id`; send `_public_id`.

## Workflow

Edit in `copy/`, then `./run checkall`; on approval, `main/run mergescratch`
(deploys to `main/`; commit is a separate step). See `agentconfig/steer.md`.

These files are illustrative and excluded from ruff/mypy/eslint — they are not
installed or run as-is.
