# Media files: storage, serve_file, post-commit cleanup + reference Download feature

## Goal

- Uploaded files live in **``media/``** in the repo root — a new runtime-data
  directory, never source, never committed.
- Framework primitives every app inherits: ``BaseModel`` file-cleanup
  markers + a traversal-safe ``serve_file`` view helper.
- The **reference app** (``docs/reference/ourapp``) grows a file-download
  feature that illustrates all three primitives: admin uploads a file,
  anyone with the link can download it until an expiry date (default one
  week), then it 404s and a daily sweep deletes row + bytes.
- The **testapp** grows a minimal upload/serve endpoint so the
  checkframework2 in-VM gate exercises the real path over HTTPS.

## Decisions (settled with operator, 2026-09-26 → 2026-09-27)

- **Expiry = date-gate + Huey sweep.** The download URL checks
  ``expires_at`` and 404s immediately; a daily ``db_periodic_task``
  deletes expired rows and their bytes. No lazy on-access deletion.
- **Downloads are anonymous share links.** Anyone with the URL may fetch a
  live file; unguessable storage names (UUID-based ``upload_to``) are the
  boundary. No session required to download.
- **Always through Django's ``serve_file``.** Caddy only reverse-proxies
  (as it already does for every non-``/static/`` route) — no
  ``handle_path`` interception for media, so ``expires_at`` is enforced
  exactly with no expired-but-unswept window. The old TODO "accelerate
  file serving with Caddy" stays future work.
- **``serve_file`` is a per-app-mounted primitive.** No default open
  ``/media/`` route anywhere — a global anonymous route would bypass the
  date gate for expired-but-unswept files. Apps mount their own pattern
  around it (reference: ``/downloads/…``; testapp: its gate endpoint).
- **File cleanup is fully explicit.** ``save_with_logs`` /
  ``delete_with_logs`` stay file-unaware, deliberately. Callers own the
  lifecycle through two new ``BaseModel`` methods; a forgotten call
  orphans a file (the documented cost of skipping them, like bare
  ``.save()`` skipping audit logs).
- **media/ rides neither git nor the scratch rsync** — gitignored +
  ``_SCRATCH_EXCLUDES``, same policy as ``staticfiles/``: runtime data,
  never source; deployscratch can't wipe VM media.
- **Naming**: model ``Download``, URLs under ``/downloads``, task module
  ``tasks/downloads.py``.
- **Gate staging**: extend the testapp (multipart upload + serve) rather
  than placing files out-of-band; the gate proves the full app path.

## Design

### Settings

- ``MEDIA_ROOT = BASE_DIR / "media"`` (``BASE_DIR`` is ``main/``).
- ``MEDIA_URL`` stays unused for serving (no global route) — storage
  writes only. Create ``media/`` lazily via storage (``FileSystemStorage``
  does) or provision; gitignored either way.

### BaseModel (``djangoapp/models/base.py``)

- ``mark_file_field_for_deletion(field_name: str)`` — the primitive.
  ``transaction.on_commit`` → ``field.delete(save=False)``:
  - rollback → callback never fires (file survives an aborted
    transaction — the point of the design);
  - autocommit (no atomic block) → fires immediately;
  - missing file → no-op; double mark → harmless.
- ``mark_all_file_fields_for_deletion()`` — the whole-row method
  ("remove all files with a row"): discovers ``FileField``s the same way
  ``_log_fields`` introspects fields for audit logging, marks every
  non-empty one.
- Tests drive both with Django's
  ``captureOnCommitCallbacks(execute=True)`` (TestCase never
  real-commits) + an overridden tmp ``MEDIA_ROOT``.

### serve_file (framework)

- ``serve_file(request, filename)`` → traversal-safe ``FileResponse``
  from ``MEDIA_ROOT``: resolve + ``is_relative_to`` discipline (the
  ``PathWrapper`` pattern in ``djangoapp/views/files.py``), 404 on escape
  or miss, attachment disposition, guessed content type.
- Lives in the framework; no URLconf entry of its own.

### Reference app — Download feature (``docs/reference/ourapp``)

- ``models/downloads.py``: ``Download(BaseModel)`` with
  ``file = FileField(upload_to=<uuid names>)`` and
  ``expires_at`` (default ``now() + 1 week``); classmethod
  ``delete_expired()`` — per expired row:
  ``mark_all_file_fields_for_deletion()`` + ``delete_with_logs`` (fat
  model, thin task).
- ``views/downloads.py`` (Router):
  - ``GET /downloads`` — superuser-only Inertia page: list + upload form
    (+ per-row replace/delete actions);
  - ``POST /downloads/upload`` — superuser-only multipart create
    (``save_with_logs``, ``expected_row_version=0``);
  - replace-file action — **the explicit-replacement illustration**:
    ``mark_file_field_for_deletion("file")`` on the old value *before*
    assigning the new one, inside the same transaction;
  - ``GET /downloads/<name>`` — anonymous: row lookup by storage name →
    ``expires_at`` gate → ``serve_file``; 404 past expiry.
- ``tasks/downloads.py``: daily ``db_periodic_task`` →
  ``Download.delete_expired()`` (FactOfTheDay wrapper pattern; tests via
  the classmethod or ``call_local()``).
- Frontend: ``DownloadsPage.vue`` + zod schema; migration; tests per
  layer (models/views/playwright); design doc with ``erDiagram`` +
  state diagram; README lines.

### Testapp (``djangoapp/tests/testapp/ourapp``)

- One superuser-only feature module: multipart POST stores via
  ``default_storage`` under a UUID name (no model), GET serves through
  ``serve_file``. Minimal — the gate's substrate, not a second
  illustration.

### Gate (``deploy/vm.sh`` — a 10th assert)

- On the smoke session: upload → 200 + name; GET serve URL → 200, bytes
  match; bogus name → 404; ``..`` traversal shape → 404.
- Expiry stays unit-side (clock control in the gate isn't worth it).

### Plumbing

- ``.gitignore``: ``media/``.
- ``run`` ``_SCRATCH_EXCLUDES``: ``--exclude='media/'`` (staticfiles
  policy).
- ``agentconfig/steer.md``: new **File uploads** section — the three
  primitives, the explicit-only philosophy (replacement + row deletion
  are caller-owned), and a pointer to ``docs/reference/`` as the
  copyable illustration.
- ``deploy/Caddyfile.site.in``: untouched.

## Checklist

- [ ] Settings: ``MEDIA_ROOT``, gitignore, scratch excludes
- [ ] ``BaseModel.mark_file_field_for_deletion`` + tests
- [ ] ``BaseModel.mark_all_file_fields_for_deletion`` + tests
- [ ] ``serve_file`` + tests (content, 404, traversal)
- [ ] Reference: ``Download`` model + migration + ``delete_expired()``
- [ ] Reference: views (page/upload/replace/anonymous serve) + tests
- [ ] Reference: daily sweep task
- [ ] Reference: frontend page + zod + playwright test
- [ ] Reference: docs (design doc, README) 
- [ ] Testapp: upload + serve endpoints
- [ ] Gate: assert 10 (upload/serve/404/traversal over HTTPS)
- [ ] steer.md: File uploads section
