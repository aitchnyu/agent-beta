#!/bin/bash
# vm-bootstrap.sh — run AS app on the VM by ./testvm provision, after the
# seed + first commit (fresh VM: nothing exists yet). Environment via the
# shared credentials file.
set -e
set -a; . /etc/credentials/app/.env.vm; set +a
cd /srv/app/main
export PATH=$HOME/.local/bin:$PATH
uv sync
(cd frontend && npm install --no-audit --no-fund && npm run build)
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput --clear

# Provisioning leftovers out of /tmp (best-effort, last step): tree.tgz
# embeds the credentials env and sat world-readable on the sticky /tmp;
# the rest is one-shot clutter. Deleting this script itself is safe —
# its open fd survives the unlink.
rm -f /tmp/tree.tgz /tmp/app-seed.tgz /tmp/inside-vm.sh \
  /tmp/vm-seed-commit.sh /tmp/vm-bootstrap.sh
