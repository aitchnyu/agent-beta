# Blank VM + curl|bash install

> **Superseded mechanics** (2026-10-06): the landed design evolved past
> several decisions below — `--domain`/`DESMO_DOMAIN` became
> `--base-url`/`BASE_URL` overriding the template's `BASE_URLS` key; the
> DB round-trip self-test was dropped (units + one HTTPS smoke remain);
> the ACME retry window became a single settled attempt; `./local-vm
> blank`/`provision` became `provision-blank`/`provision-full` (the
> latter = blank + the curl|bash, built from published main). Read the
> decisions as history; the code and README are the truth.

## Goal

- Install a full VM from a blank multipass VM with ONE curl|bash command,
  choosing a **branch/release** and a **domain** — reusing the existing
  provisioner (`deploy/inside-vm.sh`) byte-unchanged.
- Three deliverables:
  1. `./local-vm blank` — create just a blank VM (launch-only).
  2. `deploy/install.sh` — the curl|bash entry that installs everything.
  3. README §2 "install on a VM" — blank VM → run command → provision →
     run test suites.

## Decisions (settled with operator, 2026-10-05)

- **Installer source**: raw.githubusercontent of OUR repo's main branch —
  `curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/deploy/install.sh | sudo bash -s -- --domain example.com [--release <tag> | --branch <name>]`.
  README documents OUR URL only (dogfood).
- **User provides**: domain(s) + branch/release. Nothing else — secrets
  stay minted, DB names/users stay template-baked, no ACME email, no
  size/worker knobs.
- **Default ref**: latest tag via `git ls-remote --tags`, fallback `main`;
  `--branch <name>` overrides.
- **Blank VM**: multipass only, a shipped script — `./local-vm blank
  [--release 26.04|24.04]`, launch-only, fixed instance name `desmo`,
  same shape as provision (bridged `en0`, 2G ram, 20G disk), refuses an
  existing instance.
- **Payload**: install.sh clones the ref to /tmp, builds the SAME
  two-file payload (ls-files tarball → `/tmp/desmo-seed.tgz`, cp →
  `/tmp/inside-vm.sh`) and execs `inside-vm.sh provision` unchanged.
  No `.git` ships; phase 8's baseline commit unchanged. ONE provisioner,
  two entry paths (host-shipped seed vs clone-built seed).
- **Domain flow**: env-var override — install.sh exports `DESMO_DOMAIN`
  (comma-list); phase 0 takes env-over-file precedence for
  `ALLOWED_HOSTS`. Domain set → ufw opens 80/443, caddy serves public
  ACME TLS; unset → today's loopback :443. DNS pointing at the VM is a
  documented prerequisite.
- **Self-tests** (what "run test suites" means for the install itself):
  units active (granian, huey, caddy, postgres, redis, pgbackrest
  timer) + DB round-trip (`SELECT 1` as the minted `desmo_user`) + one
  HTTPS request to the site root expecting 2xx/3xx (with a retry window
  — caddy's first ACME issuance can lag). The full `gate.sh`
  battery stays a documented follow-up (`deploy/gate.sh gate`).

## Design

### `./local-vm blank`

- The launch stanza of `provision`, extracted as its own subcommand:
  same instance name/bridge/specs/exists-refusal, no payload, no exec.
- Prints the `multipass shell desmo` hint + the curl|bash line to paste
  inside. `provision` itself stays unchanged and independent.

### `deploy/install.sh` (new — zero provisioning logic)

- Guards: must run as root; `apt-get install` git/curl if a bare image
  lacks them.
- Flags: `--domain <names>` (comma-list; omitted → loopback-only
  install, same shape as `./local-vm provision`'s VM), `--release <tag>`
  (default: latest `ls-remote` tag, fallback `main`), `--branch <name>`.
- Manufacture the payload in /tmp: `git clone --depth 1 --branch <ref>`
  → `git ls-files` tar recipe (identical to `local-vm provision`'s) →
  `/tmp/desmo-seed.tgz`; `cp` the clone's `deploy/inside-vm.sh` →
  `/tmp/inside-vm.sh`.
- `export DESMO_DOMAIN=…` then `bash /tmp/inside-vm.sh provision` —
  its exit code is the verdict.
- Self-tests (above), domain-flavored access steps, `rm -rf` the clone
  dir (phase 10 already removes the payload files).

### `deploy/inside-vm.sh` (one deliberate edit)

- Phase 0: `DESMO_DOMAIN` (if set) overrides the template's
  `ALLOWED_HOSTS`, validated by the same hostname checks as today.
- Phase 1/4 branches on it: ufw allows 80/443; the caddy site renders
  public ACME on the domain(s) vs the loopback site when unset.
- Header comment: `install.sh` named as the third payload manufacturer
  (the `MAINTAIN-CONSISTENCY vm-payload` note; `local-vm` footer too).

### README §2 — install on a VM

- Create a blank VM (`./local-vm blank`) → run the curl|bash command →
  provision runs (phases + self-tests) → follow-ups: full suites via
  `desmo gate`, first login.

## Checklist

- [x] `./local-vm blank` subcommand (launch-only)
- [x] `deploy/install.sh` (guards, ref resolution, payload, exec, self-tests)
      — plus the pipe-safety lesson: a piped `bash -s` reads lazily and a
      stdin-eating child (apt, mid-provision) silently truncated the
      script; the whole body now rides ONE `{ … }` compound block so bash
      buffers it all before executing anything
- [x] `inside-vm.sh`: `DESMO_DOMAIN` override + ufw/caddy domain branch
- [x] `MAINTAIN-CONSISTENCY vm-payload` notes in `inside-vm.sh` + `local-vm`
- [x] README §2 (install on a VM)
- [x] `sh -n` on every touched script; live round-trips: blank →
      curl|bash install (no domain: full provision + self-tests + access
      steps, exit 0), re-install refusal, and `./run checkframework2`
      (dev-path rebuild + all 11 gate asserts green). The `--domain`
      branch (ufw 80/443, ACME, the ALLOWED_HOSTS sed) is verified by
      construction + shared phase-0 validation only — no DNS name to
      test against.
- [x] Found + fixed pre-existing gate breakage (since fb4a9a9, surfaced by
      the first checkframework2 run since): the Books overlay's home view
      gained `/mockup-todos`, and `agent-scratch-edit`'s marker sed got
      scoped to the first `return InertiaResponse`
