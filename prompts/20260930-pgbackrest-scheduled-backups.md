# pgbackrest: scheduled DB backups into main/dbbackups

## Goal

- Nightly **physical Postgres backup** of the app database via
  **pgbackrest** (Ubuntu apt package — no third-party repo, dpkg-owned),
  scheduled by a **systemd timer** on the VM and storing its repository
  in **``dbbackups/``** in the repo root — a **plain, unencrypted,
  self-contained folder** (backup sets + archived WAL together, no keys
  or signatures anywhere): copying the one folder carries the whole
  backup, and any copy of it IS a plaintext database.
- **Retention built in — two months of history**:
  ``repo1-retention-full=8`` +
  ``repo1-retention-diff=14`` in the conf expires old sets (diffs
  would otherwise ride along until their parent full expires); the
  schedule is **weekly full (Sundays UTC) + daily diff**, with a full
  landing automatically when none exists.
- **The backup logic lives in ``./run``** (``backupdb`` /
  ``restoredb``) — the agent's native entry points; inspection goes
  straight to the service (``sudo -u postgres pgbackrest
  --stanza=desmo info|check``); the systemd
  service is a one-line shim into ``./run backupdb``.
- **Tested in checkframework2**: the in-VM gate's **11th assert** proves
  the round-trip on the live server through the agent's own verbs —
  mark, back up, diverge, restore onto the live cluster, verify the
  backed-up marker (the ``BackupMarker`` model).
- **The tool is installed, not gated** — provisioning apt-installs
  pgbackrest on the VM; there is no enable knob and no disabled mode.

## Decisions (settled with operator, 2026-09-30 — research review)

- **pgbackrest, plain unencrypted repo.** Motivation: backups as easy
  as backing up one folder — no keyring, no signatures, nothing to
  lose besides the folder itself. Accepted trade, stated in the docs:
  any copy of ``dbbackups/`` is a plaintext database. Space: weekly
  full + daily diff under ``retention-full=8`` (two months) /
  ``retention-diff=14``.
- **systemd timer.** A oneshot service + timer because:
  - ``Persistent=true`` — if the VM is down at fire time, the timer
    catches up on next boot; a plain scheduled job would just skip the
    window. For backups, catch-up beats a silent hole in the chain.
  - Worker isolation — a hung backup runs in its own oneshot unit and
    never occupies any other unit's worker.
  - Tool-native shape — pgbackrest deployments schedule via cron or
    systemd timers.
- **The backup logic lives in ``./run``.** ``backupdb`` (the verb the
  agent, timer shim, and deployscratch call), ``restoredb`` (the coded
  restore runbook). No
  separate script, no Django boot in the backup path, **zero new env
  vars** — the stanza conf is a file, not env.
- **Everything runs AS POSTGRES.** pgbackrest refuses root; the repo is
  postgres-owned (``dbbackups/`` 700 postgres:postgres); every
  invocation — backup, restore, WAL archive-push (the server itself),
  drills — goes through ``sudo -u postgres``. Consequence: restore
  needs no ``chown`` dance; ownership is right by construction.
- **Units: ``desmo_pgbackrest.service`` (oneshot shim,
  ``ExecStart=/srv/desmo/main/run backupdb``) +
  ``desmo_pgbackrest.timer``** — naming joins ``desmo_granian``;
  rendered by ``testvm`` from ``deploy/*.in``, enabled by
  ``deploy/inside-vm.sh``. Timer fires
  ``OnCalendar=*-*-* 00:00:00 UTC`` — midnight UTC via the explicit
  timezone suffix, so the schedule is fixed regardless of the VM's
  local timezone setting.
- **Conf as a tree template.** ``deploy/pgbackrest.conf.in`` renders to
  ``/etc/pgbackrest/pgbackrest.conf`` (stanza ``desmo``,
  ``repo1-path=/srv/desmo/main/dbbackups``, ``retention-full=8`` +
  ``retention-diff=14``,
  ``log-path=/var/log/postgresql``); ``testvm`` resolves the
  versioned ``@PG_MAIN@`` data-dir path from the freshly installed VM
  (Debian paths it per major — unknowable host-side).
- **WAL archiving via ALTER SYSTEM, not file edits.**
  ``archive_mode=on`` + ``archive_command='pgbackrest --stanza=desmo
  archive-push %p'`` set in ``provision_app`` (one postgres restart),
  riding ``postgresql.auto.conf`` — which lives IN the data dir, so it
  survives restores too.
- **Honest failures**: ``set -e`` everywhere — any nonzero exit
  propagates, the unit goes red, journald carries the error. No
  tolerance branches anywhere in the backup path.
- **``dbbackups/`` rides neither git nor the scratch rsync** —
  gitignored + ``_SCRATCH_EXCLUDES``, same policy as ``media/``:
  deployscratch can't wipe VM backups.
- **Same-disk caveat accepted for now.** A backup on the same disk as
  the DB is not a real backup; the repo is one conf constant, so
  moving off-host later (``repo1-path`` → SFTP/S3) is a one-line
  change. TODO.md keeps the pointer.
- **Gate coverage: an 11th checkframework2 assert.** The bash trade
  (nothing in the suite) is bought back where it counts: the gate
  proves the deployment-real chain on a fresh VM — the agent's own
  verbs → pgbackrest → the restored live server — the parts no unit
  test could reach. Deliberately untested: ``Persistent`` catch-up
  (needs a VM reboot — too heavy) and the midnight-UTC cadence itself.
- **Naming**: stanza ``desmo``, units ``desmo_pgbackrest.service`` /
  ``.timer``, run verbs ``backupdb`` / ``restoredb <set>``, docs
  page ``docs/backups.md``.

## Design

### Backup logic (``./run``)

- ``backupdb`` — the one backup verb: resolves the type (full when the
  repo lists none yet, full on Sundays UTC via ``date -u +%u``, diff
  otherwise) and runs ``sudo -u postgres pgbackrest --stanza=desmo
  backup --type=…``. Retention is the conf's. The tool's own logs
  print to stdout (the journal under the unit) — no wrapping event
  layer: the NDJSON discipline is for OUR Python services, not the
  external tool.
- ``restoredb <set>`` — the coded runbook, snapshot-only: the
  MANDATORY label (exactly as ``pgbackrest info`` prints it) is
  verified to exist BEFORE anything stops, and so is a backup
  already running — REFUSED on the spot via ``_backup_running``
  (pgbackrest's own lock report: ``info --output=json`` →
  ``jq '.[0].status.lock.backup.held'``, verified live; the timer
  itself is never touched — a fire landing mid-restore fails its
  oneshot harmlessly) →
  stop granian + huey + the postgres instances (stop by glob; the
  meta unit alone for START) → ``sudo -u postgres pgbackrest
  --set=<label> --type=immediate --target-action=promote --delta
  restore`` — the snapshot EXACTLY as taken, no replay past it, no
  implicit "latest" → start everything → wait until the cluster is
  OUT of recovery (``SELECT NOT pg_is_in_recovery()`` — a replaying
  cluster answers pg_isready read-only; the bounded wait fails
  loudly if it never promotes). No ``chown`` — it ran as postgres.
- Inspection uses the service directly — ``sudo -u postgres
  pgbackrest --stanza=desmo info|check``; no wrapping verb.

### systemd units (``deploy/``)

- ``pgbackrest.service.in`` — a one-line shim, deliberately NOT
  modeled on the worker units: ``Type=oneshot`` and
  ``ExecStart=/srv/desmo/main/run backupdb``. No ``User=``/
  hardening/EnvironmentFile — the logic owns all of that in ``./run``.
- ``pgbackrest.timer.in``: ``OnCalendar=*-*-* 00:00:00 UTC``,
  ``Persistent=true``, ``Unit=desmo_pgbackrest.service``,
  ``[Install] WantedBy=timers.target``.

### Provisioning / run plumbing

- ``inside-vm.sh`` provision_vm: ``apt-get install -y pgbackrest``
  alongside the base packages — no release-asset curl, no downloaded
  units to disable.
- ``testvm``: resolves ``@PG_MAIN@`` from the fresh VM, renders
  ``pgbackrest.conf.in`` + both units into the tree.
- ``inside-vm.sh`` provision_app: ALTER SYSTEM archive_mode/command +
  the postgres restart; conf pinned ``root:postgres 640``; enables the
  timer (``--now`` — enable alone never activates a unit and nothing
  reboots the VM after provisioning).
- ``vm.sh extract-app-seed``: the postgres-owned ``dbbackups/`` and the
  one-time ``pgbackrest --stanza=desmo stanza-create`` (as postgres).
- ``run``: ``_SCRATCH_EXCLUDES`` entry; ``_backup_running`` (the
  shared pgbackrest lock-report check) gates both verbs — restoredb
  and deployscratch both REFUSE the moment a backup runs (checked
  first, before the battery — a coalesced pre-migration backup
  silently skips the safety copy); the deploy then runs the
  pre-migration backup through the shim BEFORE ``migrate`` (the DB
  state to restore to if the deploy's migrations go wrong;
  diff-cheap); all three verbs in the help text.

### Docs

- ``docs/backups.md``: what runs when (timer, deploy snapshots,
  weekly-full/daily-diff, retention, WAL archiving), the
  self-contained-folder property, day-to-day commands, the restore
  procedure (``./run restoredb <set>``), the verification recipe
  (``./run backupdb`` → ``pgbackrest info|check``).
- README Features bullet + layout tree (dbbackups/, the units, the
  apt-installed binary); steer.md's lean backups section (actions
  only, ``docs/backups.md`` as the source of truth).

### Gate (``deploy/vm.sh`` — an 11th assert)

- **Assert 11: the backup round-trip on the LIVE server — mark, back
  up, diverge, restore onto the live cluster, verify.** The stanza and
  WAL archiving are provisioning's (the app role gets NO extra grants
  — pgbackrest connects as the postgres superuser over the local
  socket); the marker value is tracked by the **``BackupMarker``**
  framework model
  (``djangoapp/models/backup_marker.py`` + migration ``0028``), driven
  by the ``backupmarker`` management command (``set`` / ``latest``,
  one bare value on stdout; tested in
  ``djangoapp/tests/test_backupmarker.py``).
  **Setup** (fixture actions, not assertions): a marker goes in
  (``uv run manage.py backupmarker set`` as desmo), BOTH backup paths
  run — the agent's verb ``/srv/desmo/main/run backupdb`` and the
  timer's shim ``systemctl start desmo_pgbackrest.service`` — the
  NEWEST set's label is captured from ``info``, then a SECOND
  ``backupmarker set`` diverges the live DB past that snapshot.
  Postconditions, outcome-worded:
  1. **Both backup paths ran green and the repo lists the backup
     sets** — service ``Result=success``; ``pgbackrest
     --stanza=desmo info`` (as postgres) non-empty.
  2. **The restore rolls the live server back** — the AGENT's verb
     ``/srv/desmo/main/run restoredb '<captured set>'`` restores the
     snapshot EXACTLY (no replay past it), and ``uv run manage.py
     backupmarker latest`` over the restarted app must equal the
     pre-backup marker (the diverged one post-dates the set ⇒ the
     restore provably replaced live data).
  3. **The schedule is wired** — timer ``enabled`` with a next fire
     listed.

## Checklist

- [x] ``.gitignore``: ``dbbackups/``
- [x] ``run``: ``_SCRATCH_EXCLUDES`` entry; ``backupdb`` /
      ``restoredb`` verbs + help lines; timer reload
      + post-deploy backup on the deploy path
- [x] ``deploy/pgbackrest.conf.in`` + ``pgbackrest.service.in`` +
      ``pgbackrest.timer.in``; ``testvm`` renders all three
      (``@PG_MAIN@`` resolved from the fresh VM) + tree comments
- [x] ``deploy/inside-vm.sh``: ``apt-get install pgbackrest``; ALTER
      SYSTEM archive_mode/command + restart; conf 640 root:postgres;
      timer enabled ``--now``
- [x] ``vm.sh extract-app-seed``: postgres-owned ``dbbackups/`` +
      ``stanza-create``; gate assert 11 (mark → both backup paths →
      info → restoredb → marker round-trip → timer armed)
- [x] ``BackupMarker`` model + migration 0028 + ``backupmarker``
      command (``set``/``latest``) + ``test_backupmarker.py``
      (suite-tested)
- [x] ``docs/backups.md`` (rewritten for pgbackrest) + README Features
      bullet + layout tree + steer.md section
- [x] Naming sweep: no trace of the previous backup tool remains
- [x] Batteries: ``./run test`` (277 OK), lint, typecheck;
      ``bash -n`` on every touched script
