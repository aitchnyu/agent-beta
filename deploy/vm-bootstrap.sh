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
