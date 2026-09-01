# Remove /agent (ttyd web terminal); `./run console` → `./run agent`

Planned 2026-09-01. Research done; checklist below.

## Why

/agent is the second-era console (born a7bc31e 2026-08-22 "Agent via ttyd…",
gated 789036d 2026-08-25 "Superuser-gate /agent via caddy forward_auth"): a
ttyd served by `console_ttyd` on loopback 7681, caddy-proxied at
`https://app.local/agent/`, running as the powerful `console` user. The stack
carries real weight — a systemd unit, a caddy route, a Django forward_auth
endpoint + tests, CONSOLE_URL plumbing through settings/middleware/frontend,
apt/mask dance in provisioning, two checkframework2 asserts — and a history of
ttyd-specific pain (opencode TUI hang never fixed, exit-254 reconnect loop,
http1.1-for-WS requirement, the NNP exception just so sudo works).

Decision: the operator shells into the VM the way the host always has —
`multipass shell`/`exec` (port 22 stays multipass's own channel; inside-vm.sh:102-104
— NO authorized_keys provisioning, user decision) — becomes the agent user
(`sudo -iu agent`), and runs `./run agent` (Crush) from a real shell. `setenv`
already sources /etc/credentials/app/.env.vm on the VM (run:22-40), so the
agent path is transport-agnostic and unchanged. The VM's `console` user is
RENAMED to `agent` — the one who logs in IS the agent's operator, the
`GIT_COMMITTER_NAME="Agent"` marker matches the username, and the name
`console` was always slightly misleading. No collision: no system group/binary
named agent exists, and `./run agent` is a repo command, not a user. Locally,
`./run console` (ttyd on 7681) dies too: its job — "get a shell to run
./run agent in" — is just a terminal away; `./run agent` IS the console.

History for the record: era 1 (opencode chat UI at /agent/, ~2k lines) was
removed in ca2bbc4; era 2 replaces it below. makeloginlink/TestLoginKey STAY
(app login on the VM, nothing to do with the terminal).

## Checklist

### Django — the gate

- [ ] Delete `agent_auth` (djangoapp/views/__init__.py:24-36) and the
      slashless route (djangoapp/urls.py:25 + the comment at 15-16).
- [ ] Delete djangoapp/tests/views/test_agent_auth.py (4 tests).
- [ ] require_superuser docstring (views/__init__.py:16-17): drop the
      "/agent under caddy" aside.

### CONSOLE_URL plumbing — full removal

- [ ] djangoproject/settings.py:44-47 — delete `CONSOLE_URL` (the
      "empty hides the link" escape hatch dies with the feature).
- [ ] djangoapp/middleware.py:94 — drop the `console_url` shared prop.
- [ ] frontend/src/components/Layout.vue:14 + 22-30 — drop the superuser
      "Console" nav link.
- [ ] frontend/src/schemas.ts:123 — drop `console_url` from
      SharedPropsSchema.
- [ ] ourapp/tests/test_home_views.py — remove the CONSOLE_URL
      override_settings + the two `console_url` asserts (sync the
      docs/reference/ourapp/tests/test_home_views.py copy).
- [ ] .env.example:50 + .env.vm.example:49-52 — delete the key; sweep the
      .env / staged .env.vm (all-keys rule).
- [ ] djangoapp/tests/playwright/_base.py:149-153 — stale localStorage
      comment ("Only the crush session id uses it… no /agent/ e2e"):
      drop the /agent aside.

### run — console() dies, agent() is the console

- [ ] Delete `console()` (run:115-133) and the ttyd leg of `dev()`
      (run:95-113: back to runserver+vite+huey, kill the ttyd-missing
      fallback branch). Comment updates in dev()'s header.
- [ ] `agent()` (run:135-218) UNCHANGED — it is now the only console
      entry, dev and VM alike.
- [ ] checkframework2 asserts 5/7 + 6/7 (run:376-401, the /agent gate +
      ttyd page probes) — delete; replace with an agent-shell assert (see
      below); renumber 7/7 → the playwright probe stays last.

### deploy/ + provisioning — ttyd stack out

- [ ] Delete deploy/ttyd.service.in; testvm drops its render (testvm:184-185)
      and `console_ttyd` from the restart list (testvm:272) + header/tree
      comments (testvm:10, 38).
- [ ] deploy/Caddyfile.site.in — remove the /agent redir + handle_path +
      forward_auth (lines 45-54); rewrite the header comment block (the
      /agent bullets, lines 9-18).
- [ ] deploy/inside-vm.sh — drop apt `ttyd` (line 51) and the distro-unit
      disable/mask (56-60); `console_ttyd` enable (214) → granian only;
      comments at 34, 66, 108, 122, 224-226, 232; tree diagram entry (122).
- [ ] Delete deploy/console-bashrc (both consumers — ttyd unit + ./run
      console — are gone). OPTIONAL: if a VM banner is still wanted, chain
      it from ~agent/.bashrc instead; default is no banner.
- [ ] RENAME the VM user `console` → `agent`:
      inside-vm.sh `useradd --create-home --shell /bin/bash console` (31) +
      `usermod -aG app console` (43) + every "console" comment in the
      users/permissions block (29-46) and elsewhere (227, vm-seed-commit.sh
      comments); testvm sudoers `printf 'console ALL=(ALL) NOPASSWD: ALL' >
      /etc/sudoers.d/console` (203) → `agent ALL=…` + `/etc/sudoers.d/agent`
      (and inside-vm.sh's chmod/visudo refs at 166-167);
      run:410+413 `sudo -u console` → `sudo -u agent`;
      deploy/vm.sh § console user (126-144): rename the section + the
      `console-browsers` / `console-playwright-probe` functions (call sites
      in run:410/413) + the "launch headless as console" print; README:82
      "powerful `console` user"; .env.vm.example:55 "console terminal"
      comment; .env.vm.example:4 units list.
- [ ] NO new SSH login surface: no authorized_keys, no CONSOLE_SSH_PUBLIC_KEY
      env key, no .env.vm.example addition. Port 22 stays multipass's own
      channel; the inside-vm.sh:102-104 comment ("the VM's only login path
      now; no authorized_keys are installed") stays TRUE — only s/user
      naming/ if the rename touches it.
- [ ] checkframework2 replacement assert: as the agent user over multipass,
      the two `./run agent` preconditions hold —
      `multipass exec app -- sudo -iu agent bash -c 'command -v crush'`
      (crush on PATH) and the credentials env readable + AGENT_MODEL set
      (`sudo -iu agent bash -c '. /etc/credentials/app/.env.vm 2>/dev/null;
      test -n "$AGENT_MODEL"'` — group-readable via the app-group
      membership the rename preserves).

### Docs + sweep

- [ ] README.md — lines 11-12 (agent "ONLY inside the VM's web terminal" →
      from a multipass shell, sudo -iu agent), 39, 43 (dev stack list), 82,
      90, 267 (./run console section → delete), 352 (checkframework2
      description).
- [ ] deploy/access-steps.txt:6-7 — web terminal section → multipass shell
      instructions (`multipass shell app`, `sudo -iu agent`,
      `cd /srv/app/main`, `./run agent` inside).
- [ ] grep sweep clean: `ttyd`, `/agent`, `CONSOLE_URL`, `console_url`,
      `console_ttyd`, `7681`, `-u console`, `sudoers.d/console`,
      `/home/console`, `console ALL` — expected survivors: prompts/
      provenance files and TODO.md (user notes, leave alone). Careful: bare
      `console` stays everywhere it means the BROWSER console / Django
      console log / playwright console-error harness.
- [ ] TODO.md:1,8 — user's own notes; leave (they resolve themselves).

## Out of scope / unchanged

- Crush: `.crushrc`, deploy/crush_*_guard.py + guard tests, npm pin in
  inside-vm.sh — all stay; `./run agent` from any shell needs nothing new.
- makeloginlink / login-for-test-by-key — app login, stays.
- Caddy static/proxy site, granian/huey units, redis, swap — untouched.
- The VM is build-only: no in-place edits — apply via `./testvm` destroy +
  provision (DANGEROUS: deletes the instance).

## Verification

- [ ] Local: `./run checkall` green (test_home_views without console_url,
      no test_agent_auth, guard tests 32/32, playwright suites).
- [ ] VM: destroy + provision, then checkframework2 green (7 asserts incl.
      the new agent-shell one).
- [ ] Manual: `multipass shell app` → `sudo -iu agent` → `cd /srv/app/main`
      → `./run agent` boots the Crush TUI, sudo -n true works as agent
      (NNP no longer matters — plain shell), browser https://app.local/ has
      no Console link, /agent → the Django 404 catch-all.
