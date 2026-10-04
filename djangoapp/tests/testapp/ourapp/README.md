# ourapp (test app)

The test-app fixture overlaid onto `scratch/ourapp/` by `checkframework1` (project
stage) and onto the VM's `ourapp/` by the checkframework2 gate. A complete app
exercising the framework features the project tests need:

- **Books** — the landing page's list (Inertia `ours/BooksPage`); `Author` +
  `Book` models carry the audit-log / optimistic-lock project tests
  (`djangoapp/tests/models/`, `djangoapp/tests/views/`).
- **Media** — the checkframework2 gate's file-upload illustration
  (`views/media.py`): a superuser-only multipart upload storing under
  `MEDIA_ROOT` with unguessable uuid names, plus a GET that streams bytes back
  through `djangoapp.media.serve_file` (gate assert 10). API-only — no page,
  no model — the full file feature lives in the reference app.
