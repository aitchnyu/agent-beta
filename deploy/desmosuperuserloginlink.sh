#!/bin/sh
# desmosuperuserloginlink — the operator's PATH entry for the first
# superuser's login link: pure delegation to ./run
# desmosuperuserloginlink (ops/superuserloginlink.py).
[ -f /srv/desmo/main/run ] || { echo "no /srv/desmo/main (provision the VM first)" >&2; exit 1; }
exec /srv/desmo/main/run desmosuperuserloginlink "$@"
