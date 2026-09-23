# desmo: default user as operator, `desmo` command, app → desmo rename

Planned 2026-09-23. Decisions settled with the operator; checklist below.
Build-or-destroy applies: every change is provisioning-side, no migration —
the only application path is a fresh `./testvm provision`.

## Why

The VM currently carries three users: `app` (less powerful service user),
`agent` (operator: full passwordless sudo via `/etc/sudoers.d/agent`,
app-group member), and `ubuntu` (multipass default — used only for the ssh
pubkey/tunnel). The operator flow is a wasteful hop: `multipass shell app`
(already lands as the default user) → `sudo -iu agent` → banner profile
lands you in the repo → `./run pi`. Meanwhile the deployment name `app` is
generic everywhere it appears (/srv, units, credentials dir, DB names,
caddy site, even the multipass instance name).

## Decisions (settled with operator, 2026-09-23)

- **Drop the `agent` user.** The default cloud user (`ubuntu` on multipass,
  `debian` on a future Incus/Debian switch — TODO.md:26) becomes the
  operator + agent user. Existing privileges suffice: cloud-init already
  gives the default user passwordless sudo, so `/etc/sudoers.d/agent` is
  simply deleted — nothing replaces it. The one thing `agent` had beyond
  sudo was group membership to read the `root:app 640` credentials env;
  replicated by adding the default user to the renamed group.
- **Rename `app` → `desmo` everywhere** (full scope, fresh-VM only):
  - user/group: units run `User=desmo`/`Group=desmo`; owns `/srv/desmo`
  - `/srv/app` → `/srv/desmo` (`main`, `scratch`, git safe.directory)
  - units `app_granian`/`app_huey` → `desmo_granian`/`desmo_huey`
  - `/etc/credentials/app` → `/etc/credentials/desmo`
  - DB `app_db`/`app_user` → `desmo_db`/`desmo_user`
  - `/etc/caddy/sites/app.caddy` → `desmo.caddy`
  - multipass instance `app` → `desmo` (every exec/transfer/info/delete)
- **`desmo` command, inline in provisioning** (no repo file):
  `inside-vm.sh provision_vm` writes `/usr/local/bin/desmo` from a heredoc —
  `cd /srv/desmo/main || exit 1; exec ./run "$@"`. Env sourcing stays in
  `./run`'s setenv, so the wrapper is trivially thin and user-agnostic.
  Operator flow collapses to `multipass shell desmo` → `desmo pi`.
- **Default-user detection, both names now:** provisioning (and the gate)
  detect the default cloud user — first existing of `ubuntu`/`debian` —
  for group membership and user-targeted asserts. Matches the Incus TODO.
- **Drop `deploy/agent-login.txt`** and its tree shipping — no
  `.bash_profile` override for the default user; `desmo pi` from anywhere
  replaces the cd + banner.
- **vm.sh `agent-*` function names STAY** — they denote the pi agent's
  scratch lifecycle, not the executing user; only the executing user
  changes. `runasapp` renames to `runasdesmo`.
- TODO.md is NOT touched by this work.

Privilege note (the operator's original question): yes, existing
privileges are enough — no sudoers file is added. The default user joins
group `desmo` (not a power escalation: it already holds full sudo), which
is what makes `/etc/credentials/desmo/.env.vm` (root:desmo 640) and the
group-writable `/srv/desmo` tree work for `./run`/pi without sudo.

## Checklist

### deploy/inside-vm.sh

- [ ] vars (21-23): `appdir=/srv/desmo`, `creds_dir=/etc/credentials/desmo`.
- [ ] provision_vm (28-49): `useradd` only `desmo`; delete the `agent`
      useradd, the sudoers.d/agent decision comment, and
      `usermod -aG app agent`; add default-user detection (first existing
      of ubuntu/debian) + `usermod -aG desmo <default>`;
      `install -d -m775 -o desmo -g desmo /srv/desmo`.
- [ ] provision_vm: write the `desmo` wrapper inline — heredoc to
      `/usr/local/bin/desmo` + chmod 755:
      `#!/bin/sh` / `cd /srv/desmo/main || exit 1` / `exec ./run "$@"`.
      (Lands before the seed extract — pointing at a path is fine.)
- [ ] provision_app tree comment (114-129): /srv/desmo, desmo_* units,
      credentials/desmo, sites/desmo.caddy — drop the sudoers.d/agent and
      /home/agent entries.
- [ ] provision_app: drop the sudoers block (161-165: chmod 0440 +
      visudo -cf) and the /home/agent/.bash_profile block (167-171).
- [ ] provision_app: `systemctl enable desmo_granian.service
      desmo_huey.service` (218-219).
- [ ] provision_app: `git config --system safe.directory` →
      /srv/desmo/main + /srv/desmo/scratch (232-233).

### deploy/ — templates + one-shots

- [ ] granian.service.in + huey.service.in: descriptions, `User=desmo`/
      `Group=desmo`, WorkingDirectory/ExecStart → /srv/desmo/main,
      `EnvironmentFile=/etc/credentials/desmo/.env.vm`,
      `ReadWritePaths=/srv/desmo`.
- [ ] Caddyfile.site.in:38: `root * /srv/desmo/main/staticfiles`.
- [ ] vm-seed-commit.sh: env path + cd → /etc/credentials/desmo +
      /srv/desmo/main (8-9), header comment (4).
- [ ] vm-bootstrap.sh: header "AS app" → "AS desmo" (2), env path +
      cd (6-7).
- [ ] DELETE deploy/agent-login.txt.

### deploy/vm.sh

- [ ] Header usage comments (8-15): `sudo -u desmo … runasdesmo`; drop the
      agent-user line from the "pick the function to match" note.
- [ ] `_vm_env` (20-25): `. /etc/credentials/desmo/.env.vm`,
      `cd /srv/desmo/main`.
- [ ] extract-app-seed (29-36): extract to /srv/desmo/main, chown
      desmo:desmo; retarget the g+w comment (the default user edits main/).
- [ ] playwright-setup (51-70): `sudo -u desmo … runasdesmo`.
- [ ] cleanup-provision-tmp (79-82): tarball rename app-seed.tgz →
      desmo-seed.tgz (with testvm + extract-app-seed).
- [ ] playwright-deps (86-97): /srv/desmo/main paths.
- [ ] `runasapp` → `runasdesmo` (108-114) — header comment too
      ("the one sanctioned way to run one command as the desmo user").
- [ ] agent-* section (122-186): comment notes the executing user is now
      the default cloud user; /srv/app/scratch → /srv/desmo/scratch
      (152-155, 168, 184-185).
- [ ] gate shims (203-208): `gate-as-app-user` → `gate-as-desmo-user`
      (`sudo -u desmo … runasdesmo`); `gate-as-agent-user` → default user
      via a detection helper (`_op_user`: first existing of ubuntu/debian),
      same one-argument forwarding.
- [ ] gate body: deploy-ourapp paths (248-253); restart
      desmo_granian.service (264-265); assert 5 (301-313) → default user:
      `command -v pi` AND `command -v desmo` on PATH, AGENT_MODEL resolves
      via desmo-group membership; asserts 6-9 (315-371): ride
      gate-as-<default>-user; assert 7 postcondition 3 (342) `sudo -u
      <default>` for scratch's own ./run refusal; assert 8 (355-356)
      desmo_granian is-active.
- [ ] Assert bodies may simplify: `sudo -u <default> -H desmo createscratch`
      style for the argless wrappers where it reads cleaner.

### testvm

- [ ] Header + tree comments (9, 23-59): /srv/desmo, desmo_* units,
      credentials/desmo, sites/desmo.caddy; drop sudoers.d/agent +
      /home/agent + agent-login.txt lines.
- [ ] Instance rename: refusal check (165-166), `multipass launch --name
      desmo` (173), and every `multipass exec/transfer/info app` call site
      (176-307); delete message (305-307).
- [ ] Tree build (191-228): mkdir etc/credentials/desmo; render units to
      desmo_granian/desmo_huey.service; site → sites/desmo.caddy;
      DELETE the sudoers printf (222-224) and the .bash_profile copy
      (226-228).
- [ ] Seed phase (253-267): `install -d -o desmo -g desmo /srv/desmo/main`,
      desmo-seed.tgz name, `sudo -u desmo` for vm-seed-commit +
      vm-bootstrap (273, 277).
- [ ] Playwright + restart steps (280-297): /srv/desmo/main paths, restart
      desmo_granian.service desmo_huey.service (296).
- [ ] Epilogue access text: `multipass shell desmo` → `desmo pi`; no
      sudo -iu hop.

### run

- [ ] setenv (22-40): /etc/credentials/desmo/.env.vm (comment at 26,
      test at 34, warning at 40).
- [ ] checkframework2 (254-263): `multipass info/exec desmo`,
      /srv/desmo/main/deploy/vm.sh gate.
- [ ] Scratch VM branch (423-442): credentials check, `sudo rsync` target,
      `sudo chown -R desmo:desmo`, `sudo systemctl restart
      desmo_granian.service desmo_huey.service`.
- [ ] Comment sweep: every remaining /srv/app, credentials/app,
      app_granian/app_huey mention (e.g. 357 protected-hardlinks note,
      458 scratch-dir note).

### Config + docs

- [ ] .env.vm.example:27-28: `DB_NAME="desmo_db"` / `DB_USER="desmo_user"`
      (+ any app_db/app_user prose). Local `.env.vm` (gitignored, the
      source testvm stages) needs the same values for the next provision.
- [ ] djangoproject/settings.py:20 comment: credentials path.
- [ ] README.md: 11-12 (`desmo pi` from `multipass shell desmo` — no
      sudo -iu), 83-89 (desmo_db/desmo_user, /srv/desmo/main, desmo_
      units under the less powerful `desmo` user), 104-110 (multipass
      exec desmo; note the ssh step's `~ubuntu` becomes `~debian` on
      Debian), 119-128 (`sudo -u desmo … runasdesmo`), 131-136 (scratch
      flow as the default user, /etc/credentials/desmo), 480-486
      (journal unit names). New steps to state explicitly: one-time pubkey,
      `multipass shell desmo`, `desmo pi`.
- [ ] deploy/access-steps.txt: rewrite 19-33 for the desmo instance,
      default user, runasdesmo.
- [ ] INSTRUCTIONS.md:29-75: call-site examples (paths, `sudo -u desmo`,
      runasdesmo).
- [ ] docs/logging.md + docs/errors/README.md: journalctl `-u
      desmo_granian`/`desmo_huey` + /srv/desmo paths in records.

### Verify

- [ ] `bash -n` every edited script (run, testvm, deploy/*).
- [ ] `./run checkframework2` — the real gate: rebuilds the VM fresh
      (destructive) and its asserts 5-9 are exactly the surface touched
      here (default-user privileges, desmo command, scratch lifecycle,
      deploy + unit restarts under the new names).
- [ ] Manual smoke after the gate: `multipass shell desmo` → `desmo pi`
      from ~ (not the repo dir) — proves the wrapper's cd + setenv path.
