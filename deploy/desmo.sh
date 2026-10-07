#!/bin/sh
# desmo — run the deployed repo's ./run from anywhere: `desmo pi` is the
# same as cd /srv/desmo/main && ./run pi.
# Provisioning (deploy/inside-vm.sh) copies this file to
# /usr/local/bin/desmo once the seed tree exists.
cd /srv/desmo/main || { echo "no /srv/desmo/main (provision the VM first)" >&2; exit 1; }

# Root bypasses permission checks — nothing to fix up.
[ "$(id -u)" = 0 ] && exec ./run "$@"

# Normal case: a shell logged in AFTER provisioning carries the desmo
# group (the tree is desmo:desmo group-writable) — exec directly.
case " $(id -nG) " in *" desmo "*) exec ./run "$@" ;; esac

# Stale shell — opened before provisioning added the user to the desmo
# group (group membership is fixed at process start). Group-writes into
# the tree fail: pi's settings-lock mkdir, .pi/npm/, sessions/.
# - permanent fix: log out and back in
# - this shell: re-exec as the same user via sudo -g desmo; -n keeps it
#   passwordless-or-silent
if sudo -n -g desmo -u "$(id -un)" -- true 2>/dev/null; then
  exec sudo -g desmo -u "$(id -un)" ./run "$@"
else
  echo "desmo: no desmo group in this shell and no passwordless sudo — log out/in once" >&2
  exit 1
fi
