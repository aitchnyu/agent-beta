#!/bin/bash
# vm-seed-commit.sh — run AS app on the VM by ./testvm provision, right
# after the repo seed lands. main/ is its OWN repo (the seed ships no
# .git; the parent /srv/app is NOT a repo — the agent uses
# external_directory for scratch/). The first commit marks the provisioned
# baseline; the agent's commits (identity from the env file) follow.
set -e
set -a; . /etc/credentials/app/.env.vm; set +a
cd /srv/app/main
git init -q
git add -A
git commit -qm 'First commit: provisioned from the repo seed'
