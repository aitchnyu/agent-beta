#!/bin/sh
# pi — the VM's PATH entry for the agent: pure delegation to ./run pi,
# the ONE launcher (env, cwd, user checks, dispatch live there).
# /usr/local/bin/pi SHADOWS npm's global pi (provisioning bakes @PI_BIN@).
[ -f /srv/desmo/main/run ] || { echo "no /srv/desmo/main (provision the VM first)" >&2; exit 1; }
PI_REAL_BIN='@PI_BIN@' exec /srv/desmo/main/run pi "$@"
