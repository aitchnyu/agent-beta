#!/bin/sh
# desmosetup — the operator's PATH entry for the post-provision setup:
# pure delegation to ./run desmosetup (ops/setup.py, ops/setup_app.py).
[ -f /srv/desmo/main/run ] || { echo "no /srv/desmo/main (provision the VM first)" >&2; exit 1; }
exec /srv/desmo/main/run desmosetup "$@"
