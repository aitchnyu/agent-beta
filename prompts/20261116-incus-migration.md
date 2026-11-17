# Multipass → Incus migration (local-vm)

> ## As-built notes (2026-11-16): phases 1-2 landed
> Host is Fedora 44; trust this where it and the plan differ.
> - **Host prep additions (phase 1)**: root needed subordinate ranges
>   (`usermod --add-subuids 1000000-10999999 --add-subgids … root` +
>   daemon restart) — the daemon ships none on Fedora, and the first
>   launch dies with "no functional idmap setup". firewalld had
>   incusbr0 in NO zone → DHCPv4 never answered (IPv6 SLAAC worked):
>   `firewall-cmd --zone=trusted --add-interface=incusbr0 --permanent`.
>   Until relogin, user access rides `sg incus-admin -c '…'`.
> - **Driver contract**: inside-vm.sh runs under `set -u` — the driver
>   must export BASE_URL even when empty (`env BASE_URL= bash …`), like
>   install.sh does.
> - **Provisioner fixes (deploy/inside-vm.sh)**: (1) container images
>   ship no default cloud user — phase 1 now creates `debian` when the
>   ubuntu/debian probe finds neither; (2) swap + vm.swappiness + ufw
>   blocks are skipped under `systemd-detect-virt -q --container`
>   (swapon and global vm.* sysctls aren't namespaced; containers sit
>   behind the host firewall); (3) uv's downloaded interpreters now land
>   in a shared `/usr/local/share/uv/python` (desmo-owned,
>   UV_PYTHON_INSTALL_DIR in bootstrap) — the units' ProtectHome=yes
>   sandbox made a /home-symlinked venv python uncanonicalizable; VMs
>   never noticed (their system Python avoided the download entirely).
> - **Playwright (deploy/install-playwright.sh)**: debian 13 row added
>   (fallback mapping, same as ubuntu 26.04) — but the override must
>   say `ubuntu24.04-x64`, NOT `ubuntu24.04-amd64`: playwright platform
>   ids call the arch x64 (the old arm64 multipass VM matched by luck).
>   Verified end-to-end: browsers, mapped deps, headless launch OK.
> - **Proxy device syntax on incus 6.23**: addresses need the protocol
>   prefix — `listen=tcp:127.0.0.1:8000 connect=tcp:127.0.0.1:443`.
>   Verified from the host: https://localhost:8000 → 200, no ssh.
> - **Full clean provision** (fresh container, all fixes, local
>   ls-files payload): all 11 phases green in ~4 min; units active
>   (granian, huey, caddy, redis, postgres, pgbackrest timer) and
>   in-container HTTPS smoke 200. Phase 11's done-banner still says
>   "via the ssh forward" — stale printout for phase 5's doc sweep.
> - Postgres 17 lands from trixie apt; Node 24 via NodeSource works in
>   the container; image `images:debian/13`, `limits.memory=2GB`.

> - **Phase 3 landed (2026-11-16)**: `local-vm` written and acceptance-run —
>   `provision-full` (local default) built desmo from the working tree
>   (uncommitted fixes rode the seed — the point of --local), all 11
>   phases green, proxy device attached at launch, host
>   https://localhost:8000 → 200, `runasdesmo`/`setupalogin` minted a
>   real one-time link, snapshot/rewind verified (post-rewind smoke 200).
>   Two wrinkles: (a) `local-vm` must be TRACKED for the ls-files seed to
>   carry it — `git add -N local-vm` (intent-to-add) suffices, tar reads
>   the working tree; (b) the dual-role dispatch: host-side
>   `./local-vm runasdesmo` rides the incus exec dispatcher (creds file
>   absent = host), in-container runs the guest body. `multipass`-based
>   `local-vm` still in place until phase 6.

> - **Phase 4 landed (2026-11-16)**: `run`'s checkframework2 repointed
>   (incus info / incus exec / local-vm); official record run green —
>   destructive rebuild from the LOCAL tree + all 11 asserts
>   ("checkframework2 green."), including the full deployscratch cycle
>   (rsync/backup/migrate/collectstatic/restarts) and the pgbackrest
>   restore round-trip. One more provisioner fix surfaced: the gate's
>   assert 8 deploys runs sudo as the default cloud user — cloud-init
>   grants that NOPASSWD sudo on VM images; container-created users get
>   it explicitly now (`/etc/sudoers.d/90-desmo-<user>` + `sudo` in the
>   apt list). Gate runs need the incus-admin group: `sg incus-admin -c
>   './run checkframework2'` until relogin. NB the gate's verdict line
>   ("checkframework2 green.") is easy to lose to output filters — the
>   exec's exit code is the real verdict.

> - **Phases 5-6 landed (2026-11-16)**: doc sweep done — README (§ local
>   dev quickstart, § blank container, § VM test server, § lifecycle,
>   § checkframework2), INSTRUCTIONS.md's in-VM script section (all
>   examples now incus exec + local-vm), docs/logging.md, access-steps.txt,
>   install.sh headers, gate.sh + inside-vm.sh + install-playwright.sh
>   comments, and the stale "via the ssh forward" provision banner.
>   The sweep caught a LATENT BREAK: gate.sh's desmo shim called
>   /srv/desmo/main/local-vm — dead the moment local-vm left the seed;
>   now local-vm. Cutover: `git rm local-vm` (multipass/snapd never
>   existed on this machine — the old VM was the previous system's),
>   `multipass *` dropped from kilo permissions, TODO items 1, 12-17, 21
>   struck. Final proof: full `./run checkframework2` green with local-vm
>   the only interface. Exit grep clean outside prompts/, TODO, and the
>   two VM-accurate historical comments in inside-vm.sh.

> - **Name decision (2026-11-16, post-cutover)**: the `localvm` rename
>   was ROLLED BACK — the script keeps the `local-vm` name so the
>   multipass→incus rewrite reviews as one in-place file diff instead of
>   a delete+add pair. The rename, if ever wanted, is a standalone `git
>   mv` + mechanical sweep. Everything above that says `localvm` was true
>   at the time of writing; `local-vm` is the shipped name. Same decision
>   round: the `setupalogin` subcommand was DROPPED — the admin surface
>   is the `runasdesmo` one-liner (login link:
>   `./local-vm runasdesmo ./run djangomanage makeloginlink <email>`).
>   Port decision (2026-11-17): the host forward moved **:8000 → :8443**
>   (`BASE_URLS` in deploy/template.env, the proxy device, install.sh's
>   probe default, and every doc) — :8000 stays free for the dev
>   runserver, so both can run at once. Caddy's site name strips the
>   port, so nothing inside the container changed. Re-proved by a green
>   gate + host smoke on https://localhost:8443.

> - **Instance-name plan landed (2026-11-17)** — every `local-vm` command
>   names its instance (`./local-vm shell desmo`); no defaults.
>   checkframework2 owns a DISPOSABLE instance — **`test`**, not `_test`:
>   incus instance names allow only alphanumerics + hyphens, the
>   underscore prefix was invalid (`Failed instance creation`). The gate
>   rebuilds `test` with `--no-forward` (its smoke is in-container; it
>   must never steal host :8443) and `desmo` persists untouched through
>   gate runs — verified: gate green on `test` while desmo served
>   https://localhost:8443 → 200 the whole time. deploy/gate.sh renamed
>   **deploy/checkframework2-gate.sh** (its runner is in its name).
>   Backups are snapshots named `<inst>-<yyyymmdd>-<HHMM>-<message>`
>   (`backup <inst> <message…>`); all instances share the pool, so
>   `restore <inst> <snap> [--force]` replaces any target with any
>   backup (source parsed from the name; REFUSES a running target
>   without --force — user-approved). `rewind` stays in-place;
>   `backups [<inst>]` lists. No backups of `test` — disposable by
>   design (user-approved).
> - **The /tmp tmpfs race (2026-11-17)**: an `incus exec` can land right
>   after launch BEFORE systemd mounts the /tmp tmpfs — a payload file
>   written then hides under the later mount (exit 0, file "missing";
>   cost two failed provisions to diagnose: the seed tarball vanished
>   while inside-vm.sh, written moments later, survived). provision-blank
>   now waits for `systemctl is-active multi-user.target` (bounded 60s)
>   before shipping anything. Also: `sg incus-admin` is no longer needed
>   anywhere — the login session has the group natively.
> - **Gate instance renamed (2026-11-17)**: `test` → **`volatile-test-machine`**
>   (operator's name; hyphens because incus bans underscores). Same
>   semantics: disposable, --no-forward, desmo untouched.
> - **Rename landed after review (2026-11-17 evening)**: `local-vm` →
>   **`localvm`** — the name was kept only to ease the big diff's review;
>   post-commit, `git mv` + a mechanical sweep. The earlier
>   name-decision note above is superseded.
> - **Post-review trimming (2026-11-17 evening)**: the `restore`/`backups`
>   subcommands described above were later REMOVED (backup + rewind are
>   the machine-state surface), and the boot-settle wait became a single
>   check with a delete+rebuild recovery hint.

> Plan (2026-11-16). Supersedes the multipass mechanics of
> prompts/20260818-vm-provisioning-multipass.md and the ssh-forward access
> model of deploy/access-steps.txt. TODO.md items served: no more snapd and
> multipass (1), Debian + lower memory + rewind (12), native port forward
> (13), rename to local-vm + deploy from local tracked files (14), remove the
> ssh -N -L line (15), setupalogin/portforward subcommands (16-17),
> vm-prefixed provision/delete names (21).

## Goal

- Replace the multipass VM (`desmo`, Ubuntu, bridged en0, 2G/20G) with an
  incus **container** on the same host, same instance name, same provisioner
  (`deploy/inside-vm.sh provision`, byte-unchanged where Debian allows).
- `local-vm` commands work as the single interface (rename of `local-vm`):
  same host/guest dual-role shape, plus the TODO'd subcommands.
- **No ssh for port forwarding.** The container's https (:443, Caddy
  loopback, internal CA) is published to the host as
  `https://localhost:8000` via an incus **proxy device** — the exact
  semantics of the removed `ssh -N -L 8000:localhost:443` line (including
  the "collides with dev runserver — never both" caveat).
- Optional, not default: a second proxy device `127.0.0.1:2222 → :22` if
  real ssh into the container is ever wanted. Default access is
  `./local-vm shell` (`incus exec desmo -- bash`, root, no key setup).

## Decisions (settled with operator, 2026-11-16)

- **Container, not VM**: incus container on the Fedora 44 host; Debian 13
  (trixie) image — lower memory than the 2G Ubuntu VM, systemd units work
  unprivileged, `limits.memory=2GB` preserves the old envelope. No en0
  bridge: the managed `incusbr0` (NAT) + proxy device for ingress is enough;
  the LAN IP and its ssh-authorized-keys step disappear.
- **Local-first deploy**: `provision-full` defaults to seeding from the
  LOCAL working tree (`git ls-files` tarball, same payload contract
  install.sh manufactures) — the "push first, then gate" coupling is gone;
  `--published` keeps the old curl|bash-from-main semantics for parity.
- **Proxy device is part of provision**: every provision-full/provision-blank
  ends with (idempotent)
  `incus config device add desmo https proxy listen=127.0.0.1:8000 connect=127.0.0.1:443`
  — connect resolves in the container namespace, so it hits Caddy's
  loopback origin exactly like the tunnel did (`-k` internal CA).
- **Two principals only**: `incus exec` lands as root (no `ubuntu` user, no
  key dance); the service user stays `desmo` via the unchanged `runasdesmo`
  guest role. `checkframework2`'s exec becomes
  `incus exec desmo -- sudo bash /srv/desmo/main/deploy/gate.sh gate`.
- **No data migration**: desmo is a destructive test VM by design
  (checkframework2 wipes it). Optional one-off `pg_dump` off the old VM
  before `./local-vm delete` if test data matters.
- **Naming**: instance stays `desmo`; script becomes `local-vm`; the
  vm-prefix debate (TODO 21) lands as `provision-full`/`provision-blank`/
  `delete` keeping their names inside `local-vm` (one namespace, one verb
  surface).

## Design

### `local-vm` (host role) — replaces `local-vm`

- `provision-full [--local|--published] [--release 13|12]`
  - `--local` (default): `(cd main && git ls-files -z) | tar czf - --null -T -`
    piped through `incus exec desmo -- tar xzf - -C /srv/seed` (tar-over-exec;
    `incus file push -r` of a tree is slow), then
    `incus exec desmo -- bash /srv/seed/deploy/inside-vm.sh provision` with
    BASE_URL empty (loopback, as today).
  - `--published`: the current curl|bash line run via `incus exec` —
    identical to today's provision-full modulo the driver.
  - Both end: proxy device add (guarded by `incus config device show`) +
    the access printout (now "browse https://localhost:8000 — no forward to
    run; `./local-vm shell` to get in").
- `provision-blank [--release]`: `incus launch images:debian/<rel> desmo
  --config limits.memory=2GB` + proxy device; prints the installer line.
  Refuses an existing instance (as today).
- `delete`: `incus delete -f desmo` — same no-backup warning as today.
- `shell`: `incus exec desmo -- bash` (replaces `multipass shell desmo`).
- `portforward [add|rm|ls]`: manage the https device (and the optional ssh
  one) — the TODO 17 subcommand.
- `setupalogin <email>`: TODO 16 — wraps
  `incus exec desmo -- sudo -u desmo -H bash /srv/desmo/main/local-vm runasdesmo
  djangomanage makeloginlink …` (README § VM commands, minus the ssh hop).
- `snapshot [<name>]` / `rewind <name>`: thin `incus snapshot create|restore`
  wrappers — TODO 12's "incus can rewind machines"; cheap on dir storage.

### Guest role — unchanged

`runasdesmo` is self-contained at `/srv/desmo/main/local-vm`; only its
invocation loses the multipass hop.

### File manifest

| File | Change |
|---|---|
| `local-vm` → `local-vm` | rewrite host role onto incus; guest role unchanged |
| `run` (checkframework2) | `multipass info/exec` → `incus list/exec`; keep the never-pipe-exec-into-grep -q caution |
| `deploy/inside-vm.sh` | Debian fixes only if phase 0-9 audit finds Ubuntu-isms (apt itself is shared) |
| `deploy/install.sh` | header comment only (references `local-vm provision-blank` + `multipass shell`); zero logic — it targets real cloud VMs |
| `deploy/access-steps.txt`, README § VM | drop ssh -L + authorized-keys steps; proxy device + `local-vm shell` flow |
| `~/.config/kilo/kilo.jsonc` | add `"incus *": "allow"` during transition; drop `multipass *` at cutover |
| `.pi/repo-map.md` | rename entry + this file |

## Phases

### 1. Host prep

- `sudo dnf install incus incus-tools`; `sudo systemctl enable --now incus`.
- `sudo usermod -aG incus-admin jesvin` — then RELOGIN (group membership is
  per-session; `newgrp incus-admin` covers the current shell only).
- `incus admin init` — accept defaults: dir storage on /var/lib/incus,
  managed `incusbr0` (NAT + DHCP), no clustering, no auto-bridge to en0.
- Smoke the toolchain before touching the plan: `incus launch
  images:debian/13 smoke && incus exec smoke -- apt-get update && incus
  delete smoke -f` — proves image pull, DHCP, exec-as-non-root.
- Transition permission: add `"incus *": "allow"` to
  `~/.config/kilo/kilo.jsonc` bash rules (multipass stays until phase 6).
- **Exit criteria**: a throwaway container launches, gets an incusbr0 lease,
  answers `incus exec` as `jesvin`, and deletes cleanly.

### 2. Debian rehearsal (proves the provisioner before any new code)

- `incus launch images:debian/13 desmo-test --config limits.memory=2GB`.
- `incus exec desmo-test -- bash`, then run the EXISTING
  `deploy/install.sh` (curl|bash, no `--base-url` → loopback install).
- Watch every phase banner; collect the Ubuntu-isms as they surface. Known
  suspects to check first in `deploy/inside-vm.sh`:
  - the `ubuntu` user / `multipass` references (exec lands as root here);
  - `ufw` (Ubuntu's firewall — Debian ships nftables; either install ufw
    or gate the firewall phase on loopback-only installs, which don't need
    one);
  - package-name drift and systemd unit quirks (ReadWritePaths on missing
    dirs — the opencode-unit lesson from the multipass file);
  - apt sources/portalocker-style assumptions that differ on trixie.
- Fixes land in `inside-vm.sh` as Debian-AND-Ubuntu compatible —
  `install.sh` still declares both targets (cloud Ubuntu stays supported).
- Manual forward check: `incus config device add desmo-test https proxy
  listen=127.0.0.1:8000 connect=127.0.0.1:443`, browse
  `https://localhost:8000` from the host (accept the internal-CA warning),
  then `incus config device remove desmo-test https`.
- `incus delete desmo-test -f`.
- **Exit criteria**: install.sh's self-tests green on Debian (units active +
  HTTPS smoke), the fix list committed, the proxy device pattern proven.

### 3. Write `local-vm` (parallel — `local-vm` keeps working)

- New file `local-vm` (do NOT `git mv` yet — the multipass `local-vm` must
  keep operating as the fallback until phase 6; both can coexist since
  multipass and incus namespaces are independent, but never run the
  :8000 forward of both at once).
- Host role, subcommand by subcommand:
  - `provision-full [--local|--published] [--release 13|12]` — `--local`
    seeds from the working tree via tar-over-exec (`git ls-files -z | tar
    czf - --null -T - | incus exec desmo -- tar xzf - -C /srv/seed`), then
    execs `inside-vm.sh provision`; `--published` runs the curl|bash line
    through `incus exec` (today's semantics). Guard + idempotent proxy
    device add at the end; print the new access steps.
  - `provision-blank [--release]` — launch-only + device; refuses an
    existing instance; prints the installer line (still derived from
    install.sh's `repo_url`, MAINTAIN-CONSISTENCY vm-payload).
  - `delete` — `incus delete -f desmo`, same no-backup warning.
  - `shell` — `incus exec desmo -- bash`.
  - `portforward [add|rm|ls]` — device management incl. the optional
    `127.0.0.1:2222 → :22` ssh device.
  - `setupalogin <email>` — README § VM login-link command, minus the
    multipass hop.
  - `snapshot [name]` / `rewind <name>` — `incus snapshot create|restore`
    wrappers (TODO 12).
- Guest role: `runasdesmo` verbatim; the seeded copy at
  `/srv/desmo/main/local-vm` arrives with the tarball automatically.
- Update the MAINTAIN-CONSISTENCY payload comments in `local-vm` AND
  `install.sh` (two manufacturers now: cloud clone vs local ls-files).
- **Exit criteria**: `provision-full --local` builds a container from the
  uncommitted working tree; `https://localhost:8000` answers;
  `local-vm runasdesmo` (via `incus exec desmo -- sudo -u desmo -H bash
  /srv/desmo/main/local-vm runasdesmo …`) runs a manage.py command.

### 4. Repoint the gate

- `run`'s `checkframework2`: `multipass info desmo` → `incus list desmo`,
  `multipass exec desmo -- …` → `incus exec desmo -- …`; the
  `$_TREE_DIR/local-vm` calls → `$_TREE_DIR/local-vm`.
- Carry over verbatim: the never-pipe-exec-output-into-`grep -q` caution
  (incus exec streams the same way).
- Acceptance run: `./run checkframework2` — destructive rebuild from the
  LOCAL tree + all 11 gate asserts green. If the gate's testapp overlay or
  scratch lifecycle trips on container differences (paths, speeds), fix in
  gate.sh/ops, not by loosening asserts.
- **Exit criteria**: green gate against local code — TODO 14's "deploy from
  local instead of git" is now the tested path.

### 5. Docs + config

- `deploy/access-steps.txt`: rewrite — no authorized_keys step, no
  `ssh -N -L`; "browse https://localhost:8000 (forward is part of
  provision); `./local-vm shell` to get in; :8000 still collides with the
  dev runserver — never both".
- README § VM: same content; § install (cloud) keeps its ssh-based flow but
  drops the `local-vm`/`multipass shell` dress-rehearsal wording.
- `deploy/install.sh`: header comment swap (`./local-vm provision-blank` +
  `shell`) — zero logic changes.
- `.pi/repo-map.md`: `local-vm` → `local-vm`; list this prompts file.
- Append the as-built notes here (house convention) — deviations from this
  plan get recorded as they land.
- **Exit criteria**: `grep -rn 'multipass\|ssh -N -L'` clean outside
  historical prompts/.

### 6. Cutover + cleanup

- One parallel cycle first: gate green on incus while the multipass desmo
  still exists as the fallback.
- Rescue anything wanted off the OLD VM (its DB dies with it): `multipass
  exec desmo -- pg_dump …` → host file.
- `./local-vm delete`; `git rm local-vm`.
- `sudo dnf remove multipass`; remove snapd per TODO 1 (audit what else
  snapped first: `snap list`).
- Drop `"multipass *": "allow"` from `~/.config/kilo/kilo.jsonc`.
- TODO.md: strike the resolved items (1, 12-17, 21).
- Final proof: `./run checkframework2` green with multipass gone.
- **Exit criteria**: no multipass/snapd on the host; `local-vm` the only VM
  interface; gate green.

## Risks / gotchas

- Proxy device add is not idempotent — guard on `incus config device show
  desmo https` before adding.
- Unprivileged container + postgres/caddy on Debian 13: expected fine
  (namespaces cover the low ports in-container); phase 2 exists to catch
  surprises, e.g. systemd unit ReadWritePaths quirks (precedent: the
  opencode-unit home-dir lesson in the multipass file).
- The gate's destructive rebuild now tests local code by default — intended
  (that is what deployscratch is about to ship); `--published` remains the
  escape hatch.
- `incus exec` streams like `multipass exec`: never pipe into `grep -q`
  (early-exit readers) — the existing run-comment caution carries over.
