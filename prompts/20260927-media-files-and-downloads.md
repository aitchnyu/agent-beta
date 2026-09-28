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
  live file; no session required to download. *(Re-settled 2026-09-28:
  storage naming is Django's — ``upload_to="downloads"`` with the original
  filename plus random collision suffixes — so URLs are guessable from
  filenames and the expiry date, not URL secrecy, is the guard.)*
- **Serving = FileResponse, Caddy X-Accel-Redirect handoff for proxied
  requests** *(re-settled 2026-09-28; supersedes the env-knob and
  redirect variants)*. ``serve_file`` returns Django's ``FileResponse``
  for direct requests; for requests that arrived through the reverse
  proxy — detected PER-REQUEST via ``X-Forwarded-For`` (Caddy stamps it
  on everything it forwards; granian binds 127.0.0.1 so the header has
  exactly one possible writer; a spoofed XFF only ever yields an empty
  200, never wrong bytes) — it replies empty-bodied with
  ``X-Accel-Redirect: /<resolved-relative-path>`` (percent-quoted,
  built from the post-resolution path so dot-segments/newlines can't ride
  it). The Caddyfile's ``reverse_proxy`` response interception
  (``@accel`` + ``handle_response``, stock Caddy v2) rewrites to that
  path and streams from ``MEDIA_ROOT``. No env knob: the
  ``MEDIA_ACCEL_PREFIX`` setting and its ``.env`` entries were removed
  (retires two markers); the handoff path is built purely from
  the resolved file's location — no prefix constant, no coupling beyond
  the Caddyfile's root. The gate's byte-compare through caddy proves the
  whole chain.
- **``serve_file`` is a per-app-mounted primitive.** No default open
  ``/media/`` route in Django — a global anonymous route would bypass the
  date gate for expired-but-unswept files. Apps mount their own pattern
  around it (reference: ``/downloads/…``; testapp: its gate endpoint).
- **File cleanup rides the tracked pair** *(re-settled 2026-09-28;
  supersedes the "fully explicit marks" stance of 2026-09-26)*.
  ``save_plus``/``delete_plus`` REPLACE ``save_with_logs``/
  ``delete_with_logs`` outright (precursor commit 8f49c95): every
  replaced/cleared FileField's old bytes queue for post-commit deletion
  inside the tracked save (one locked read carries ``row_version`` AND the
  pre-edit file names); the tracked delete treats the row's files as
  cleared and removes row + audit log + bytes together. Bare
  ``.save()``/``.delete()``/``update()``-swapped file columns orphan the
  bytes — no separate cleanup call exists to remember or forget.
- **media/ rides neither git nor the scratch rsync** — gitignored +
  ``_SCRATCH_EXCLUDES``, same policy as ``staticfiles/``: runtime data,
  never source; deployscratch can't wipe VM media.
- **Naming**: model ``Download``, URLs under ``/downloads``, task module
  ``tasks/downloads.py``.
- **Gate staging**: extend the testapp (multipart upload + serve) rather
  than placing files out-of-band; the gate proves the full app path.
- **READMEs**: the reference README lists the Downloads feature; the
  testapp gains a README (Books / media gate endpoints).

## Design

### Settings

- ``MEDIA_ROOT = BASE_DIR / "media"`` (``BASE_DIR`` is ``main/``).
- ``X-Forwarded-For`` — Caddy-handoff detection, per-request (no setting;
  the knob was removed 2026-09-28).
- ``MEDIA_URL`` stays unused for serving (no global route) — storage
  writes only. Create ``media/`` lazily via storage (``FileSystemStorage``
  does) or provision; gitignored either way.

### BaseModel (``djangoapp/models/base.py``)

- ``save_plus(*, actor, expected_row_version)`` — the tracked save:
  persist + one ``BaseModelUpdateLog`` + replaced-file cleanup. Every
  FileField whose stored name changed from the DB (reassigned or cleared
  to empty) queues its old file via ``_queue_file_deletion`` (the
  ``transaction.on_commit`` primitive):
  - rollback → callback never fires (the edit AND the old file survive);
  - autocommit (no atomic block) → fires immediately;
  - missing file → no-op; queued twice → harmless.
  The locked read fetches ``row_version`` + pre-edit file names in ONE
  query; models without FileFields pay nothing extra.
- ``delete_plus(*, actor)`` — the tracked delete: row + ``deleted`` log +
  every file's bytes, queued the same way inside the delete's atomic
  block (it "pretends the file fields are cleared").
- Tests drive the semantics via ``captureOnCommitCallbacks(execute=True)``
  (TestCase never real-commits) + an overridden tmp ``MEDIA_ROOT`` — the
  reference app's Download tests carry this coverage.

### serve_file (framework)

- ``serve_file(request, filename)`` → traversal-safe ``FileResponse``
  from ``MEDIA_ROOT``: resolve + ``is_relative_to`` discipline (the
  ``PathWrapper`` pattern in ``djangoapp/views/files.py``), 404 on escape
  or miss, attachment disposition, guessed content type.
- Lives in the framework; no URLconf entry of its own.

### Reference app — Download feature (``docs/reference/ourapp``)

- ``models/downloads.py``: ``Download(BaseModel)`` with
  ``file = FileField(upload_to=_uuid_name)`` storing under this feature's
  own folder ``media/downloads/<uuid>.<ext>`` and
  ``expires_at`` (default ``now() + 1 week``); classmethod
  ``delete_expired()`` — per expired row: ``delete_plus(actor=None)``
  (fat model, thin task).
- ``views/downloads.py`` (Router):
  - ``GET /downloads`` — superuser-only Inertia page: list + upload form
    (+ per-row replace/delete actions);
  - ``POST /downloads/upload`` — superuser-only multipart create
    (``save_plus``, ``expected_row_version=SKIP_ROW_VERSION_CHECK``);
  - replace-file action — **the replacement illustration**: just reassign
    + ``save_plus`` (old bytes die post-commit; rollback keeps both);
  - ``GET /downloads/{path:storage_name}`` — anonymous: row lookup by
    storage name → ``expires_at`` gate → ``serve_file``; 404 past expiry.
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

- On the smoke session: upload → 200 + name; GET serve URL (the
  X-Accel-Redirect handoff is transparent — bytes arrive on the SAME url)
  → bytes match; bogus name → 404; ``..`` traversal shape → 404.
- Expiry stays unit-side (clock control in the gate isn't worth it).

### Plumbing

- ``.gitignore``: ``media/``.
- ``run`` ``_SCRATCH_EXCLUDES``: ``--exclude='media/'`` (staticfiles
  policy).
- ``agentconfig/steer.md``: new **File uploads** section — the tracked-pair
  cleanup rule, the ``serve_file`` serving rule, and a pointer to
  ``docs/reference/`` as the copyable illustration.
- ``deploy/Caddyfile.site.in``: the ``@accel`` + ``handle_response``
  interception inside the site's ``reverse_proxy`` (stock Caddy v2).
  Review-corrected mechanics: ``{rp.header.X-Accel-Redirect}`` (the
  reverse_proxy response placeholder — ``{resp.*}`` belongs to the
  separate intercept directive and is unset here), ``rewrite`` to the
  header's path with ``root /srv/desmo/main/media`` mapping it directly
  (no prefix to strip — the header carries the bare resolved-relative
  path), and ``copy_response_headers Content-Disposition Content-Type``
  so the served file keeps the original filename (``file_server`` writes
  a fresh response otherwise; the selective copy also keeps the marker
  header from the client). Detection is the request's
  ``X-Forwarded-For`` — no env knob ships.

## Checklist

- [x] Settings: ``MEDIA_ROOT`` (+ XFF-based accel detection, no knob), gitignore, scratch excludes
- [x] Precursor commit 8f49c95: ``save_plus``/``delete_plus`` replace the old pair, all callers migrated
- [x] ``serve_file`` + tests (content, 404, traversal, X-Accel-Redirect)
- [x] Reference: ``Download`` model + migration + ``delete_expired()`` + tests
- [x] Reference: views (page/upload/replace/anonymous serve) + tests
- [x] Reference: daily sweep task + tests
- [x] Reference: frontend page + zod + playwright test
- [x] Reference: docs (design doc, README)
- [x] Testapp: upload + serve endpoints + README
- [x] Gate: assert 10 (upload/serve/404/traversal over HTTPS)
- [x] steer.md: File uploads section
- [x] Caddyfile @accel interception (XFF detection, no env knobs)
- [ ] Batteries: ``./run test``, lint, typecheck, reference + gated overlays
