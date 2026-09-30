# Backups (pgbackrest)

```bash
./run backupdb                                        # back up now
sudo -u postgres pgbackrest --stanza=desmo info       # list snapshots
./run restoredb 2026-10-02-000010F                    # restore one (stops the app!)
```

The label for a restore is the one `info` prints per snapshot —
`2026-10-02-000010F` is a full taken 2026-10-02 00:00:10, `…D` a diff.

## What's automatic

- Every night at 00:00 UTC.
- A snapshot before every deploy's `migrate` — the state to roll back
  to if a migration goes wrong.
- Two months of history: weekly fulls + daily diffs, old sets expire
  on their own.

## Restoring

1. Pick a snapshot: read the labels from `pgbackrest info`.
2. `./run restoredb <label>` — it stops the whole app, restores that
   snapshot exactly (nothing later comes back), and brings everything
   up.
3. Wait for it to finish, then confirm the app serves the data you
   expected.

If it refuses: an unknown label costs nothing (checked before
anything stops), and a backup that's currently running means waiting
a minute and re-running.

## If backups fail

```bash
sudo journalctl -u desmo_pgbackrest -o cat
```

Read the error, fix, then prove it: `./run backupdb` and
`sudo -u postgres pgbackrest --stanza=desmo check` (the consistency
check). The in-VM gate also runs a full mark → back up → restore →
verify round-trip on every fresh VM.

## Details

- [pgbackrest](https://pgbackrest.org/) from Ubuntu's apt. Everything
  runs as postgres over the local socket.
- `dbbackups/` in the repo root is self-contained: backup sets +
  WAL together. Copying the folder carries the whole backup — so any
  copy of it IS a plaintext database; never commit or share it.
  Deploys never wipe it.
- Provisioning does all setup (config, WAL archiving, the stanza) —
  there is nothing to set up by hand.
- Restores are always onto the live database, always from an explicit
  label, and only on request — the runbook above is the only path.
