#!/bin/bash
# vm-seed-commit.sh — run AS desmo on the VM by ./testvm provision, right
# after the repo seed lands. main/ is its OWN repo (the seed ships no
# .git; the parent /srv/desmo is NOT a repo — the agent uses
# external_directory for scratch/). The first commit marks the provisioned
# baseline; the agent's commits (identity from the env file) follow.
set -e
set -a; . /etc/credentials/desmo/.env.vm; set +a
cd /srv/desmo/main
git init -q
# Group-shared repo: the 'desmo' user owns it, but the default cloud user
# (desmo pi) commits here too — core.sharedRepository makes future git
# objects group-writable, and the chmod fixes what init already created
# under the default umask.
git config core.sharedRepository group
chmod -R g+w .git
# Author identity for VM commits: repo config, NOT the env (the env keeps
# only the GIT_COMMITTER_NAME agent marker). Blank email by design — the
# VM has no real addresses, and git cannot auto-derive one from the
# .local hostname (without this, every commit fails with "unable to
# auto-detect email address").
git config user.name "agent"
git config user.email ""
git add -A
git commit -qm 'First commit: provisioned from the repo seed'
