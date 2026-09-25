#!/bin/bash
# gen-vapid-b64.sh — mint a VAPID private key with OpenSSL only; stdout is
# the base64url P-256 scalar settings/pywebpush consume (the public half is
# derived at call time — djangoapp.models.notifications.vapid_public_key).
# Called by BOTH provisioners: `run init` (repo copy) and inside-vm.sh
# provision_app (tree copy at /usr/local/lib/desmo/). Fails loudly —
# callers must refuse to proceed.
set -euo pipefail

pem="$(mktemp)"
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$pem" 2>/dev/null
# `pkey -text` prints the scalar as a colon-hex "priv:" block; extract it.
scalar_hex="$(
  openssl pkey -in "$pem" -text -noout 2>/dev/null |
    awk '/^priv:/ {f=1; next} /^pub:/ {f=0} f' | tr -d ' :[:space:]'
)"
rm -f "$pem"
[[ -n "$scalar_hex" ]] || { echo "REFUSING: extraction produced no scalar (openssl format drift?)" >&2; exit 1; }
# Left-pad to 64 hex (openssl may print unpadded); anything else = broken extraction.
scalar_hex="$(printf '%64s' "$scalar_hex" | tr ' ' 0)"
[[ "$scalar_hex" =~ ^[0-9A-Fa-f]{64}$ ]] || { echo "REFUSING: could not extract the P-256 scalar" >&2; exit 1; }
# hex → \xNN escapes → printf (no xxd) → base64url, unpadded.
esc="$(printf '%s' "$scalar_hex" | sed 's/\(..\)/\\x\1/g')"
printf "$esc" | base64 | tr '+/' '-_' | tr -d '='
